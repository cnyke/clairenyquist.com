"""Extract a dominant color from each audiobook's cover image.

Reads cover URLs from the library CSV, downloads a small (160px) copy of
each, and quantizes it to find a representative spine color — scored to
prefer saturated mid-tones over white/black backgrounds. Also saves a
teeny (96px) thumbnail per cover for the shelf tooltips. Run from the
repo root. Outputs:
  public/data/audible-cover-colors.json
    { ASIN: {"color": "#rrggbb", "dark": true} }   # dark => use light text
  public/images/covers/<ASIN>.webp
"""
import colorsys, csv, io, json, os, subprocess, time
from PIL import Image

CSV = 'public/data/AudibleLibraryCombined.csv'
OUT = 'public/data/audible-cover-colors.json'
THUMBS = 'public/images/covers'
os.makedirs(THUMBS, exist_ok=True)

rows = list(csv.DictReader(open(CSV)))
covers = {}
for r in rows:
    asin = (r.get('ASIN') or '').strip()
    url = (r.get('Cover') or '').strip()
    if asin and url.startswith('http') and asin not in covers:
        # Amazon image CDN serves any size; 160px is plenty for a dominant color.
        covers[asin] = url.replace('_SL500_', '_SL160_')

def dominant_color(im):
    im = im.resize((64, 64))
    pal = im.quantize(colors=8, method=Image.Quantize.MEDIANCUT).convert('RGB')
    best, best_score = None, -1
    for count, (r, g, b) in pal.getcolors(64 * 64):
        h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
        # Weight by how much of the cover it is, but favor saturated mid-tones
        # so white pages / black gutters don't win.
        score = count * (s + 0.15) * (1 - abs(l - 0.5) * 1.4)
        if score > best_score:
            best, best_score = (r, g, b), score
    return best

def luminance(rgb):
    r, g, b = [c / 255 for c in rgb]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

result, misses = {}, []
for i, (asin, url) in enumerate(covers.items(), 1):
    proc = subprocess.run(['curl', '-s', '--max-time', '15', url],
                          capture_output=True, timeout=20)
    try:
        im = Image.open(io.BytesIO(proc.stdout)).convert('RGB')
        rgb = dominant_color(im)
        thumb = im.copy()
        thumb.thumbnail((96, 96))
        thumb.save(f'{THUMBS}/{asin}.webp', 'WEBP', quality=75)
    except Exception:
        rgb = None
    if rgb:
        result[asin] = {'color': '#%02x%02x%02x' % rgb, 'dark': luminance(rgb) < 0.55}
    else:
        misses.append(asin)
    if i % 50 == 0:
        print(f'{i}/{len(covers)}')
    time.sleep(0.1)

json.dump(result, open(OUT, 'w'), indent=1)
print(f'done: {len(result)}/{len(covers)} covers -> {OUT}')
if misses:
    print('missed:', misses)
