import os
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'assets' / 'cars.json'
DST_DIR = ROOT / 'api' / 'data'
DST = DST_DIR / 'cars.json'

def main():
    DST_DIR.mkdir(parents=True, exist_ok=True)
    if not SRC.exists():
        print('Source file', SRC, 'not found')
        return
    with open(SRC, 'r', encoding='utf-8') as f:
        data = json.load(f)
    # minimal normalization: ensure list
    if isinstance(data, dict):
        items = [data]
    else:
        items = data
    with open(DST, 'w', encoding='utf-8') as f:
        json.dump(items, f, indent=2)
    print('Wrote', DST)

if __name__ == '__main__':
    main()
