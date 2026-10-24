"""Clipping check for a Decentraland wearable on the real avatar, through Decentraland's own animations.

usage (one body shape per run, with that shape's avatar .blend):
  blender -b <avatar.blend> --python check_clipping.py -- --glb item_female.glb --category upper_body \
      [--hides hands] [--anims ~/.cache/dcl-animations] [--samples 12] [--tol 4] [--json report.json]

Get the animations first with fetch_dcl_animations.py. The avatar .blend is the official base avatar for that body
shape (meshes named *uBody*, *lBody*, *Feet*, *Hands*, *Head* on the 62-bone `Armature`).

What it measures, per sampled frame (BVH triangle overlap on the evaluated meshes):
  1. item vs every base-body part the item doesn't hide;
  2. item part vs item part (separate loose pieces, e.g. a strap through its buckle).
Overlaps already present at rest are listed as REST lines for a person to judge: a collar tucked into the neck is
fine, a strap through a buckle is not. Posed frames count only overlaps outside those rest seams (grown 2 rings).
Idle/Walk/Jog gate (exit 1 on FAIL). Run and emotes are reported: the bare avatar intersects itself in some Run
frames, and rigid items can't clear every emote. Spring-bone geometry is checked at rest only (the explorer
simulates it in motion).
"""
import argparse, bpy, collections, glob, json, os, re, sys
from mathutils import Matrix, Quaternion, Vector
from mathutils.bvhtree import BVHTree

GATED = ('Idle', 'Walk', 'Jog')
LOCO = ('Idle', 'Walk', 'Jog', 'Run')
PARTS = {'ubody': 'upper_body', 'lbody': 'lower_body', 'feet': 'feet', 'hands': 'hands', 'head': 'head'}
COVERS = {'upper_body': ('ubody',), 'lower_body': ('lbody',), 'feet': ('feet',), 'skin': tuple(PARTS),
          'hands': ('hands',), 'head': ('head',), 'helmet': (), 'hat': (), 'mask': ()}
RINGS = 2

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument('--glb', required=True)
ap.add_argument('--category', required=True)
ap.add_argument('--hides', default='')
ap.add_argument('--anims', default=os.path.expanduser('~/.cache/dcl-animations'))
ap.add_argument('--samples', type=int, default=12, help='samples per locomotion cycle')
ap.add_argument('--emote-samples', type=int, default=8)
ap.add_argument('--tol', type=int, default=4, help='new overlapping triangle pairs tolerated per pair and frame')
ap.add_argument('--json')
A = ap.parse_args(argv)

av = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
P = av.pose.bones
MW = av.matrix_world.copy()
MWq = MW.to_quaternion()


# ---- base body: which parts the item leaves visible ----
def part_key(o):
    n = o.name.lower()
    return next((k for k in PARTS if k in n and 'mask' not in n), None)


body = {part_key(o): o for o in bpy.data.objects if o.type == 'MESH' and part_key(o)}
hidden = set(COVERS.get(A.category, ()))
for h in [h for h in A.hides.split(',') if h]:
    hidden |= set(COVERS.get(h, ()))
if A.category == 'upper_body' and 'hands' in A.hides.split(','):
    hidden.add('hands')
visible = {k: o for k, o in body.items() if k not in hidden}

# ---- import the item and bind it to the avatar's armature ----
before = set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=A.glb)
new = [o for o in bpy.data.objects if o not in before]
for o in new:
    if o.type == 'MESH':
        mw = o.matrix_world.copy()
        o.parent = av
        o.matrix_world = mw
        for m in o.modifiers:
            if m.type == 'ARMATURE':
                m.object = av
items = [o for o in new if o.type == 'MESH']
for o in [o for o in new if o.type != 'MESH']:
    bpy.data.objects.remove(o, do_unlink=True)
if not items:
    sys.exit('no meshes in ' + A.glb)
bones = {b.name for b in av.data.bones}


def spring_polys(o):
    """Polygons weighted to bones the avatar doesn't have (spring bones): they can't follow the pose here."""
    gname = {g.index: g.name for g in o.vertex_groups}
    loose = {v.index for v in o.data.vertices if any(g.weight > 1e-4 and gname[g.group] not in bones for g in v.groups)}
    return {p.index for p in o.data.polygons if any(v in loose for v in p.vertices)}


def welded(o):
    """Vertex -> id of its position: the glTF importer splits vertices at UV seams and hard edges."""
    ids = {}
    return [ids.setdefault(tuple(round(c, 5) for c in v.co), len(ids)) for v in o.data.vertices]


