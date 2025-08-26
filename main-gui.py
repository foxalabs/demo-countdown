#!/usr/bin/env python3
"""
Demo Segment Countdown Timer (GUI)
- Pygame-based visual countdown with progress bar and controls.
- Windows-focused; requires pygame (pip install pygame).

Hotkeys (window focused):
  Space  : Pause/Resume
  n      : Next segment
  p      : Previous segment
  + / =  : Add 10s to current segment
  - / _  : Subtract 10s (floors at 5s)
  m      : Mute/unmute beep
  q / Esc: Quit
"""

import sys
import time
import math
import platform
import os
import csv

# ---- CONFIGURE YOUR SEGMENTS HERE ----
# (name, duration_in_seconds)
def parse_duration(text: str) -> int:
    t = text.strip()
    if not t:
        raise ValueError("empty duration")
    if t.endswith("s") or t.endswith("S"):
        t = t[:-1]
    if ":" in t:
        parts = [int(p) for p in t.split(":")]
        if len(parts) == 2:
            m, s = parts
            return m * 60 + s
        if len(parts) == 3:
            h, m, s = parts
            return h * 3600 + m * 60 + s
        raise ValueError("invalid time format")
    return int(t)

def load_segments(path: str) -> list[tuple[str, int]]:
    segments: list[tuple[str, int]] = []
    if not os.path.exists(path):
        return segments
    try:
        with open(path, "r", encoding="utf-8", newline="") as f:
            lines = [ln for ln in f if ln.strip() and not ln.lstrip().startswith("#")]
        if not lines:
            return segments
        reader = csv.reader(lines)
        rows = list(reader)
        if not rows:
            return segments
        first = [c.strip().lower() for c in rows[0]]
        if ("duration" in first) and ("name" in first or "segment" in first or "title" in first):
            header_map = {name: idx for idx, name in enumerate(first)}
            start_idx = 1
        else:
            header_map = None
            start_idx = 0
        for row in rows[start_idx:]:
            if not row:
                continue
            try:
                if header_map:
                    name = row[header_map.get("name", header_map.get("segment", header_map.get("title", 0)))].strip()
                    dur_text = row[header_map["duration"]].strip()
                else:
                    name = row[0].strip()
                    dur_text = row[1].strip() if len(row) > 1 else ""
                secs = parse_duration(dur_text)
                segments.append((name, secs))
            except Exception:
                continue
    except Exception:
        pass
    return segments

def find_segments_file() -> str:
    candidates = []
    # 1) Current working directory
    candidates.append(os.path.join(os.getcwd(), "segments.txt"))
    # 2) Directory of the executable when frozen
    if getattr(sys, "frozen", False):
        candidates.append(os.path.join(os.path.dirname(sys.executable), "segments.txt"))
        base = getattr(sys, "_MEIPASS", None)
        if base:
            candidates.append(os.path.join(base, "segments.txt"))
    # 4) Source directory (dev)
    candidates.append(os.path.join(os.path.dirname(__file__), "segments.txt"))
    for p in candidates:
        if p and os.path.exists(p):
            return p
    return candidates[-1]

_SEGMENTS_FILE = find_segments_file()
SEGMENTS = load_segments(_SEGMENTS_FILE)
if not SEGMENTS:
    SEGMENTS = [
        ("Introduction", 60),
        ("Overview", 45),
        ("Feature Demonstration", 90),
        ("Technical Details", 75),
        ("Q&A Session", 30),
        ("Summary", 40),
        ("Closing Remarks", 20),
    ]

IS_WINDOWS = platform.system().lower().startswith("win")

def format_time(secs: float) -> str:
    m, s = divmod(max(0, int(math.ceil(secs))), 60)
    return f"{m:02d}:{s:02d}"

def total_demo_left_secs(current_index: int, remaining_current: float) -> int:
    future = sum(d for _, d in SEGMENTS[current_index+1:])
    return max(0, int(math.ceil(max(0.0, remaining_current))) + future)

def beep(muted: bool = False):
    if muted:
        return
    if IS_WINDOWS:
        try:
            import winsound
            winsound.Beep(880, 120)
        except Exception:
            pass

