"""Wild Dye Plants card: square crop of the wheel, yellow/green arc lit.

Drives /wilddyeplants in headless Chrome. The page's own auto-rotation is
stopped (requestAnimationFrame is stubbed) so every frame is deterministic;
the script then sways the wheel gently and runs a bold/grow pulse along the
yellow-green arc. The whole rainbow stays at full color and brightness —
the pulse alone does the highlighting. The sway and the pulse both complete
whole cycles, so the clip loops seamlessly with no boomerang. Writes the
MP4, the poster, and re-encodes the WebP.
"""
import sys, os, time, threading, functools, socket, subprocess, tempfile, shutil, math, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
from gifify import Chrome
from http.server import HTTPServer, SimpleHTTPRequestHandler
from PIL import Image

S = tempfile.gettempdir()
FPS = 30
SECONDS = 10.0
SWAY_DEG = 18
# The page's colorNameToHex values that count as yellow or green.
YG = ["#facc15", "#fde047", "#fef08a", "#d4cc6a", "#bef264", "#a3e635",
      "#84cc16", "#65a30d", "#34d399", "#86efac"]

os.chdir("dist")
s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
httpd = HTTPServer(("127.0.0.1", port), functools.partial(SimpleHTTPRequestHandler))
threading.Thread(target=httpd.serve_forever, daemon=True).start()

ch = Chrome(os.path.join(S, ".dyecap"))
frames = []
try:
    ch.send("Page.enable"); ch.send("Runtime.enable")
    ch.send("Emulation.setDeviceMetricsOverride", width=720, height=760,
            deviceScaleFactor=2, mobile=False)
    ch.send("Page.navigate", url="http://127.0.0.1:%d/wilddyeplants/" % port)

    for _ in range(120):
        ok = ch.js("document.querySelectorAll('#viz svg text').length > 60")
        if ok: break
        time.sleep(0.5)
    if not ok: raise RuntimeError("wheel never appeared")
    time.sleep(2)

    n_hl = ch.js("""(function(){
        // Freeze the page's own spin, then take over the wheel.
        window.requestAnimationFrame = function(){ return 0; };
        var hd = document.querySelector('header') || document.querySelector('nav');
        if (hd) hd.style.display = 'none';
        document.querySelectorAll('.text-center, #symbol-key').forEach(
            function(el){ el.style.display = 'none'; });
        var wrap = document.querySelector('.px-4');
        if (wrap) { wrap.style.padding = '0'; }
        var svg = document.querySelector('#viz svg');
        svg.setAttribute('width', 720); svg.setAttribute('height', 720);
        window.scrollTo(0, 0);
        window.__svg = svg;
        window.__g = svg.querySelector('g');

        var YG = %s;
        window.__hl = []; var angles = [];
        svg.querySelectorAll('g.plant-ray').forEach(function(ray){
            var t = ray.querySelector('text');
            if (!t) return;
            var fill = (t.getAttribute('fill') || '').toLowerCase();
            var m = /rotate\\((-?[\\d.]+)\\)/.exec(t.getAttribute('transform') || '');
            var deg = m ? parseFloat(m[1]) : 0;
            if (YG.indexOf(fill) >= 0) {
                window.__hl.push({t: t, deg: deg});
                angles.push(deg);
            }
        });
        window.__hl.sort(function(a, b){ return a.deg - b.deg; });
        // Rotate the wheel so the middle of the yellow-green arc sits
        // upper right (-45deg on screen).
        var mid = angles.sort(function(a,b){return a-b;})[Math.floor(angles.length/2)];
        window.__r0 = -45 - mid;
        window.__set = function(rot, t){
            window.__g.setAttribute('transform',
                'translate(500,500) rotate(' + (window.__r0 + rot) + ')');
            var M = window.__hl.length;
            window.__hl.forEach(function(h, j){
                var d = Math.abs(t - j / M); d = Math.min(d, 1 - d) * M;
                var w = Math.max(0, 1 - d / 2.0);
                w = w * w * (3 - 2 * w);
                h.t.setAttribute('font-weight', w > 0.4 ? 700 : 500);
                h.t.setAttribute('font-size', 18 + 10 * w);
            });
        };
        return window.__hl.length;})()""" % json.dumps(YG))
    print("yellow/green names:", n_hl)
    time.sleep(0.5)

    box = ch.js("""(function(){
        var r = window.__svg.getBoundingClientRect();
        var x0 = Math.max(0, r.x), y0 = Math.max(0, r.y);
        var x1 = Math.min(window.innerWidth, r.x + r.width);
        var y1 = Math.min(window.innerHeight, r.y + r.height);
        return [x0, y0, x1 - x0, y1 - y0];})()""")
    x, y, w, h = box
    side = min(int(w), int(h))
    side -= side % 2
    print("crop:", box, "-> square", side)

    n = int(SECONDS * FPS)
    for i in range(n):
        t = i / n  # frame n would equal frame 0: a seamless loop
        rot = SWAY_DEG * math.sin(2 * math.pi * t)
        ch.js("window.__set(%f, %f); 1" % (rot, t))
        time.sleep(0.02)
        shot = ch.shot()
        crop = shot.crop((int(x * 2), int(y * 2),
                          int(x * 2) + 2 * side, int(y * 2) + 2 * side))
        frames.append(crop)
finally:
    ch.close(); httpd.shutdown()

tmp = tempfile.mkdtemp(prefix="dye-")
for i, f in enumerate(frames):
    f.save(os.path.join(tmp, "f%05d.png" % i))
os.chdir("..")
subprocess.run(["scripts/png2mp4", tmp, "public/videos/wilddyeplants.mp4",
                str(FPS), "0.05"], check=True)
shutil.rmtree(tmp, ignore_errors=True)
frames[0].resize((606, 606), Image.LANCZOS).save(
    "public/images/gifs/wilddyeplants-poster.webp", quality=85, method=6)
print("frames:", len(frames), "size:", frames[0].size)
