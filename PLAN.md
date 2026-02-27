# PLAN.md — Design Rationale

## Why This Rewrite

The original `h264streamGen/` toolkit had accumulated significant technical debt:

- **5 redundant Python 2 scripts** (`genStream.py`, `genStreamFromFiles.py`, `genStream_encodeonly.py`, `genOverlay.py`, `genBlackOverlay.py`) that were copy-pasted variants of each other with minor differences
- **Most scripts were broken**: encode functions commented out, references to non-existent directories (`ToS/`, `ToS_original/`), unused signal handlers
- **C/OpenGL binary (`pgen`)** required X11 display and OpenGL context, making it unusable on headless servers
- **Deprecated dependencies**: `avconv` (dead Ubuntu fork of FFmpeg), GStreamer 0.10 (EOL since 2012)
- **Inconsistent file naming**: mix of 10-digit and 5-digit zero-padded frame numbers
- **Security issues**: `os.system()` with unsanitized paths for `rm` commands

## Architecture

```
Input video file          Pillow Overlay              FFmpeg Encoder
┌─────────────────────┐  ┌──────────────────┐  ┌──────────────────────┐
│  FFmpeg decoder      │─>│  OverlayRenderer │─>│  stdin pipe (rgb24)  │
│  (pipe raw RGB)      │  │  (RGBA composite) │  │  libx264/265/av1     │
│  or solid blue bg    │  │                  │  │  output.mkv          │
└─────────────────────┘  └──────────────────┘  └──────────────────────┘
```

Each frame: decode background via FFmpeg pipe -> render RGBA overlay -> `Image.alpha_composite()` -> write raw RGB to FFmpeg encoder stdin.

No intermediate files on disk. Single pass. Memory efficient (one frame at a time).

## Overlay Elements

All 6 elements from the original C/OpenGL `pgen` binary, reimplemented in Python/Pillow:

1. **Binary Counter** — 32-bit frame number displayed as 8x4 grid of colored rectangles. Green = 1, white = 0, on black background. Default: single counter at bottom-left. With `--quad-counters`: one counter at top-left of each screen quadrant (2x2 video wall layout). Essential for frame-accurate sync verification.

2. **Scrolling Bars** — Gray vertical and horizontal bars that scroll across the frame at configurable speed. Used to detect motion/timing issues.

3. **Sync Dots** — Red dots in 4 screen quadrants scrolling along edges. Two sets with different scroll behaviors enable detecting per-region sync offsets.

4. **Alignment Grid** — Static white checkered squares along frame corners. Used to verify picture alignment and cropping.

5. **Scrolling Ticker** — Horizontally scrolling strip near top of frame. Supports two modes: `--ticker-text` generates text on-the-fly using Pillow/ImageFont, `--ticker-image` loads a pre-rendered image file (TGA/PNG/etc). For testing text rendering and scrolling smoothness.

6. **Snow/Noise** — Random RGB pixel blocks centered on screen. Configurable block size and coverage area. For testing noise handling and compression behavior.

## Key Decisions

- **Pillow over FFmpeg filter chains**: The binary counter grid, sync dots, and alignment patterns are awkward to express as FFmpeg `drawbox`/`drawtext` filters. Pillow's `ImageDraw` makes them trivial.
- **Pipe to FFmpeg**: Raw RGB bytes piped to FFmpeg stdin avoids thousands of intermediate PNG files on disk.
- **Video input via FFmpeg decoder pipe**: Input video is decoded by a separate FFmpeg process piping raw RGB frames. No need to pre-extract PNGs.
- **Auto frame count**: When `--frames` is omitted with `--input`, `ffprobe` reads container metadata (`nb_frames`) or computes from duration. Instant — no frame decoding needed.
- **Single file**: `generate.py` stays under 800 lines. No package structure needed until it grows significantly.
- **FFmpeg for streaming**: Replaced GStreamer 0.10 pipeline with `ffmpeg -re -stream_loop -1 ... -f rtp` which is simpler and universally available.
- **Headless operation**: Replaced C/OpenGL renderer with Python/Pillow — no X11 or GPU required.

## Future Features

### High Priority

1. **Audio sync tone** — Periodic beep (e.g., every 1 second) with a corresponding visual flash. Enables audio-to-video (lip sync) measurement. Currently the tool is video-only (`-an`).

2. **Human-readable frame number** — Decimal frame number text overlay (e.g., "Frame: 00247") for quick visual verification without manually decoding the 8x4 binary grid.

3. **Wall clock timestamp burn-in** — Generation timestamp (e.g., `2026-02-27 14:30:05.123`) burned into each frame. Enables absolute glass-to-glass latency measurement by comparing burned-in time with current wall clock at the receiver.

### Medium Priority

4. **SMPTE timecode overlay** — Standard `HH:MM:SS:FF` timecode that broadcast engineers expect. More readable than raw frame numbers in professional workflows.

5. **Additional streaming protocols** — SRT (Secure Reliable Transport) and RIST support beyond RTP. Both are supported by FFmpeg and widely used in modern AV-over-IP.

6. **Binary counter decoder** — A companion mode that takes a screenshot/frame as input, reads the binary counter grid, and outputs the frame number. Closes the loop for automated latency measurement.

7. **Color bars** — SMPTE or EBU color bars for display calibration. Common in broadcast test patterns.

### Nice to Have

8. **Resolution/format presets** — Common broadcast formats like `--preset 1080p25`, `--preset 720p50`, `--preset 2160p30` instead of manually specifying resolution + framerate.

9. **QR code per frame** — Encode frame metadata (frame number, timestamp, stream ID) in a QR code for automated machine reading at the receiver. More robust than binary counter for automated workflows.

10. **Multi-stream ID** — Visible stream identifier (number/color code) to distinguish multiple streams on the receiving end when testing simultaneous streams.
