from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import json
import os
import requests
import time
import re
from urllib.parse import quote

app = FastAPI()

# serve the repo root static files so you can open results.html via the API server
app.mount("/static", StaticFiles(directory=".."), name="static")

# ensure api/media exists and serve it at /api/media so `thumbnail_local` paths work
MEDIA_DIR = os.path.join(os.path.dirname(__file__), 'media')
os.makedirs(MEDIA_DIR, exist_ok=True)
app.mount("/api/media", StaticFiles(directory=MEDIA_DIR), name="api_media")

# User-Agent for third-party requests (Wikipedia requires one)
USER_AGENT = os.environ.get('COUGAR_USER_AGENT') or 'CougarFallback/1.0 (https://example.com)'

def wiki_search_title(query):
    """Return the top Wikipedia search result title for `query`, or None."""
    try:
        params = {
            'action': 'query',
            'list': 'search',
            'srsearch': query,
            'format': 'json',
            'srlimit': 1,
        }
        r = requests.get('https://en.wikipedia.org/w/api.php', params=params, headers={'User-Agent': USER_AGENT}, timeout=10)
        r.raise_for_status()
        data = r.json()
        hits = data.get('query', {}).get('search', [])
        if not hits:
            return None
        return hits[0].get('title')
    except Exception:
        return None


def wiki_search_candidates(query, limit=5):
    """Return up to `limit` Wikipedia search result titles for `query`."""
    try:
        params = {
            'action': 'query',
            'list': 'search',
            'srsearch': query,
            'format': 'json',
            'srlimit': limit,
        }
        r = requests.get('https://en.wikipedia.org/w/api.php', params=params, headers={'User-Agent': USER_AGENT}, timeout=10)
        r.raise_for_status()
        data = r.json()
        hits = data.get('query', {}).get('search', [])
        return [h.get('title') for h in hits]
    except Exception:
        return []

def wiki_fetch_summary(title):
    """Fetch the Wikipedia REST summary for a title. Returns dict or None."""
    try:
        url = 'https://en.wikipedia.org/api/rest_v1/page/summary/' + quote(title)
        r = requests.get(url, headers={'User-Agent': USER_AGENT}, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def wiki_fetch_specs(title):
    """Attempt to fetch the page HTML and parse the infobox for common vehicle specs.
    Returns a dict of normalized spec keys (engine, displacement, power, torque, transmission, drivetrain, weight, production).
    This is best-effort and may return an empty dict if parsing fails.
    """
    try:
        page_url = 'https://en.wikipedia.org/wiki/' + quote(title)
        r = requests.get(page_url, headers={'User-Agent': USER_AGENT}, timeout=10)
        r.raise_for_status()
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, 'lxml')
        infobox = soup.find('table', class_='infobox')
        if not infobox:
            return {}

        specs = {}
        # iterate rows
        for row in infobox.find_all('tr'):
            header = row.find('th')
            val = row.find('td')
            if not header or not val:
                continue
            key = header.get_text(' ', strip=True).lower()
            text = val.get_text(' ', strip=True)
            # normalize some likely keys
            if 'engine' in key:
                specs['engine'] = text
            elif 'power' in key or 'horsepower' in key:
                specs['power'] = text
            elif 'displacement' in key or 'capacity' in key:
                specs['displacement'] = text
            elif 'torque' in key:
                specs['torque'] = text
            elif 'transmission' in key:
                specs['transmission'] = text
            elif 'drive' in key or 'drivetrain' in key:
                specs['drivetrain'] = text
            elif 'weight' in key:
                specs['weight'] = text
            elif 'production' in key or 'model years' in key or 'in production' in key:
                specs['production'] = text

        return specs
    except Exception:
        return {}


def wikidata_entity_for_title(title):
    """Return the Wikidata entity id (e.g., Qxxxx) for an enwiki title, or None."""
    try:
        params = {
            'action': 'wbgetentities',
            'sites': 'enwiki',
            'titles': title,
            'format': 'json'
        }
        r = requests.get('https://www.wikidata.org/w/api.php', params=params, headers={'User-Agent': USER_AGENT}, timeout=10)
        r.raise_for_status()
        data = r.json()
        entities = data.get('entities') or {}
        for k,v in entities.items():
            if k.startswith('-'):
                continue
            # k is the Q-id
            return k
    except Exception:
        return None


