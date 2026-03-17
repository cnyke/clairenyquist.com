#!/usr/bin/env python3
"""
Met Museum Color Extraction Pipeline

Uses the Met API to find public-domain objects with images,
fetches metadata + images, extracts dominant colors, and exports CSV.

No CSV download needed — everything comes from the API.

Usage:
    python3 scripts/met_color_extract.py [--sample-size 1000] [--keep-thumbnails] [--reset]

Dependencies:
    pip install colorgram.py requests Pillow
"""

import argparse
import colorsys
import csv
import io
import json
import random
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import colorgram
import requests
from PIL import Image

# --- Configuration ---
MET_API_BASE = "https://collectionapi.metmuseum.org/public/collection/v1"
SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "met_progress.db"
THUMB_DIR = SCRIPT_DIR / "thumbnails"
OUTPUT_DIR = Path(__file__).parent.parent / "public" / "data"
OUTPUT_CSV = OUTPUT_DIR / "met_colors.csv"

API_WORKERS = 3


def init_db(db_path):
    """Initialize SQLite database for checkpointing."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sampled_objects (
            objectID INTEGER PRIMARY KEY,
            department TEXT,
            culture TEXT,
            medium TEXT,
            objectName TEXT,
            objectBeginDate INTEGER,
            imageUrl TEXT,
            hex TEXT,
            hue REAL,
            status TEXT DEFAULT 'pending'
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON sampled_objects(status)")
    conn.commit()
    return conn


def fetch_image_ids():
    """Get all public-domain object IDs with images from the search API."""
    print("  Querying Met API for public-domain objects with images...")
    print("  (Large response — may take a minute...)")
    search_url = f"{MET_API_BASE}/search"

    for attempt in range(5):
        try:
            resp = requests.get(search_url, params={
                "isPublicDomain": "true",
                "hasImages": "true",
                "q": "*",
            }, timeout=300, stream=True)
            resp.raise_for_status()
            raw = b""
            for chunk in resp.iter_content(chunk_size=256 * 1024):
                raw += chunk
            data = json.loads(raw)
            ids = data.get("objectIDs", []) or []
            print(f"  API returned {len(ids)} object IDs with images")
            return ids
        except (requests.exceptions.ChunkedEncodingError,
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as e:
            print(f"  Attempt {attempt + 1} failed: {e.__class__.__name__}")
            if attempt < 4:
                wait = 10 * (attempt + 1)
                print(f"  Retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise RuntimeError("Could not fetch IDs from Met API after 5 attempts") from e


def stage1_sample(conn, sample_size):
    """Sample object IDs from the API results."""
    existing = conn.execute("SELECT COUNT(*) FROM sampled_objects").fetchone()[0]
    if existing >= sample_size:
        print(f"  Already have {existing} sampled objects in DB, skipping")
        return

    all_ids = fetch_image_ids()

    # Oversample 5x — API search index is stale, ~30% of IDs lack images
    oversample = min(len(all_ids), sample_size * 5)
    random.seed(42)
    sampled_ids = random.sample(all_ids, oversample)
    print(f"  Sampled {oversample} IDs (5x oversample, ~70% success rate expected)")

    for oid in sampled_ids:
        conn.execute(
            "INSERT OR IGNORE INTO sampled_objects (objectID, status) VALUES (?, 'pending')",
            (oid,),
        )
    conn.commit()
    print(f"  Inserted {oversample} object IDs into checkpoint DB")


def fetch_object_and_color(object_id, session, keep_thumbs):
    """Fetch metadata + image from API, extract color — all in one step."""
    try:
        # Fetch object metadata (retry once on 404 — API is sometimes flaky)
        resp = session.get(f"{MET_API_BASE}/objects/{object_id}", timeout=15)
        if resp.status_code == 404:
            time.sleep(0.5)
            resp = session.get(f"{MET_API_BASE}/objects/{object_id}", timeout=15)
        if resp.status_code != 200:
            return object_id, None

        data = resp.json()
        img_url = data.get("primaryImageSmall") or data.get("primaryImage") or ""
        if not img_url:
            return object_id, None

        # Download image
        img_resp = session.get(img_url, timeout=20)
        if img_resp.status_code != 200:
            return object_id, None

        img = Image.open(io.BytesIO(img_resp.content)).convert("RGB")

        if keep_thumbs:
            THUMB_DIR.mkdir(exist_ok=True)
            img.save(THUMB_DIR / f"{object_id}.jpg", "JPEG", quality=60)

        # Extract dominant color (most saturated of top 6)
        colors = colorgram.extract(img, 6)
        if not colors:
            return object_id, None

        best = None
        best_sat = -1
        for c in colors:
            r, g, b = c.rgb
            h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
            if s > best_sat:
                best_sat = s
                best = (r, g, b, h)

        if best is None or (best_sat < 0.05 and colors):
            r, g, b = colors[0].rgb
            h, _, _ = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
        else:
            r, g, b, h = best

        hex_color = f"#{r:02x}{g:02x}{b:02x}"
        hue = round(h * 360, 1)

        # Parse date
        begin_date = data.get("objectBeginDate")
        try:
            begin_date = int(begin_date)
        except (TypeError, ValueError):
            begin_date = 0

        return object_id, {
            "department": (data.get("department") or "")[:100],
            "culture": (data.get("culture") or "")[:100],
            "medium": (data.get("medium") or "")[:200],
            "objectName": (data.get("objectName") or data.get("title") or "")[:100],
            "objectBeginDate": begin_date,
            "imageUrl": img_url,
            "hex": hex_color,
            "hue": hue,
        }
    except Exception as e:
        print(f"\n  ERROR {object_id}: {type(e).__name__}: {e}", flush=True)
        return object_id, None


def stage2_fetch_and_extract(conn, sample_size, keep_thumbnails):
    """Fetch metadata, images, and extract colors in one pass."""
    # Count how many are already done
    done_count = conn.execute("SELECT COUNT(*) FROM sampled_objects WHERE status = 'done'").fetchone()[0]
    if done_count >= sample_size:
        print(f"  Already have {done_count} completed objects, skipping")
        return

    pending = conn.execute(
        "SELECT objectID FROM sampled_objects WHERE status = 'pending'"
    ).fetchall()
    if not pending:
        print("  No pending objects")
        return

    # Shuffle so we don't get stuck on long runs of imageless objects
    random.shuffle(pending)

    need = sample_size - done_count
    print(f"  Need {need} more objects ({done_count} already done, {len(pending)} pending)")
    print(f"  Fetching metadata + images + extracting colors...")

    session = requests.Session()
    session.headers.update({"User-Agent": "MetColorViz/1.0 (educational project)"})

    done = 0
    successes = done_count
    total = len(pending)
    batch_size = 10

    for i in range(0, total, batch_size):
        if successes >= sample_size:
            print(f"\n  Reached target of {sample_size} objects!")
            break

        batch = pending[i : i + batch_size]
        with ThreadPoolExecutor(max_workers=API_WORKERS) as executor:
            futures = {}
            for (oid,) in batch:
                futures[executor.submit(fetch_object_and_color, oid, session, keep_thumbnails)] = oid

            for future in as_completed(futures):
                oid, result = future.result()
                if result:
                    conn.execute(
                        """UPDATE sampled_objects SET
                           department=?, culture=?, medium=?, objectName=?,
                           objectBeginDate=?, imageUrl=?, hex=?, hue=?, status='done'
                           WHERE objectID=?""",
                        (result["department"], result["culture"], result["medium"],
                         result["objectName"], result["objectBeginDate"],
                         result["imageUrl"], result["hex"], result["hue"], oid),
                    )
                    successes += 1
                else:
                    conn.execute(
                        "UPDATE sampled_objects SET status = 'failed' WHERE objectID = ?",
                        (oid,),
                    )
                done += 1

        conn.commit()
        failed = done - (successes - done_count)
        print(f"\r  {done}/{total} processed — {successes} successes, {failed} failed", end="", flush=True)
        time.sleep(1)  # rate limit: pause 1s between batches

    print(f"\n  Complete: {successes} objects with colors")


def stage3_export(conn):
    """Export final CSV."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    rows = conn.execute(
        """SELECT objectID, hex, hue, objectBeginDate, culture, department, medium, objectName, imageUrl
           FROM sampled_objects WHERE status = 'done'
           ORDER BY objectBeginDate"""
    ).fetchall()

    if not rows:
        print("  No completed objects to export!")
        return

    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["objectID", "hex", "hue", "objectBeginDate", "culture", "department", "medium", "objectName", "imageUrl"])
        writer.writerows(rows)

    print(f"  Exported {len(rows)} objects to {OUTPUT_CSV}")
    print(f"  File size: {OUTPUT_CSV.stat().st_size / 1024:.0f}KB")


def main():
    parser = argparse.ArgumentParser(description="Met Museum Color Extraction Pipeline")
    parser.add_argument("--sample-size", type=int, default=1000, help="Number of objects to sample (default: 1000)")
    parser.add_argument("--keep-thumbnails", action="store_true", help="Keep downloaded thumbnail images")
    parser.add_argument("--reset", action="store_true", help="Reset progress database and start fresh")
    args = parser.parse_args()

    if args.reset and DB_PATH.exists():
        DB_PATH.unlink()
        print("Reset: deleted progress database")

    conn = init_db(DB_PATH)

    print("\n=== Stage 1: Sample Object IDs ===")
    stage1_sample(conn, args.sample_size)

    print("\n=== Stage 2: Fetch Metadata + Extract Colors ===")
    stage2_fetch_and_extract(conn, args.sample_size, args.keep_thumbnails)

    print("\n=== Stage 3: Export CSV ===")
    stage3_export(conn)

    conn.close()
    print("\nDone!")


if __name__ == "__main__":
    main()
