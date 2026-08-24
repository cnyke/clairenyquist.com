"""Animate the AI models timeline: dots rise year by year in a sweeping wave.

Captured forward (empty -> full) but assembled reverse-first, so the video
opens on the complete chart (matching the poster), empties, and refills.
"""
import sys, os, time, threading, functools, socket, subprocess, tempfile, shutil
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
from gifify import Chrome
from http.server import HTTPServer, SimpleHTTPRequestHandler
from PIL import Image

S = tempfile.gettempdir()
FPS = 30
SECONDS = 6.0

os.chdir("dist")
s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
httpd = HTTPServer(("127.0.0.1", port), functools.partial(SimpleHTTPRequestHandler))
threading.Thread(target=httpd.serve_forever, daemon=True).start()

ch = Chrome(os.path.join(S, ".aicap"))
frames = []
try:
    ch.send("Page.enable"); ch.send("Runtime.enable")
    ch.send("Emulation.setDeviceMetricsOverride", width=718, height=770,
            deviceScaleFactor=2, mobile=False)
    ch.send("Page.navigate", url="http://127.0.0.1:%d/ai-models-timeline/" % port)

    for _ in range(120):
        ok = ch.js("document.querySelectorAll('svg circle').length > 100")
        if ok: break
        time.sleep(0.5)
    if not ok: raise RuntimeError("chart never appeared")
    time.sleep(2)

    # Index every dot: columns left to right, bottom dot first within each.
    ch.js("""(function(){
        var svg = Array.from(document.querySelectorAll('svg')).find(function(s){
            return s.querySelectorAll('circle').length > 100; });
        window.__chart = svg;
        var hd = document.querySelector('header') || document.querySelector('nav');
        if (hd) hd.style.display = 'none';
        svg.scrollIntoView({block:'end'});
        var dots = Array.from(svg.querySelectorAll('circle'));
        var cols = {};
        dots.forEach(function(c){
            var x = Math.round(parseFloat(c.getAttribute('cx')) || 0);
            (cols[x] = cols[x] || []).push(c);
        });
        var xs = Object.keys(cols).map(Number).sort(function(a,b){return a-b;});
        window.__dots = [];
        xs.forEach(function(x, ci){
            var col = cols[x].sort(function(a,b){
                return parseFloat(b.getAttribute('cy')) - parseFloat(a.getAttribute('cy'));});
            col.forEach(function(c, di){
                window.__dots.push({el: c,
                    t: 0.8 * ci / Math.max(1, xs.length - 1)
                     + 0.2 * di / Math.max(1, col.length - 1)});
            });
        });
        window.__reveal = function(p){
            window.__dots.forEach(function(d){
                d.el.style.visibility = p >= d.t ? 'visible' : 'hidden';});
        };
        return window.__dots.length;})()""")
    time.sleep(0.5)

    box = ch.js("""(function(){
        var r = window.__chart.getBoundingClientRect();
        var x0 = Math.max(0, r.x), y0 = Math.max(0, r.y);
        var x1 = Math.min(window.innerWidth, r.x + r.width);
        var y1 = Math.min(window.innerHeight, r.y + r.height);
        return [x0, y0, x1 - x0, y1 - y0];})()""")
    x, y, w, h = box
    W = int(w) - int(w) % 2
    H = int(h) - int(h) % 2
    print("crop:", box, "->", W, H)

    n = int(SECONDS * FPS)
    for i in range(n):
        t = i / (n - 1)
        e = t * t * (3 - 2 * t)
        ch.js("window.__reveal(%f); 1" % e)
        time.sleep(0.03)
        shot = ch.shot()
        crop = shot.crop((int(x*2), int(y*2), int((x+w)*2), int((y+h)*2)))
        frames.append(crop.resize((2 * W, 2 * H), Image.LANCZOS))
finally:
    ch.close(); httpd.shutdown()

frames = frames[::-1] + frames[1:-1]  # start full, empty out, refill
tmp = tempfile.mkdtemp(prefix="ai-")
for i, f in enumerate(frames):
    f.save(os.path.join(tmp, "f%05d.png" % i))
os.chdir("..")
subprocess.run(["scripts/png2mp4", tmp, "public/videos/ai-models-timeline.mp4",
                str(FPS), "0.07"], check=True)
shutil.rmtree(tmp, ignore_errors=True)
frames[0].save(os.path.join(S, "aiz_first.png"))
frames[len(frames)//2].save(os.path.join(S, "aiz_mid.png"))
print("frames:", len(frames), "size:", W, H)