def wikidata_get_entity(qid):
    """Fetch the full Wikidata entity JSON for qid."""
    try:
        params = {
            'action': 'wbgetentities',
            'ids': qid,
            'format': 'json',
            'props': 'claims|labels'
        }
        r = requests.get('https://www.wikidata.org/w/api.php', params=params, headers={'User-Agent': USER_AGENT}, timeout=10)
        r.raise_for_status()
        data = r.json()
        return (data.get('entities') or {}).get(qid)
    except Exception:
        return None


def _resolve_unit_label(unit_url, cache):
    """Given a wikidata unit URL like 'http://www.wikidata.org/entity/Qxxxx', return its english label by fetching the entity. Uses cache dict to avoid repeated calls."""
    if not unit_url:
        return None
    if not unit_url.startswith('http'):
        return unit_url
    # extract Qid
    q = unit_url.rstrip('/').rsplit('/', 1)[-1]
    if q in cache:
        return cache[q]
    try:
        ent = wikidata_get_entity(q)
        lbl = None
        if ent:
            lbl = (ent.get('labels') or {}).get('en', {}).get('value')
        cache[q] = lbl
        return lbl
    except Exception:
        return None


def wikidata_extract_quantity_claims(entity):
    """Return a dict of property -> list of {'amount': float, 'unit': unit_label, 'raw_unit': raw_unit_url} for quantity claims found in entity claims."""
    out = {}
    if not entity:
        return out
    claims = entity.get('claims') or {}
    unit_cache = {}
    for prop, prop_claims in claims.items():
        for c in prop_claims:
            mainsnak = c.get('mainsnak') or {}
            datav = mainsnak.get('datavalue')
            if not datav:
                continue
            if datav.get('type') == 'quantity':
                q = datav.get('value', {}).get('amount')
                unit = datav.get('value', {}).get('unit')
                try:
                    amt = float(str(q))
                except Exception:
                    try:
                        amt = float(q.lstrip('+'))
                    except Exception:
                        amt = None
                unit_label = _resolve_unit_label(unit, unit_cache) if unit else None
                out.setdefault(prop, []).append({'amount': amt, 'unit_label': unit_label, 'raw_unit': unit})
    return out


def wikidata_extract_linked_entity_qids(entity):
    """Return a set of QIDs referenced by this entity via wikibase-entityid claims.
    These are candidates like engine items or variants that may carry quantity claims.
    """
    qids = set()
    if not entity:
        return qids
    claims = entity.get('claims') or {}
    for prop, prop_claims in claims.items():
        for c in prop_claims:
            mainsnak = c.get('mainsnak') or {}
            dv = mainsnak.get('datavalue')
            if not dv:
                continue
            if dv.get('type') == 'wikibase-entityid':
                val = dv.get('value') or {}
                q = val.get('id')
                if q:
                    qids.add(q)
    return qids


def wikidata_fetch_linked_quantities(entity):
    """Fetch quantity claims from linked entities (e.g., engine items). Returns dict qid->quantities."""
    out = {}
    if not entity:
        return out
    qids = wikidata_extract_linked_entity_qids(entity)
    # allowlist keywords for relevant linked entities
    ALLOW_KEYWORDS = ['engine', 'motor', 'internal combustion', 'vehicle', 'car', 'automobile', 'model', 'variant']
    for q in qids:
        try:
            ent = wikidata_get_entity(q)
            if not ent:
                continue
            label = (ent.get('labels') or {}).get('en', {}).get('value') or ''
            # check instance-of (P31) labels if present to decide relevance
            claims = ent.get('claims') or {}
            p31 = claims.get('P31') or []
            p31_labels = []
            for c in p31:
                dv = c.get('mainsnak', {}).get('datavalue')
                if dv and dv.get('type') == 'wikibase-entityid':
                    pid = dv.get('value', {}).get('id')
                    # fetch a brief entity for this pid to get its label
                    try:
                        p31ent = wikidata_get_entity(pid)
                        if p31ent:
                            p31_labels.append((p31ent.get('labels') or {}).get('en', {}).get('value') or '')
                    except Exception:
                        pass
            combined = ' '.join([label] + p31_labels).lower()
            qs = wikidata_extract_quantity_claims(ent)
            # include if label/instance-of suggests relevance OR if the entity has quantity claims
            if not any(k in combined for k in ALLOW_KEYWORDS) and not qs:
                # skip non-relevant linked entities (e.g., company financial nodes)
                continue
            if qs:
                out[q] = {'label': label, 'quantities': qs, 'p31_labels': p31_labels}
            else:
                # include entity without quantity claims if it's likely relevant (e.g., model/engine label)
                out[q] = {'label': label, 'quantities': {}, 'p31_labels': p31_labels}
        except Exception:
            continue
    return out


