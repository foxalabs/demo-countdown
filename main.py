#!/usr/bin/env python3
"""
Demo Segment Countdown Timer
- Steps through a list of named demo segments with individual countdowns.
- Shows remaining time and a basic progress bar in the terminal.
- Hotkeys (while the timer is focused in your terminal):
    Space  : Pause/Resume
    n      : Next segment
    p      : Previous segment (restarts that segment)
    +      : Add 10s to current segment
    -      : Subtract 10s from current segment (floors at 5s)
    m      : Mute/unmute beep
    q      : Quit

Works on Windows, macOS, and Linux (pure standard library).
"""

import sys
import time
import math
import os
import csv
import platform

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
        # Read and filter comments/blank lines but preserve CSV formatting
        with open(path, "r", encoding="utf-8", newline="") as f:
            lines = [ln for ln in f if ln.strip() and not ln.lstrip().startswith("#")]
        if not lines:
            return segments
        reader = csv.reader(lines)
        rows = list(reader)
        if not rows:
            return segments
        # Detect header
        header_map = None
        first = [c.strip().lower() for c in rows[0]]
        if ("duration" in first) and ("name" in first or "segment" in first or "title" in first):
            header_map = {name: idx for idx, name in enumerate(first)}
            start_idx = 1
        else:
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
                # Skip malformed lines
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
        # 3) Bundled data directory (_MEIPASS) for PyInstaller
        base = getattr(sys, "_MEIPASS", None)
        if base:
            candidates.append(os.path.join(base, "segments.txt"))
    # 4) Source file directory (dev mode)
    candidates.append(os.path.join(os.path.dirname(__file__), "segments.txt"))
    for p in candidates:
        if p and os.path.exists(p):
            return p
    return candidates[-1]

# Prefer external config if available
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

# ---- IMPLEMENTATION BELOW ----

# Cross-platform non-blocking keypress
IS_WINDOWS = platform.system().lower().startswith("win")
if IS_WINDOWS:
    import msvcrt
else:
    import sys
    import select
    import termios
    import tty

def kbhit():
    """Return True if a keypress is waiting; non-blocking."""
    if IS_WINDOWS:
        return msvcrt.kbhit()
    else:
        dr, _, _ = select.select([sys.stdin], [], [], 0)
        return bool(dr)

def getch():
    """Get a single character (non-blocking). Returns None if no key."""
    if IS_WINDOWS:
        if msvcrt.kbhit():
            ch = msvcrt.getwch()
            return ch
        return None
    else:
        # Use non-blocking read
        if not kbhit():
            return None
        return sys.stdin.read(1)

class RawTerminal:
    """Context manager to set terminal to raw mode on POSIX."""
    def __enter__(self):
        if not IS_WINDOWS:
            self.fd = sys.stdin.fileno()
            self.old_settings = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd)
        return self
    def __exit__(self, exc_type, exc, tb):
        if not IS_WINDOWS:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)

def beep(muted=False):
    """Simple cross-platform beep."""
    if muted:
        return
    if IS_WINDOWS:
        try:
            import winsound
            winsound.Beep(880, 120)  # freq, duration ms
        except Exception:
            print("\a", end="", flush=True)
    else:
        # Terminal bell
        print("\a", end="", flush=True)

def format_time(secs: int) -> str:
    m, s = divmod(max(0, int(secs)), 60)
    return f"{m:02d}:{s:02d}"

def progress_bar(frac: float, width: int = 30) -> str:
    frac = max(0.0, min(1.0, frac))
    filled = int(round(frac * width))
    return "[" + "#" * filled + "-" * (width - filled) + "]"

def total_demo_left_secs(current_index: int, remaining_current: float) -> int:
    """Compute total remaining seconds for the entire demo.
    Includes current segment's remaining time (ceil) plus all future segments' durations.
    """
    future = sum(d for _, d in SEGMENTS[current_index+1:])
    return max(0, int(math.ceil(max(0.0, remaining_current))) + future)

def clear_line():
    # Move cursor to line start and clear to end
    sys.stdout.write("\r\033[K")
    sys.stdout.flush()

# Track previous status line length to avoid flicker when redrawing
_STATUS_PREV_LEN = 0

