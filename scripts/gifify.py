#!/usr/bin/env python3
"""Turn edited screen recordings into looping GIFs for the site.

WORKFLOW
    1. Crop and trim the clip however you like.
    2. Save it into  media/  named after the page it belongs to, so the file
       stem matches the page slug:  media/octopuses.mov  ->  /octopuses
    3. Run:  python3 scripts/gifify.py
       The GIF lands in  public/images/gifs/<slug>.gif  and the card on
       /data-visualizations picks it up on the next build.

Only clips whose GIF is missing or older than the video are rebuilt, so
re-running is cheap. Pass --force to rebuild everything, or name specific
files to do just those.

COLOUR
    Two things usually make a screen-recording GIF look dull, and both are
    handled here:

    * Colour management. macOS records in Display P3. Decoding without saying
      what to convert to gives washed-out or shifted colour, so Chrome is
      pinned to sRGB, which is what browsers show GIFs in.
    * Palette. A GIF holds 256 colours. Quantising each frame separately makes
      colours crawl between frames, so one shared palette is built from the
      whole clip and every frame is mapped to it.

    --vivid applies a gentle saturation lift on top of that (1.0 is off).

USAGE
    python3 scripts/gifify.py                    # convert what's new
    python3 scripts/gifify.py --force            # rebuild everything
    python3 scripts/gifify.py media/octopuses.mov
    python3 scripts/gifify.py --width 560 --fps 15 --vivid 1.12

REQUIREMENTS
    Google Chrome (used as the video decoder, so no ffmpeg needed),
    Pillow, and websocket-client:  pip3 install Pillow websocket-client
"""

import argparse
import base64
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler

try:
    import websocket  # websocket-client
except ImportError:
    sys.exit("Missing dependency. Run:  pip3 install websocket-client Pillow")

from PIL import Image, ImageEnhance, ImageSequence  # noqa: F401

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEDIA_DIR = os.path.join(REPO, "media")
OUT_DIR = os.path.join(REPO, "public", "images", "gifs")
PAGES_DIR = os.path.join(REPO, "src", "pages")
VIDEO_EXT = (".mov", ".mp4", ".m4v", ".webm")

CHROME = os.environ.get(
    "CHROME_PATH", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
)


# ----------------------------------------------------------------- file server

class _RangeHandler(SimpleHTTPRequestHandler):
    """Serves the clips. Chrome will not seek without byte-range support."""

    root = MEDIA_DIR

    def translate_path(self, path):
        rel = urllib.parse.unquote(path.split("?", 1)[0].split("#", 1)[0])
        return os.path.join(self.root, rel.lstrip("/"))

    def guess_type(self, path):
        if path.lower().endswith((".mov", ".m4v")):
            return "video/mp4"
        return SimpleHTTPRequestHandler.guess_type(self, path)

    def do_GET(self):
        if self.path.startswith("/__player"):
            body = (
                b"<body style='margin:0;background:#000'>"
                b"<video id='v' muted playsinline preload='auto' "
                b"style='display:block;width:100vw;height:100vh;object-fit:contain'>"
                b"</video><script>"
                b"var v=document.getElementById('v');"
                b"v.src=new URLSearchParams(location.search).get('src');v.load();"
                b"</script>"
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        path = self.translate_path(self.path)
        if not os.path.isfile(path):
            self.send_error(404)
            return
        size = os.path.getsize(path)
        ctype = self.guess_type(path)
        rng = self.headers.get("Range")

        if not rng:
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(size))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            with open(path, "rb") as f:
                shutil.copyfileobj(f, self.wfile)
            return

        import re
        m = re.match(r"bytes=(\d*)-(\d*)", rng)
        start = int(m.group(1)) if m and m.group(1) else 0
        end = int(m.group(2)) if m and m.group(2) else size - 1
        end = min(end, size - 1)
        length = max(0, end - start + 1)
        self.send_response(206)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        with open(path, "rb") as f:
            f.seek(start)
            left = length
            while left > 0:
                chunk = f.read(min(65536, left))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    return
                left -= len(chunk)

    def log_message(self, *args):
        pass


