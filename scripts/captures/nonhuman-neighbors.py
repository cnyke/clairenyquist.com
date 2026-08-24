"""Capture a smooth scripted zoom of the live nonhuman-neighbors map."""
import sys, os, time, threading, functools, socket, subprocess, tempfile, shutil
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
from gifify import Chrome
from http.server import HTTPServer, SimpleHTTPRequestHandler
from PIL import Image

S = tempfile.gettempdir()
W, H = 538, 720
FPS = 30
SECONDS = 4.5
ZOOM_IN = 3.4           # zoom levels to travel
ANCHOR = (0.22, 0.50)   # screen point (frac of w,h) to zoom toward

os.chdir("dist")
s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
httpd = HTTPServer(("127.0.0.1", port), functools.partial(SimpleHTTPRequestHandler))
threading.Thread(target=httpd.serve_forever, daemon=True).start()

ch = Chrome(os.path.join(S, ".nncap"))
frames = []
try:
    ch.send("Page.enable"); ch.send("Runtime.enable")
    # Steal the Leaflet map instance the page creates.
    ch.send("Page.addScriptToEvaluateOnNewDocument", source="""
        (function(){
            var val;
            Object.defineProperty(window, 'L', {
                configurable: true,
                get: function(){ return val; },
                set: function(v){
                    val = v;
                    if (v && v.map && !v.__wrapped) {
                        var orig = v.map;
                        v.map = function(){
                            var m = orig.apply(v, arguments);
                            window.__map = m; return m;
                        };
                        v.__wrapped = true;
                    }
                }
            });
        })();
    """)
    ch.send("Emulation.setDeviceMetricsOverride", width=W, height=H,
            deviceScaleFactor=2, mobile=False)
    ch.send("Page.navigate", url="http://127.0.0.1:%d/nonhuman-neighbors/" % port)

    for _ in range(120):
        ok = ch.js("!!(window.__map && document.querySelectorAll('#map img').length > 10)")
        if ok: break
        time.sleep(0.5)
    if not ok: raise RuntimeError("map never appeared")
    time.sleep(2)

    # Map fills the viewport; chrome-less.
    ch.js("""(function(){
        var el = document.getElementById('map');
        document.body.appendChild(el);
        ['position:fixed','inset:0','width:100vw','height:100vh','z-index:9999']
            .forEach(function(d){ var kv = d.split(':');
                el.style.setProperty(kv[0], kv[1], 'important'); });
        var st = document.createElement('style');
        st.textContent = '.leaflet-control-container{display:none!important}';
        document.head.appendChild(st);
        Array.prototype.forEach.call(document.body.children, function(sib){
            if (sib !== el) sib.style.display = 'none';
        });
        window.__map.invalidateSize();
        return 1;})()""")
    time.sleep(1.5)

    # Plan the move: ease zoom toward the latlng under the anchor point.
    ch.js("""(function(){
        var m = window.__map;
        window.__z0 = m.getZoom();
        window.__c0 = m.getCenter();
        window.__t  = m.containerPointToLatLng([%f * %d, %f * %d]);
        return 1;})()""" % (ANCHOR[0], W, ANCHOR[1], H))

    n = int(SECONDS * FPS)
    setf = """(function(t){
        var m = window.__map, e = t*t*(3-2*t);
        var z = window.__z0 + %f * e;
        var lat = window.__c0.lat + (window.__t.lat - window.__c0.lat) * e;
        var lng = window.__c0.lng + (window.__t.lng - window.__c0.lng) * e;
        m.setView([lat, lng], z, {animate:false});
        return 1;})(%%f)""" % ZOOM_IN

    # Warm pass so every tile and icon is cached before the real capture.
    for i in range(0, n, 5):
        ch.js(setf % (i / (n - 1)))
        time.sleep(0.08)
    ch.js(setf % 0.0)
    time.sleep(1.0)

    for i in range(n):
        ch.js(setf % (i / (n - 1)))
        time.sleep(0.05)
        frames.append(ch.shot())  # native 2x pixels
finally:
    ch.close(); httpd.shutdown()

frames = frames + frames[-2:0:-1]  # bounce
tmp = tempfile.mkdtemp(prefix="nn-")
for i, f in enumerate(frames):
    f.save(os.path.join(tmp, "f%05d.png" % i))
os.chdir("..")
subprocess.run(["scripts/png2mp4", tmp, "public/videos/nonhuman-neighbors.mp4",
                str(FPS), "0.07"], check=True)
shutil.rmtree(tmp, ignore_errors=True)
frames[0].save(os.path.join(S, "nnz_first.png"))
frames[len(frames)//2].save(os.path.join(S, "nnz_mid.png"))
print("frames:", len(frames))
