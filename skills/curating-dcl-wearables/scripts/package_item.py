#!/usr/bin/env python3
"""Package a wearable into the Builder's item zip: wearable.json + one GLB per body shape + thumbnail.png.

The same zip feeds Decentraland's official validator (`wearable-validator validate item.zip`), which reads category,
hides and representations from wearable.json, and the Builder's "Multiple items" upload.

usage:
  python3 package_item.py out.zip --name "Pointy Shoes" --category feet --male shoes_male.glb --female shoes_female.glb \
      --thumbnail thumb.png [--description "..."] [--rarity epic] [--hides hair,hat] [--replaces ...] [--tags a,b]
  python3 package_item.py out.zip --name "Cap" --category hat --unisex cap.glb --thumbnail thumb.png
  python3 package_item.py out.zip --name "Eyes" --category eyes --male eyes_male.png --male-extra eyes_male_mask.png \
      --female eyes_female.png --female-extra eyes_female_mask.png --thumbnail thumb.png   (facial features: PNG sets)
"""
import argparse, json, os, sys, zipfile

MALE = 'urn:decentraland:off-chain:base-avatars:BaseMale'
FEMALE = 'urn:decentraland:off-chain:base-avatars:BaseFemale'
RARITIES = ['common', 'uncommon', 'rare', 'epic', 'legendary', 'exotic', 'mythic', 'unique']


def csv(s):
    return [x.strip() for x in s.split(',') if x.strip()] if s else []


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('out')
    ap.add_argument('--name', required=True)
    ap.add_argument('--description', default='')
    ap.add_argument('--category', required=True)
    ap.add_argument('--rarity', default='epic', choices=RARITIES)
    ap.add_argument('--male')
    ap.add_argument('--female')
    ap.add_argument('--unisex', help='one GLB fitted to both body shapes')
    ap.add_argument('--thumbnail', required=True)
    ap.add_argument('--male-extra', default='', help='more content files of the male representation, e.g. a facial '
                    'feature\'s _mask.png (comma-separated)')
    ap.add_argument('--female-extra', default='')
    ap.add_argument('--hides', default='')
    ap.add_argument('--replaces', default='')
    ap.add_argument('--tags', default='')
    a = ap.parse_args()

    if not (a.unisex or a.male or a.female):
        sys.exit('give --male and/or --female, or --unisex')
    for label, limit, text in (('name', 32, a.name), ('description', 64, a.description)):
        if len(text) > limit or ':' in text:
            sys.exit(f'{label} must be <= {limit} characters with no ":" ({len(text)} given)')

    files, reps = {}, []
    def rep(path, shapes, extra=''):
        keys = []
        for pth in [path] + csv(extra):
            key = os.path.basename(pth)
            if key in files and files[key] != pth:
                sys.exit(f'two different files are both named {key}')
            files[key] = pth; keys.append(key)
        reps.append({'bodyShapes': shapes, 'mainFile': keys[0], 'contents': keys,
                     'overrideHides': [], 'overrideReplaces': []})
    if a.unisex:
        rep(a.unisex, [MALE, FEMALE])
    if a.male:
        rep(a.male, [MALE], a.male_extra)
    if a.female:
        rep(a.female, [FEMALE], a.female_extra)

    manifest = {'name': a.name, 'description': a.description, 'rarity': a.rarity,
                'data': {'category': a.category, 'hides': csv(a.hides), 'replaces': csv(a.replaces),
                         'tags': csv(a.tags), 'representations': reps}}
    with zipfile.ZipFile(a.out, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('wearable.json', json.dumps(manifest, indent=2))
        for key, path in files.items():
            z.write(path, key)
        z.write(a.thumbnail, 'thumbnail.png')
    size = os.path.getsize(a.out)
    print(f'{a.out}: {len(files)} model(s) + thumbnail, {size / 1048576:.2f} MB zipped')
    print('next: npx -y @dcl-regenesislabs/wearable-validator validate ' + a.out + '   (Node >= 22.19)')


if __name__ == '__main__':
    main()
