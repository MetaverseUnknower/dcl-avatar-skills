#!/usr/bin/env python3
"""Build a corpus of published Marketplace wearables for the clipping eval: a seeded random sample per category,
both body shapes' GLBs from the catalyst, and the metadata check_clipping.py needs (category, effective hides).

usage: python3 sample_marketplace.py [--out ~/.cache/dcl-clip-eval/corpus] [--seed 1] [--per upper_body=8,feet=6,...]
       python3 sample_marketplace.py --urn urn:decentraland:matic:collections-v2:0x...:2 [--urn ...]

Every item lands in <out>/<slug>/ as female.glb, male.glb, thumbnail.png and item.json; <out>/manifest.json lists
them. Items already downloaded are kept, so re-running with the same seed adds nothing and a bigger --per adds more.
Published items have passed curation, which makes them a realistic mix of clean work and work that slipped through.
"""
import argparse, json, os, random, sys, time, urllib.parse, urllib.request

MARKET = 'https://marketplace-api.decentraland.org/v1/items'
PEER = 'https://peer.decentraland.org/content'
DEFAULT_PER = dict(upper_body=8, lower_body=6, feet=6, hands_wear=4, helmet=3, hat=3, mask=2, hair=3, eyewear=2,
                   earring=1, top_head=1, facial_hair=1, skin=1)
SHAPES = {'BaseFemale': 'female', 'BaseMale': 'male'}
BODY_PARTS = ('upper_body', 'lower_body', 'feet', 'hands', 'head', 'skin')   # what check_clipping can hide


def get(url, data=None, tries=4):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, data=json.dumps(data).encode() if data else None,
                                         headers={'content-type': 'application/json', 'user-agent': 'dcl-clip-eval'})
            return urllib.request.urlopen(req, timeout=120).read()
        except Exception as e:
            if k == tries - 1:
                raise
            print(f'  retry {url[:80]}: {e}', file=sys.stderr)
            time.sleep(2 * (k + 1))


def market_page(category, first, skip):
    q = urllib.parse.urlencode({'category': 'wearable', 'wearableCategory': category, 'first': first, 'skip': skip,
                                'sortBy': 'newest'})
    return json.loads(get(f'{MARKET}?{q}'))


def effective_hides(data, rep):
    """Body parts hidden for one representation: its override if set, else the item's hides, plus Decentraland's
    implicit upper_body -> hands unless removesDefaultHiding lists hands."""
    hides = set(rep.get('overrideHides') or data.get('hides') or [])
    if data['category'] == 'upper_body' and 'hands' not in (data.get('removesDefaultHiding') or []):
        hides.add('hands')
    hides.discard(data['category'])
    return sorted(h for h in hides if h in BODY_PARTS)


def fetch_item(urn, out, market_row=None):
    ent = json.loads(get(f'{PEER}/entities/active', {'pointers': [urn]}))
    if not ent:
        print(f'  no active entity for {urn}')
        return None
    ent = ent[0]
    meta, data = ent['metadata'], ent['metadata']['data']
    content = {c['file']: c['hash'] for c in ent['content']}
    slug = urn.split(':')[-2][-10:] + '-' + urn.split(':')[-1]
    d = os.path.join(out, slug)
    os.makedirs(d, exist_ok=True)
    item = {'slug': slug, 'urn': urn, 'name': meta.get('name'), 'category': data['category'],
            'hides': data.get('hides', []), 'replaces': data.get('replaces', []),
            'removesDefaultHiding': data.get('removesDefaultHiding', []), 'shapes': {},
            'creator': (market_row or {}).get('creator'), 'rarity': (market_row or {}).get('rarity'),
            'marketplace': f"https://decentraland.org/marketplace{(market_row or {}).get('url', '')}"}
    for rep in data['representations']:
        main = rep['mainFile']
        if not main.lower().endswith('.glb'):
            continue                                     # .gltf + loose files: rare on new items, skipped
        for bs in rep['bodyShapes']:
            shape = SHAPES.get(bs.split(':')[-1])
            if not shape or shape in item['shapes']:
                continue
            dest = os.path.join(d, f'{shape}.glb')
            if not os.path.exists(dest):
                blob = get(f'{PEER}/contents/{content[main]}')
                if blob[:4] != b'glTF':
                    print(f'  {slug} {shape}: not a GLB, skipped')
                    continue
                open(dest, 'wb').write(blob)
            item['shapes'][shape] = {'glb': f'{shape}.glb', 'hides': effective_hides(data, rep)}
    thumb = os.path.join(d, 'thumbnail.png')
    if 'thumbnail.png' in content and not os.path.exists(thumb):
        open(thumb, 'wb').write(get(f'{PEER}/contents/{content["thumbnail.png"]}'))
    if not item['shapes']:
        return None
    json.dump(item, open(os.path.join(d, 'item.json'), 'w'), indent=1)
    return item


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', default=os.path.expanduser('~/.cache/dcl-clip-eval/corpus'))
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--per', default='', help='category=count overrides, comma list (others keep their default)')
    ap.add_argument('--only', default='', help='sample just these categories')
    ap.add_argument('--urn', action='append', default=[], help='add specific items instead of sampling')
    A = ap.parse_args()
    out = os.path.expanduser(A.out)
    os.makedirs(out, exist_ok=True)
    mpath = os.path.join(out, 'manifest.json')
    manifest = json.load(open(mpath)) if os.path.exists(mpath) else {'items': {}}
    jobs = []
    if A.urn:
        jobs = [(u, None) for u in A.urn]
    else:
        per = dict(DEFAULT_PER)
        for kv in filter(None, A.per.split(',')):
            k, v = kv.split('=')
            per[k.strip()] = int(v)
        if A.only:
            per = {k: v for k, v in per.items() if k in A.only.split(',')}
        rng = random.Random(A.seed)
        for cat, n in per.items():
            total = market_page(cat, 1, 0).get('total', 0)
            have = sum(1 for it in manifest['items'].values() if it['category'] == cat)
            if total == 0 or have >= n:
                continue
            picks = rng.sample(range(total), min(total, n * 3))      # extra picks: some lack a GLB or a shape
            got = 0
            for skip in picks:
                if have + got >= n:
                    break
                rows = market_page(cat, 1, skip)['data']
                if rows and rows[0]['urn'] not in {it['urn'] for it in manifest['items'].values()}:
                    jobs.append((rows[0]['urn'], rows[0]))
                    got += 1
            print(f'{cat}: {got} new of {total} listed')
    for urn, row in jobs:
        try:
            it = fetch_item(urn, out, row)
        except Exception as e:
            print(f'  {urn}: {e}')
            continue
        if it:
            manifest['items'][it['slug']] = {k: it[k] for k in ('urn', 'name', 'category')} | \
                {'shapes': sorted(it['shapes'])}
            print(f"  {it['slug']:<14} {it['category']:<12} {it['name']}  {sorted(it['shapes'])}")
            json.dump(manifest, open(mpath, 'w'), indent=1)
    print(f"{len(manifest['items'])} items in {mpath}")


if __name__ == '__main__':
    main()
