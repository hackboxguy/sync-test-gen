# CLAUDE.md — Coding Conventions for sync-test-gen

## Project Overview

Single-file Python 3 tool (`generate.py`) that generates AV sync test videos using Pillow for overlay rendering and FFmpeg for encoding/streaming. Works on headless servers — no X11/OpenGL required.

## Project Structure

```
sync-test-gen/
├── generate.py          # All logic: CLI, OverlayRenderer, StreamGenerator
├── requirements.txt     # Pillow>=9.0
├── assets/
│   └── custom-ticker.tga  # Default scrolling ticker texture
├── PLAN.md              # Design rationale and architecture
├── README.md            # User-facing documentation
└── CLAUDE.md            # This file
```

## Key Dependencies

- **Python 3.8+** — minimum version
- **Pillow** — overlay frame rendering (RGBA compositing, drawing primitives, text rendering via ImageFont)
- **FFmpeg** — video decoding (input), encoding (`libx264`, `libx265`, `libaom-av1`), and RTP streaming; invoked via `subprocess.Popen` with piped stdin/stdout

## Architecture

- `OverlayRenderer` — Stateful class that renders 6 overlay elements onto RGBA Pillow images. Holds pre-computed snow buffer and scaled ticker image. One instance per generation run.
  - Binary counter: 32-bit frame counter in 8x4 grid. Single (bottom-left) or quad mode (top-left of each quadrant).
  - Scrolling bars, sync dots, alignment grid, ticker (image or text-based), snow/noise.
- `StreamGenerator` — Pipeline controller. Decodes input video via FFmpeg pipe, composites overlays per frame, pipes raw RGB to FFmpeg encoder.
- `main()` — Argparse CLI with `generate` and `stream` subcommands.

## Coding Style

- Python 3, f-strings, `Path` objects for file paths
- `subprocess.Popen` for long-running FFmpeg pipes, `subprocess.run` for one-shot commands
- No `os.system()` — always use subprocess
- Type hints not required but welcome on public methods
- Keep everything in `generate.py` unless it exceeds ~800 lines

## Testing

```bash
# Basic test (blue background, all overlays)
python3 generate.py generate --frames 50 --output test.mkv

# With background video
python3 generate.py generate --input assets/tears_of_steel_1080p.mov --frames 50 --output test_bg.mkv

# With custom ticker text and quad counters
python3 generate.py generate --input assets/tears_of_steel_1080p.mov --ticker-text "TEST" --quad-counters --frames 50 --output test_quad.mkv

# Verify output
ffplay test.mkv
ffprobe test.mkv
```
