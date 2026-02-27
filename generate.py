#!/usr/bin/env python3
"""Video sync test stream generator.

Generates video streams with overlay patterns (binary frame counter, scrolling
bars, sync dots, alignment grid, scrolling ticker, snow/noise) for AV
synchronization testing. Overlays are composited onto background frames (from
PNG directory or video file) and encoded via FFmpeg.
"""

import argparse
import os
import random
import struct
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


# ---------------------------------------------------------------------------
# Overlay Renderer
# ---------------------------------------------------------------------------

class OverlayRenderer:
    """Renders all overlay elements onto an RGBA image for a single frame."""

    def __init__(self, width, height, bar_width=100, bar_speed=5,
                 enable_bars=True, enable_sync_dots=True, sync_dot_count=3,
                 enable_grid=True, enable_ticker=True, ticker_speed=10,
                 ticker_image=None, ticker_text=None, enable_snow=True,
                 snow_pixel_size=32, snow_coverage=100, quad_counters=False):
        self.width = width
        self.height = height

        # binary counter mode
        self.quad_counters = quad_counters

        # bars
        self.enable_bars = enable_bars
        self.bar_width = bar_width
        self.bar_speed = bar_speed

        # sync dots
        self.enable_sync_dots = enable_sync_dots
        self.sync_dot_count = sync_dot_count

        # grid
        self.enable_grid = enable_grid

        # ticker
        self.enable_ticker = enable_ticker
        self.ticker_speed = ticker_speed
        self.ticker_image_obj = None
        if enable_ticker and ticker_text:
            self.ticker_image_obj = self._generate_ticker_from_text(ticker_text)
        elif enable_ticker and ticker_image:
            p = Path(ticker_image)
            if p.exists():
                self.ticker_image_obj = Image.open(p).convert("RGB")
            else:
                print(f"Warning: ticker image '{ticker_image}' not found, "
                      "disabling ticker.")
                self.enable_ticker = False

        # snow
        self.enable_snow = enable_snow
        self.snow_pixel_size = snow_pixel_size
        self.snow_coverage = snow_coverage
        self._snow_buffer = None
        if enable_snow and snow_pixel_size > 0:
            self._init_snow()
        elif enable_snow and snow_pixel_size <= 0:
            self.enable_snow = False

    # -- ticker text rendering --

    @staticmethod
    def _generate_ticker_from_text(text, height=64):
        """Generate a wide ticker image from a text string."""
        # try to find a good system font, fall back to default
        font = None
        font_size = int(height * 0.7)
        for font_name in [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        ]:
            if Path(font_name).exists():
                font = ImageFont.truetype(font_name, font_size)
                break
        if font is None:
            font = ImageFont.load_default(font_size)

        # measure text width, repeat text with spacing to fill a wide strip
        spacer = "     +++     "
        segment = text + spacer
        # use a temp image to measure
        tmp = Image.new("RGB", (1, 1))
        tmp_draw = ImageDraw.Draw(tmp)
        bbox = tmp_draw.textbbox((0, 0), segment, font=font)
        segment_w = bbox[2] - bbox[0]

        # make the strip at least 4x the typical screen width for smooth scroll
        min_width = max(7680, segment_w * 4)
        repeats = (min_width // segment_w) + 1
        full_text = segment * repeats

        # render
        bbox = tmp_draw.textbbox((0, 0), full_text, font=font)
        text_w = bbox[2] - bbox[0]
        img = Image.new("RGB", (text_w, height), (0, 0, 0))
        draw = ImageDraw.Draw(img)
        y_offset = (height - (bbox[3] - bbox[1])) // 2
        draw.text((0, y_offset), full_text, fill=(255, 255, 255), font=font)
        return img

    # -- snow buffer --

    def _init_snow(self):
        """Pre-generate a large random-pixel buffer for snow effect."""
        k = self.snow_pixel_size
        pct = self.snow_coverage / 100.0
        sw = int(self.width * pct)
        sh = int(self.height * pct)
        # align to block size
        sw = sw - (sw % k) if sw % k else sw
        sh = sh - (sh % k) if sh % k else sh
        if sw <= 0 or sh <= 0:
            self.enable_snow = False
            return
        self.snow_w = sw
        self.snow_h = sh

        buf_pages = 10
        cols = sw // k
        rows = (sh // k) * buf_pages

        # generate random blocks
        pixels = []
        for _ in range(rows):
            row_data = []
            for _ in range(cols):
                r, g, b = random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)
                row_data.extend([r, g, b] * k)
            row_bytes = bytes(row_data)
            for _ in range(k):
                pixels.append(row_bytes)

        self._snow_buffer = pixels
        self._snow_total_rows = len(pixels)

    # -- rendering entry point --

    def render_frame(self, frame_number):
        """Render the complete overlay for one frame. Returns an RGBA Image."""
        img = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # In the original OpenGL code, depth testing (GL_LESS) prevented later
        # draws from overwriting earlier ones at the same Z. In Pillow 2D, the
        # last draw wins. So we reverse the priority: draw background elements
        # first, then foreground elements (counter) last to keep them visible.
        if self.enable_grid:
            self._draw_alignment_grid(draw)
        if self.enable_snow and self.snow_coverage <= 50:
            self._draw_snow(img, frame_number)
        if self.enable_bars:
            self._draw_scrolling_bars(draw, frame_number)
        if self.enable_snow and self.snow_coverage > 50:
            self._draw_snow(img, frame_number)
        if self.enable_ticker:
            self._draw_ticker(img, frame_number)
        if self.enable_sync_dots:
            self._draw_sync_dots(draw, frame_number)
        # binary counter drawn LAST so it's always visible on top
        self._draw_binary_counter(draw, frame_number)

        return img

    # -- binary counter --

    def _draw_binary_counter(self, draw, frame_number):
        """Draw 32-bit frame counter as 8x4 grid of rectangles.

        Green = 1-bit, white = 0-bit, on black background.
        Default: single counter at bottom-left.
        With --quad-counters: one counter at the top-left of each quadrant
        (frame divided into a 2x2 video wall layout).
        """
        bits = 32
        cols = 8

        bit_w = int(0.02 * self.width)
        bit_h = int(0.02 * self.height)
        pad_x = int(0.004 * self.width)
        pad_y = int(0.004 * self.height)
        border = int(0.02 * self.width)
        border_y = int(0.02 * self.height)

        n_rows = bits // cols
        bg_w = cols * (pad_x + bit_w) + pad_x
        bg_h = n_rows * (pad_y + bit_h) + pad_y

        # pack frame number as 4 bytes big-endian
        data = struct.pack(">I", frame_number & 0xFFFFFFFF)

        if self.quad_counters:
            # 2x2 video wall: counter at top-left of each quadrant
            half_w = self.width // 2
            half_h = self.height // 2
            positions = [
                (border, border_y),                  # Q1: top-left quadrant
                (half_w + border, border_y),          # Q2: top-right quadrant
                (border, half_h + border_y),          # Q3: bottom-left quadrant
                (half_w + border, half_h + border_y), # Q4: bottom-right quadrant
            ]
        else:
            # single counter at bottom-left
            positions = [
                (border, self.height - border_y - bg_h),
            ]

        for ox, oy in positions:
            # black background
            draw.rectangle([ox, oy, ox + bg_w, oy + bg_h], fill=(0, 0, 0, 255))

            # draw bit rectangles
            for i in range(bits):
                byte_idx = i // 8
                bit_idx = 7 - (i % 8)
                bit_val = (data[byte_idx] >> bit_idx) & 1

                color = (0, 255, 0, 255) if bit_val else (255, 255, 255, 255)

                col = i % cols
                row = i // cols

                x = ox + pad_x + col * (bit_w + pad_x)
                y = oy + pad_y + row * (bit_h + pad_y)
                draw.rectangle([x, y, x + bit_w, y + bit_h], fill=color)

    # -- scrolling bars --

    def _draw_scrolling_bars(self, draw, frame_number):
        """Draw gray vertical and horizontal scrolling bars."""
        w, h = self.width, self.height
        sw = self.bar_width
        speed = self.bar_speed
        color = (204, 204, 204, 200)

        xs = (frame_number * speed) % w
        ys = (frame_number * speed) % h

        # vertical bar (scrolls horizontally)
        if xs + sw > w:
            draw.rectangle([xs, 0, w, h], fill=color)
            draw.rectangle([0, 0, (xs + sw) - w, h], fill=color)
        else:
            draw.rectangle([xs, 0, xs + sw, h], fill=color)

        # horizontal bar (scrolls vertically)
        if ys + sw > h:
            draw.rectangle([0, ys, w, h], fill=color)
            draw.rectangle([0, 0, w, (ys + sw) - h], fill=color)
        else:
            draw.rectangle([0, ys, w, ys + sw], fill=color)

    # -- sync dots --

    def _draw_sync_dots(self, draw, frame_number):
        """Draw scrolling sync dots in 4 quadrants along edges."""
        half_w = self.width // 2
        half_h = self.height // 2
        dot_size = 10
        dot_spacing = 15
        speed = self.bar_speed
        count = self.sync_dot_count
        color = (255, 0, 0, 255)

        for quadrant in range(4):
            tx = 0 if quadrant >= 2 else half_w
            ty = 0 if quadrant % 2 == 1 else half_h

            xs = (frame_number * speed) % half_w
            ys = (frame_number * speed) % half_h

            # set 1: uniform scroll
            for i in range(-count, count + 1):
                ds_x = dot_size * 2 if i == 0 else dot_size
                ds_y = dot_size * 2 if i == 0 else dot_size
                x = (xs + i * 2 * dot_spacing) % half_w
                y = (ys + i * 2 * dot_spacing) % half_h

                # top/bottom edges: horizontal dots
                if ty == 0:
                    bx1 = tx + x
                    by1 = ty + half_h - ds_y
                    if x + dot_size > half_w:
                        draw.rectangle([tx, by1, tx + (x + dot_size - half_w), ty + half_h], fill=color)
                        draw.rectangle([bx1, by1, tx + half_w, ty + half_h], fill=color)
                    else:
                        draw.rectangle([bx1, by1, bx1 + dot_size, ty + half_h], fill=color)

                # left/right edges: vertical dots
                if tx == 0:
                    bx1 = tx + half_w - ds_x
                    by1 = ty + y
                    if y + dot_size > half_h:
                        draw.rectangle([bx1, ty, tx + half_w, ty + (y + dot_size - half_h)], fill=color)
                        draw.rectangle([bx1, by1, tx + half_w, ty + half_h], fill=color)
                    else:
                        draw.rectangle([bx1, by1, tx + half_w, by1 + dot_size], fill=color)

            # set 2: per-dot speed offset
            for i in range(-count, count + 1):
                ds_x = dot_size * 2 if i == 0 else dot_size
                ds_y = dot_size * 2 if i == 0 else dot_size
                x = (xs + i * 2 * dot_spacing + i * speed) % half_w
                y = (ys + i * 2 * dot_spacing + i * speed) % half_h

                # bottom/top edges (opposite of set 1)
                if ty != 0:
                    bx1 = tx + x
                    by1 = ty
                    if x + dot_size > half_w:
                        draw.rectangle([tx, by1, tx + (x + dot_size - half_w), by1 + ds_y], fill=color)
                        draw.rectangle([bx1, by1, tx + half_w, by1 + ds_y], fill=color)
                    else:
                        draw.rectangle([bx1, by1, bx1 + dot_size, by1 + ds_y], fill=color)

                if tx != 0:
                    bx1 = tx
                    by1 = ty + y
                    if y + dot_size > half_h:
                        draw.rectangle([bx1, ty, bx1 + ds_x, ty + (y + dot_size - half_h)], fill=color)
                        draw.rectangle([bx1, by1, bx1 + ds_x, ty + half_h], fill=color)
                    else:
                        draw.rectangle([bx1, by1, bx1 + ds_x, by1 + dot_size], fill=color)

    # -- alignment grid --

    def _draw_alignment_grid(self, draw):
        """Draw white checkered corner markers along all 4 edges."""
        w, h = self.width, self.height
        color = (255, 255, 255, 255)
        sq = 10  # square size

        # horizontal edges (top and bottom corners)
        for i in range(0, w // 7, 20):
            # bottom-left
            draw.rectangle([i, h - sq, i + sq, h], fill=color)
            # top-left
            draw.rectangle([i, 0, i + sq, sq], fill=color)
            # bottom-right
            draw.rectangle([w - sq - i, h - sq, w - i, h], fill=color)
            # top-right
            draw.rectangle([w - sq - i, 0, w - i, sq], fill=color)

        # vertical edges (left and right corners)
        for i in range(0, h // 7, 20):
            # bottom-left
            draw.rectangle([0, h - sq - i, sq, h - i], fill=color)
            # bottom-right
            draw.rectangle([w - sq, h - sq - i, w, h - i], fill=color)
            # top-left
            draw.rectangle([0, i, sq, i + sq], fill=color)
            # top-right
            draw.rectangle([w - sq, i, w, i + sq], fill=color)

    # -- ticker --

    def _draw_ticker(self, img, frame_number):
        """Draw scrolling ticker image at top of frame."""
        if self.ticker_image_obj is None:
            return

        ticker_h = 64
        tex_w, tex_h = self.ticker_image_obj.size

        # build the visible strip by tiling the ticker image
        strip = Image.new("RGBA", (self.width, ticker_h), (0, 0, 0, 0))

        # scale ticker height to match ticker_h while preserving aspect
        scale = ticker_h / tex_h
        scaled_w = int(tex_w * scale)
        ticker_scaled = self.ticker_image_obj.resize(
            (scaled_w, ticker_h), Image.LANCZOS
        )
        # scroll offset in screen pixels (consistent speed regardless of
        # source image dimensions)
        scaled_offset = (frame_number * self.ticker_speed) % scaled_w

        # tile across the strip width
        x = 0
        src_x = scaled_offset
        while x < self.width:
            chunk_w = min(scaled_w - src_x, self.width - x)
            crop = ticker_scaled.crop((src_x, 0, src_x + chunk_w, ticker_h))
            strip.paste(crop, (x, 0))
            x += chunk_w
            src_x = 0  # after first chunk, start from beginning

        # paste at top of frame
        y_pos = self.height - ticker_h - 64  # near top, with some margin
        img.alpha_composite(strip, (0, y_pos))

    # -- snow --

    def _draw_snow(self, img, frame_number):
        """Draw random noise block pattern centered on screen."""
        if self._snow_buffer is None:
            return

        sw, sh = self.snow_w, self.snow_h
        total = self._snow_total_rows

        # pick a random start row that leaves room for sh rows
        start = random.randint(0, total - sh - 1) if total > sh else 0

        # build raw RGB data from buffer rows
        raw = b"".join(self._snow_buffer[start:start + sh])
        snow_img = Image.frombytes("RGB", (sw, sh), raw).convert("RGBA")

        # center on screen
        ox = (self.width - sw) // 2
        oy = (self.height - sh) // 2
        img.alpha_composite(snow_img, (ox, oy))


# ---------------------------------------------------------------------------
# Stream Generator
# ---------------------------------------------------------------------------

CODEC_MAP = {
    "h264": "libx264",
    "h265": "libx265",
    "av1": "libaom-av1",
}


class StreamGenerator:
    """Pipeline controller for generation and streaming."""

    def _probe_frame_count(self, video_path, framerate, start_time=None):
        """Use ffprobe to get the total number of frames in a video file."""
        # try nb_frames from container metadata (instant)
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=nb_frames",
            "-print_format", "csv=p=0",
            video_path,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            count = int(result.stdout.strip())
            if count > 0:
                offset = int(float(start_time) * framerate) if start_time else 0
                return max(1, count - offset)
        except (ValueError, subprocess.TimeoutExpired):
            pass

        # fallback: compute from duration * framerate
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=duration,r_frame_rate",
            "-print_format", "csv=p=0",
            video_path,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            parts = result.stdout.strip().split(",")
            duration = float(parts[0])
            if start_time:
                duration = max(0, duration - float(start_time))
            return max(1, int(duration * framerate))
        except (ValueError, IndexError, subprocess.TimeoutExpired):
            pass
        return None

    def generate(self, args):
        """Full pipeline: render overlays, composite on background, encode."""
        width, height = args.width, args.height

        # resolve frame count
        if args.frames is None:
            if args.input:
                print("Probing input video for frame count ...")
                probed = self._probe_frame_count(args.input, args.framerate, args.start_time)
                if probed:
                    args.frames = probed
                    print(f"  detected {probed} frames")
                else:
                    args.frames = 1000
                    print("  could not detect frame count, using default 1000")
            else:
                args.frames = 1000

        renderer = OverlayRenderer(
            width, height,
            bar_width=args.bar_width,
            bar_speed=args.bar_speed,
            enable_bars=not args.no_bars,
            enable_sync_dots=not args.no_sync_dots,
            sync_dot_count=args.sync_dot_count,
            enable_grid=not args.no_grid,
            enable_ticker=not args.no_ticker,
            ticker_speed=args.ticker_speed,
            ticker_image=args.ticker_image,
            ticker_text=args.ticker_text,
            enable_snow=not args.no_snow,
            snow_pixel_size=args.snow_pixel_size,
            snow_coverage=args.snow_coverage,
            quad_counters=args.quad_counters,
        )

        # start encoder
        encoder = self._start_encoder(args)

        # start decoder if input video provided
        decoder = None
        if args.input:
            decoder = self._start_decoder(args)

        frame_size = width * height * 3
        total = args.frames
        report_interval = max(1, total // 10)

        print(f"Generating {total} frames at {args.framerate} fps, "
              f"{width}x{height}, codec={args.codec} ...")

        try:
            for frame_num in range(1, total + 1):
                # load background
                bg = self._load_background(
                    frame_num, args, decoder, frame_size
                )

                # render overlay
                overlay = renderer.render_frame(frame_num)

                # composite
                composite = Image.alpha_composite(bg.convert("RGBA"), overlay)

                # write raw RGB to encoder
                encoder.stdin.write(composite.convert("RGB").tobytes())

                if frame_num % report_interval == 0 or frame_num == total:
                    pct = int(100 * frame_num / total)
                    print(f"  frame {frame_num}/{total} ({pct}%)")

        except BrokenPipeError:
            print("Error: FFmpeg encoder process terminated unexpectedly.")
        finally:
            encoder.stdin.close()
            encoder.wait()
            if decoder:
                decoder.stdout.close()
                decoder.wait()

        print(f"Done. Output: {args.output}")

    def stream(self, args):
        """Stream an encoded video file via RTP."""
        input_file = args.input
        dest = args.destination
        if ":" not in dest:
            print("Error: destination must be IP:PORT")
            sys.exit(1)

        ip, port = dest.rsplit(":", 1)
        print(f"Streaming {input_file} to rtp://{ip}:{port} (Ctrl+C to stop)")

        cmd = [
            "ffmpeg", "-re", "-stream_loop", "-1",
            "-i", input_file,
            "-c:v", "copy", "-an",
            "-f", "rtp", f"rtp://{ip}:{port}",
        ]
        try:
            subprocess.run(cmd, check=True)
        except KeyboardInterrupt:
            print("\nStreaming stopped.")
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg error: {e}")
            sys.exit(1)

    # -- helpers --

    def _start_encoder(self, args):
        codec = CODEC_MAP.get(args.codec)
        if not codec:
            print(f"Error: unsupported codec '{args.codec}'")
            sys.exit(1)

        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "warning",
            "-f", "rawvideo", "-pix_fmt", "rgb24",
            "-s", f"{args.width}x{args.height}",
            "-r", str(args.framerate),
            "-i", "pipe:0",
            "-an",
            "-c:v", codec,
            "-b:v", args.bitrate,
            "-pix_fmt", "yuv420p",
            args.output,
        ]
        return subprocess.Popen(cmd, stdin=subprocess.PIPE)

    def _start_decoder(self, args):
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "warning",
        ]
        if args.start_time:
            cmd += ["-ss", args.start_time]
        cmd += [
            "-i", args.input,
            "-vframes", str(args.frames),
            "-s", f"{args.width}x{args.height}",
            "-pix_fmt", "rgb24",
            "-f", "rawvideo", "pipe:1",
        ]
        return subprocess.Popen(cmd, stdout=subprocess.PIPE)

    def _load_background(self, frame_num, args, decoder, frame_size):
        """Load background image for a given frame number."""
        w, h = args.width, args.height

        if decoder:
            raw = decoder.stdout.read(frame_size)
            if len(raw) == frame_size:
                return Image.frombytes("RGB", (w, h), raw)
            # ran out of video frames — fall back to blue
            return Image.new("RGB", (w, h), (0, 0, 255))

        # no input: blue background (matches original pgen)
        return Image.new("RGB", (w, h), (0, 0, 255))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_resolution(s):
    """Parse 'WxH' string into (width, height) tuple."""
    try:
        w, h = s.lower().split("x")
        return int(w), int(h)
    except (ValueError, AttributeError):
        raise argparse.ArgumentTypeError(
            f"Invalid resolution '{s}'. Expected format: WxH (e.g. 1920x1080)"
        )


def main():
    parser = argparse.ArgumentParser(
        description="Video sync test stream generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="available commands")

    # -- generate subcommand --
    gen = subparsers.add_parser(
        "generate",
        help="Generate a sync test video with overlay patterns",
    )
    gen.add_argument(
        "--resolution", type=parse_resolution, default=(1920, 1080),
        metavar="WxH", help="Video resolution (default: 1920x1080)",
    )
    gen.add_argument(
        "--framerate", type=int, default=30,
        help="Frame rate in fps (default: 30)",
    )
    gen.add_argument(
        "--frames", type=int, default=None,
        help="Number of frames to generate (default: full input video, or 1000 if no input)",
    )
    gen.add_argument(
        "--codec", choices=list(CODEC_MAP.keys()), default="h264",
        help="Video codec (default: h264)",
    )
    gen.add_argument(
        "--bitrate", default="4M",
        help="Encoding bitrate (default: 4M)",
    )
    gen.add_argument(
        "--input", metavar="FILE",
        help="Video file to use as background (if omitted, solid blue background)",
    )
    gen.add_argument(
        "--start-time", metavar="SECONDS",
        help="Skip first N seconds of input video",
    )
    gen.add_argument(
        "--output", required=True, metavar="FILE",
        help="Output video file path",
    )
    # overlay toggle options
    overlay = gen.add_argument_group("overlay options")
    overlay.add_argument("--no-bars", action="store_true", help="Disable scrolling bars")
    overlay.add_argument("--bar-width", type=int, default=100, help="Bar width in pixels (default: 100)")
    overlay.add_argument("--bar-speed", type=int, default=5, help="Bar scroll speed in px/frame (default: 5)")
    overlay.add_argument("--no-sync-dots", action="store_true", help="Disable sync dots")
    overlay.add_argument("--sync-dot-count", type=int, default=3, help="Number of sync dots per side (default: 3)")
    overlay.add_argument("--no-grid", action="store_true", help="Disable alignment grid")
    overlay.add_argument("--quad-counters", action="store_true", help="Draw binary counter at top-left of each quadrant (2x2 video wall layout)")
    overlay.add_argument("--no-ticker", action="store_true", help="Disable scrolling ticker")
    overlay.add_argument("--ticker-speed", type=int, default=10, help="Ticker scroll speed (default: 10)")
    overlay.add_argument("--ticker-text", default=None, metavar="TEXT", help="Custom ticker text (overrides --ticker-image)")
    overlay.add_argument("--ticker-image", default=None, help="Ticker image file (default: assets/custom-ticker.tga)")
    overlay.add_argument("--no-snow", action="store_true", help="Disable snow/noise pattern")
    overlay.add_argument("--snow-pixel-size", type=int, default=32, help="Snow block size in pixels (default: 32, 0=disable)")
    overlay.add_argument("--snow-coverage", type=int, default=100, help="Snow area as %% of screen (default: 100)")

    # -- stream subcommand --
    st = subparsers.add_parser(
        "stream",
        help="Stream an encoded video file via RTP",
    )
    st.add_argument("input", help="Encoded video file to stream")
    st.add_argument("destination", help="Destination as IP:PORT")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # unpack resolution tuple into width/height for generate command
    if args.command == "generate":
        args.width, args.height = args.resolution

        # default ticker image path relative to this script
        if args.ticker_image is None and not args.no_ticker:
            script_dir = Path(__file__).resolve().parent
            args.ticker_image = str(script_dir / "assets" / "custom-ticker.tga")

    gen = StreamGenerator()
    if args.command == "generate":
        gen.generate(args)
    elif args.command == "stream":
        gen.stream(args)


if __name__ == "__main__":
    main()
