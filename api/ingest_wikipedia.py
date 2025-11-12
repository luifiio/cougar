#!/usr/bin/env python3
"""Simple ingestion: enrich cars in assets/cars.json with Wikipedia summary & thumbnail.

For each car record, this script searches Wikipedia by name, fetches the REST summary
for the best match, and merges summary, wiki_url, and thumbnail into the record.
Writes results to api/data/cars.json (creating directory if needed).
"""
import os
import requests
import json
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'assets' / 'cars.json'
DST_DIR = ROOT / 'api' / 'data'
DST = DST_DIR / 'cars.json'
MAPPINGS_PATH = ROOT / 'api' / 'mappings.json'

WIKI_SEARCH = 'https://en.wikipedia.org/w/api.php?action=query&format=json&list=search&srsearch={q}&utf8=1&srprop=snippet|titlesnippet&srwhat=text'
WIKI_SUMMARY = 'https://en.wikipedia.org/api/rest_v1/page/summary/{title}'

# configurable User-Agent for Wikipedia (per their API policy)
USER_AGENT = os.environ.get('COUGAR_USER_AGENT', 'cougar-portfolio/0.1 (https://example.com; contact: kenny@example.com)')

def search_wikipedia(q, limit=5):
    """Return up to `limit` candidate titles for query q."""
    try:
        url = WIKI_SEARCH.format(q=quote(q))
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        hits = data.get('query', {}).get('search', [])
        if not hits:
            return []
        return [h.get('title') for h in hits[:limit] if h.get('title')]
    except Exception:
        return []

def fetch_summary(title):
    try:
        url = WIKI_SUMMARY.format(title=quote(title))
        headers = {'User-Agent': USER_AGENT}
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None

def likely_car_summary(summary, manufacturer=None):
    """Heuristic: decide whether a Wikipedia summary JSON looks like a car page."""
    if not summary:
        return False
    desc = (summary.get('description') or '') + ' ' + (summary.get('extract') or '')
    desc = desc.lower()
    keywords = ['car', 'automobile', 'roadster', 'sports car', 'convertible', 'sedan', 'coupe']
    if manufacturer and manufacturer.lower() in desc:
        return True
    for k in keywords:
        if k in desc:
            return True
    return False


# toggle looser matching behavior
LOOSE_MATCH = True


def enrich_item(item):
    # build richer search query using manufacturer, name, and year where available
    name = item.get('name') or item.get('model') or ''
    manufacturer = item.get('manufacturer') or ''
    year = item.get('year') or ''
    if not name:
        return item

    parts = [manufacturer, name, year]
    q = ' '.join([p for p in parts if p]).strip()
    if not q:
        q = name

    # check manual mappings first
    mapped_title = None
    if MAPPINGS_PATH.exists():
        try:
            with open(MAPPINGS_PATH, 'r', encoding='utf-8') as mf:
                maps = json.load(mf)
            # try exact match on name or slug
            if name in maps:
                mapped_title = maps[name]
            elif item.get('slug') and item.get('slug') in maps:
                mapped_title = maps[item.get('slug')]
            elif (manufacturer + ' ' + name).strip() in maps:
                mapped_title = maps[(manufacturer + ' ' + name).strip()]
        except Exception:
            mapped_title = None
    if mapped_title:
        print('  mapping found for', name, '->', mapped_title)
    else:
        print('  no mapping for', name)

    # try multiple query fallbacks to improve recall
    tried = set()
    candidates = []
    if mapped_title:
        candidates = [mapped_title]
    else:
        candidates = search_wikipedia(q, limit=6)
    print('  candidates:', candidates)
    if not candidates and name != q:
        # try name alone
        candidates = search_wikipedia(name, limit=6)
    if not candidates and item.get('slug'):
        candidates = search_wikipedia(item.get('slug'), limit=6)

    chosen = None
    for title in candidates:
        if title in tried:
            continue
        tried.add(title)
        print('   trying title:', title)
        summary = fetch_summary(title)
        if not summary:
            print('    fetch failed for', title)
            continue
        print('    got summary title=', summary.get('title'))
        if likely_car_summary(summary, manufacturer=manufacturer):
            chosen = summary
            break
        if LOOSE_MATCH and chosen is None:
            # accept first candidate if looser matching is enabled
            chosen = summary

    # final fallback: if still no candidate, try name tokens
    if not chosen and LOOSE_MATCH:
        tokens = name.split()
        for t in tokens:
            c = search_wikipedia(t, limit=3)
            if c:
                s = fetch_summary(c[0])
                if s:
                    chosen = s
                    break

    if not chosen:
        return item

    wiki = {
        'title': chosen.get('title'),
        'description': chosen.get('description'),
        'extract': chosen.get('extract'),
        'wiki_url': chosen.get('content_urls', {}).get('desktop', {}).get('page'),
        'thumbnail': None
    }
    thumb = chosen.get('thumbnail')
    if thumb and thumb.get('source'):
        wiki['thumbnail'] = thumb.get('source')

    item['_wiki'] = wiki

    # remove heavy/unnecessary fields for the public JSON
    for remove_key in ['performance', 'images', 'rating', 'ratings', 'thumbs']:
        if remove_key in item:
            del item[remove_key]

    return item

def main():
    DST_DIR.mkdir(parents=True, exist_ok=True)
    if not SRC.exists():
        print('Source file', SRC, 'not found')
        return
    with open(SRC, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if isinstance(data, dict):
        items = [data]
    else:
        items = data

    out = []
    for i, item in enumerate(items, 1):
        print(f'[{i}/{len(items)}] Enriching: {item.get("name","(no-name)")}', end=' ... ')
        enriched = enrich_item(item)
        out.append(enriched)
        print('done' if '_wiki' in enriched else 'no wiki')

    with open(DST, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print('Wrote', DST)

if __name__ == '__main__':
    main()
