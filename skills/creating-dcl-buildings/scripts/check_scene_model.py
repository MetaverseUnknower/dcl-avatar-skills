#!/usr/bin/env python3
"""Check a scene model GLB (building, furniture or decor) against Decentraland's rules (see ../requirements.md).

usage: python3 check_scene_model.py <glb> --kind building|furniture|decor [--footprint 1x1] [--type chair]
                                    [--sittables <file>.sittables.json]

FAIL = breaks a rule that makes the model wrong in-world (a collider that doesn't collide, a texture the explorer
mangles, a seat people get pushed off) or a hard deploy limit. WARN = over a recommendation (triangles, materials,
textures: Decentraland's scene limits are soft, so these never fail). INFO = numbers to read. Exit 1 on any FAIL.
Walkability (stairs, doorways, floors) is check_walk.py's job.
"""
import argparse
import json
import math
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glbscene  # noqa: E402

PARCEL_M = 16.0
FOOTPRINTS = {'0.5x0.5': (8.0, 8.0), '1x1': (16.0, 16.0), '1x2': (16.0, 32.0), '2x2': (32.0, 32.0), '4x4': (64.0, 64.0)}
# Recommended triangles for a piece (soft): about 30% of the footprint's 10,000 a parcel for a building
TRIS = {'chair': 800, 'stool': 800, 'table': 800, 'bench': 1000, 'couch': 1500, 'sofa': 1500, 'bed': 1500,
        'shelf': 800, 'lamp': 400, 'decor': 300}
FURNITURE_TRIS, BUILDING_SHARE = 1500, 0.3
MAX_MATERIALS, MAX_TEXTURES = 3, 2
HARD_FILE_BYTES = 50 * 1024 * 1024          # Decentraland refuses a deploy with a bigger file
SOFT_FILE_BYTES = 2 * 1024 * 1024           # a furniture piece much over this is heavy for what it is
FLOOR_TOL, CENTRE_TOL, FOOTPRINT_TOL = 0.02, 0.05, 0.01
# The avatar about to sit stands at the seat's position: nothing may collide in this column there
STAND_RADIUS, STAND_LOW, STAND_HIGH = 0.15, 0.05, 1.7
COLLISIONS, KINDS = ('model', 'colliders', 'stool'), ('stool', 'couch', 'bench')


def parse_footprint(text):
    if text not in FOOTPRINTS:
        raise ValueError(f'footprint must be one of {", ".join(FOOTPRINTS)} (parcels, X by Z)')
    return FOOTPRINTS[text]


def pow2(n):
    return n > 0 and n & (n - 1) == 0


def image_size(g, data, bs, i):
    im = g['images'][i]
    if 'bufferView' not in im:
        return None
    bv = g['bufferViews'][im['bufferView']]
    d = data[bs + bv.get('byteOffset', 0):][:bv['byteLength']]
    if d[:4] == b'\x89PNG':
        return struct.unpack('>II', d[16:24])
    if d[:2] == b'\xff\xd8':
        j = 2
        while j < len(d) - 9:
            if d[j] == 0xFF and d[j + 1] in (0xC0, 0xC1, 0xC2):
                h, w = struct.unpack('>HH', d[j + 5:j + 9])
                return w, h
            j += 2 + struct.unpack('>H', d[j + 2:j + 4])[0]
    return (0, 0)


def seat_column(seat, yaw):
    """Points filling the column where a sitter stands, in the model's frame. The model faces +Z; a sitter's right is
    -X (glTF), forward +Z, up +Y; yawOffset 180 turns that round."""
    sign = -1 if round(yaw) % 360 == 180 else 1
    x, z, y0 = -seat['across'] * sign, seat['forward'] * sign, seat.get('rise', 0)
    ring = [(0, 0)] + [(STAND_RADIUS * math.cos(a), STAND_RADIUS * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 8, endpoint=False)]
    hs = np.arange(y0 + STAND_LOW, y0 + STAND_HIGH + 1e-9, 0.1)
    return np.array([(x + dx, h, z + dz) for h in hs for dx, dz in ring])


