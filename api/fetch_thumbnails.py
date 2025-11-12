#!/usr/bin/env python3
"""Download thumbnails from `_wiki.thumbnail` in `api/data/cars.json`, convert to WebP 320px wide,
save under `api/media/` and update `thumbnail_local` and `thumbnail_source` fields in the JSON.

This script uses a configurable User-Agent (COUGAR_USER_AGENT env var) because Wikimedia
rejects automated requests without one.
"""
import os
import json
import requests
from pathlib import Path
from PIL import Image
from io import BytesIO

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data' / 'cars.json'
MEDIA_DIR = ROOT / 'media'
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

USER_AGENT = os.environ.get('COUGAR_USER_AGENT') or 'CougarThumbnailFetcher/1.0 (https://example.com)'

def fetch_image(url):
    headers = {'User-Agent': USER_AGENT, 'Accept': 'image/*,*/*;q=0.8'}
    try:
        r = requests.get(url, timeout=20, headers=headers)
        r.raise_for_status()
        return r.content
    except requests.exceptions.RequestException as e:
        print('  download error:', str(e))
        return None


def save_webp(content, out_path):
    try:
        im = Image.open(BytesIO(content)).convert('RGB')
        w = 320
        im.thumbnail((w, w * 2))
        im.save(out_path, 'WEBP', quality=80, method=6)
        return True
    except Exception as e:
        print('  conversion error:', str(e))
        return False


def main():
    if not DATA.exists():
        print('data file not found; run ingest first')
        return
    with open(DATA, 'r', encoding='utf-8') as f:
        items = json.load(f)

    changed = False
    for it in items:
        wiki = it.get('_wiki') or {}
        thumb = wiki.get('thumbnail')
        if not thumb:
            continue
        car_id = it.get('id') or (it.get('slug') or it.get('name')).replace(' ', '_')
        filename = f"{car_id}-thumb.webp"
        out_path = MEDIA_DIR / filename
        if out_path.exists():
            it['thumbnail_local'] = str(Path('api') / 'media' / filename)
            it['thumbnail_source'] = thumb
            continue
        print('Downloading thumbnail for', it.get('name'))
        data = fetch_image(thumb)
        if not data:
            print('  failed to download')
            continue
        ok = save_webp(data, out_path)
        if ok:
            it['thumbnail_local'] = str(Path('api') / 'media' / filename)
            it['thumbnail_source'] = thumb
            changed = True
            print('  saved', out_path)
        else:
            print('  failed to convert')

    if changed:
        with open(DATA, 'w', encoding='utf-8') as f:
            json.dump(items, f, indent=2, ensure_ascii=False)
        print('Updated', DATA)
    else:
        print('No changes')


if __name__ == '__main__':
    main()
