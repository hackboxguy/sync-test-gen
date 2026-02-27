# sync-test-gen

A toolkit for generating video streams with overlay patterns for AV synchronization testing. Renders a binary frame counter, scrolling bars, sync dots, alignment grid, scrolling ticker, and snow/noise pattern on top of background video content, then encodes to H.264/H.265/AV1.

## Prerequisites

- Python 3.8+
- FFmpeg (with `libx264`, optionally `libx265`, `libaom-av1`)
- Pillow (`pip install Pillow`)

## Installation

```bash
git clone <repo-url>
cd sync-test-gen
pip install -r requirements.txt
```

## Quick Start

```bash
# Generate 100 frames with all overlays on blue background
python3 generate.py generate --frames 100 --output test.mkv

# Generate with a background video
python3 generate.py generate \
  --input video.mp4 \
  --frames 500 \
  --framerate 60 \
  --output sync_test.mkv

# Skip first 10 seconds of input video
python3 generate.py generate \
  --input video.mp4 \
  --start-time 10 \
  --frames 300 \
  --output sync_test.mkv

# Custom ticker text instead of default image
python3 generate.py generate \
  --input video.mp4 \
  --ticker-text "MY SYNC TEST STREAM" \
  --frames 300 \
  --output sync_test.mkv

# Binary counters in all 4 quadrants (2x2 video wall mode)
python3 generate.py generate \
  --input video.mp4 \
  --quad-counters \
  --frames 300 \
  --output sync_test.mkv

# Stream an encoded file via RTP
python3 generate.py stream sync_test.mkv 232.22.7.86:3000
```

## Commands

### `generate` — Create a sync test video

```
python3 generate.py generate [options] --output FILE
```

**Video options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--resolution WxH` | `1920x1080` | Output resolution |
| `--framerate FPS` | `30` | Frame rate in fps |
| `--frames N` | `1000` | Number of frames to generate |
| `--codec` | `h264` | Video codec: `h264`, `h265`, or `av1` |
| `--bitrate BR` | `4M` | Encoding bitrate |
| `--output FILE` | *(required)* | Output video file path |

**Input options:**

| Option | Description |
|--------|-------------|
| `--input FILE` | Video file to use as background (if omitted, solid blue background) |
| `--start-time SECONDS` | Skip first N seconds of input video |

**Overlay options (all enabled by default):**

| Option | Default | Description |
|--------|---------|-------------|
| `--no-bars` | | Disable scrolling bars |
| `--bar-width N` | `100` | Bar width in pixels |
| `--bar-speed N` | `5` | Bar scroll speed in px/frame |
| `--no-sync-dots` | | Disable sync dots |
| `--sync-dot-count N` | `3` | Number of dots per side |
| `--no-grid` | | Disable alignment grid |
| `--quad-counters` | | Draw binary counter at top-left of each quadrant (2x2 video wall layout) |
| `--no-ticker` | | Disable scrolling ticker |
| `--ticker-speed N` | `10` | Ticker scroll speed in px/frame |
| `--ticker-text TEXT` | | Custom ticker text (overrides `--ticker-image`) |
| `--ticker-image FILE` | `assets/custom-ticker.tga` | Ticker image file |
| `--no-snow` | | Disable snow/noise |
| `--snow-pixel-size N` | `32` | Snow block size in pixels (0 = disable) |
| `--snow-coverage N` | `100` | Snow area as % of screen |

### `stream` — RTP stream a video file

```
python3 generate.py stream INPUT_FILE IP:PORT
```

Streams the encoded video file in a loop via RTP/UDP using FFmpeg. Press Ctrl+C to stop.

## Overlay Elements

- **Binary Counter**: 32-bit frame number as 8x4 colored rectangle grid (green=1, white=0). Default: single counter at bottom-left. With `--quad-counters`: one counter at the top-left of each screen quadrant (2x2 video wall layout).
- **Scrolling Bars**: Gray vertical + horizontal bars moving across the frame. Wraps at edges.
- **Sync Dots**: Red dots scrolling along edges in all 4 screen quadrants.
- **Alignment Grid**: White checkered squares at frame corners for picture alignment verification.
- **Scrolling Ticker**: Horizontally scrolling strip near top of frame. Use `--ticker-text` for custom text or `--ticker-image` for an image file.
- **Snow/Noise**: Random RGB pixel blocks centered on screen.

## License

MIT