def islands(o):
    """Separate pieces of the item (loose parts after welding by position), as an id per polygon."""
    w = welded(o)
    parent = list(range(max(w) + 1 if w else 0))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for e in o.data.edges:
        a, b = find(w[e.vertices[0]]), find(w[e.vertices[1]])
        if a != b:
            parent[a] = b
    return [find(w[p.vertices[0]]) for p in o.data.polygons]


ITEM = {o.name: {'spring': spring_polys(o), 'island': islands(o)} for o in items}
for o in items:
    w = welded(o)
    ITEM[o.name]['corners'] = [frozenset(w[v] for v in p.vertices) for p in o.data.polygons]


def bvh(o, skip=()):
    dg = bpy.context.evaluated_depsgraph_get()
    e = o.evaluated_get(dg)
    me = e.to_mesh()
    vs = [e.matrix_world @ v.co for v in me.vertices]
    polys = [(0, 0, 0) if p.index in skip else tuple(p.vertices) for p in me.polygons]
    centres = [sum((vs[i] for i in p.vertices), Vector()) / len(p.vertices) for p in me.polygons]
    e.to_mesh_clear()
    return BVHTree.FromPolygons(vs, polys), centres


def grow(o, polys, rings=RINGS):
    by_vert = collections.defaultdict(set)
    for p in o.data.polygons:
        for v in p.vertices:
            by_vert[v].add(p.index)
    out = set(polys)
    for _ in range(rings):
        out |= {q for p in out for v in o.data.polygons[p].vertices for q in by_vert[v]}
    return out


def measure(at_rest):
    """{pair label: (set of (polyA, polyB), centres of A)} for item-body and item-part pairs."""
    out = {}
    cache = {}
    def get(o, skip=()):
        if o.name not in cache:
            cache[o.name] = bvh(o, skip)
        return cache[o.name]
    for o in items:
        skip = () if at_rest else ITEM[o.name]['spring']
        t, c = get(o, skip)
        for k, b in visible.items():
            out[f'{o.name} x {k}'] = (set(t.overlap(get(b)[0])), c)
        isl = ITEM[o.name]['island']
        cor = ITEM[o.name]['corners']
        out[f'{o.name} x itself'] = ({(a, b) for a, b in t.overlap(t) if a < b and isl[a] != isl[b] and not cor[a] & cor[b]}, c)
    for i, o in enumerate(items):
        for o2 in items[i + 1:]:
            out[f'{o.name} x {o2.name}'] = (set(get(o)[0].overlap(get(o2)[0])), get(o)[1])
    return out


def nearest_bone(o, poly):
    gname = {g.index: g.name for g in o.vertex_groups}
    w = collections.Counter()
    for v in o.data.polygons[poly].vertices:
        for g in o.data.vertices[v].groups:
            w[gname[g.group]] += g.weight
    return w.most_common(1)[0][0] if w else '?'


