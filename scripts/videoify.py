#!/usr/bin/env python3
"""Turn edited screen recordings into looping H.264 videos for the site.

Same capture pipeline as gifify.py (Chrome decodes the clip so color is
handled identically), but the frames are handed to png2mp4 (AVFoundation)
and come out as a small hardware-decodable MP4 with the boomerang loop
baked in: forward, then backward, so the loop never snaps.

    python3 scripts/videoify.py --slug octopuses --width 772 media/octopus.mov

Requires scripts/png2mp4.swift compiled next to this script:

    swiftc -O scripts/png2mp4.swift -o scripts/png2mp4
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gifify import REPO, Chrome, start_server, _RangeHandler, grab_frames  # noqa: E402

OUT_DIR = os.path.join(REPO, "public", "videos")
PNG2MP4 = os.path.join(REPO, "scripts", "png2mp4")


def main():
    ap = argparse.ArgumentParser(description="Convert a clip to a bouncing MP4.")
    ap.add_argument("file", help="source video file")
    ap.add_argument("--slug", required=True, help="output name: public/videos/<slug>.mp4")
    ap.add_argument("--width", type=int, default=480, help="output width (default 480)")
    ap.add_argument("--fps", type=int, default=20, help="capture fps (default 20)")
    ap.add_argument("--bpp", type=float, default=0.12,
                    help="H.264 bits per pixel; higher = larger + sharper")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--max-seconds", type=float, default=0)
    ap.add_argument("--no-bounce", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(PNG2MP4):
        sys.exit("png2mp4 missing. Run: swiftc -O scripts/png2mp4.swift -o scripts/png2mp4")

    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.abspath(args.file)
    _RangeHandler.root = os.path.dirname(path)
    httpd, port = start_server()
    ch = Chrome(os.path.join(REPO, ".videoify-profile-%d" % os.getpid()))
    try:
        frames, dur, dims = grab_frames(
            ch, port, os.path.basename(path), args.fps, args.max_seconds, args.start)
    finally:
        ch.close()
        httpd.shutdown()

    # Resize to target width (even dimensions for yuv420) and bake the bounce.
    from PIL import Image
    w = args.width - (args.width % 2)
    h = frames[0].size[1] * w // frames[0].size[0]
    h -= h % 2
    frames = [f.resize((w, h), Image.LANCZOS) for f in frames]
    if not args.no_bounce and len(frames) > 2:
        frames = frames + frames[-2:0:-1]

    out = os.path.join(OUT_DIR, args.slug + ".mp4")
    tmp = tempfile.mkdtemp(prefix="videoify-")
    try:
        for i, f in enumerate(frames):
            f.save(os.path.join(tmp, "f%05d.png" % i))
        subprocess.run([PNG2MP4, tmp, out, str(args.fps), str(args.bpp)], check=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("%s  %.1fs source, %d frames -> %.0f KB"
          % (os.path.relpath(out, REPO), dur, len(frames),
             os.path.getsize(out) / 1024))


if __name__ == "__main__":
    main()
