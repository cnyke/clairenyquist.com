"""Scripted Minneapolis Trees video: a smooth zoom out from downtown to the whole
city, colored by genus, then back (bounce baked in).

    python3 scripts/captures/minneapolis-trees.py            # homepage card, 900x1080 css @2x
    python3 scripts/captures/minneapolis-trees.py --reel     # Instagram Reel, 540x960 css @2x = 1080x1920
    python3 scripts/captures/minneapolis-trees.py --check    # one panel screenshot of the page, no video

Run from the repo root after `npm run build`.
"""
import sys, os, time, threading, functools, socket, subprocess, tempfile, shutil, argparse
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import gifify, json, subprocess as sp
from gifify import Chrome
from http.server import HTTPServer, SimpleHTTPRequestHandler

ap = argparse.ArgumentParser()
ap.add_argument("--reel", action="store_true")
ap.add_argument("--check", action="store_true")
ap.add_argument("--seconds", type=float, default=6.0)
args = ap.parse_args()


class GLChrome(Chrome):
    def __init__(self, profile):
        import shutil as sh, websocket, urllib.request
        s = socket.socket(); s.bind(("127.0.0.1", 0)); self.port = s.getsockname()[1]; s.close()
        self.profile = profile
        sh.rmtree(profile, ignore_errors=True)
        self.proc = sp.Popen(
            [gifify.CHROME, "--headless", "--hide-scrollbars", "--mute-audio",
             "--no-sandbox", "--force-device-scale-factor=1",
             "--force-color-profile=srgb",
             "--enable-unsafe-swiftshader", "--use-angle=swiftshader",
             "--user-data-dir=" + profile,
             "--remote-debugging-port=%d" % self.port, "about:blank"],
            stdout=sp.DEVNULL, stderr=sp.DEVNULL)
        self.ws, self.msg_id = None, 0
        for _ in range(100):
            try:
                raw = urllib.request.urlopen("http://127.0.0.1:%d/json/list" % self.port, timeout=2).read()
                pages = [t for t in json.loads(raw) if t.get("type") == "page"]
                if pages:
                    self.ws = websocket.create_connection(pages[0]["webSocketDebuggerUrl"], timeout=120, suppress_origin=True)
                    break
            except Exception: pass
            time.sleep(0.25)
        if not self.ws: raise RuntimeError("no chrome")


S = tempfile.gettempdir()
if args.reel:
    W, H, SLUG = 540, 960, "minneapolis-trees-reel"
    Z0, Z1 = 15.2, 12.15
else:
    W, H, SLUG = 900, 1080, "minneapolis-trees"
    Z0, Z1 = 15.2, 12.4
C0 = (44.9765, -93.2705)   # downtown, the page's opening view
C1 = (44.9700, -93.2650)   # whole city centered
FPS = 30
SECONDS = args.seconds

os.chdir("dist")
s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
httpd = HTTPServer(("127.0.0.1", port), functools.partial(SimpleHTTPRequestHandler))
threading.Thread(target=httpd.serve_forever, daemon=True).start()

ch = GLChrome(os.path.join(S, ".treecap"))
frames = []
try:
    ch.send("Page.enable"); ch.send("Runtime.enable")
    # Catch the Leaflet map instance the page creates inside its closure.
    ch.send("Page.addScriptToEvaluateOnNewDocument", source="""
        (function(){
            var real;
            Object.defineProperty(window, 'L', {
                configurable: true,
                get: function(){ return real; },
                set: function(v){
                    real = v;
                    if (v && v.map && !v.__hooked) {
                        var orig = v.map;
                        v.map = function(){ var m = orig.apply(this, arguments); window.__map = m; return m; };
                        v.__hooked = true;
                    }
                }
            });
        })();""")
    if args.check:
        ch.send("Emulation.setDeviceMetricsOverride", width=1280, height=900, deviceScaleFactor=1, mobile=False)
    else:
        ch.send("Emulation.setDeviceMetricsOverride", width=W, height=H, deviceScaleFactor=2, mobile=False)
    ch.send("Page.navigate", url="http://127.0.0.1:%d/minneapolis-trees/" % port)

    for _ in range(240):
        ok = ch.js("(function(){ return !!window.__map && !document.getElementById('tree-loading'); })()")
        if ok: break
        time.sleep(0.5)
    if not ok: raise RuntimeError("trees never finished loading")
    time.sleep(3)

    if args.check:
        ch.js("document.getElementById('tree-app').scrollIntoView(); 1")
        time.sleep(1)
        ch.shot().save(os.path.join(S, "trees_panel_check.png"))
        # switch color-by to planting year and shoot again
        ch.js("document.querySelector('.tp-color[data-dim=year]').click(); 1")
        time.sleep(1.5)
        ch.shot().save(os.path.join(S, "trees_panel_check_year.png"))
        print("check shots in", S); sys.exit(0)

    # Map only: fill the viewport with #map, hide the panel and controls.
    ch.js("""(function(){
        var st = document.createElement('style');
        st.textContent = 'body>*{display:none !important} #tree-mapwrap{display:block !important;position:fixed !important;inset:0 !important;z-index:99999}'
          + ' #map{width:100vw !important;height:100vh !important} .leaflet-control-container{display:none !important}'
          + ' #tree-tip{display:none !important}';
        document.head.appendChild(st);
        var wrap = document.getElementById('tree-mapwrap');
        document.body.appendChild(wrap);
        window.__map.invalidateSize(false);
        return 1;})()""")
    time.sleep(1)

    # Hook to the basemap so we can wait for tiles each frame.
    ch.js("""window.__ml = (function(){
        var m = window.__map, out = null;
        Object.keys(m._layers).forEach(function(k){ var l = m._layers[k]; if (l.getMaplibreMap) out = l.getMaplibreMap(); });
        return out; })(); 1""")

    def set_view(lat, lon, z):
        ch.js("window.__map.setView([%f,%f], %f, {animate:false}); 1" % (lat, lon, z))

    def wait_tiles(limit=3.0):
        t0 = time.time()
        while time.time() - t0 < limit:
            done = ch.js("(function(){ var m=window.__ml; if(!m) return true; return m.areTilesLoaded() && m.loaded(); })()")
            if done: return
            time.sleep(0.05)

    set_view(*C0, Z0); time.sleep(2); wait_tiles(10)

    n = int(SECONDS * FPS)
    for i in range(n):
        t = i / (n - 1)
        e = t * t * (3 - 2 * t)
        lat = C0[0] + (C1[0] - C0[0]) * e
        lon = C0[1] + (C1[1] - C0[1]) * e
        z = Z0 + (Z1 - Z0) * e
        set_view(lat, lon, z)
        wait_tiles()
        time.sleep(0.05)
        frames.append(ch.shot())
        if i % 30 == 0: print("frame", i, "of", n, flush=True)
finally:
    ch.close(); httpd.shutdown()

frames = frames + frames[-2:0:-1]  # bounce
tmp = tempfile.mkdtemp(prefix="trees-")
for i, f in enumerate(frames):
    f.save(os.path.join(tmp, "f%05d.png" % i))
os.chdir("..")
out = ("media/%s.mp4" % SLUG) if args.reel else ("public/videos/%s.mp4" % SLUG)
os.makedirs(os.path.dirname(out), exist_ok=True)
subprocess.run(["scripts/png2mp4", tmp, out, str(FPS), "0.07"], check=True)
shutil.rmtree(tmp, ignore_errors=True)
frames[0].save(os.path.join(S, "trees_first.png"))
frames[len(frames)//2].save(os.path.join(S, "trees_mid.png"))
print("frames:", len(frames), "->", out, frames[0].size)
