"""Scripted Minnesota mosses video: smooth orbit of the 3D map via pointer drag."""
import sys, os, time, threading, functools, socket, subprocess, tempfile, shutil
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import gifify, json, subprocess as sp
from gifify import Chrome
from http.server import HTTPServer, SimpleHTTPRequestHandler
from PIL import Image

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
                    self.ws = websocket.create_connection(pages[0]["webSocketDebuggerUrl"], timeout=60, suppress_origin=True)
                    break
            except Exception: pass
            time.sleep(0.25)
        if not self.ws: raise RuntimeError("no chrome")

S = tempfile.gettempdir()
W, H = 656, 720
FPS = 30
SECONDS = 6.0

os.chdir("dist")
s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
httpd = HTTPServer(("127.0.0.1", port), functools.partial(SimpleHTTPRequestHandler))
threading.Thread(target=httpd.serve_forever, daemon=True).start()

ch = GLChrome(os.path.join(S, ".mosscap"))
frames = []
try:
    ch.send("Page.enable"); ch.send("Runtime.enable")
    ch.send("Emulation.setDeviceMetricsOverride", width=W, height=H,
            deviceScaleFactor=2, mobile=False)
    ch.send("Page.navigate", url="http://127.0.0.1:%d/minnesota-bryophytes/" % port)

    for _ in range(240):
        ok = ch.js("""(function(){
            var c = document.querySelector('#canvas-container canvas');
            if (!c) return false;
            var spin = document.querySelector('.animate-spin');
            return !spin || !spin.offsetParent;})()""")
        if ok: break
        time.sleep(0.5)
    if not ok: raise RuntimeError("scene never finished loading")
    time.sleep(4)

    # Hide everything except the canvas.
    ch.js("""(function(){
        var cc = document.getElementById('canvas-container');
        Array.prototype.forEach.call(document.body.children, function(sib){
            if (sib !== cc && !sib.contains(cc)) sib.style.display = 'none';
        });
        var node = cc;
        while (node && node.parentElement && node !== document.body) {
            Array.prototype.forEach.call(node.parentElement.children, function(sib){
                if (sib !== node) sib.style.display = 'none';
            });
            node = node.parentElement;
        }
        return 1;})()""")
    time.sleep(0.5)

    # Zoom in a touch so the map fills the frame.
    ch.js('''(function(){
        var c = document.querySelector('#canvas-container canvas');
        for (var i = 0; i < 3; i++)
            c.dispatchEvent(new WheelEvent('wheel',
                {deltaY: -120, clientX: ''' + str(W//2) + ''', clientY: '''
            + str(H//2) + ''', bubbles: true, cancelable: true}));
        return 1;})()''')
    time.sleep(1.5)

    # Drag helper: dispatch pointer events on the canvas.
    ch.js("""window.__drag = (function(){
        var c = document.querySelector('#canvas-container canvas');
        function ev(type, x, y){
            c.dispatchEvent(new PointerEvent(type, {
                pointerId: 1, pointerType: 'mouse', isPrimary: true,
                clientX: x, clientY: y, button: 0, buttons: type==='pointerup'?0:1,
                bubbles: true}));
        }
        return ev;})();""")

    n = int(SECONDS * FPS)
    x0, y0 = W * 0.75, H * 0.50
    x1, y1 = W * 0.29, H * 0.50
    ch.js("window.__drag('pointerdown', %f, %f); 1" % (x0, y0))
    for i in range(n):
        t = i / (n - 1)
        e = t * t * (3 - 2 * t)
        x = x0 + (x1 - x0) * e
        y = y0 + (y1 - y0) * e
        ch.js("window.__drag('pointermove', %f, %f); 1" % (x, y))
        time.sleep(0.08)
        frames.append(ch.shot())  # native 2x pixels
    ch.js("window.__drag('pointerup', %f, %f); 1" % (x1, y1))
finally:
    ch.close(); httpd.shutdown()

frames = frames + frames[-2:0:-1]  # bounce
tmp = tempfile.mkdtemp(prefix="moss-")
for i, f in enumerate(frames):
    f.save(os.path.join(tmp, "f%05d.png" % i))
os.chdir("..")
subprocess.run(["scripts/png2mp4", tmp, "public/videos/minnesota-bryophytes.mp4",
                str(FPS), "0.07"], check=True)
shutil.rmtree(tmp, ignore_errors=True)
frames[0].save(os.path.join(S, "mossz_first.png"))
frames[len(frames)//2].save(os.path.join(S, "mossz_mid.png"))
print("frames:", len(frames))