def wikidata_fetch_claims_for_title(title):
    """Given a Wikipedia title, return a small dict: {'qid': Qxx, 'quantities': {...}}"""
    try:
        qid = wikidata_entity_for_title(title)
        if not qid:
            return None
        ent = wikidata_get_entity(qid)
        if not ent:
            return None
        quantities = wikidata_extract_quantity_claims(ent)
        linked = wikidata_fetch_linked_quantities(ent)
        return {'qid': qid, 'quantities': quantities, 'linked': linked}
    except Exception:
        return None


def _parse_power(text):
    """Parse power strings to return a dict with hp and kW when possible.
    Handles multiple values and ranges; returns min/max/avg and representative primary values.
    """
    import re
    out = {}
    if not text:
        return out
    def to_num(s):
        return float(s.replace(',', '').replace('\u202F',''))

    kws = [to_num(m) for m in re.findall(r'([0-9][0-9,\.\u202F]*)\s*kW', text, flags=re.I)]
    hps = [to_num(m) for m in re.findall(r'([0-9][0-9,\.\u202F]*)\s*(?:hp|PS|ps)', text, flags=re.I)]

    if kws:
        out['power_kw_min'] = round(min(kws), 1)
        out['power_kw_max'] = round(max(kws), 1)
        out['power_kw_avg'] = round(sum(kws) / len(kws), 1)
    if hps:
        out['power_hp_min'] = round(min(hps), 1)
        out['power_hp_max'] = round(max(hps), 1)
        out['power_hp_avg'] = round(sum(hps) / len(hps), 1)

    # Representative primary values (prefer explicit hp if present, otherwise kW)
    if 'power_hp_max' in out and 'power_kw_max' in out:
        out['power_hp'] = out['power_hp_max']
        out['power_kw'] = out['power_kw_max']
    elif 'power_hp_max' in out:
        out['power_hp'] = out['power_hp_max']
        out['power_kw'] = round(out['power_hp'] / 1.34102, 1)
    elif 'power_kw_max' in out:
        out['power_kw'] = out['power_kw_max']
        out['power_hp'] = round(out['power_kw'] * 1.34102, 1)
    return out