def check_sittables(path, visible, solids):
    rows = []
    add = lambda *r: rows.append(r)
    try:
        model = json.loads(open(path).read())
    except (OSError, ValueError) as e:
        add('FAIL', 'sittables', os.path.basename(path), f'not readable JSON: {e}')
        return rows
    seats = model.get('seats')
    problems = []
    if not isinstance(seats, list) or not seats:
        problems.append('needs at least one seat')
    elif not all(isinstance(s, dict) and all(isinstance(s.get(k), (int, float)) for k in ('across', 'forward')) for s in seats):
        problems.append('every seat needs numeric across and forward')
    if model.get('collision') not in COLLISIONS:
        problems.append(f"collision must be one of {', '.join(COLLISIONS)}")
    if model.get('kind') not in KINDS:
        problems.append(f"kind must be one of {', '.join(KINDS)}")
    if problems:
        add('FAIL', 'sittables', os.path.basename(path), '; '.join(problems))
        return rows
    add('PASS', 'sittables', f"{len(seats)} seat(s), {model['collision']}, {model['kind']}")
    if model.get('scale', 1) != 1 or model.get('uprightX', 0) != 0 or round(model.get('yawOffset', 0)) % 360 not in (0, 180):
        add('WARN', 'sittables orientation', f"scale {model.get('scale', 1)}, uprightX {model.get('uprightX', 0)}, yawOffset {model.get('yawOffset', 0)}",
            'export at scale 1, Y up, facing +Z (yawOffset 0) so the numbers mean what they say')
    yaw = model.get('yawOffset', 0)
    for i, seat in enumerate(seats):
        if model['collision'] == 'stool':
            add('INFO', f'seat {i} standing spot', 'collision stool', 'the kit adds the step and pole collider')
            continue
        pts = seat_column(seat, yaw)
        if model['collision'] == 'colliders':
            blocked = int(glbscene.inside_any(pts, solids, margin=0.005).sum())
            what = 'a collider'
        else:  # the visible mesh collides: any of it inside the column
            x, z, y0 = pts[0][0], pts[0][2], pts[0][1]
            v = visible
            near = (np.hypot(v[:, 0] - x, v[:, 2] - z) < STAND_RADIUS) & (v[:, 1] > y0) & (v[:, 1] < y0 + STAND_HIGH)
            blocked, what = int(near.sum()), 'the visible mesh'
        add('FAIL' if blocked else 'PASS', f'seat {i} standing spot', f'{blocked} point(s) inside {what}' if blocked else 'clear',
            'nothing may collide where the sitter stands (they get pushed off): trim the collider short of it')
    return rows


