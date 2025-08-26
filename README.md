# Demo Countdown Timer

A simple, cross‑platform terminal countdown timer for demos and talks. Step through named segments, see a progress bar and remaining time, and control the flow with quick hotkeys.

## Features

- Multi-segment countdown with names and durations
- Smooth, flicker-free in-place progress bar
- Shows remaining time and total for the segment (e.g. `01:09 <- 01:30`)
- Hotkeys: pause/resume, next/prev, +/- 10s, mute beep, quit
- Works on Windows, macOS, and Linux (standard library only)

## Usage

1. Ensure you have Python 3.8+ installed.
2. Clone this repo and run the script:

```powershell
python .\main.py
```

3. While the terminal window is focused, use hotkeys:

- Space: Pause/Resume
- n: Next segment
- p: Previous segment (restarts that segment)
- +: Add 10s to current segment
- -: Subtract 10s from current segment (floors at 5s)
- m: Mute/unmute beep
- q: Quit

## Configure segments

Edit the `SEGMENTS` list at the top of `main.py`:

```python
SEGMENTS = [
    ("Intro", 90),
    ("Deep dive", 300),
    ("Q&A", 120),
]
```

## Output

```
Demo Timer — total planned time: 06:00
Press any listed hotkey while this window is focused.

Segment 1/7: Introduction
Controls: Space=Pause/Resume  n=Next  p=Prev  +=+10s  -=-10s  m=Mute  q=Quit
[##############################]  00:00 <- 01:00 [COMPLETED] | Demo Left: 05:00
✅ Segment complete.

Segment 2/7: Overview
Controls: Space=Pause/Resume  n=Next  p=Prev  +=+10s  -=-10s  m=Mute  q=Quit
[########----------------------]  00:32 <- 00:45 [RUNNING] | Demo Left: 04:48
```

## Notes

- The app uses ANSI escape sequences for in-place updates. Windows Terminal and VS Code terminal fully support this. On very old terminals, it will still work but updates may not be as smooth.
- The beep uses `winsound` on Windows and the terminal bell elsewhere. You can toggle it with `m`.

## Contributing

Issues and pull requests are welcome. Please keep the standard library dependency and cross-platform support.

## License

MIT — see `LICENSE`.
