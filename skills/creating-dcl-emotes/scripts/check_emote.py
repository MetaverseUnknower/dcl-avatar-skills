#!/usr/bin/env python3
"""Check exported emote GLBs against Decentraland's documented rules (see ../requirements.md) and past pitfalls.

usage: python3 check_emote.py <glb> [<glb> ...] [--loop] [--audio <file>]

FAIL = breaks a docs/server rule. WARN = Builder warning, size headroom or a known in-world failure. INFO = numbers.
Exit code 1 if anything FAILs. This reads only the GLB: run verify_space.py / check_limbs.py / check_props.py in
Blender as well for the 4x4 m box and clipping on the real meshes.
"""
import argparse, json, os, re, struct, sys
import numpy as np

SIDES = ('Left', 'Right')
BONES = {f'Avatar_{b}' for b in ('Hips', 'Spine', 'Spine1', 'Spine2', 'Neck', 'Head')}
BONES |= {f'Avatar_{s}{b}' for s in SIDES for b in ('Shoulder', 'Arm', 'ForeArm', 'Hand', 'UpLeg', 'Leg', 'Foot', 'ToeBase')}
BONES |= {f'Avatar_{s}Hand{f}{i}' for s in SIDES for f in ('Thumb', 'Index', 'Middle', 'Ring', 'Pinky') for i in range(1, 5)}
ARMATURES = {'Armature', 'Armature_Prop', 'Armature_Other'}
CLIP_NAME = re.compile(r'^[A-Z][A-Za-z0-9]*(_[A-Z0-9][A-Za-z0-9]*)*$')
COMP = {5121: np.uint8, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NCOMP = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}
MB = 1048576


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
    arr = np.frombuffer(raw.tobytes(), dt).reshape(a['count'], k).astype(float)
    if a.get('normalized') and dt.kind == 'i':
        arr = np.maximum(arr / np.iinfo(dt).max, -1)
    return arr


def quat_rotate(q, v):
    x, y, z, w = q
    u = np.array([x, y, z])
    return v + 2 * np.cross(u, np.cross(u, v) + w * v)


def image_size(g, data, bs, i):
    im = g['images'][i]
    if 'bufferView' not in im:
        return 0, 0
    bv = g['bufferViews'][im['bufferView']]
    d = data[bs + bv.get('byteOffset', 0):][:24]
    return struct.unpack('>II', d[16:24]) if d[:4] == b'\x89PNG' else (0, 0)


