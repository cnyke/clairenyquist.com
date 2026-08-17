"""Fetch Audible genre category ladders for every ASIN in the library CSV.

Uses the public (unauthenticated) catalog API. Tries audible.com first,
falls back to audible.co.uk for ASINs that 404 (UK-marketplace editions).
Also captures the audiobook edition's release year (product_attrs).
Output: audible-categories.json mapping
  ASIN -> {title, ladders: [[names...]], year: int|None}
"""
import csv, json, time, subprocess

CSV = 'public/data/AudibleLibraryCombined.csv'
OUT = 'public/data/audible-categories.json'
HOSTS = ['api.audible.com', 'api.audible.co.uk']

rows = list(csv.DictReader(open(CSV)))
asins = {}
for r in rows:
    a = (r.get('ASIN') or '').strip()
    if a and a not in asins:
        asins[a] = (r.get('Title Short') or r.get('Title') or '').strip()

def fetch(asin):
    for host in HOSTS:
        url = (f'https://{host}/1.0/catalog/products/{asin}'
               '?response_groups=category_ladders,product_attrs')
        try:
            out = subprocess.run(['curl', '-s', '--max-time', '15', url],
                                 capture_output=True, text=True, timeout=20).stdout
            product = json.loads(out).get('product', {})
            ladders = [[step['name'] for step in lad['ladder']]
                       for lad in product.get('category_ladders', [])]
            year = None
            date = product.get('release_date') or product.get('issue_date') or ''
            if len(date) >= 4 and date[:4].isdigit():
                year = int(date[:4])
            if ladders or year:
                return ladders, year
        except (json.JSONDecodeError, subprocess.TimeoutExpired):
            continue
    return [], None

result, misses = {}, []
for i, (asin, title) in enumerate(asins.items(), 1):
    ladders, year = fetch(asin)
    if ladders or year:
        result[asin] = {'title': title, 'ladders': ladders, 'year': year}
    else:
        misses.append((asin, title))
    if i % 50 == 0:
        print(f'{i}/{len(asins)} — {len(result)} with categories')
    time.sleep(0.15)

json.dump(result, open(OUT, 'w'), indent=1)
print(f'done: {len(result)}/{len(asins)} ASINs have category ladders')
if misses:
    print('no categories for:')
    for a, t in misses[:20]:
        print('  ', a, t)