def where(label, pairs, centres):
    o = bpy.data.objects[label.split(' x ')[0]]
    a = sorted(pairs)[len(pairs) // 2][0]
    c = centres[a] * 100
    return f'{nearest_bone(o, a)} @ ({c.x:.0f}, {c.y:.0f}, {c.z:.0f}) cm'


# ---- poses from Decentraland's clips ----
def parse_anim(path):
    """Unity text .anim -> {bone: [[t, x, y, z, w], ...]} local rotation curves."""
    txt = open(path, errors='ignore').read()
    i = txt.find('  m_RotationCurves:')
    j = txt.find('\n  m_', i + 5)
    out = {}
    for item in txt[i:j].split('\n  - curve:')[1:]:
        pm = re.search(r'\n    path: (.*)', item)
        vals = re.findall(r'time: ([\d.e-]+)\n\s+value: \{x: ([^,]+), y: ([^,]+), z: ([^,]+), w: ([^}]+)\}', item)
        if pm and vals:
            out[pm.group(1).strip().split('/')[-1]] = [[float(v) for v in row] for row in vals]
    return out


def keyed(keys, t):
    if t <= keys[0][0]:
        return keys[0][1:]
    for a, b in zip(keys, keys[1:]):
        if t <= b[0]:
            f = (t - a[0]) / max(b[0] - a[0], 1e-9)
            q = Quaternion((a[4], a[1], a[2], a[3])).slerp(Quaternion((b[4], b[1], b[2], b[3])), f)
            return [q.x, q.y, q.z, q.w]
    return keys[-1][1:]


def reset():
    for pb in P:
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
        pb.scale = (1, 1, 1)
    bpy.context.view_layer.update()


def anim_poses(path, n):
    curves = parse_anim(path)
    if not curves:
        return []
    T = max(k[-1][0] for k in curves.values())
    poses = []
    for i in range(n):
        t = T * i / n if n > 1 else 0
        def apply(t=t):
            reset()
            for b in av.data.bones:
                if b.parent is not None and b.name in curves:
                    x, y, z, w = keyed(curves[b.name], t)
                    rest = (b.parent.matrix_local.inverted() @ b.matrix_local).to_quaternion()
                    P[b.name].rotation_quaternion = rest.inverted() @ Quaternion((w, x, -y, -z))
            bpy.context.view_layer.update()
        poses.append((i, apply))
    return poses


ORDER = []
def walk(b):
    ORDER.append(b.name)
    for c in b.children:
        walk(c)
for b in av.data.bones:
    if b.parent is None:
        walk(b)


def glb_poses(path, n):
    """Copy each bone's world rotation change from rest (independent of the importer's bone axes) + hips travel."""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    src = next((o for o in new if o.type == 'ARMATURE' and o.animation_data and o.animation_data.action), None)
    frames = []
    if src:
        f0, f1 = src.animation_data.action.frame_range
        SP, SW = src.pose.bones, src.matrix_world
        hips0 = SW @ src.data.bones['Avatar_Hips'].head_local if 'Avatar_Hips' in SP else None
        for i in range(n):
            bpy.context.scene.frame_set(int(round(f0 + (f1 - f0) * i / max(n - 1, 1))))
            bpy.context.view_layer.update()
            snap = {}
            for name in ORDER:
                if name in SP:
                    sb = src.data.bones[name]
                    d = (SW @ SP[name].matrix).to_quaternion() @ (SW @ sb.matrix_local).to_quaternion().inverted()
                    snap[name] = d
            hips_dw = (SW @ SP['Avatar_Hips'].head) - hips0 if hips0 is not None else Vector()
            frames.append((snap, hips_dw.copy()))
    for o in new:
        bpy.data.objects.remove(o, do_unlink=True)
    def make(snap, hips_dw):
        def apply():
            reset()
            for name in ORDER:
                if name not in snap:
                    continue
                tgt = MWq.inverted() @ snap[name] @ (MW @ av.data.bones[name].matrix_local).to_quaternion()
                head = P[name].matrix.translation.copy()
                if name == 'Avatar_Hips':
                    head = av.data.bones[name].head_local + MW.inverted().to_3x3() @ hips_dw
                P[name].matrix = Matrix.Translation(head) @ tgt.to_matrix().to_4x4()
                bpy.context.view_layer.update()
        return apply
    return [(i, make(s, h)) for i, (s, h) in enumerate(frames)]


clips = []
for path in sorted(glob.glob(os.path.join(A.anims, '*.anim')) + glob.glob(os.path.join(A.anims, '*.glb'))):
    name = os.path.splitext(os.path.basename(path))[0]
    n = A.samples if name in LOCO else A.emote_samples
    poses = anim_poses(path, n) if path.endswith('.anim') else glb_poses(path, n)
    if poses:
        clips.append((name, poses))
clips.sort(key=lambda c: (c[0] not in LOCO, LOCO.index(c[0]) if c[0] in LOCO else 0, c[0]))
if not any(c[0] in GATED for c in clips):
    sys.exit(f'no Idle/Walk/Jog clips in {A.anims}: run fetch_dcl_animations.py first')

def piece_info(o):
    """Per polygon: its piece id, and per piece a short description (size, location, bone)."""
    isl = ITEM[o.name]['island'] if o.name in ITEM else islands(o)
    by = collections.defaultdict(list)
    for p in o.data.polygons:
        by[isl[p.index]].append(p.index)
    mw = o.matrix_world
    desc = {}
    for k, polys in by.items():
        pts = [mw @ o.data.vertices[v].co for p in polys for v in o.data.polygons[p].vertices]
        lo = Vector((min(q.x for q in pts), min(q.y for q in pts), min(q.z for q in pts)))
        hi = Vector((max(q.x for q in pts), max(q.y for q in pts), max(q.z for q in pts)))
        c, size = (lo + hi) / 2 * 100, (hi - lo) * 100
        bone = nearest_bone(o, polys[len(polys) // 2])
        desc[k] = f'{len(polys)}-tri piece {size.x:.0f}x{size.y:.0f}x{size.z:.0f} cm on {bone} @ ({c.x:.0f}, {c.y:.0f}, {c.z:.0f})'
    return isl, desc


_pieces = {}
def pieces(label, pairs, top=int(os.environ.get("CLIP_TOP", "8"))):
    a_name, b_name = label.split(' x ')
    oa = bpy.data.objects[a_name]
    ob = oa if b_name == 'itself' else bpy.data.objects[b_name]
    for o in (oa, ob):
        if o.name not in _pieces:
            _pieces[o.name] = piece_info(o)
    ia, da = _pieces[oa.name]
    ib, db = _pieces[ob.name]
    groups = collections.Counter((ia[a], ib[b]) for a, b in pairs)
    lines = [f'{n:>4} pairs: {da[x]}  x  {db[y]}' for (x, y), n in groups.most_common(top)]
    if len(groups) > top:
        lines.append(f'... and {len(groups) - top} more piece pairs')
    return lines


# ---- rest: seams + the overlaps someone has to judge ----
reset()
rest = measure(at_rest=True)
SEAM = {}
report = {'glb': A.glb, 'category': A.category, 'visible_body': sorted(visible), 'rest': {}, 'clips': {}}
print(f'CLIP {os.path.basename(A.glb)} ({A.category}) vs body parts {sorted(visible)}')
for label, (pairs, centres) in rest.items():
    oa = bpy.data.objects[label.split(' x ')[0]]
    other = label.split(' x ')[1]
    ob = oa if other == 'itself' else visible.get(other) or bpy.data.objects.get(other)
    SEAM[label] = (grow(oa, {a for a, b in pairs}), grow(ob, {b for a, b in pairs}))
    if pairs:
        is_item = other == 'itself' or other in [o.name for o in items]
        if is_item:
            print(f'  REST  {label:<44} {len(pairs):>4} triangle pairs, by piece:')
            for line in pieces(label, pairs):
                print('          ' + line)
            print('          -> judge each: a strap/plate/buckle passing through another piece is a bug; '
                  'a piece lying on cloth it is sewn to is fine')
        else:
            print(f'  REST  {label:<44} {len(pairs):>4} triangle pairs near {where(label, pairs, centres)}'
                  '  -> a tuck into the body (collar, cuff, hem)? fine if the item covers it')
        report['rest'][label] = {'pairs': len(pairs), 'near': where(label, pairs, centres),
                                 'pieces': pieces(label, pairs) if is_item else []}

# ---- poses ----
failed = []
hands = body.get('hands')      # hidden or not: this asks whether Decentraland's own bare hand is in its own thigh
lbody = body.get('lbody')
for name, poses in clips:
    bad = []
    for i, apply in poses:
        apply()
        m = measure(at_rest=False)
        bare_hand_thigh = False
        if hands is not None and lbody is not None:
            bare_hand_thigh = bool(bvh(hands)[0].overlap(bvh(lbody)[0]))
        hits = {}
        for label, (pairs, centres) in m.items():
            sa, sb = SEAM[label]
            new_pairs = {(a, b) for a, b in pairs if a not in sa or b not in sb}
            if len(new_pairs) > A.tol:
                tag = ' (bare hand already in thigh)' if bare_hand_thigh and ('hands' in label or 'lbody' in label) else ''
                hits[label + tag] = (len(new_pairs), where(label, new_pairs, centres))
        if hits:
            bad.append((i, hits))
    total = len(poses)
    gated = name in GATED
    real = [b for b in bad if any('bare hand' not in k for k in b[1])]
    status = ('FAIL' if real else 'PASS') if gated else ('REPORT' if bad else 'PASS')
    if gated and real:
        failed.append(name)
    print(f'  {status:<6} {name:<20} {len(bad)}/{total} frames clip')
    for i, hits in bad[:6]:
        for label, (n, near) in hits.items():
            print(f'         frame {i:>2}: {label:<44} {n:>4} pairs near {near}')
    report['clips'][name] = {'status': status, 'frames': total,
                             'clipping': [{'frame': i, 'hits': {k: {'pairs': n, 'near': w} for k, (n, w) in h.items()}}
                                          for i, h in bad]}
reset()
print('CLIP GATE ' + ('FAIL: ' + ', '.join(failed) if failed else 'PASS (Idle/Walk/Jog)') +
      ' | REST overlaps listed above need a judgment | Run + emotes are reported, not gated')
if A.json:
    json.dump(report, open(A.json, 'w'), indent=1)
sys.exit(1 if failed else 0)
