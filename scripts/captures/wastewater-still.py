"""Static wastewater card: the COVID map at the latest week, retina card width."""
import sys, os, time, threading, functools, socket, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gifify import Chrome
from http.server import HTTPServer, SimpleHTTPRequestHandler
from PIL import Image

S = tempfile.gettempdir()

os.chdir("dist")
s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
httpd = HTTPServer(("127.0.0.1", port), functools.partial(SimpleHTTPRequestHandler))
threading.Thread(target=httpd.serve_forever, daemon=True).start()

ch = Chrome(os.path.join(S, ".wwstill"))
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
    ch.js("""(function(){
        var sl = document.getElementById('week-slider');
        sl.value = sl.max;
        sl.dispatchEvent(new Event('input'));})()""")
    time.sleep(0.3)
    shot = ch.shot()
    crop = shot.crop((int(x*2), int(y*2), int((x+w)*2), int((y+h)*2)))
finally:
    ch.close(); httpd.shutdown()

os.chdir("..")
crop.resize((1200, round(1200 * h / w)), Image.LANCZOS).save(
    "public/images/gifs/wastewater-still.webp", quality=85)
print("still:", crop.size)
