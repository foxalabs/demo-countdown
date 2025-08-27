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
    e      : Edit segments (toggle editor)
    q / Esc: Quit (Esc exits editor first)
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

    # Timeline colors
    TL_BG = (28, 30, 36)
    TL_SEG = (50, 56, 66)
    TL_SEG_DONE = (70, 140, 100)
    TL_SEG_CURRENT = (80, 140, 200)
    TL_MARK = (245, 245, 245)

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
    paused = True  # start paused; Space toggles start/stop
    muted = False
    status = "RUNNING"
    duration = SEGMENTS[i][1] if total_segments else 0
    remaining = float(duration)
    last_time = time.time()
    completed_until = 0.0  # timestamp; if > now, show completed state

    # Timeline state
    TIMELINE_PX_PER_SEC = 1.5
    TIMELINE_SCROLL_SMOOTH = 0.15
    timeline_scroll_x = 0.0

    # Elapsed (including pauses) tracking
    demo_started = False
    demo_start_ts = 0.0
    demo_end_ts = 0.0

    # Simple in-app editor state
    editor_mode = False
    ed_sel_row = 0
    ed_sel_col = 1  # 1=name, 2=duration
    ed_editing = False
    ed_buffer = ""
    ed_message = "Esc/E: exit • Arrows: move • Left/Right/Tab: switch column • Enter/F2: edit • A: add • Del: delete • S: save"

    # Set initial caption to segment name if available
    if total_segments > 0:
        try:
            import pygame as _pg
            _pg.display.set_caption(f"{SEGMENTS[i][0]} — Demo Countdown")
        except Exception:
            pass

    running = True
    while running:
        now = time.time()
        dt = now - last_time
        last_time = now

        # Pump events once per frame and route by mode
        events = pygame.event.get()

        if editor_mode:
            # Editor mode input
            for ev in events:
                if ev.type == pygame.QUIT:
                    running = False
                elif ev.type == pygame.KEYDOWN:
                    key = ev.key
                    if key in (pygame.K_ESCAPE, pygame.K_e):
                        # Exit editor (don't quit app)
                        editor_mode = False
                        break
                    if ed_editing:
                        if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                            if 0 <= ed_sel_row < total_segments:
                                nm, secs = SEGMENTS[ed_sel_row]
                                if ed_sel_col == 1:
                                    nm = ed_buffer.strip() or nm
                                else:
                                    try:
                                        secs = parse_duration(ed_buffer.strip())
                                    except Exception:
                                        pass
                                SEGMENTS[ed_sel_row] = (nm, secs)
                                if ed_sel_row == i:
                                    duration = float(secs)
                                    remaining = min(remaining, duration)
                                    # If renaming current, update caption
                                    try:
                                        import pygame as _pg
                                        _pg.display.set_caption(f"{nm} — Demo Countdown")
                                    except Exception:
                                        pass
                            ed_editing = False
                            try:
                                import pygame as _pg
                                _pg.key.stop_text_input()
                            except Exception:
                                pass
                        elif key == pygame.K_BACKSPACE:
                            ed_buffer = ed_buffer[:-1]
                        else:
                            ch = ev.unicode
                            if ch:
                                ed_buffer += ch
                    else:
                        if key == pygame.K_UP:
                            ed_sel_row = max(0, ed_sel_row - 1)
                        elif key == pygame.K_DOWN:
                            ed_sel_row = min(total_segments - 1, ed_sel_row + 1)
                        elif key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_TAB):
                            ed_sel_col = 1 if ed_sel_col == 2 else 2
                        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_F2):
                            cur = SEGMENTS[ed_sel_row][0 if ed_sel_col == 1 else 1]
                            ed_buffer = str(cur)
                            ed_editing = True
                            try:
                                import pygame as _pg
                                _pg.key.start_text_input()
                            except Exception:
                                pass
                        elif key == pygame.K_a:
                            SEGMENTS.insert(ed_sel_row + 1, ("New Segment", 60))
                            total_segments = len(SEGMENTS)
                        elif key in (pygame.K_DELETE,) and total_segments > 1:
                            if ed_sel_row < i:
                                i -= 1
                            elif ed_sel_row == i:
                                if i < total_segments - 1:
                                    i = i
                                else:
                                    i = max(0, i - 1)
                            del SEGMENTS[ed_sel_row]
                            total_segments = len(SEGMENTS)
                            ed_sel_row = max(0, min(ed_sel_row, total_segments - 1))
                            duration = float(SEGMENTS[i][1]) if total_segments else 0
                            remaining = float(duration)
                            paused = True
                        elif key == pygame.K_s:
                            try:
                                with open(_SEGMENTS_FILE, "w", encoding="utf-8", newline="") as f:
                                    f.write("name,duration\n")
                                    for nm, secs in SEGMENTS:
                                        m, s = divmod(int(secs), 60)
                                        f.write(f"{nm},{m:02d}:{s:02d}\n")
                                ed_message = f"Saved: {_SEGMENTS_FILE}"
                            except Exception as e:
                                ed_message = f"Save failed: {e}"
                elif ev.type == pygame.TEXTINPUT and ed_editing:
                    # Robust text input for names/durations
                    ed_buffer += ev.text
        else:
            # Normal play mode input
            for event in events:
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    key = event.key
                    if key in (pygame.K_ESCAPE, pygame.K_q):
                        running = False
                    elif key == pygame.K_SPACE:
                        if total_segments > 0 and time.time() >= completed_until:
                            paused = not paused
                            if not paused and not demo_started:
                                demo_started = True
                                demo_start_ts = time.time()
                    elif key in (pygame.K_n,):
                        if i < total_segments:
                            beep(muted)
                            status = "COMPLETED"
                            remaining = 0.0
                            completed_until = time.time() + 0.6
                    elif key in (pygame.K_p,):
                        if i > 0:
                            beep(muted)
                            i -= 1
                            duration = float(SEGMENTS[i][1])
                            remaining = duration
                            paused = False
                            status = "RUNNING"
                            completed_until = 0.0
                            try:
                                pygame.display.set_caption(f"{SEGMENTS[i][0]} — Demo Countdown")
                            except Exception:
                                pass
                    elif (event.unicode == '+' or key == pygame.K_KP_PLUS):
                        if i < total_segments and time.time() >= completed_until:
                            duration += 10
                            remaining += 10
                            beep(muted)
                    elif (event.unicode == '-' or key == pygame.K_KP_MINUS):
                        if i < total_segments and time.time() >= completed_until:
                            if duration > 5:
                                cut = min(10, duration - 5)
                                duration -= cut
                                remaining = min(remaining, duration)
                                beep(muted)
                    elif key in (pygame.K_m,):
                        muted = not muted
                    elif key in (pygame.K_e,):
                        editor_mode = True
                        paused = True
                        ed_sel_row = max(0, min(i, total_segments - 1))
                        ed_sel_col = 1
                        ed_editing = False

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
                if demo_end_ts == 0.0 and demo_started:
                    demo_end_ts = now_ts
                try:
                    pygame.display.set_caption("Summary — Demo Countdown")
                except Exception:
                    pass
            else:
                duration = float(SEGMENTS[i][1])
                remaining = duration
                paused = False
                status = "RUNNING"
                try:
                    pygame.display.set_caption(f"{SEGMENTS[i][0]} — Demo Countdown")
                except Exception:
                    pass
            completed_until = 0.0

        # Handle segment completion: arm a single flash only once
        if total_segments > 0 and i < total_segments and remaining <= 0 and completed_until == 0.0:
            beep(muted)
            status = "COMPLETED"
            completed_until = now_ts + 0.6

        # Drawing
        screen.fill(BG)

        # Editor rendering overrides normal UI
        if editor_mode:
            # Editor screen
            draw_text(screen, "Segment Editor", title_font, FG, (24, 18))
            draw_text(screen, ed_message, small_font, MUTE, (24, 56))
            x_num, x_name, x_dur = 24, 80, 650
            draw_text(screen, "#", small_font, FG, (x_num, 86))
            draw_text(screen, "Name", small_font, FG, (x_name, 86))
            draw_text(screen, "Duration", small_font, FG, (x_dur, 86))
            row_y = 110
            row_h = 30
            for ridx, (nm, secs) in enumerate(SEGMENTS):
                is_sel = (ridx == ed_sel_row)
                color = ACCENT_DIM if is_sel else TL_BG
                pygame.draw.rect(screen, color, pygame.Rect(20, row_y - 4, WIDTH - 40, row_h), border_radius=6)
                draw_text(screen, str(ridx + 1), small_font, FG, (x_num, row_y))
                if is_sel and ed_editing and ed_sel_col == 1:
                    draw_text(screen, ed_buffer + "|", small_font, FG, (x_name, row_y))
                else:
                    draw_text(screen, nm, small_font, FG, (x_name, row_y))
                m, s = divmod(int(secs), 60)
                dtxt = f"{m:02d}:{s:02d}"
                if is_sel and ed_editing and ed_sel_col == 2:
                    draw_text(screen, ed_buffer + "|", small_font, FG, (x_dur, row_y))
                else:
                    draw_text(screen, dtxt, small_font, FG, (x_dur, row_y))
                row_y += row_h

            pygame.display.flip()
            clock.tick(60)
            continue

        # All completed?
        if i >= total_segments:
            # Summary screen
            draw_text(screen, "Summary", title_font, OK, (24, 18))
            planned_total = sum(d for _, d in SEGMENTS)
            final_elapsed = max(0.0, ((demo_end_ts or now) - demo_start_ts)) if demo_started else 0.0
            delta_secs = final_elapsed - planned_total
            delta_color = WARN if delta_secs > 0 else (OK if delta_secs < 0 else FG)

            draw_text(screen, f"Segments: {total_segments}", h2_font, FG, (24, 72))
            draw_text(screen, f"Planned total: {format_time(planned_total)}", h2_font, FG, (24, 110))
            draw_text(screen, f"Elapsed total: {format_time(final_elapsed)}", h2_font, FG, (24, 148))
            sign = "+" if delta_secs > 0 else ("" if delta_secs == 0 else "-")
            draw_text(screen, f"Delta: {sign}{format_time(abs(delta_secs))}", h2_font, delta_color, (24, 186))
            draw_text(screen, "Press Q or Esc to quit", small_font, FG, (24, 230))
            pygame.display.flip()
            clock.tick(30)
            continue

    # Title = current segment name (eye-catching)
        draw_text(screen, SEGMENTS[i][0], title_font, FG, (24, 18))

        # Current segment info (index/total only to avoid duplication)
        seg_title = f"Segment {i+1}/{total_segments}"
        draw_text(screen, seg_title, h2_font, FG, (24, 72))

        # Progress bar area
        bar_rect = pygame.Rect(24, 130, WIDTH - 48, 40)
        frac_done = 1.0 - max(0.0, remaining) / duration if duration > 0 else 1.0
        draw_progress(screen, frac_done, bar_rect, ACCENT, ACCENT_DIM)

        # Times and status
        total_left = total_demo_left_secs(i, remaining)
        # Elapsed time including pauses (wall clock since first start)
        elapsed_secs = max(0.0, ((demo_end_ts or now) - demo_start_ts)) if demo_started else 0.0
        times_line = (
            f"{format_time(remaining)} <- {format_time(duration)}    | "
            f"Demo Left: {format_time(total_left)}    | Elapsed: {format_time(elapsed_secs)}"
        )
        draw_text(screen, times_line, mono_font, FG, (24, 190))

        status_color = OK if status == "RUNNING" else (WARN if status == "COMPLETED" else ACCENT)
        draw_text(screen, f"[{status}]", h2_font, status_color, (24, 230))

        # Next up (optional)
        if i + 1 < total_segments:
            next_line = f"Next: {SEGMENTS[i+1][0]} ({format_time(SEGMENTS[i+1][1])})"
            draw_text(screen, next_line, small_font, FG, (24, 270))

        # Timeline visualization (position within the entire demo)
        tl_rect = pygame.Rect(24, 300, WIDTH - 48, 64)
        pygame.draw.rect(screen, TL_BG, tl_rect, border_radius=8)

        # Compute content width in pixels, auto-fit to viewport when possible
        total_secs = sum(d for _, d in SEGMENTS)
        GAP = 3  # gap between segments in px
        nsegs = len(SEGMENTS)
        gaps_total = max(0, (nsegs - 1) * GAP)
        if total_secs > 0:
            fit_px_per_sec = max(0.05, (tl_rect.width - gaps_total) / total_secs)
        else:
            fit_px_per_sec = TIMELINE_PX_PER_SEC
        px_per_sec = max(TIMELINE_PX_PER_SEC, fit_px_per_sec)
        content_w = int(total_secs * px_per_sec + gaps_total)

        # Current absolute elapsed seconds
        elapsed_before = sum(d for _, d in SEGMENTS[:i])
        if completed_until:
            elapsed_in_current = duration
        else:
            elapsed_in_current = max(0.0, min(duration, duration - max(0.0, remaining)))
        elapsed_total = elapsed_before + elapsed_in_current

        # Desired scroll to keep the current position centered
        desired_scroll = (elapsed_total * px_per_sec) - (tl_rect.width / 2)
        max_scroll = max(0, content_w - tl_rect.width)
        desired_scroll = max(0, min(max_scroll, desired_scroll))
        timeline_scroll_x += (desired_scroll - timeline_scroll_x) * TIMELINE_SCROLL_SMOOTH

        # Clip to timeline area while drawing segments
        prev_clip = screen.get_clip()
        screen.set_clip(tl_rect.inflate(-2, -2))

        # Draw segments as proportional blocks
        cursor_x = tl_rect.left - int(timeline_scroll_x)
        for idx, (_, secs) in enumerate(SEGMENTS):
            seg_w = max(1, int(secs * px_per_sec))
            seg_rect = pygame.Rect(cursor_x, tl_rect.top + 6, seg_w, tl_rect.height - 12)

            # Only draw if intersects viewport
            if seg_rect.right >= tl_rect.left and seg_rect.left <= tl_rect.right:
                if idx < i:
                    color = TL_SEG_DONE
                elif idx == i:
                    color = TL_SEG_CURRENT
                else:
                    color = TL_SEG
                pygame.draw.rect(screen, color, seg_rect, border_radius=6)

                # For current segment, draw inner progress fill
                if idx == i and secs > 0:
                    frac = (elapsed_in_current / secs)
                    frac = max(0.0, min(1.0, frac))
                    inner = seg_rect.inflate(-4, -4)
                    fill_w = int(inner.width * frac)
                    if fill_w > 0:
                        fill_rect = pygame.Rect(inner.left, inner.top, fill_w, inner.height)
                        pygame.draw.rect(screen, ACCENT, fill_rect, border_radius=6)

            cursor_x += seg_w + GAP  # gap between segments

        # Draw current position marker line (account for gaps)
        marker_x = tl_rect.left - int(timeline_scroll_x)
        # advance through completed segments
        for k in range(i):
            marker_x += int(SEGMENTS[k][1] * px_per_sec) + GAP
        # advance within current segment
        if i < nsegs:
            marker_x += int(min(SEGMENTS[i][1] * px_per_sec, elapsed_in_current * px_per_sec))
        x_now = marker_x
        pygame.draw.line(screen, TL_MARK, (x_now, tl_rect.top + 2), (x_now, tl_rect.bottom - 2), 2)

        # Outline
        pygame.draw.rect(screen, ACCENT_DIM, tl_rect, width=2, border_radius=8)

        # Restore clip
        screen.set_clip(prev_clip)

        # Controls
        controls = "Space=Pause  n=Next  p=Prev  +=+10s  -=-10s  m=Mute  e=Edit  q/Esc=Quit"
        draw_text(screen, controls, small_font, MUTE, (24, HEIGHT - 36))

        # Mute indicator
        if muted:
            draw_text(screen, "Muted", small_font, MUTE, (WIDTH - 90, 18))

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()

if __name__ == "__main__":
    run_gui()