def reset_status_line_len():
    global _STATUS_PREV_LEN
    _STATUS_PREV_LEN = 0

def draw_status_line(text: str):
    """Redraw the single status line in-place with minimal flicker.
    Writes a carriage return, the text, and pads with spaces to clear leftovers.
    """
    global _STATUS_PREV_LEN
    # One write, no separate clear/flush to minimize flicker
    pad = max(0, _STATUS_PREV_LEN - len(text))
    sys.stdout.write("\r" + text + (" " * pad))
    sys.stdout.flush()
    _STATUS_PREV_LEN = len(text)

def hide_cursor():
    # ANSI to hide cursor (supported on modern Windows terminals)
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()

def show_cursor():
    # ANSI to show cursor
    sys.stdout.write("\033[?25h")
    sys.stdout.flush()

def print_header(current_idx, total, segment_name):
    clear_line()
    sys.stdout.write(f"\nSegment {current_idx+1}/{total}: {segment_name}\n")
    sys.stdout.flush()

def print_footer(help_every=5):
    # Optionally show controls reminder
    sys.stdout.write("Controls: Space=Pause/Resume  n=Next  p=Prev  +=+10s  -=-10s  m=Mute  q=Quit\n")
    sys.stdout.flush()

def main():
    total_segments = len(SEGMENTS)
    if total_segments == 0:
        print("No segments configured. Create or edit segments.txt in this folder.")
        return

    # Pre-calc total time for info
    total_time = sum(d for _, d in SEGMENTS)
    print(f"Demo Timer — total planned time: {format_time(total_time)}")
    print("Press any listed hotkey while this window is focused.")

    muted = False
    paused = False
    i = 0

    # POSIX raw terminal for non-blocking reads
    with RawTerminal():
        try:
            hide_cursor()
        except Exception:
            pass
        try:
            while i < total_segments:
                name, duration = SEGMENTS[i]
                remaining = duration
                last_tick = time.time()

                print_header(i, total_segments, name)
                print_footer()
                reset_status_line_len()

                while remaining > 0:
                    # Handle timing
                    now = time.time()
                    delta = now - last_tick
                    last_tick = now
                    if not paused:
                        remaining -= delta

                    # Draw line
                    frac_done = 1.0 - max(0.0, remaining) / duration if duration > 0 else 1.0
                    bar = progress_bar(frac_done)
                    status = "PAUSED" if paused else "RUNNING"
                    total_left = total_demo_left_secs(i, remaining)
                    draw_status_line(f"{bar}  {format_time(remaining)} <- {format_time(duration)} [{status}] | Demo Left: {format_time(total_left)}")

                    # Check keys (non-blocking)
                    ch = getch()
                    if ch:
                        if ch in (" ",):  # Space pause/resume
                            paused = not paused
                        elif ch in ("n", "N"):
                            # Next segment
                            beep(muted)
                            remaining = 0
                            break
                        elif ch in ("p", "P"):
                            # Previous segment (restart previous)
                            beep(muted)
                            i = max(0, i - 1)
                            # Clear lines to move "up" on restart
                            clear_line()
                            print()
                            break
                        elif ch in ("+", "="):
                            duration += 10
                            remaining += 10
                            beep(muted)
                        elif ch in ("-", "_"):
                            # Reduce but keep a minimum
                            if duration > 5:
                                cut = min(10, duration - 5)
                                duration -= cut
                                remaining = min(remaining, duration)
                                beep(muted)
                        elif ch in ("m", "M"):
                            muted = not muted
                        elif ch in ("q", "Q"):
                            print("\nQuitting.")
                            return

                    time.sleep(0.1)

                if remaining <= 0:
                    # Segment complete: show final completed line once
                    bar_complete = progress_bar(1.0)
                    # After completion, the remaining total excludes this segment
                    total_left_after = sum(d for _, d in SEGMENTS[i+1:])
                    draw_status_line(f"{bar_complete}  00:00 <- {format_time(duration)} [COMPLETED] | Demo Left: {format_time(total_left_after)}")
                    beep(muted)
                    print("\n✅ Segment complete.")
                    i += 1
                    # Small spacer
                    time.sleep(0.6)

        finally:
            try:
                show_cursor()
            except Exception:
                pass

        print("\nAll segments finished. Good show!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted. Bye!")
