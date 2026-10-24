#!/usr/bin/env python3
"""
Prepare Minnesota Wastewater Map Data

Reads the CSVs downloaded from the MDH wastewater dashboard
(https://www.health.state.mn.us/diseases/wastewater/stats/index.html):
  wwsite.csv   weekly PMMoV-normalized concentration per plant and pathogen
  wwregion.csv population-weighted regional and statewide values

Usage: python3 scripts/prepare_wastewater.py "<folder with the MDH CSVs>"

Outputs: public/data/mdh_wastewater.json
"""

import csv
import json
import os
import sys
from datetime import datetime

OUTPUT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "public", "data", "mdh_wastewater.json"
)

PATHOGENS = ["SARS-CoV-2", "Influenza A", "Influenza B", "RSV"]

# MDH publishes county but not location; these are the plants' approximate
# coordinates (city or plant site), good enough at statewide map scale.
PLANTS = {
    "Albert Lea WWTP": ("Albert Lea", 43.656, -93.352),
    "Alexandria WWTP": ("Alexandria (ALASD)", 45.858, -95.398),
    "Blue Lake WWTP": ("Shakopee", 44.795, -93.470),
    "Buffalo WWTP": ("Buffalo", 45.176, -93.858),
    "Chisholm (CIRSSD) WWTP": ("Chisholm", 47.483, -92.878),
    "Duluth (WLSSD) WWTP": ("Duluth", 46.760, -92.130),
    "Eagles Point WWTP": ("Cottage Grove", 44.807, -92.946),
    "East Bethel WWTP": ("East Bethel", 45.319, -93.203),
    "Elk River WWTP": ("Elk River", 45.304, -93.567),
    "Empire WWTP": ("Empire Township", 44.660, -93.105),
    "Fergus Falls WWTP": ("Fergus Falls", 46.283, -96.077),
    "Glacial Lakes WWTP": ("Spicer–New London", 45.233, -94.940),
    "Grand Rapids WWTP": ("Grand Rapids", 47.237, -93.530),
    "Hastings WWTP": ("Hastings", 44.744, -92.852),
    "Lafayette WWTP": ("Lafayette", 44.447, -94.395),
    "Le Sueur WWTP": ("Le Sueur", 44.461, -93.915),
    "Little Falls WWTP": ("Little Falls", 45.976, -94.362),
    "Mankato WWTP": ("Mankato", 44.164, -94.000),
    "Marshall WWTP": ("Marshall", 44.447, -95.788),
    "Metro WWTP": ("St. Paul", 44.928, -93.040),
    "Mora WWTP": ("Mora", 45.877, -93.294),
    "Northfield WWTP": ("Northfield", 44.458, -93.161),
    "Red Wing WWTP": ("Red Wing", 44.567, -92.534),
    "Rochester WWTP": ("Rochester", 43.990, -92.462),
    "Rogers WWTP": ("Rogers", 45.189, -93.553),
    "Seneca WWTP": ("Eagan", 44.832, -93.171),
    "St. Cloud WWTP": ("St. Cloud", 45.531, -94.147),
    "St. Croix Valley WWTP": ("Oak Park Heights", 45.031, -92.790),
    "Willmar WWTP": ("Willmar", 45.122, -95.043),
    "Worthington WWTP": ("Worthington", 43.620, -95.596),
}


def read(folder, name):
    with open(os.path.join(folder, name), encoding="utf-8-sig") as f:
        # Skip MDH's footnote rows, which have no date
        return [r for r in csv.DictReader(f) if r["Week Beginning"]]


def iso(d):
    return datetime.strptime(d, "%m/%d/%Y").date().isoformat()


def num(v):
    return round(float(v), 3) if v not in ("", None) else None


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    folder = sys.argv[1]
    site_rows = read(folder, "wwsite.csv")
    region_rows = read(folder, "wwregion.csv")

    weeks = sorted({iso(r["Week Beginning"]) for r in site_rows})
    index = {w: i for i, w in enumerate(weeks)}

    plants = {}
    values = {p: {} for p in PATHOGENS}
    unmapped = set()
    for r in site_rows:
        name = r["Wastewater Treatment Plant"].rstrip("*").strip()
        if name not in PLANTS:
            unmapped.add(name)
            continue
        if name not in plants:
            city, lat, lon = PLANTS[name]
            plants[name] = {
                "name": name, "city": city, "region": r["Region"],
                "population": int(r["Population Served"] or 0),
                "lat": lat, "lon": lon,
            }
        series = values[r["Pathogen"]].setdefault(name, [None] * len(weeks))
        series[index[iso(r["Week Beginning"])]] = num(r["Average Normalized Concentration"])

    missing = set(PLANTS) - set(plants)
    if missing:
        print("Warning: plants with coordinates but no data:", sorted(missing))
    # Rows like "Northeast" and "Statewide Weighted" are aggregates, not plants
    print("Skipped non-plant rows:", sorted(unmapped))

    statewide = {p: [None] * len(weeks) for p in PATHOGENS}
    for r in region_rows:
        w = iso(r["Week Beginning"])
        if r["Region"] == "Statewide" and w in index:
            statewide[r["Pathogen"]][index[w]] = num(r["Weighted Average Normalized Value"])

    out = {
        "updated": datetime.fromtimestamp(
            os.path.getmtime(os.path.join(folder, "wwsite.csv"))).date().isoformat(),
        "weeks": weeks,
        "pathogens": PATHOGENS,
        "plants": sorted(plants.values(), key=lambda p: -p["population"]),
        "values": values,
        "statewide": statewide,
    }
    with open(OUTPUT_PATH, "w") as f:
        json.dump(out, f, separators=(",", ":"))
    print(f"Wrote {OUTPUT_PATH}: {len(plants)} plants, {len(weeks)} weeks "
          f"({weeks[0]} to {weeks[-1]}), {os.path.getsize(OUTPUT_PATH) // 1024} KB")


if __name__ == "__main__":
    main()
