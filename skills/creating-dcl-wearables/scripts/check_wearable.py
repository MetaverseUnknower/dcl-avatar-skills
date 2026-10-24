#!/usr/bin/env python3
"""Check exported wearable GLBs against Decentraland's documented rules (see ../requirements.md).

usage: python3 check_wearable.py <glb> [<glb> ...] --category upper_body [--hides lower_body,hands] [--strict]

FAIL = breaks a docs/server rule (curation or upload will reject it). WARN = Builder warning, strict rule or likely
mistake. INFO = numbers to read. Exit code 1 if anything FAILs. Geometry/clipping is NOT checked here: run the
project's clip/motion checks on DCL's real animations as well.
"""
import argparse, json, os, re, struct, sys
import numpy as np

TRIS = {**dict.fromkeys(['mask', 'eyewear', 'earring', 'tiara', 'top_head', 'facial_hair'], 500),
        'hands_wear': 1000,
        **dict.fromkeys(['hat', 'helmet', 'hair', 'upper_body', 'lower_body', 'feet'], 1500),
        'skin': 5000}
CATEGORIES = set(TRIS) | {'eyes', 'eyebrows', 'mouth', 'body_shape'}
SIDES = ('Left', 'Right')
BONES = {f'Avatar_{b}' for b in ('Hips', 'Spine', 'Spine1', 'Spine2', 'Neck', 'Head')}
BONES |= {f'Avatar_{s}{b}' for s in SIDES for b in ('Shoulder', 'Arm', 'ForeArm', 'Hand', 'UpLeg', 'Leg', 'Foot', 'ToeBase')}
BONES |= {f'Avatar_{s}Hand{f}{i}' for s in SIDES for f in ('Thumb', 'Index', 'Middle', 'Ring', 'Pinky') for i in range(1, 5)}
assert len(BONES) == 62
FINGER = re.compile(r'Hand(Thumb|Index|Middle|Ring|Pinky)\d$')
FORBIDDEN = ('_mouth', '_eyebrows', '_eyes')
COMP = {5121: np.uint8, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NCOMP = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}


def load(path):
    data = open(path, 'rb').read()
    n = struct.unpack('<I', data[12:16])[0]
    return json.loads(data[20:20 + n]), data, 20 + n + 8


def accessor(g, data, bs, idx):
    a = g['accessors'][idx]
    bv = g['bufferViews'][a['bufferView']]
    dt = np.dtype(COMP[a['componentType']]).newbyteorder('<')
    k = NCOMP[a['type']]
    stride = bv.get('byteStride', dt.itemsize * k)
    off = bs + bv.get('byteOffset', 0) + a.get('byteOffset', 0)
    raw = np.lib.stride_tricks.as_strided(np.frombuffer(data, np.uint8, offset=off),
                                          (a['count'], dt.itemsize * k), (stride, 1))
    arr = np.frombuffer(raw.tobytes(), dt).reshape(a['count'], k)
    if a.get('normalized') and dt.kind == 'u':
        return arr.astype(float) / np.iinfo(dt).max
    return arr


def image_info(g, data, bs, i):
    """(format, w, h, has_alpha) read from the embedded image header."""
    im = g['images'][i]
    if 'bufferView' not in im:
        return ('external', 0, 0, False)
    bv = g['bufferViews'][im['bufferView']]
    d = data[bs + bv.get('byteOffset', 0):][:bv['byteLength']]
    if d[:4] == b'\x89PNG':
        w, h = struct.unpack('>II', d[16:24])
        return ('png', w, h, d[25] in (4, 6) or b'tRNS' in d[:min(len(d), 1 << 16)])
    if d[:2] == b'\xff\xd8':
        j = 2
        while j < len(d) - 9:
            if d[j] == 0xFF and d[j + 1] in (0xC0, 0xC2):
                h, w = struct.unpack('>HH', d[j + 5:j + 9])
                return ('jpeg', w, h, False)
            j += 2 + struct.unpack('>H', d[j + 2:j + 4])[0]
        return ('jpeg', 0, 0, False)
    return ('unknown', 0, 0, False)