def start_server():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    httpd = HTTPServer(("127.0.0.1", port), _RangeHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, port


# ---------------------------------------------------------------- chrome / CDP

class Chrome:
    def __init__(self, profile):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        self.port = s.getsockname()[1]
        s.close()
        self.profile = profile
        shutil.rmtree(profile, ignore_errors=True)
        self.proc = subprocess.Popen(
            [
                CHROME, "--headless", "--disable-gpu", "--no-sandbox",
                "--hide-scrollbars", "--mute-audio",
                "--force-device-scale-factor=1",
                # Decode and composite in sRGB so colours match what a browser
                # will later show for the GIF.
                "--force-color-profile=srgb",
                "--autoplay-policy=no-user-gesture-required",
                "--user-data-dir=" + profile,
                "--remote-debugging-port=%d" % self.port,
                "about:blank",
            ],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.ws, self.msg_id = None, 0
        for _ in range(100):
            try:
                import urllib.request
                raw = urllib.request.urlopen(
                    "http://127.0.0.1:%d/json/list" % self.port, timeout=2).read()
                pages = [t for t in json.loads(raw) if t.get("type") == "page"]
                if pages:
                    self.ws = websocket.create_connection(
                        pages[0]["webSocketDebuggerUrl"], timeout=60,
                        suppress_origin=True)
                    break
            except Exception:
                pass
            time.sleep(0.25)
        if not self.ws:
            raise RuntimeError("could not start Chrome (set CHROME_PATH?)")

    def send(self, method, **params):
        self.msg_id += 1
        mid = self.msg_id
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError("%s: %s" % (method, msg["error"]))
                return msg.get("result", {})

    def js(self, expr):
        r = self.send("Runtime.evaluate", expression=expr,
                      returnByValue=True, awaitPromise=True)
        return r.get("result", {}).get("value")

    def shot(self):
        r = self.send("Page.captureScreenshot", format="png", fromSurface=True)
        return Image.open(io.BytesIO(base64.b64decode(r["data"]))).convert("RGB")

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass
        self.proc.terminate()
        try:
            self.proc.wait(timeout=10)
        except Exception:
            self.proc.kill()
        shutil.rmtree(self.profile, ignore_errors=True)


# -------------------------------------------------------------------- pipeline

def grab_frames(ch, port, filename, fps, max_seconds, start=0.0):
    src = urllib.parse.quote(filename)
    ch.send("Page.enable")
    ch.send("Runtime.enable")
    ch.send("Page.navigate",
            url="http://127.0.0.1:%d/__player?src=%s" % (port, src))
    time.sleep(1.0)

    meta = None
    for _ in range(60):
        meta = ch.js("(function(){var v=document.getElementById('v');"
                     "if(!v||!v.videoWidth)return null;"
                     "return [v.videoWidth,v.videoHeight,v.duration];})()")
        if meta:
            break
        time.sleep(0.4)
    if not meta:
        raise RuntimeError("Chrome could not decode this file")
    vw, vh, dur = meta

    # Render at the clip's own aspect ratio so nothing is letterboxed.
    shot_w = 1000
    shot_h = max(2, int(round(shot_w * vh / vw)))
    ch.send("Emulation.setDeviceMetricsOverride", width=shot_w, height=shot_h,
            deviceScaleFactor=1, mobile=False)
    time.sleep(0.3)

    start = max(0.0, min(start, max(0.0, dur - 0.2)))
    span = min(dur - start, max_seconds) if max_seconds else (dur - start)
    span = max(0.2, span - 0.03)
    n = max(2, int(round(span * fps)))
    frames = []
    for i in range(n):
        t = start + span * i / (n - 1)
        ch.js("new Promise(function(r){var v=document.getElementById('v');"
              "v.onseeked=function(){r(1)};v.currentTime=%f;"
              "setTimeout(function(){r(0)},2500);})" % t)
        time.sleep(0.04)
        frames.append(ch.shot())
    return frames, dur, (vw, vh)


def content_box(frames, pad=0.035, min_frac=0.5, max_aspect=1.9, min_aspect=0.62):
    """Bounding box of everything that is not background, padded and shaped.

    Only used with --crop, for clips that were not trimmed by hand.
    """
    import numpy as np
    w, h = frames[0].size
    arrs = [np.asarray(f.convert("RGB"), dtype=np.int16) for f in frames]
    corner = np.concatenate([
        arrs[0][:14, :14].reshape(-1, 3), arrs[0][:14, -14:].reshape(-1, 3),
        arrs[0][-14:, :14].reshape(-1, 3), arrs[0][-14:, -14:].reshape(-1, 3),
    ])
    bg = np.median(corner, axis=0)
    mask = np.zeros((h, w), dtype=bool)
    for a in arrs:
        mask |= (np.abs(a - bg).max(axis=2) > 20)
    rows = np.where(mask.sum(axis=1) > w * 0.006)[0]
    cols = np.where(mask.sum(axis=0) > h * 0.006)[0]
    if not len(rows) or not len(cols):
        return (0, 0, w, h)
    top, bot, left, right = rows.min(), rows.max(), cols.min(), cols.max()
    px, py = int(w * pad), int(h * pad)
    left, right = max(0, left - px), min(w, right + px)
    top, bot = max(0, top - py), min(h, bot + py)

    def grow(lo, hi, limit, need):
        while (hi - lo) < need:
            if lo > 0:
                lo -= 1
            if hi < limit and (hi - lo) < need:
                hi += 1
            if lo == 0 and hi == limit:
                break
        return lo, hi

    left, right = grow(left, right, w, int(w * min_frac))
    top, bot = grow(top, bot, h, int(h * min_frac))
    cw, chh = right - left, bot - top
    if cw / chh > max_aspect:
        top, bot = grow(top, bot, h, int(cw / max_aspect))
    elif cw / chh < min_aspect:
        left, right = grow(left, right, w, int(chh * min_aspect))
    return (int(left), int(top), int(right), int(bot))


def encode(frames, out_path, width, fps, colors, vivid, dither="fs", hold=0.0,
           quality=82, bounce=False):
    w, h = frames[0].size
    height = max(2, int(round(width * h / w)))
    frames = [f.resize((width, height), Image.LANCZOS) for f in frames]

    if vivid and abs(vivid - 1.0) > 1e-3:
        frames = [ImageEnhance.Color(f).enhance(vivid) for f in frames]

    # Boomerang: play forward then back so the loop never snaps to the start.
    if bounce and len(frames) > 2:
        frames = frames + frames[-2:0:-1]

    base = int(round(1000.0 / fps))
    durations = [base] * len(frames)
    durations[-1] = base + int(round(hold * 1000))

    # Animated WebP: no 256-colour palette, so no quantising or dithering,
    # and lossy compression keeps even 20 fps clips lighter than a GIF.
    if out_path.lower().endswith(".webp"):
        frames[0].save(out_path, save_all=True, append_images=frames[1:],
                       duration=durations, loop=0, quality=quality, method=4)
        return width, height

    # One palette for the whole clip: per-frame palettes make colours crawl.
    step = max(1, len(frames) // 24)
    sample = frames[::step]
    strip = Image.new("RGB", (width, height * len(sample)))
    for i, f in enumerate(sample):
        strip.paste(f, (0, i * height))
    palette = strip.quantize(colors=colors, method=Image.MEDIANCUT)

    mode = Image.FLOYDSTEINBERG if dither == "fs" else Image.NONE
    conv = [f.quantize(palette=palette, dither=mode) for f in frames]
    conv[0].save(out_path, save_all=True, append_images=conv[1:],
                 duration=durations, loop=0, optimize=True, disposal=1)
    return width, height


def known_slugs():
    if not os.path.isdir(PAGES_DIR):
        return set()
    return {f[:-6] for f in os.listdir(PAGES_DIR) if f.endswith(".astro")}


def main():
    ap = argparse.ArgumentParser(description="Convert edited clips in media/ to GIFs.")
    ap.add_argument("files", nargs="*", help="specific video files (default: all of media/)")
    ap.add_argument("--width", type=int, default=480, help="output width in px (default 480)")
    ap.add_argument("--fps", type=int, default=20, help="frames per second (default 20)")
    ap.add_argument("--format", choices=("gif", "webp"), default="webp",
                    help="webp (default) is smoother and lighter: real colour, "
                         "no palette; gif is the legacy output")
    ap.add_argument("--colors", type=int, default=160, help="palette size, max 256 (default 160)")
    ap.add_argument("--dither", choices=("fs", "none"), default="fs",
                    help="fs keeps gradients smooth; none is smaller and crisper "
                         "on flat-colour charts")
    ap.add_argument("--no-bounce", action="store_true",
                    help="loop straight through instead of the default "
                         "forward-then-backward boomerang")
    ap.add_argument("--quality", type=int, default=82,
                    help="webp lossy quality 0-100 (default 82); lower it for "
                         "long clips that come out heavy")
    ap.add_argument("--vivid", type=float, default=1.06,
                    help="saturation multiplier, 1.0 leaves colour untouched")
    ap.add_argument("--start", type=float, default=0.0,
                    help="begin at this second (use with --max-seconds to take a "
                         "segment from the middle or end of a clip)")
    ap.add_argument("--slug", default=None,
                    help="output name, when the file is not already named after "
                         "its page (e.g. --slug respiratoryviruses)")
    ap.add_argument("--max-seconds", type=float, default=0,
                    help="trim to this many seconds (0 keeps the whole clip)")
    ap.add_argument("--hold", type=float, default=0.0,
                    help="extra seconds to rest on the last frame before looping")
    ap.add_argument("--crop", action="store_true",
                    help="trim dead margins automatically; for clips you have "
                         "not already cropped by hand")
    ap.add_argument("--force", action="store_true", help="rebuild even if up to date")
    args = ap.parse_args()

    os.makedirs(MEDIA_DIR, exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)

    if args.files:
        vids = [os.path.abspath(f) for f in args.files]
    else:
        vids = [os.path.join(MEDIA_DIR, f) for f in sorted(os.listdir(MEDIA_DIR))
                if f.lower().endswith(VIDEO_EXT)]
    if not vids:
        print("No videos in %s. Drop clips there named after their page, "
              "e.g. octopuses.mov" % os.path.relpath(MEDIA_DIR, REPO))
        return

    slugs = known_slugs()
    httpd, port = start_server()
    _RangeHandler.root = os.path.dirname(vids[0]) if args.files else MEDIA_DIR
    made = skipped = 0
    try:
        for path in vids:
            slug = args.slug or os.path.splitext(os.path.basename(path))[0]
            out = os.path.join(OUT_DIR, slug + "." + args.format)

            if (not args.force and os.path.exists(out)
                    and os.path.getmtime(out) >= os.path.getmtime(path)):
                print("%-26s up to date" % slug)
                skipped += 1
                continue

            ch = Chrome(os.path.join(REPO, ".gifify-profile-%d" % os.getpid()))
            try:
                frames, dur, dims = grab_frames(
                    ch, port, os.path.basename(path), args.fps, args.max_seconds,
                    args.start)
            finally:
                ch.close()

            if args.crop:
                frames = [f.crop(content_box(frames)) for f in frames]
            w, h = encode(frames, out, args.width, args.fps, args.colors,
                          args.vivid, args.dither, args.hold, args.quality,
                          bounce=not args.no_bounce)
            kb = os.path.getsize(out) / 1024
            note = "" if slug in slugs else "   (no page /%s yet)" % slug
            if kb > 1200:
                note += "   <- heavy; try --fps 8, --width 420, or --dither none"
            print("%-26s %5.1fs  %d frames  %dx%-4d %6.0f KB%s"
                  % (slug, dur, len(frames), w, h, kb, note))
            made += 1
    finally:
        httpd.shutdown()

    print("\n%d built, %d already current -> %s"
          % (made, skipped, os.path.relpath(OUT_DIR, REPO)))
    if made:
        print("Run `npm run build` (or reload the dev server) to see them.")


if __name__ == "__main__":
    main()
