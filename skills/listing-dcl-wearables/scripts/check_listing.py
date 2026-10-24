#!/usr/bin/env python3
"""Check a collection's Builder listing (names, rarities, descriptions, utility, tags) and print the fill-in sheet.

usage: python3 check_listing.py listing.json [--sheet]

listing.json:
{
  "collection": "Techwear Vol 1",
  "items": [
    {"file": "pants", "name": "Techwear Strap Pants", "category": "lower_body", "rarity": "epic",
     "description": "Matte black cargo pants rigged with straps that swing",
     "utility": "", "tags": ["techwear", "pants", "black", "straps", "cyberpunk"],
     "hides": [], "price": null, "giveaways": 0, "event_tag": null}
  ]
}

FAIL = the Builder or the server will refuse it. WARN = likely to hurt curation or search. Exit 1 on FAIL.
"""
import json, re, sys

RARITY = {'unique': 1, 'mythic': 10, 'exotic': 50, 'legendary': 100, 'epic': 1000, 'rare': 5000, 'uncommon': 10000,
          'common': 100000}
CATEGORIES = {'hair', 'eyes', 'eyebrows', 'facial_hair', 'mouth', 'upper_body', 'lower_body', 'feet', 'hands_wear',
              'hat', 'helmet', 'mask', 'tiara', 'top_head', 'earring', 'eyewear', 'skin'}
NAME_MAX, DESC_MAX, UTIL_MAX, TAGS_MAX, COLL_MAX, ITEMS_MAX = 32, 64, 64, 20, 32, 50
# words that suggest a utility claim in a description, or IP that tends to get items rejected
CLAIMS = re.compile(r'\b(boost|increase|damage|speed|grants?|unlocks?|access|bonus|power-?up|xp)\b', re.I)


def main():
    path = sys.argv[1]
    sheet = '--sheet' in sys.argv
    data = json.load(open(path))
    rows, fails = [], 0
    def add(level, where, msg):
        nonlocal fails
        rows.append(f'  {level:<4}  {where:<34} {msg}')
        fails += level == 'FAIL'

    coll = data.get('collection', '')
    if not coll or len(coll) > COLL_MAX:
        add('FAIL', 'collection name', f'{len(coll)} chars (1-{COLL_MAX}); fixed once published')
    items = data.get('items', [])
    if not 0 < len(items) <= ITEMS_MAX:
        add('FAIL', 'items', f'{len(items)} (1-{ITEMS_MAX} per collection; the item count is fixed once published)')
    names = {}
    for i, it in enumerate(items):
        w = it.get('name') or f'item {i + 1}'
        name, desc, util = it.get('name', ''), it.get('description', ''), it.get('utility', '') or ''
        if not name or len(name) > NAME_MAX:
            add('FAIL', w, f'name is {len(name)} chars (1-{NAME_MAX})')
        if ':' in name or ':' in desc:
            add('FAIL', w, 'no ":" in name or description')
        if name.lower() in names:
            add('WARN', w, f'same name as item {names[name.lower()] + 1}: curators reject duplicates')
        names[name.lower()] = i
        if len(desc) > DESC_MAX:
            add('FAIL', w, f'description is {len(desc)} chars (max {DESC_MAX})')
        elif not desc:
            add('WARN', w, 'no description: it shows in the Marketplace and Backpack')
        elif desc.lower().startswith(name.lower()):
            add('WARN', w, "description starts by repeating the name: use the 64 chars for what the name doesn't say")
        if len(util) > UTIL_MAX:
            add('FAIL', w, f'utility is {len(util)} chars (max {UTIL_MAX})')
        if CLAIMS.search(desc) and not util:
            add('WARN', w, 'description sounds like a utility claim: only claim what the item really does')
        if it.get('category') not in CATEGORIES:
            add('FAIL', w, f'category {it.get("category")!r} is not a wearable category')
        rarity = it.get('rarity')
        if rarity not in RARITY:
            add('FAIL', w, f'rarity {rarity!r}: one of {", ".join(RARITY)}')
        elif it.get('giveaways', 0) > RARITY[rarity]:
            add('FAIL', w, f'{it["giveaways"]} giveaways but {rarity} caps supply at {RARITY[rarity]}')
        tags = it.get('tags', [])
        if len(tags) > TAGS_MAX:
            add('FAIL', w, f'{len(tags)} tags (max {TAGS_MAX})')
        bad = [t for t in tags if not t or re.search(r'[\s,#]', t)]
        if bad:
            add('FAIL', w, f'tags must be single words without "#": {bad}')
        upper = [t for t in tags if t != t.lower()]
        if upper:
            add('WARN', w, f'keep tags lowercase so search matches: {upper}')
        dupes = sorted({t.lower() for t in tags if [x.lower() for x in tags].count(t.lower()) > 1})
        if dupes:
            add('WARN', w, f'duplicate tags (the Builder drops them): {dupes}')
        if len(tags) < 5:
            add('WARN', w, f'only {len(tags)} tags: add style, colour, material, theme and set words')
        if it.get('event_tag') and it['event_tag'] not in tags:
            add('WARN', w, f'event tag {it["event_tag"]!r} is set but not in tags')
    if not rows:
        rows.append('  PASS  every field within the Builder and server limits')
    print(f'{coll} ({len(items)} items)')
    print('\n'.join(rows))
    if sheet:
        print('\nBuilder sheet, in field order:')
        for i, it in enumerate(items, 1):
            sup = RARITY.get(it.get('rarity'), '?')
            print(f'\n[{i}] {it.get("file", "")}')
            print(f'  Name ({len(it.get("name", ""))}/{NAME_MAX}): {it.get("name", "")}')
            print(f'  Rarity: {it.get("rarity")} (max supply {sup})   Category: {it.get("category")}')
            print(f'  Description ({len(it.get("description", ""))}/{DESC_MAX}): {it.get("description", "")}')
            print(f'  Utility ({len(it.get("utility") or "")}/{UTIL_MAX}): {it.get("utility") or "(leave empty)"}')
            print(f'  Tags ({len(it.get("tags", []))}/{TAGS_MAX}): {" ".join(it.get("tags", []))}')
            if it.get('hides'):
                print(f'  Hides: {", ".join(it["hides"])}')
            print(f'  Price: {"free" if it.get("price") == 0 else it.get("price") or "(ask)"}')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
