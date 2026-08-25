"""Rebuild the Gene Editing card video from the body-part SVG layers.

genes-body.svg (exported from bodysvgswhiteonblack.ai) carries every trait
layer in one file, keyed by path id. This script inlines it on a black page,
recolors the layers white, and cross-fades them in turn — the same x-ray
glow the gallery installation had — capturing at retina and encoding the
card video. The cycle is periodic, so the video loops seamlessly with no
boomerang needed.

Unlike the other capture scripts this one serves its own page, not dist/;
run it from the repo root, no build required.
"""
import sys, os, time, threading, functools, socket, subprocess, tempfile, shutil, math, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gifify import Chrome
from http.server import HTTPServer, SimpleHTTPRequestHandler
from PIL import Image

S = tempfile.gettempdir()
FPS = 30
SECONDS = 11.0
# One glow slot per trait, in the order the light travels: mind, eyes,
# vessels, muscles, bones, then the organ systems.
TRAITS = ["intelligence", "depression", "eyecolor", "hemophilia",
          "athleticism", "height", "huntingtons", "taysachs",
          "obesity", "alcoholism", "sex"]
OUTLINE_OPACITY = 0.28   # constant dim silhouette behind the glow
GLOW_WIDTH = 1.8         # falloff, in slots: ~2-3 layers lit at once

HERE = os.path.dirname(os.path.abspath(__file__))
svg = open(os.path.join(HERE, "genes-body.svg")).read()
svg = re.sub(r"<style>.*?</style>", "", svg, flags=re.S)  # drop the .ai visibility rules

site = tempfile.mkdtemp(prefix="genes-site-")
with open(os.path.join(site, "index.html"), "w") as f:
    f.write("""<!doctype html><meta charset="utf-8">
<style>
  html, body { margin: 0; background: #000; }
  svg { display: block; width: 600px; height: 960px; }
  svg [id] { display: inline; }
  svg path, svg polygon, svg circle, svg rect { fill: #fff; }
</style>
""" + svg + """
<script>
  var LAYERS = %s;
  LAYERS.concat(["outline"]).forEach(function (id) {
    document.getElementById(id).style.opacity = 0;
  });
  window.__set = function (ops) {
    for (var id in ops) document.getElementById(id).style.opacity = ops[id];
  };
</script>""" % repr(TRAITS).replace("'", '"'))

os.chdir(site)
s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
httpd = HTTPServer(("127.0.0.1", port), functools.partial(SimpleHTTPRequestHandler))
threading.Thread(target=httpd.serve_forever, daemon=True).start()

ch = Chrome(os.path.join(S, ".genescap"))
frames = []
try:
    ch.send("Page.enable"); ch.send("Runtime.enable")
    ch.send("Emulation.setDeviceMetricsOverride", width=600, height=960,
            deviceScaleFactor=2, mobile=False)
    ch.send("Page.navigate", url="http://127.0.0.1:%d/" % port)
    for _ in range(60):
        if ch.js("typeof window.__set === 'function'"): break
        time.sleep(0.25)

    n = int(SECONDS * FPS)
    N = len(TRAITS)
    for i in range(n):
        t = i / n  # frame n would equal frame 0: a seamless loop
        ops = {"outline": OUTLINE_OPACITY}
        for k, trait in enumerate(TRAITS):
            d = abs(t - k / N)
            d = min(d, 1 - d) * N          # cyclic distance, in slots
            g = max(0.0, 1 - d / GLOW_WIDTH)
            g = g * g * (3 - 2 * g)        # smooth ease at both ends
            ops[trait] = round(g, 4)
        ch.js("window.__set(%s); 1" % repr(ops).replace("'", '"'))
        time.sleep(0.02)
        frames.append(ch.shot())
finally:
    ch.close(); httpd.shutdown()

tmp = tempfile.mkdtemp(prefix="genes-")
for i, f in enumerate(frames):
    f.save(os.path.join(tmp, "f%05d.png" % i))
os.chdir(HERE + "/../..")
subprocess.run(["scripts/png2mp4", tmp, "public/videos/genes.mp4",
                str(FPS), "0.05"], check=True)
shutil.rmtree(tmp, ignore_errors=True)
shutil.rmtree(site, ignore_errors=True)
frames[0].save("public/images/gifs/genes-poster.webp", quality=85, method=6)
print("frames:", len(frames), "size:", frames[0].size)