def check(path, kind, footprint=None, type_=None, sittables=None):
    rows = []
    add = lambda *r: rows.append(r)
    all_parts, g, data, bs = glbscene.parts(path)
    colliders = [p for p in all_parts if p.collider]
    visible = [p for p in all_parts if not p.collider]
    near_miss = sorted({p.name for p in visible if 'collider' in p.name.lower()})

    # Colliders
    if kind == 'decor':
        add('PASS' if colliders else 'INFO', 'colliders', len(colliders), 'optional for small decor')
    else:
        add('PASS' if colliders else 'FAIL', 'colliders', len(colliders),
            'at least one *_collider mesh, or visitors walk through it')
    if near_miss:
        add('FAIL', 'collider names', near_miss, "must END in _collider (Blender's .001 copies don't count): renamed, they collide; as is, they render")
    solids = []
    for p in colliders:
        if p.material is not None:
            add('FAIL', f'collider {p.name} material', 'has one', 'collider meshes have no material')
        pieces = glbscene.components(p)
        sheet = glbscene.sheets(p)
        add('PASS' if not sheet else 'FAIL', f'collider {p.name} closed',
            'yes' if not sheet else f'{len(sheet)} one-sided face(s), first at {np.round(sheet[0][0], 2).tolist()}',
            'solid shapes (boxes): a plane blocks from one side only')
        convex = all(glbscene.is_convex(v, f) for v, f in pieces)
        add('PASS' if convex else 'WARN', f'collider {p.name} convex', f'{len(pieces)} piece(s)' if convex else 'concave',
            'each separate piece convex (split L shapes into boxes): the docs say concave colliders stutter')
        solids += [glbscene.planes(v, f) for v, f in pieces]

    # Placement
    vis = np.vstack([p.verts for p in visible]) if visible else np.vstack([p.verts for p in all_parts])
    every = np.vstack([p.verts for p in all_parts])
    lo, hi = vis.min(0), vis.max(0)
    size = hi - lo
    add('PASS' if abs(lo[1]) <= FLOOR_TOL else 'FAIL', 'origin on the floor', f'lowest point y {lo[1]:+.3f} m',
        'the model stands on y 0 (apply transforms; origin at floor level)')
    add('INFO', 'size w x h x d', f'{size[0]:.2f} x {size[1]:.2f} x {size[2]:.2f} m')
    if kind == 'building':
        w, d = parse_footprint(footprint)
        ehi, elo = every.max(0), every.min(0)
        inside = elo[0] >= -w / 2 - FOOTPRINT_TOL and ehi[0] <= w / 2 + FOOTPRINT_TOL and \
            elo[2] >= -d / 2 - FOOTPRINT_TOL and ehi[2] <= d / 2 + FOOTPRINT_TOL
        add('PASS' if inside else 'FAIL', 'inside the footprint', f'x {elo[0]:.2f}..{ehi[0]:.2f}, z {elo[2]:.2f}..{ehi[2]:.2f}',
            f'{footprint} = {w:g} x {d:g} m centred on the origin: anything outside its parcels is cut off in-world')
        if ehi[1] > 330:
            add('FAIL', 'height', f'{ehi[1]:.1f} m', '<= 330 m')
    else:
        cx, cz = (lo[0] + hi[0]) / 2, (lo[2] + hi[2]) / 2
        ok = abs(cx) <= max(CENTRE_TOL, 0.05 * size[0]) and abs(cz) <= max(CENTRE_TOL, 0.05 * size[2])
        add('PASS' if ok else 'FAIL', 'origin under the middle', f'centre x {cx:+.2f}, z {cz:+.2f}',
            'the origin sits under the middle of the piece, so it places and rotates where people expect')

    # Weight (soft)
    tris = sum(len(p.faces) for p in visible)
    if kind == 'building':
        w, d = parse_footprint(footprint)
        rec = int(BUILDING_SHARE * (w * d / PARCEL_M ** 2) * 10_000)
    else:
        rec = TRIS.get((type_ or '').lower(), TRIS['decor'] if kind == 'decor' else FURNITURE_TRIS)
    add('PASS' if tris <= rec else 'WARN', 'triangles', tris, f'recommended <= {rec} (visible; Decentraland only warns)')
    add('INFO', 'collider triangles', sum(len(p.faces) for p in colliders))
    used = sorted({p.material for p in visible if p.material is not None})
    mats = g.get('materials', [])
    add('PASS' if len(mats) <= MAX_MATERIALS else 'WARN', 'materials', len(mats),
        f'recommended <= {MAX_MATERIALS}: one swatch material, plus metal/glass/glow only when needed')
    for m in mats:
        name = m.get('name', '?')
        if m.get('alphaMode') == 'BLEND':
            add('WARN', f'material {name} alphaMode', 'BLEND', 'MASK (alpha clip) unless it must be see-through glass')
        if m.get('doubleSided'):
            add('WARN', f'material {name} doubleSided', 'on', 'backface culling on, except true two-sided cards (leaves)')
    images = g.get('images', [])
    add('PASS' if len(images) <= MAX_TEXTURES else 'WARN', 'textures', len(images), f'recommended <= {MAX_TEXTURES}')
    for i in range(len(images)):
        s = image_size(g, data, bs, i)
        if s is None:
            add('WARN', f'texture {i}', 'external file', 'embed it, or ship the file beside the GLB')
            continue
        ok = pow2(s[0]) and pow2(s[1]) and max(s) <= 1024
        add('PASS' if ok else 'FAIL', f'texture {i}', f'{s[0]}x{s[1]}', 'each side a power of two, <= 1024')
    size_b = os.path.getsize(path)
    if size_b > HARD_FILE_BYTES:
        add('FAIL', 'model file size', f'{size_b / 1048576:.1f} MB', '<= 50 MB (Decentraland refuses the deploy)')
    else:
        soft = int(BUILDING_SHARE * 15 * 1048576 * (w * d / PARCEL_M ** 2)) if kind == 'building' else SOFT_FILE_BYTES
        add('PASS' if size_b <= soft else 'WARN', 'model file size', f'{size_b / 1048576:.2f} MB', f'recommended <= {soft / 1048576:.1f} MB')

    if sittables:
        rows += check_sittables(sittables, vis, solids)
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('glb')
    ap.add_argument('--kind', required=True, choices=('building', 'furniture', 'decor'))
    ap.add_argument('--footprint', help=f'buildings: {", ".join(FOOTPRINTS)}')
    ap.add_argument('--type', dest='type_', help=f'furniture type for its triangle recommendation: {", ".join(TRIS)}')
    ap.add_argument('--sittables', help='the dcl-sittables FurnitureModel JSON for this piece')
    a = ap.parse_args(argv)
    if a.kind == 'building' and not a.footprint:
        ap.error('--footprint is required for a building')
    rows = check(a.glb, a.kind, a.footprint, a.type_, a.sittables)
    print(os.path.basename(a.glb))
    for level, label, value, *rule in rows:
        print(f'  {level:<4}  {label:<40} {str(value):<30} {rule[0] if rule else ""}')
    worst = any(r[0] == 'FAIL' for r in rows)
    print('SOME FAILED' if worst else 'NO FAILS')
    return 1 if worst else 0


if __name__ == '__main__':
    sys.exit(main())
