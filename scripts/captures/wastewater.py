"""Scripted wastewater video: the COVID map stepping through every week."""
import sys, os, time, threading, functools, socket, subprocess, tempfile, shutil
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gifify import Chrome
from http.server import HTTPServer, SimpleHTTPRequestHandler
from PIL import Image

S = tempfile.gettempdir()
FPS = 30
HOLD = 4      # frames per week
END_HOLD = 30 # linger on the latest week before the loop restarts

os.chdir("dist")
s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
httpd = HTTPServer(("127.0.0.1", port), functools.partial(SimpleHTTPRequestHandler))
threading.Thread(target=httpd.serve_forever, daemon=True).start()

ch = Chrome(os.path.join(S, ".wwcap"))
frames = []
try:
    ch.send("Page.enable"); ch.send("Runtime.enable")
    ch.send("Emulation.setDeviceMetricsOverride", width=720, height=1100,
            deviceScaleFactor=2, mobile=False)
    ch.send("Page.navigate", url="http://127.0.0.1:%d/wastewater/" % port)

    for _ in range(60):
        ok = ch.js("!!document.querySelector('#state-map circle')")
        if ok: break
        time.sleep(0.5)
    if not ok: raise RuntimeError("map never appeared")
    time.sleep(1.0)

    ch.js("document.getElementById('state-map').scrollIntoView({block:'center'})")
    time.sleep(0.5)
    x, y, w, h = ch.js("""(function(){
        var r = document.getElementById('state-map').getBoundingClientRect();
        return [r.x, r.y, r.width, r.height];})()""")
    W = int(w) - int(w) % 2
    H = int(h) - int(h) % 2
    weeks = int(ch.js("+document.getElementById('week-slider').max")) + 1
    print("map box:", (x, y, w, h), "->", W, "x", H, "weeks:", weeks)

    setw = """(function(i){
        var sl = document.getElementById('week-slider');
        sl.value = i;
        sl.dispatchEvent(new Event('input'));
        return sl.value;})(%d)"""

    for i in range(weeks):
        ch.js(setw % i)
        time.sleep(0.05)
        shot = ch.shot()
        crop = shot.crop((int(x*2), int(y*2), int((x+w)*2), int((y+h)*2)))
        frame = crop.resize((2 * W, 2 * H), Image.LANCZOS)
        frames += [frame] * (END_HOLD if i == weeks - 1 else HOLD)
finally:
    ch.close(); httpd.shutdown()

tmp = tempfile.mkdtemp(prefix="ww-")
for i, f in enumerate(frames):
    f.save(os.path.join(tmp, "f%05d.png" % i))
os.chdir("..")
subprocess.run(["scripts/png2mp4", tmp, "public/videos/wastewater.mp4",
                str(FPS), "0.07"], check=True)
shutil.rmtree(tmp, ignore_errors=True)
# Card poster: the first frame, at retina card width
frames[0].resize((1200, round(1200 * H / W)), Image.LANCZOS).save(
    "public/images/gifs/wastewater-poster.webp", quality=85)
print("frames:", len(frames), "size:", W, H)