def _parse_weight(text):
    """Parse weight text and return kg and lb ranges and primary values."""
    import re
    out = {}
    if not text:
        return out
    def to_num(s):
        return float(s.replace(',', '').replace('\u202F',''))

    # ranges like '1,931–2,055 kg' or singular matches
    kg_ranges = re.findall(r'([0-9][0-9,\.\u202F]*)\s*[–-]\s*([0-9][0-9,\.\u202F]*)\s*kg', text, flags=re.I)
    kgs = []
    for a,b in kg_ranges:
        kgs.extend([to_num(a), to_num(b)])
    # also capture standalone kg numbers
    kgs += [to_num(m) for m in re.findall(r'([0-9][0-9,\.\u202F]*)\s*kg', text, flags=re.I)]
    kgs = list(dict.fromkeys(kgs))  # unique-preserve order
    if kgs:
        out['weight_kg_min'] = round(min(kgs), 1)
        out['weight_kg_max'] = round(max(kgs), 1)
        out['weight_kg_avg'] = round(sum(kgs) / len(kgs), 1)
        out['weight_lb_min'] = round(out['weight_kg_min'] * 2.20462, 1)
        out['weight_lb_max'] = round(out['weight_kg_max'] * 2.20462, 1)
        out['weight_lb_avg'] = round(out['weight_kg_avg'] * 2.20462, 1)
        # representative: choose max as worst-case curb weight
        out['weight_kg'] = out['weight_kg_max']
        out['weight_lb'] = out['weight_lb_max']
    else:
        # fallback: try lb numbers
        lbs = [to_num(m) for m in re.findall(r'([0-9][0-9,\.\u202F]*)\s*(?:lb|lbs)', text, flags=re.I)]
        if lbs:
            out['weight_lb_min'] = round(min(lbs), 1)
            out['weight_lb_max'] = round(max(lbs), 1)
            out['weight_lb_avg'] = round(sum(lbs) / len(lbs), 1)
            out['weight_kg_min'] = round(out['weight_lb_min'] / 2.20462, 1)
            out['weight_kg_max'] = round(out['weight_lb_max'] / 2.20462, 1)
            out['weight_kg_avg'] = round(out['weight_lb_avg'] / 2.20462, 1)
            out['weight_kg'] = out['weight_kg_max']
            out['weight_lb'] = out['weight_lb_max']
    return out


def _parse_displacement(text):
    """Parse displacement strings and return liters and cc, supporting ranges and multiple values."""
    import re
    out = {}
    if not text:
        return out
    def to_num(s):
        return float(s.replace(',', '').replace('\u202F',''))

    ls = [to_num(m) for m in re.findall(r'([0-9][0-9,\.\u202F]*)\s*(?:L|litre|litres)', text, flags=re.I)]
    ccs = [to_num(m) for m in re.findall(r'([0-9][0-9,\.\u202F]*)\s*(?:cc|cm3)', text, flags=re.I)]
    if ls:
        out['displacement_l_min'] = round(min(ls), 3)
        out['displacement_l_max'] = round(max(ls), 3)
        out['displacement_l'] = round(max(ls), 3)
        out['displacement_cc'] = int(round(out['displacement_l'] * 1000))
    elif ccs:
        out['displacement_cc_min'] = int(round(min(ccs)))
        out['displacement_cc_max'] = int(round(max(ccs)))
        out['displacement_cc'] = int(round(max(ccs)))
        out['displacement_l'] = round(out['displacement_cc'] / 1000.0, 3)
    return out


def _parse_torque(text):
    """Parse torque and return Nm and lb-ft with min/max/avg if multiple values present."""
    import re
    out = {}
    if not text:
        return out
    def to_num(s):
        return float(s.replace(',', '').replace('\u202F',''))

    nms = [to_num(m) for m in re.findall(r'([0-9][0-9,\.\u202F]*)\s*(?:N\.?\s?m|Nm|N·m)', text, flags=re.I)]
    lbfts = [to_num(m) for m in re.findall(r'([0-9][0-9,\.\u202F]*)\s*(?:lb-?ft|ft-lb)', text, flags=re.I)]
    if nms:
        out['torque_nm_min'] = round(min(nms), 1)
        out['torque_nm_max'] = round(max(nms), 1)
        out['torque_nm'] = round(max(nms), 1)
        out['torque_lbft_min'] = round(out['torque_nm_min'] * 0.737562, 1)
        out['torque_lbft_max'] = round(out['torque_nm_max'] * 0.737562, 1)
        out['torque_lbft'] = round(out['torque_nm'] * 0.737562, 1)
    elif lbfts:
        out['torque_lbft_min'] = round(min(lbfts), 1)
        out['torque_lbft_max'] = round(max(lbfts), 1)
        out['torque_lbft'] = round(max(lbfts), 1)
        out['torque_nm_min'] = round(out['torque_lbft_min'] / 0.737562, 1)
        out['torque_nm_max'] = round(out['torque_lbft_max'] / 0.737562, 1)
        out['torque_nm'] = round(out['torque_lbft'] / 0.737562, 1)
    return out

# convenience endpoints to serve top-level HTML files at root paths
ROOT_DIR = os.path.join(os.path.dirname(__file__), '..')