def check(path, loop, audio):
    g, data, bs = load(path)
    rows = []
    add = lambda level, label, value, rule='': rows.append((level, label, value, rule))
    nodes = g['nodes']
    name = lambda i: nodes[i].get('name', '')
    par = {c: i for i, n in enumerate(nodes) for c in n.get('children', [])}

    def armature_of(i):
        while i in par:
            i = par[i]
        return name(i)

    # Size: the GLB is the model; audio + thumbnail share the 3 MB item total.
    size = len(data)
    total = size + (os.path.getsize(audio) if audio else 0)
    add('FAIL' if size > 2 * MB else 'WARN' if size > MB else 'PASS', 'model file size', f'{size / MB:.2f} MB',
        '<= 2 MB server; warn over 1 MB (export keyed channels only)')
    if audio:
        add('FAIL' if total > 3 * MB else 'PASS', 'GLB + audio', f'{total / MB:.2f} MB', '<= 3 MB item total')
        ext = os.path.splitext(audio)[1].lower()
        add('PASS' if ext in ('.mp3', '.ogg') else 'FAIL', 'audio format', ext, '.mp3 or .ogg, same length as clip')

    # Armatures.
    roots = [name(i) for i in g['scenes'][g.get('scene', 0)]['nodes']]
    bad_roots = [r for r in roots if r not in ARMATURES]
    add('FAIL' if bad_roots or 'Armature' not in roots else 'PASS', 'scene roots', roots, 'Armature [+ Armature_Prop]')
    has_prop = 'Armature_Prop' in roots

    # Clips.
    anims = g.get('animations', [])
    names = [a.get('name', '') for a in anims]
    if has_prop:
        stems = {n.rsplit('_', 1)[0] for n in names}
        ok = len(anims) == 2 and {n.rsplit('_', 1)[-1] for n in names} == {'Avatar', 'Prop'} and len(stems) == 1
        add('PASS' if ok else 'FAIL', 'clips', names, '<Name>_Avatar + <Name>_Prop')
    else:
        add('PASS' if len(anims) == 1 else 'FAIL', 'clips', names, 'exactly 1')
    for n in names:
        if not CLIP_NAME.match(n):
            add('WARN', f'clip name {n}', 'not Capitalized_Words', 'e.g. Rainbow_Dance')

    spans = {}
    for a in anims:
        ins = [g['accessors'][s['input']] for s in a['samplers']]
        t0, t1 = min(i['min'][0] for i in ins), max(i['max'][0] for i in ins)
        keys = max(i['count'] for i in ins)
        dur = t1 - t0
        fps = (keys - 1) / dur if dur > 0 else 0
        spans[a['name']] = (t0, t1, keys)
        add('FAIL' if dur > 10 + 1e-6 else 'PASS', f'{a["name"]} length', f'{dur:.3f} s', '<= 10 s (hard error)')
        add('FAIL' if keys > 300 else 'PASS', f'{a["name"]} frames', keys, '<= 300')
        add('PASS' if abs(fps - 30) <= 5 else 'WARN', f'{a["name"]} fps (keys / length)', f'{fps:.1f}', '30 (Builder estimates this way)')
    if has_prop and len(spans) == 2:
        (a0, a1, ak), (b0, b1, bk) = spans.values()
        same = abs(a1 - b1) < 1e-4 and abs(a0 - b0) < 1e-4
        add('PASS' if same else 'FAIL', 'avatar and prop clip same length', 'yes' if same else f'{a1 - a0:.3f} vs {b1 - b0:.3f}')

    avatar = next((a for a in anims if a['name'].endswith('_Avatar')), anims[0] if len(anims) == 1 else None)
    if avatar:
        t0, t1, _ = spans[avatar['name']]
        foreign = sorted({name(c['target']['node']) for c in avatar['channels'] if armature_of(c['target']['node']) != 'Armature'})
        if foreign:
            add('FAIL', 'avatar clip animates non-avatar nodes', foreign[:6])
        targets = {name(c['target']['node']) for c in avatar['channels']}
        unknown = sorted(t for t in targets if t not in BONES and armature_of_name(nodes, t) == 'Armature')
        if unknown:
            add('WARN', 'avatar clip animates unknown bones', unknown[:6], 'only the 62 Avatar_* deform bones')
        # Builder: deform bones should be keyed at the first and last frame.
        edge = {}
        for c in avatar['channels']:
            tt = accessor(g, data, bs, avatar['samplers'][c['sampler']]['input'])[:, 0]
            n = name(c['target']['node'])
            hit = edge.setdefault(n, [False, False])
            hit[0] |= abs(tt[0] - t0) < 1e-4
            hit[1] |= abs(tt[-1] - t1) < 1e-4
        missing = sorted(b for b in BONES if not all(edge.get(b, [False, False])))
        add('WARN' if missing else 'PASS', 'deform bones keyed at first+last frame', f'{len(missing)} missing' if missing else '62/62',
            'Builder warning; docs ask for all')

    # Per-channel motion checks across every clip.
    jumps, scale_hi, seams = [], (1.0, ''), []
    root_tf = {name(i): nodes[i] for i in g['scenes'][g.get('scene', 0)]['nodes']}
    hips_travel = hips_top = None
    for a in anims:
        chans = {}
        for c in a['channels']:
            s = a['samplers'][c['sampler']]
            v = accessor(g, data, bs, s['output'])
            chans[(c['target']['node'], c['target']['path'])] = (
                accessor(g, data, bs, s['input'])[:, 0], v[1::3] if s.get('interpolation') == 'CUBICSPLINE' else v)

        def hidden(i, tt):
            # Visible size of node i at times tt: its own scale x every ancestor's (props hide at 0.001).
            out = np.ones(len(tt))
            while i is not None:
                if (i, 'scale') in chans:
                    st, sv = chans[(i, 'scale')]
                    out *= np.interp(tt, st, np.abs(sv).max(1))   # static scales (the 0.01 unit root) don't hide
                i = par.get(i)
            return out < 0.02

        for (ni, path_), (t, v) in chans.items():
            n = name(ni)
            if path_ == 'rotation' and len(v) > 1:
                q = v / np.linalg.norm(v, axis=1, keepdims=True)
                ang = np.degrees(2 * np.arccos(np.clip(np.abs((q[1:] * q[:-1]).sum(1)), 0, 1)))
                hid = hidden(ni, t)
                ang[hid[1:] | hid[:-1]] = 0
                k = int(ang.argmax())
                if ang[k] > 90:
                    jumps.append(f'{n} {ang[k]:.0f}deg @ {t[k]:.2f}-{t[k + 1]:.2f}s')
                if loop and np.degrees(2 * np.arccos(min(1, abs(float(q[0] @ q[-1]))))) > 2:
                    seams.append(f'{n}.rot')
            if path_ == 'scale' and armature_of(ni) == 'Armature':
                m = float(v.max())
                if m > scale_hi[0]:
                    scale_hi = (m, n)
            if path_ in ('translation', 'scale') and loop and np.abs(v[0] - v[-1]).max() > (0.5 if path_ == 'translation' else 0.01):
                seams.append(f'{n}.{path_[:5]}')
            if n == 'Avatar_Hips' and path_ == 'translation':
                rt = root_tf.get('Armature', {})
                rq = rt.get('rotation', [0, 0, 0, 1])
                rs = np.array(rt.get('scale', [1, 1, 1]))
                w = np.array([quat_rotate(rq, p * rs) for p in v])
                hips_travel = float(np.linalg.norm((w - w[0])[:, [0, 2]], axis=1).max())
                hips_top = float(w[:, 1].max())
    add('WARN' if jumps else 'PASS', 'rotation jumps between keys (>90deg)', jumps[:5] or 'none',
        'players interpolate: a flip sweeps through in-world')
    add('WARN' if scale_hi[0] > 4 else 'INFO', 'largest avatar bone scale', f'{scale_hi[0]:.2f} {scale_hi[1]}',
        'cross-fade blends scale linearly: big counter-scales balloon' if scale_hi[0] > 4 else '')
    if hips_travel is not None:
        add('FAIL' if hips_travel > 1 else 'PASS', 'hips horizontal travel', f'{hips_travel:.2f} m', '<= 1 m')
        add('FAIL' if hips_top > 4 else 'INFO', 'hips highest point', f'{hips_top:.2f} m', '<= 4 m')
    if loop:
        add('WARN' if seams else 'PASS', 'loop seam: first key == last key', seams[:8] or 'all match', 'run check_loop.py too')

    # Meshes and props.
    meshes = [i for i, n in enumerate(nodes) if 'mesh' in n]
    if not has_prop:
        add('FAIL' if meshes else 'PASS', 'no meshes without Armature_Prop', len(meshes))
    else:
        tris, mats = 0, set()
        for i in meshes:
            for p in g['meshes'][nodes[i]['mesh']]['primitives']:
                c = g['accessors'][p['indices']]['count'] if 'indices' in p else g['accessors'][p['attributes']['POSITION']]['count']
                tris += c // 3
                if 'material' in p:
                    mats.add(p['material'])
        add('FAIL' if tris > 3000 else 'PASS', 'prop triangles', tris, '<= 3000')
        add('FAIL' if len(mats) > 2 else 'PASS', 'prop materials', len(mats), '<= 2')
        imgs = g.get('images', [])
        add('FAIL' if len(imgs) > 2 else 'PASS', 'prop textures', len(imgs), '<= 2')
        for i in range(len(imgs)):
            w, h = image_size(g, data, bs, i)
            add('FAIL' if w != h or not 0 < w <= 1024 else 'PASS', f'texture {imgs[i].get("name", i)}', f'{w}x{h}', 'square <= 1024')
        pskin = next((s for s in g.get('skins', []) if armature_of(s['joints'][0]) == 'Armature_Prop'), None)
        if pskin:
            add('FAIL' if len(pskin['joints']) > 62 else 'PASS', 'prop bones', len(pskin['joints']), '<= 62')
        unskinned = [name(i) for i in meshes if 'skin' not in nodes[i]]
        add('FAIL' if unskinned else 'PASS', 'prop meshes skinned to Armature_Prop', unskinned or 'yes', 'bone animation only')
        two_sided = [m.get('name') for m in g.get('materials', []) if m.get('doubleSided')]
        if two_sided:
            add('WARN', 'doubleSided materials', two_sided, 'ignored on emote props: build real back faces')
        obj_anim = sorted({name(c['target']['node']) for a in anims for c in a['channels'] if 'mesh' in nodes[c['target']['node']]})
        add('FAIL' if obj_anim else 'PASS', 'no object animation on meshes', obj_anim or 'none')
    return rows


def armature_of_name(nodes, nm):
    par = {c: i for i, n in enumerate(nodes) for c in n.get('children', [])}
    i = next((k for k, n in enumerate(nodes) if n.get('name') == nm), None)
    while i in par:
        i = par[i]
    return nodes[i].get('name', '') if i is not None else ''


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('glb', nargs='+')
    ap.add_argument('--loop', action='store_true', help='emote is set to Loop: compare first and last keys')
    ap.add_argument('--audio', help='the .mp3/.ogg shipped with it (counts toward 3 MB)')
    a = ap.parse_args()
    worst = False
    for path in a.glb:
        print(os.path.basename(path))
        for level, label, value, rule in check(path, a.loop, a.audio):
            print(f'  {level:<4}  {label:<40} {str(value):<30} {rule}')
            worst |= level == 'FAIL'
    print('SOME FAILED' if worst else 'NO FAILS')
    sys.exit(1 if worst else 0)


if __name__ == '__main__':
    main()
