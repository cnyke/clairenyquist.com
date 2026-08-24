"""Scripted exoplanets video: eased log sweep of the distance slider."""
import sys, os, time, threading, functools, socket, subprocess, tempfile, shutil, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
from gifify import Chrome
from http.server import HTTPServer, SimpleHTTPRequestHandler
from PIL import Image

S = tempfile.gettempdir()
FPS = 30
SECONDS = 6.0
Y_HI, Y_LO = 27500, 500

os.chdir("dist")
s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
httpd = HTTPServer(("127.0.0.1", port), functools.partial(SimpleHTTPRequestHandler))
threading.Thread(target=httpd.serve_forever, daemon=True).start()

ch = Chrome(os.path.join(S, ".exocap"))
frames = []
try:
    ch.send("Page.enable"); ch.send("Runtime.enable")
    ch.send("Emulation.setDeviceMetricsOverride", width=720, height=900,
            deviceScaleFactor=2, mobile=False)
    ch.send("Page.navigate", url="http://127.0.0.1:%d/exoplanets/" % port)

    for _ in range(60):
        ok = ch.js("!!document.querySelector('#exo-chart svg circle')")
        if ok: break
        time.sleep(0.5)
    if not ok: raise RuntimeError("chart never appeared")
    time.sleep(1.5)

    # Loosen the slider so fractional light-year values are allowed, and
    # find the svg box to crop to.
    box = ch.js("""(function(){
        var sl = document.getElementById('exo-ymax');
        sl.step = 1;
        var svg = document.querySelector('#exo-chart svg');
        svg.scrollIntoView({block:'center'});
        var r = svg.getBoundingClientRect();
        return [r.x, r.y, r.width, r.height];})()""")
    time.sleep(0.5)
    box = ch.js("""(function(){
        var r = document.querySelector('#exo-chart svg').getBoundingClientRect();
        return [r.x, r.y, r.width, r.height];})()""")
    x, y, w, h = box
    W = int(w) - int(w) % 2
    H = int(h) - int(h) % 2
    print("svg box:", box, "->", W, "x", H)

    setf = """(function(t){
        var e = t*t*(3-2*t);
        var v = Math.round(%d * Math.pow(%f, e));
        var sl = document.getElementById('exo-ymax');
        sl.value = v;
        sl.dispatchEvent(new Event('input'));
        return sl.value;})(%%f)""" % (Y_HI, Y_LO / Y_HI)

    n = int(SECONDS * FPS)
    ch.js(setf % 0.0); time.sleep(0.5)
    for i in range(n):
        ch.js(setf % (i / (n - 1)))
        time.sleep(0.03)
        shot = ch.shot()
        crop = shot.crop((int(x*2), int(y*2), int((x+w)*2), int((y+h)*2)))
        frames.append(crop.resize((2 * W, 2 * H), Image.LANCZOS))
finally:
    ch.close(); httpd.shutdown()

frames = frames + frames[-2:0:-1]  # bounce
tmp = tempfile.mkdtemp(prefix="exo-")
for i, f in enumerate(frames):
    f.save(os.path.join(tmp, "f%05d.png" % i))
os.chdir("..")
subprocess.run(["scripts/png2mp4", tmp, "public/videos/exoplanets.mp4",
                str(FPS), "0.07"], check=True)
shutil.rmtree(tmp, ignore_errors=True)
frames[0].save(os.path.join(S, "exoz_first.png"))
frames[len(frames)//2].save(os.path.join(S, "exoz_mid.png"))
print("frames:", len(frames), "size:", W, H)