def run_gui():
    try:
        import pygame
    except Exception:
        print("This GUI requires pygame. Install it with: pip install pygame")
        sys.exit(1)

    pygame.init()
    pygame.display.set_caption("Demo Countdown (GUI)")
    WIDTH, HEIGHT = 900, 520
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()

    # Colors
    BG = (16, 18, 22)
    FG = (234, 237, 243)
    ACCENT = (99, 179, 237)
    ACCENT_DIM = (60, 120, 180)
    WARN = (237, 99, 99)
    OK = (120, 200, 120)
    MUTE = (180, 180, 180)

    # Fonts
    try:
        title_font = pygame.font.SysFont("Segoe UI Semibold", 36)
        h2_font = pygame.font.SysFont("Segoe UI", 28)
        mono_font = pygame.font.SysFont("Consolas", 28)
        small_font = pygame.font.SysFont("Segoe UI", 18)
    except Exception:
        title_font = pygame.font.Font(None, 36)
        h2_font = pygame.font.Font(None, 28)
        mono_font = pygame.font.Font(None, 28)
        small_font = pygame.font.Font(None, 18)

    def draw_text(surface, text, font, color, pos):
        surface.blit(font.render(text, True, color), pos)

    def draw_progress(surface, frac: float, rect, color_fill, color_border):
        frac = max(0.0, min(1.0, frac))
        pygame.draw.rect(surface, color_border, rect, border_radius=6, width=2)
        inner = rect.inflate(-4, -4)
        fill_width = int(inner.width * frac)
        if fill_width > 0:
            fill_rect = pygame.Rect(inner.left, inner.top, fill_width, inner.height)
            pygame.draw.rect(surface, color_fill, fill_rect, border_radius=6)

    total_segments = len(SEGMENTS)
    i = 0
    paused = False
    muted = False
    status = "RUNNING"
    duration = SEGMENTS[i][1] if total_segments else 0
    remaining = float(duration)
    last_time = time.time()
    completed_until = 0.0  # timestamp; if > now, show completed state

    running = True
    while running:
        now = time.time()
        dt = now - last_time
        last_time = now

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                key = event.key
                if key in (pygame.K_ESCAPE, pygame.K_q):
                    running = False
                elif key == pygame.K_SPACE:
                    if total_segments > 0 and time.time() >= completed_until:
                        paused = not paused
                elif key in (pygame.K_n,):
                    # Next segment: mark completed then advance after short delay
                    if i < total_segments:
                        beep(muted)
                        status = "COMPLETED"
                        remaining = 0.0
                        completed_until = time.time() + 0.6
                elif key in (pygame.K_p,):
                    # Previous segment (restart previous)
                    if i > 0:
                        beep(muted)
                        i -= 1
                        duration = float(SEGMENTS[i][1])
                        remaining = duration
                        paused = False
                        status = "RUNNING"
                        completed_until = 0.0
                elif (event.unicode == '+' or key == pygame.K_KP_PLUS):
                    # Add 10s
                    if i < total_segments and time.time() >= completed_until:
                        duration += 10
                        remaining += 10
                        beep(muted)
                elif (event.unicode == '-' or key == pygame.K_KP_MINUS):
                    # Subtract 10s but floor at 5s total
                    if i < total_segments and time.time() >= completed_until:
                        if duration > 5:
                            cut = min(10, duration - 5)
                            duration -= cut
                            remaining = min(remaining, duration)
                            beep(muted)
                elif key in (pygame.K_m,):
                    muted = not muted

        # Time update (only when not in the completed flash window)
        if total_segments > 0 and completed_until == 0.0:
            if not paused:
                remaining -= dt
            status = "PAUSED" if paused else "RUNNING"

        now_ts = time.time()

        # Advance to next segment after completed flash (run this BEFORE arming another flash)
        if total_segments > 0 and completed_until and now_ts >= completed_until:
            i += 1
            if i >= total_segments:
                # Finished all
                i = total_segments
            else:
                duration = float(SEGMENTS[i][1])
                remaining = duration
                paused = False
                status = "RUNNING"
            completed_until = 0.0

        # Handle segment completion: arm a single flash only once
        if total_segments > 0 and i < total_segments and remaining <= 0 and completed_until == 0.0:
            beep(muted)
            status = "COMPLETED"
            completed_until = now_ts + 0.6

        # Drawing
        screen.fill(BG)

        # Title
        draw_text(screen, "Demo Countdown", title_font, FG, (24, 18))

        if i >= total_segments:
            # Done screen
            done_msg = "All segments finished. Good show!"
            draw_text(screen, done_msg, h2_font, OK, (24, 80))
            draw_text(screen, "Press Q or Esc to quit", small_font, FG, (24, 120))
            pygame.display.flip()
            clock.tick(30)
            continue

        # Current segment info
        seg_title = f"Segment {i+1}/{total_segments}: {SEGMENTS[i][0]}"
        draw_text(screen, seg_title, h2_font, FG, (24, 72))

        # Progress bar area
        bar_rect = pygame.Rect(24, 130, WIDTH - 48, 40)
        frac_done = 1.0 - max(0.0, remaining) / duration if duration > 0 else 1.0
        draw_progress(screen, frac_done, bar_rect, ACCENT, ACCENT_DIM)

        # Times and status
        total_left = total_demo_left_secs(i, remaining)
        times_line = f"{format_time(remaining)} <- {format_time(duration)}    | Demo Left: {format_time(total_left)}"
        draw_text(screen, times_line, mono_font, FG, (24, 190))

        status_color = OK if status == "RUNNING" else (WARN if status == "COMPLETED" else ACCENT)
        draw_text(screen, f"[{status}]", h2_font, status_color, (24, 230))

        # Next up (optional)
        if i + 1 < total_segments:
            next_line = f"Next: {SEGMENTS[i+1][0]} ({format_time(SEGMENTS[i+1][1])})"
            draw_text(screen, next_line, small_font, FG, (24, 270))

        # Controls
        controls = "Space=Pause  n=Next  p=Prev  +=+10s  -=-10s  m=Mute  q/Esc=Quit"
        draw_text(screen, controls, small_font, MUTE, (24, HEIGHT - 36))

        # Mute indicator
        if muted:
            draw_text(screen, "Muted", small_font, MUTE, (WIDTH - 90, 18))

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()

if __name__ == "__main__":
    run_gui()