def material_images(g, m):
    out = {}
    pbr = m.get('pbrMetallicRoughness', {})
    for slot, ref in list(pbr.items()) + [(k, m[k]) for k in ('normalTexture', 'occlusionTexture', 'emissiveTexture') if k in m]:
        if isinstance(ref, dict) and 'index' in ref:
            out[slot] = g['textures'][ref['index']]['source']
    return out


def is_spring(name):
    return 'springbone' in name.lower()


def check(path, category, hides, strict):
    g, data, bs = load(path)
    rows = []
    add = lambda level, label, value, rule='': rows.append((level, label, value, rule))
    nodes = g['nodes']
    name = lambda i: nodes[i].get('name', '')
    par = {c: i for i, n in enumerate(nodes) for c in n.get('children', [])}
    is_skin = category == 'skin'

    # Triangles, with the hide combiner (Builder sums every hidden category's budget).
    tris = 0
    for m in g.get('meshes', []):
        for p in m['primitives']:
            c = g['accessors'][p['indices']]['count'] if 'indices' in p else g['accessors'][p['attributes']['POSITION']]['count']
            tris += c // 3
    limit = TRIS.get(category, 1500) + sum(TRIS.get(h, 0) for h in hides if h != category)
    if category == 'hands_wear' and 'hands' in hides:
        limit = max(limit, 1500)   # docs: hands_wear hiding the base hands gets 1.5K (Builder still says 1K)
    rule = f'<= {limit}' + (' (Builder sums hidden budgets; docs quote 4K for a full-head helmet)' if category == 'helmet' and hides else '')
    add('FAIL' if tris > limit else 'PASS', f'triangles ({category}{" + hides" if hides else ""})', tris, rule)

    # Materials and textures (AvatarSkin_MAT and images only it uses don't count).
    mats = g.get('materials', [])
    counted = [m for m in mats if not m.get('name', '').startswith('AvatarSkin')]
    mlim = 5 if is_skin else 2
    add('FAIL' if len(counted) > mlim else 'PASS', 'materials (excl. AvatarSkin_MAT)', len(counted), f'<= {mlim}')
    skin_imgs = {i for m in mats if m.get('name', '').startswith('AvatarSkin') for i in material_images(g, m).values()}
    other_imgs = {i for m in counted for i in material_images(g, m).values()}
    imgs = [i for i in range(len(g.get('images', []))) if i in other_imgs or i not in skin_imgs]
    add('FAIL' if len(imgs) > mlim else 'PASS', 'textures (excl. AvatarSkin_MAT)', len(imgs), f'<= {mlim}')
    if skin_imgs - other_imgs:
        add('INFO', 'AvatarSkin_MAT placeholder images', len(skin_imgs - other_imgs), 'not counted; replaced by player skin')
    for i in imgs:
        fmt, w, h, alpha = image_info(g, data, bs, i)
        nm = g['images'][i].get('name', i)
        bad = w != h or not 0 < w <= 1024
        pot = w > 0 and w & (w - 1) == 0
        level = 'FAIL' if bad else 'WARN' if not pot or (strict and w > 512) else 'PASS'
        add(level, f'texture {nm}', f'{fmt} {w}x{h}', 'square <= 1024, power of 2' + (', strict 512' if strict else ''))
    for m in counted:
        mode = m.get('alphaMode', 'OPAQUE')
        base = material_images(g, m).get('baseColorTexture')
        if mode == 'BLEND':
            add('WARN', f'material {m.get("name")} alphaMode', 'BLEND', 'prefer MASK (alpha clip) on the toon shader')
        if mode in ('MASK', 'BLEND') and base is not None and not image_info(g, data, bs, base)[3]:
            add('FAIL', f'material {m.get("name")} alpha', 'base color image has NO alpha channel',
                f'{mode} needs alpha: stale embedded RGB copy? recreate the image')
        if m.get('emissiveTexture') and base is None and not m.get('pbrMetallicRoughness', {}).get('baseColorFactor'):
            add('INFO', f'material {m.get("name")}', 'emission only', '')

    # Names that trigger the facial shader.
    names = [m.get('name', '') for m in mats] + [m.get('name', '') for m in g.get('meshes', [])] + [name(i) for i in range(len(nodes))]
    bad_names = sorted({n for n in names if any(f in n.lower() for f in FORBIDDEN)})
    add('FAIL' if bad_names else 'PASS', 'no _mouth/_eyebrows/_eyes names', bad_names or 'ok')

    # File contents.
    size = len(data)
    slim = 8 if is_skin else 2
    add('FAIL' if size > slim * 1048576 else 'PASS', 'model file size', f'{size / 1048576:.2f} MB', f'<= {slim} MB (server)')
    for key, label in (('animations', 'animations'), ('cameras', 'cameras')):
        add('WARN' if g.get(key) else 'PASS', f'no {label}', len(g.get(key, [])))
    lights = 'KHR_lights_punctual' in g.get('extensionsUsed', [])
    add('WARN' if lights else 'PASS', 'no lights', 'present' if lights else 0)
    shape_keys = sum(len(p.get('targets', [])) for m in g.get('meshes', []) for p in m['primitives'])
    add('WARN' if shape_keys else 'PASS', 'no shape keys', shape_keys)
    roots = [name(i) for i in g['scenes'][g.get('scene', 0)]['nodes']]
    add('PASS' if roots == ['Armature'] else 'WARN', 'scene root', roots, "['Armature']")
    unskinned = [name(i) for i, n in enumerate(nodes) if 'mesh' in n and 'skin' not in n]
    add('FAIL' if unskinned else 'PASS', 'every mesh skinned', unskinned or 'yes')

    # Skeleton.
    joints = {name(j) for s in g.get('skins', []) for j in s['joints']}
    all_bones = {name(i) for i in range(len(nodes)) if name(i).startswith('Avatar_') or is_spring(name(i))} | joints
    unknown = sorted(j for j in joints if j not in BONES and not is_spring(j))
    add('FAIL' if unknown else 'PASS', 'joints are Avatar_* or *springbone*', unknown or 'yes')
    leaf = sorted(n for n in all_bones if (n.endswith('_end') or n.endswith('_neutral')) and not is_spring(n))
    add('WARN' if leaf else 'PASS', 'no _end/_neutral leaf bones', leaf or 'none')
    missing = sorted(BONES - {name(i) for i in range(len(nodes))})
    add('WARN' if missing else 'PASS', 'full Avatar skeleton present', f'{len(missing)} missing' if missing else '62/62')

    # Skin weights: influences, unweighted vertices, finger-bone weights.
    jw = {}
    unweighted = extra_sets = 0
    for n in nodes:
        if 'mesh' not in n or 'skin' not in n:
            continue
        js = g['skins'][n['skin']]['joints']
        for p in g['meshes'][n['mesh']]['primitives']:
            at = p['attributes']
            if 'JOINTS_1' in at:
                extra_sets += 1
            if 'JOINTS_0' not in at:
                unweighted += g['accessors'][at['POSITION']]['count']
                continue
            J = accessor(g, data, bs, at['JOINTS_0']).astype(int)
            W = accessor(g, data, bs, at['WEIGHTS_0']).astype(float)
            unweighted += int((W.sum(1) < 1e-3).sum())
            for k in range(J.shape[1]):
                for j in np.unique(J[W[:, k] > 1e-4, k]):
                    nm = name(js[j])
                    jw[nm] = max(jw.get(nm, 0.0), float(W[J[:, k] == j, k].max()))
    add('FAIL' if extra_sets else 'PASS', '<= 4 influences (no JOINTS_1)', extra_sets)
    add('FAIL' if unweighted else 'PASS', 'unweighted vertices', unweighted, '0')
    fingers = sorted(n for n in jw if FINGER.search(n))
    if fingers and category != 'hands_wear' and 'hands' not in hides:
        add('WARN', 'weights on finger bones', fingers, 'intended? held items went "spiky" in-world')
    else:
        add('INFO', 'finger bones weighted', len(fingers))

    # Bounding box from POSITION extents (bind pose, glTF Y up).
    lo, hi = np.full(3, np.inf), np.full(3, -np.inf)
    for m in g.get('meshes', []):
        for p in m['primitives']:
            a = g['accessors'][p['attributes']['POSITION']]
            if 'min' in a:
                lo, hi = np.minimum(lo, a['min']), np.maximum(hi, a['max'])
    if np.isfinite(lo).all():
        w, h, d = hi - lo
        over = w > 2.42 or h > 2.42 or d > 1.4
        add('FAIL' if over else 'PASS', 'bounding box w x h x d', f'{w:.2f} x {h:.2f} x {d:.2f} m', '<= 2.42 x 2.42 x 1.4')

    # Spring bones.
    sp = lambda i: i is not None and is_spring(name(i))
    chains = []
    for i in range(len(nodes)):
        if sp(i) and not sp(par.get(i)):
            ch = [i]
            while True:
                kids = [c for c in nodes[ch[-1]].get('children', []) if sp(c)]
                if len(kids) != 1:
                    break
                ch.append(kids[0])
            chains.append(ch)
    if chains:
        n_spring = sum(1 for i in range(len(nodes)) if sp(i))
        depth = max(len(c) for c in chains)
        branching = [name(i) for i in range(len(nodes)) if sp(i) and sum(sp(c) for c in nodes[i].get('children', [])) > 1]
        def on_axis(t):
            L = max(1e-9, float(np.linalg.norm(t)))
            return t[1] > 0 and abs(t[0]) <= 1e-3 * L and abs(t[2]) <= 1e-3 * L
        offset = [name(i) for c in chains for i in c[1:] if not on_axis(nodes[i].get('translation', [0, 0, 0]))]
        short = [name(c[0]) for c in chains if len(c) < 2]
        bad_root = [name(c[0]) for c in chains if not name(par.get(c[0], 0)).startswith('Avatar_')]
        weighted_end = [name(c[-1]) for c in chains if jw.get(name(c[-1]), 0) > 1e-4]
        add('FAIL' if len(chains) > 6 else 'PASS', 'spring chains', len(chains), '<= 6')
        add('FAIL' if n_spring > 12 else 'PASS', 'spring bones (end bones count)', n_spring, '<= 12')
        add('FAIL' if depth > 6 else 'PASS', 'spring chain depth', depth, '<= 6')
        add('FAIL' if short else 'PASS', 'chains have an end bone', short or 'yes')
        add('FAIL' if branching else 'PASS', 'chains linear', branching or 'yes')
        add('FAIL' if offset else 'PASS', 'chains connected', offset or 'yes', 'child on parent bone axis')
        add('FAIL' if bad_root else 'PASS', 'chain roots parented to Avatar_*', bad_root or 'yes')
        add('FAIL' if weighted_end else 'PASS', 'end bones unweighted', weighted_end or 'yes')
        add('INFO', 'spring roots (enter params in Builder)', [name(c[0]) for c in chains])
    else:
        add('INFO', 'spring chains', 0)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('glb', nargs='+')
    ap.add_argument('--category', required=True, choices=sorted(CATEGORIES))
    ap.add_argument('--hides', default='', help='comma list of hidden categories (raises the triangle budget)')
    ap.add_argument('--strict', action='store_true', help='also warn on textures over 512 px')
    a = ap.parse_args()
    hides = [h for h in a.hides.split(',') if h]
    worst = 0
    for path in a.glb:
        print(os.path.basename(path))
        for level, label, value, rule in check(path, a.category, hides, a.strict):
            print(f'  {level:<4}  {label:<40} {str(value):<30} {rule}')
            worst |= level == 'FAIL'
    print('SOME FAILED' if worst else 'NO FAILS')
    sys.exit(1 if worst else 0)


if __name__ == '__main__':
    main()