@app.get('/index.html')
def index_html():
    path = os.path.join(ROOT_DIR, 'index.html')
    if os.path.exists(path):
        return FileResponse(path, media_type='text/html')
    raise HTTPException(status_code=404, detail='index.html not found')

@app.get('/results.html')
def results_html():
    path = os.path.join(ROOT_DIR, 'results.html')
    if os.path.exists(path):
        return FileResponse(path, media_type='text/html')
    raise HTTPException(status_code=404, detail='results.html not found')

@app.get('/favicon.ico')
def favicon():
    path = os.path.join(ROOT_DIR, 'favicon.ico')
    if os.path.exists(path):
        return FileResponse(path, media_type='image/x-icon')
    raise HTTPException(status_code=404, detail='favicon not found')

DATA_PATH = os.path.join(os.path.dirname(__file__), 'data', 'cars.json')
CACHE_PATH = os.path.join(os.path.dirname(__file__), 'data', 'wiki_cache.json')
CACHE_TTL_DAYS = int(os.environ.get('COUGAR_WIKI_CACHE_TTL_DAYS') or '7')


def _load_cache():
    try:
        if not os.path.exists(CACHE_PATH):
            return {}
        with open(CACHE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cache(cache):
    try:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        with open(CACHE_PATH, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def _normalize_query(q: str):
    """Normalize a query into a stable key: lowercase, keep word tokens joined by spaces."""
    try:
        toks = [t.lower() for t in re.findall(r"\w+", (q or '').lower())]
        return ' '.join(toks)
    except Exception:
        return (q or '').lower().strip()


def _cache_get_query(q: str):
    """Return cached item for normalized query if present and not expired."""
    cache = _load_cache()
    key = 'q:' + _normalize_query(q)
    entry = cache.get(key)
    if not entry:
        return None
    try:
        ts = float(entry.get('ts', 0))
        age_days = (time.time() - ts) / 86400.0
        if age_days > CACHE_TTL_DAYS:
            return None
        return entry.get('item')
    except Exception:
        return None


def _cache_set_query(q: str, item):
    cache = _load_cache()
    key = 'q:' + _normalize_query(q)
    cache[key] = {'ts': time.time(), 'item': item}
    _save_cache(cache)


def _cache_get(title):
    cache = _load_cache()
    key = title.lower()
    entry = cache.get(key)
    if not entry:
        return None
    try:
        ts = float(entry.get('ts', 0))
        age_days = (time.time() - ts) / 86400.0
        if age_days > CACHE_TTL_DAYS:
            # expired
            return None
        return entry.get('item')
    except Exception:
        return None


def _cache_set(title, item):
    cache = _load_cache()
    key = title.lower()
    cache[key] = {'ts': time.time(), 'item': item}
    _save_cache(cache)

def load_data():
    if not os.path.exists(DATA_PATH):
        return []
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

@app.get('/cars')
def get_cars(q: str = ''):
    items = load_data()
    if not q:
        return items

    ql = q.lower()
    matches = [i for i in items if ql in (i.get('name','')+ ' ' + i.get('manufacturer','') + ' ' + (i.get('year','') or '')).lower()]
    if matches:
        return matches

    # check query-keyed cache first so repeated queries are immediate
    qcached = _cache_get_query(q)
    if qcached:
        return [qcached]

    # no local matches — attempt a Wikipedia fallback to build a best-effort item
    # try multiple candidates and prefer the one that yields richer specs
    candidates = wiki_search_candidates(q, limit=8)
    title = None
    if candidates:
        # score candidates by token match + richness
        # normalize query tokens and candidate tokens using word characters so
        # tokens like 'GT-R' -> 'gtr' and 'R34' -> 'r34' match correctly
        qtokens = [t.lower() for t in re.findall(r"\w+", q.lower())]
        best = (None, -1)
        for cand in candidates:
            # quick token match score
            cand_tokens = [t.lower() for t in re.findall(r"\w+", cand.lower())]
            token_score = len(set(qtokens) & set(cand_tokens))
            # small bonus if candidate contains any numeric/token model part (e.g., 'r34', 'mk2')
            model_bonus = 1 if any(re.search(r"\d", t) for t in cand_tokens) else 0
            # stronger model bonus if the query itself contains a numeric/model token and candidate contains it
            query_has_model_token = any(re.search(r"\d", t) for t in qtokens)
            if query_has_model_token and any(t in qtokens for t in cand_tokens):
                model_bonus = 6
            # require at least one token overlap with the query; skip unrelated candidates
            if token_score == 0:
                continue
            # prefer cached items quickly (per-candidate)
            cached_cand = _cache_get(cand)
            if cached_cand:
                try:
                    cached_richness = len((cached_cand.get('specs') or {}).keys())
                except Exception:
                    cached_richness = 0
                # prefer cached items but avoid an overwhelming boost: use a modest multiplier
                cand_score = cached_richness * 20 + token_score * 5 + model_bonus * 5
                if cand_score > best[1]:
                    best = (cand, cand_score)
                continue
            # fetch specs richness
            specs_try = wiki_fetch_specs(cand) or {}
            richness = len(specs_try.keys())
            # also check wikidata quantities (direct + linked) to prefer model pages with structured numeric claims
            wd = None
            try:
                wd = wikidata_fetch_claims_for_title(cand)
            except Exception:
                wd = None
            wd_richness = 0
            if wd:
                try:
                    wd_richness += len(wd.get('quantities', {}) or {})
                    # add linked quantities count
                    linked = wd.get('linked') or {}
                    for lk in linked.values():
                        wd_richness += sum(len(v) for v in (lk.get('quantities') or {}).values())
                except Exception:
                    wd_richness = wd_richness
            # heuristics to penalize likely non-vehicle/wrong-type pages
            non_vehicle_penalty = 0
            try:
                desc = (wikidata_fetch_claims_for_title(cand) or {}).get('description') or ''
                if desc:
                    bad_keywords = ['company', 'manufacturer', 'business', 'organization', 'software', 'film']
                    if any(bk in desc.lower() for bk in bad_keywords):
                        non_vehicle_penalty = 50
            except Exception:
                non_vehicle_penalty = 0

            # weight richness and wikidata richness so structured data wins, then apply penalty
            cand_score = (richness * 8) + (wd_richness * 12) + (token_score * 4) + (model_bonus * 5) - non_vehicle_penalty
            # optional debug logging controlled by COUGAR_DEBUG
            try:
                if os.environ.get('COUGAR_DEBUG'):
                    print(f"DEBUG SCORE - cand={cand!r} token={token_score} model_bonus={model_bonus} cached={cached_cand is not None} richness={richness} wd_richness={wd_richness} penalty={non_vehicle_penalty} -> {cand_score}")
            except Exception:
                pass
            if cand_score > best[1]:
                best = (cand, cand_score)
        title = best[0]
    # fallback: use top hit if nothing found via scoring
    if not title:
        top = wiki_search_title(q)
        # only accept top hit if it shares tokens with the query
        if top:
            qtokens = [t.lower() for t in re.findall(r"\w+", q.lower())]
            top_tokens = [t.lower() for t in re.findall(r"\w+", top.lower())]
            if len(set(qtokens) & set(top_tokens)) > 0:
                title = top
            else:
                title = None
    # check title-keyed cache first
    cached = _cache_get(title)
    if cached:
        # also populate query-keyed cache for faster repeats
        try:
            _cache_set_query(q, cached)
        except Exception:
            pass
        return [cached]
    if not title:
        return []
    summary = wiki_fetch_summary(title)
    if not summary:
        return []

    # Construct a synthetic item with minimal fields and a _wiki block
    specs = wiki_fetch_specs(title) or {}
    # Normalize common units into additional keys
    try:
        # power
        p_raw = specs.get('power')
        if p_raw:
            specs.update(_parse_power(p_raw))
        # weight
        w_raw = specs.get('weight')
        if w_raw:
            specs.update(_parse_weight(w_raw))
        # displacement
        d_raw = specs.get('displacement')
        if d_raw:
            specs.update(_parse_displacement(d_raw))
        # torque
        t_raw = specs.get('torque')
        if t_raw:
            specs.update(_parse_torque(t_raw))
    except Exception:
        pass

    # enrich with Wikidata structured quantities when available
    try:
        wd = wikidata_fetch_claims_for_title(title)
        if wd and wd.get('quantities'):
            wd_q = wd['quantities']
            # common property mappings (Wikidata property ids):
            # P1100 - displacement (but actual properties can vary), P1112 - power (sometimes), P2067 - mass
            # We'll defensively check these and merge numeric amounts if present.
            # displacement -> displacement_l (if unit is 'm³' or 'cm³' convert appropriately)
            if 'P1100' in wd_q and wd_q['P1100']:
                # values often in cm³ (cc)
                val = wd_q['P1100'][0]
                amt = val.get('amount')
                unit = (val.get('unit_label') or '').lower() if val.get('unit_label') else ''
                if amt:
                    # assume amount is in cubic centimetres if unit contains 'cubic' or 'centimetre' or 'cm'
                    if 'centimet' in unit or 'cm' in unit:
                        try:
                            cc = float(amt)
                            specs['displacement_cc'] = int(round(cc))
                            specs['displacement_l'] = round(cc / 1000.0, 3)
                        except Exception:
                            pass
                    else:
                        # fallback: store raw
                        specs['wikidata_P1100'] = val
            # power -> power in kW or hp (property ids vary; P1112 used sometimes)
            if 'P1112' in wd_q and wd_q['P1112']:
                val = wd_q['P1112'][0]
                amt = val.get('amount')
                unit = (val.get('unit_label') or '').lower() if val.get('unit_label') else ''
                if amt:
                    try:
                        a = float(amt)
                        # measure in watts/kW or hp for units
                        if 'watt' in unit or 'kw' in unit:
                            kw = a / 1000.0 if 'watt' in unit else a
                            specs['power_kw'] = round(kw, 1)
                            specs['power_hp'] = round(kw * 1.34102, 1)
                        elif 'hp' in unit:
                            specs['power_hp'] = round(a, 1)
                            specs['power_kw'] = round(a / 1.34102, 1)
                        else:
                            specs['wikidata_P1112'] = val
                    except Exception:
                        pass
            # mass/weight -> P2067 (mass)
            if 'P2067' in wd_q and wd_q['P2067']:
                val = wd_q['P2067'][0]
                amt = val.get('amount')
                unit = (val.get('unit_label') or '').lower() if val.get('unit_label') else ''
                if amt:
                    try:
                        a = float(amt)
                        # unit likely in kg
                        if 'gram' in unit or 'kg' in unit:
                            # if grams, convert
                            if 'gram' in unit and 'kilogram' not in unit:
                                kg = a / 1000.0
                            else:
                                kg = a
                            specs['weight_kg'] = round(kg, 1)
                            specs['weight_lb'] = round(kg * 2.20462, 1)
                        else:
                            specs['wikidata_P2067'] = val
                    except Exception:
                        pass
            # attach raw wikidata block for reference
            synth['_wikidata'] = wd
    except Exception:
        pass

    synth = {
        'id': 'wiki-' + title.replace(' ', '-').lower(),
        'name': summary.get('title') or title,
        'manufacturer': '',
        'year': '',
        'slug': (summary.get('title') or title).lower().replace(' ', '-'),
        'specs': specs,
        'description': summary.get('extract') or '',
        '_wiki': {
            'title': summary.get('title'),
            'description': summary.get('description'),
            'extract': summary.get('extract'),
            'wiki_url': summary.get('content_urls', {}).get('desktop', {}).get('page') if summary.get('content_urls') else None,
            'thumbnail': (summary.get('thumbnail', {}) or {}).get('source')
        }
    }
    # persist to cache (both title-keyed and query-keyed)
    try:
        _cache_set(title, synth)
    except Exception:
        pass
    try:
        _cache_set_query(q, synth)
    except Exception:
        pass
    return [synth]


@app.get('/data/cars.json')
def serve_data_file():
    if not os.path.exists(DATA_PATH):
        raise HTTPException(status_code=404, detail='data not found; run ingest script')
    return FileResponse(DATA_PATH, media_type='application/json')
