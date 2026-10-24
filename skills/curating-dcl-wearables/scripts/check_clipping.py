"""Clipping check for a Decentraland wearable on the real avatar, through Decentraland's own animations.

usage (one body shape per run, with that shape's avatar .blend):
  blender -b <avatar.blend> --python check_clipping.py -- --glb item_female.glb --category upper_body \
      [--hides hands] [--anims ~/.cache/dcl-animations] [--gate Idle,Walk,Jog | all] [--except KO,SittingChair_v01] \
      [--depth 0.3] [--fps 30] [--only dance,wave] [--json report.json]

Get the animations first with fetch_dcl_animations.py: locomotion, the explorer's built-in emotes, the emote-wheel
emotes and the per-category showcase animations. The avatar .blend is the official base avatar for that body shape
(meshes named *uBody*, *lBody*, *Feet*, *Hands*, *Head* on the 62-bone `Armature`).

Every clip is sampled at --fps (30 = every frame the players key). Each frame, BVH triangle overlap on the
evaluated meshes:
  1. item vs every base-body part the item doesn't hide;
  2. item piece vs item piece (separate loose pieces, e.g. a strap through its buckle).
Each overlap gets a DEPTH: how far the triangles pass through each other (the shallower side of the crossing, in
cm). A frame clips when some overlap outside the rest-pose seams is deeper than --depth; shallower contacts are
grazes and only counted.
Overlaps already present at rest are listed as REST lines for a person to judge: a collar tucked into the neck is
fine, a strap through a buckle is not.
--gate picks the clips that must pass (exit 1 if one fails); the rest are reported. Default Idle,Walk,Jog: the bare
avatar intersects itself in some Run frames, and rigid items can't clear every emote. `--gate all --except ...`
makes every other clip must-pass. Spring-bone geometry is checked at rest only (the explorer simulates it).
"""
import argparse, bpy, collections, glob, json, math, os, re, sys
from mathutils import Matrix, Quaternion, Vector
from mathutils.bvhtree import BVHTree

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
ap.add_argument('--gate', default='Idle,Walk,Jog', help="clips that must pass, comma list, or 'all'")
ap.add_argument('--except', dest='exempt', default='', help='clips left out of --gate all')
ap.add_argument('--only', default='', help='check just these clips (comma list)')
ap.add_argument('--depth', type=float, default=0.3, help='cm: deeper overlaps clip, shallower ones are grazes')
ap.add_argument('--fps', type=float, default=30, help='samples per second of animation (30 = every frame)')
ap.add_argument('--json')
A = ap.parse_args(argv)
csv = lambda s: [x.strip() for x in s.split(',') if x.strip()]

av = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
P = av.pose.bones
MW = av.matrix_world.copy()
MWq = MW.to_quaternion()
bpy.context.scene.render.fps = int(round(A.fps)) if A.fps >= 1 else 30


# ---- base body: which parts the item leaves visible ----
def part_key(o):
    n = o.name.lower()
    return next((k for k in PARTS if k in n and 'mask' not in n), None)


body = {part_key(o): o for o in bpy.data.objects if o.type == 'MESH' and part_key(o)}
hidden = set(COVERS.get(A.category, ()))
for h in csv(A.hides):
    hidden |= set(COVERS.get(h, ()))
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


class Snap:
    """One mesh evaluated in the current pose: BVH, world vertices, polygon corners and centres."""
    def __init__(self, o, skip=()):
        dg = bpy.context.evaluated_depsgraph_get()
        e = o.evaluated_get(dg)
        me = e.to_mesh()
        self.vs = [e.matrix_world @ v.co for v in me.vertices]
        self.polys = [tuple(p.vertices) for p in me.polygons]
        e.to_mesh_clear()
        self.tree = BVHTree.FromPolygons(self.vs, [(0, 0, 0) if i in skip else p for i, p in enumerate(self.polys)])
        self.centres = [sum((self.vs[i] for i in p), Vector()) / len(p) for p in self.polys]


def crossing(pa, pb):
    """How far polygon pa passes through pb's plane, on its shallower side (0 if it doesn't straddle it)."""
    n = (pb[1] - pb[0]).cross(pb[2] - pb[0])
    if n.length < 1e-12:
        return 0.0
    n.normalize()
    d = [(p - pb[0]).dot(n) for p in pa]
    hi, lo = max(d), min(d)
    return min(hi, -lo) if hi > 0 and lo < 0 else 0.0


def depth(pairs, sa, sb):
    """Deepest crossing among the pairs, in metres (each pair: the smaller of the two polygons' crossings)."""
    best = 0.0
    for a, b in pairs:
        pa = [sa.vs[i] for i in sa.polys[a]]
        pb = [sb.vs[i] for i in sb.polys[b]]
        best = max(best, min(crossing(pa, pb), crossing(pb, pa)))
    return best


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
    """{pair label: (set of (polyA, polyB), Snap A, Snap B)} for item-body and item-part pairs."""
    out, cache = {}, {}
    def get(o, skip=()):
        if o.name not in cache:
            cache[o.name] = Snap(o, skip)
        return cache[o.name]
    for o in items:
        sa = get(o, () if at_rest else ITEM[o.name]['spring'])
        for k, b in visible.items():
            sb = get(b)
            out[f'{o.name} x {k}'] = (set(sa.tree.overlap(sb.tree)), sa, sb)
        isl, cor = ITEM[o.name]['island'], ITEM[o.name]['corners']
        out[f'{o.name} x itself'] = ({(a, b) for a, b in sa.tree.overlap(sa.tree)
                                      if a < b and isl[a] != isl[b] and not cor[a] & cor[b]}, sa, sa)
    for i, o in enumerate(items):
        for o2 in items[i + 1:]:
            out[f'{o.name} x {o2.name}'] = (set(get(o).tree.overlap(get(o2).tree)), get(o), get(o2))
    return out


def nearest_bone(o, poly):
    gname = {g.index: g.name for g in o.vertex_groups}
    w = collections.Counter()
    for v in o.data.polygons[poly].vertices:
        for g in o.data.vertices[v].groups:
            w[gname[g.group]] += g.weight
    return w.most_common(1)[0][0] if w else '?'


def where(label, pairs, snap):
    o = bpy.data.objects[label.split(' x ')[0]]
    a = sorted(pairs)[len(pairs) // 2][0]
    c = snap.centres[a] * 100
    return f'{nearest_bone(o, a)} @ ({c.x:.0f}, {c.y:.0f}, {c.z:.0f}) cm'


# ---- poses from Decentraland's clips ----
ORDER = []
def walk(b):
    ORDER.append(b.name)
    for c in b.children:
        walk(c)
for b in av.data.bones:
    if b.parent is None:
        walk(b)
REST_REL = {b.name: (b.parent.matrix_local.inverted() @ b.matrix_local).to_quaternion() if b.parent else
            b.matrix_local.to_quaternion() for b in av.data.bones}
REST_ARM = {b.name: (MW @ b.matrix_local).to_quaternion() for b in av.data.bones}


def reset():
    for pb in P:
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
        pb.scale = (1, 1, 1)
    bpy.context.view_layer.update()


def apply_pose(local, hips_loc=None):
    """Set every bone's pose rotation at once, then evaluate the scene a single time."""
    for pb in P:
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = local.get(pb.name, Quaternion())
        pb.location = (0, 0, 0)
        pb.scale = (1, 1, 1)
    if hips_loc is not None:
        P['Avatar_Hips'].location = hips_loc
    bpy.context.view_layer.update()


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


def anim_frames(path):
    curves = parse_anim(path)
    if not curves:
        return []
    T = max(k[-1][0] for k in curves.values())
    frames = []
    for i in range(max(1, int(T * A.fps) + 1)):
        t = i / A.fps
        local = {}
        for name, keys in curves.items():
            if name in REST_REL and av.data.bones[name].parent is not None:
                x, y, z, w = keyed(keys, t)
                local[name] = REST_REL[name].inverted() @ Quaternion((w, x, -y, -z))
        frames.append((local, None))
    return frames


def to_local(arm, hips_world_delta):
    """Armature-space target rotations (+ hips travel in world metres) -> pose rotations and hips location."""
    local = {}
    for name in ORDER:
        if name not in arm:
            continue
        b = av.data.bones[name]
        if b.parent is None:
            local[name] = b.matrix_local.to_quaternion().inverted() @ arm[name]
        elif b.parent.name in arm:
            local[name] = REST_REL[name].inverted() @ arm[b.parent.name].inverted() @ arm[name]
    hb = av.data.bones['Avatar_Hips']
    head = hb.head_local + MW.inverted().to_3x3() @ hips_world_delta
    return local, hb.matrix_local.to_quaternion().inverted() @ (head - hb.head_local)


def gltf_world(path):
    """A glTF file's Avatar_* nodes in world space (Blender axes: glTF Y-up -> Z-up), from the nodes' own TRS with
    the file's first animation sampled on top. Returns (world(t) -> (rotations, hips position), duration);
    world(None) is the un-animated node pose."""
    import struct
    data = open(path, 'rb').read()
    n = struct.unpack('<I', data[12:16])[0]
    g = json.loads(data[20:20 + n])
    bs = 20 + n + 8
    def acc(i):
        a = g['accessors'][i]
        bv = g['bufferViews'][a['bufferView']]
        k = {'SCALAR': 1, 'VEC3': 3, 'VEC4': 4}[a['type']]
        off = bs + bv.get('byteOffset', 0) + a.get('byteOffset', 0)
        stride = bv.get('byteStride', 4 * k)
        return [struct.unpack_from('<' + 'f' * k, data, off + j * stride) for j in range(a['count'])]
    nodes = g['nodes']
    parent = {c: i for i, nd in enumerate(nodes) for c in nd.get('children', [])}
    rest = [(Vector(nd.get('translation', (0, 0, 0))), Quaternion(nd['rotation'][3:] + nd['rotation'][:3])
             if 'rotation' in nd else Quaternion(), Vector(nd.get('scale', (1, 1, 1)))) for nd in nodes]
    tracks = collections.defaultdict(dict)
    T = 0.0
    anim = g['animations'][0] if g.get('animations') else {'channels': [], 'samplers': []}
    for ch in anim['channels']:
        smp = anim['samplers'][ch['sampler']]
        if ch['target']['path'] not in ('rotation', 'translation'):
            continue
        times = [t[0] for t in acc(smp['input'])]
        vals = acc(smp['output'])
        if smp.get('interpolation') == 'CUBICSPLINE':
            vals = vals[1::3]
        tracks[ch['target']['node']][ch['target']['path']] = (times, vals, smp.get('interpolation', 'LINEAR'))
        T = max(T, times[-1])
    def sample(track, t, rot):
        times, vals, interp = track
        if t <= times[0]:
            v = vals[0]
        elif t >= times[-1]:
            v = vals[-1]
        else:
            j = next(k for k in range(1, len(times)) if times[k] >= t)
            f = (t - times[j - 1]) / max(times[j] - times[j - 1], 1e-9)
            a, b = vals[j - 1], vals[j]
            if interp == 'STEP':
                v = a
            elif rot:
                return Quaternion((a[3], a[0], a[1], a[2])).slerp(Quaternion((b[3], b[0], b[1], b[2])), f)
            else:
                v = [x + (y - x) * f for x, y in zip(a, b)]
        return Quaternion((v[3], v[0], v[1], v[2])) if rot else Vector(v)
    C = Matrix.Rotation(math.radians(90), 4, 'X')        # glTF Y-up -> Blender Z-up
    named = {nd.get('name'): i for i, nd in enumerate(nodes) if nd.get('name') in REST_ARM}
    def world(t):
        local = {}
        for i, (tr, rq, sc) in enumerate(rest):
            if t is not None and i in tracks:
                tr = sample(tracks[i]['translation'], t, False) if 'translation' in tracks[i] else tr
                rq = sample(tracks[i]['rotation'], t, True) if 'rotation' in tracks[i] else rq
            local[i] = Matrix.LocRotScale(tr, rq, sc)
        cache = {}
        def w(i):
            if i not in cache:
                cache[i] = (w(parent[i]) @ local[i]) if i in parent else local[i]
            return cache[i]
        rots = {name: (C @ w(i)).to_quaternion() for name, i in named.items()}
        return rots, (C @ w(named['Avatar_Hips'])).translation.copy()
    return world, T


# Unskinned emote files (the emote-wheel ones) store their FIRST FRAME as the node TRS and carry no bind pose, so
# their rest can't come from themselves. The wearable under test is exported in the rest pose on the same rig: its
# node TRS is the bind pose every emote frame is measured against.
BIND_ROT, BIND_HIPS = gltf_world(A.glb)[0](None)


def gltf_node_frames(path):
    world, T = gltf_world(path)
    steps = max(1, int(T * A.fps) + 1)
    return (BIND_ROT, BIND_HIPS), [world(k / A.fps) for k in range(steps)]


def glb_frames(path):
    """Copy each bone's world rotation change from its rest (independent of the importer's bone axes) + hips travel,
    converted straight to pose-space rotations so a frame costs one scene update. Skinned emotes import as an
    armature; unskinned ones (the emote-wheel files) as a hierarchy of animated empties."""
    before = set(bpy.data.objects)
    acts_before = set(bpy.data.actions)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    src = next((o for o in new if o.type == 'ARMATURE' and o.animation_data and o.animation_data.action), None)
    empties = {o.name.split('.')[0]: o for o in new if o.type == 'EMPTY' and o.name.split('.')[0] in REST_ARM}
    frames = []
    if src and 'Avatar_Hips' in src.pose.bones:
        f0, f1 = (int(round(f)) for f in src.animation_data.action.frame_range)
        SP, SW = src.pose.bones, src.matrix_world
        rest_rot = {n: (SW @ src.data.bones[n].matrix_local).to_quaternion() for n in ORDER if n in SP}
        hips0 = SW @ src.data.bones['Avatar_Hips'].head_local
        def sample():
            cur = {n: (SW @ SP[n].matrix).to_quaternion() for n in rest_rot}
            return cur, (SW @ SP['Avatar_Hips'].head) - hips0
    elif 'Avatar_Hips' in empties:
        (rest_rot, hips0), samples = gltf_node_frames(path)
        hips_start = samples[0][1]
        for cur, hips in samples:
            arm = {nm: MWq.inverted() @ (cur[nm] @ rest_rot[nm].inverted()) @ REST_ARM[nm] for nm in cur if nm in rest_rot}
            frames.append(to_local(arm, hips - hips_start))     # travel from where the emote starts
        f0, f1, sample = 0, -1, None
    else:
        f0, f1, sample = 0, -1, None
    for f in range(f0, f1 + 1):
        bpy.context.scene.frame_set(f)
        cur, hips_dw = sample()
        arm = {n: MWq.inverted() @ (cur[n] @ rest_rot[n].inverted()) @ REST_ARM[n] for n in cur}
        frames.append(to_local(arm, hips_dw.copy()))
    for o in new:
        bpy.data.objects.remove(o, do_unlink=True)
    for act in set(bpy.data.actions) - acts_before:
        bpy.data.actions.remove(act)
    return frames


only = set(csv(A.only))
clips = []
for path in sorted(glob.glob(os.path.join(A.anims, '*.anim')) + glob.glob(os.path.join(A.anims, '*.glb'))):
    name = os.path.splitext(os.path.basename(path))[0]
    if name.lower() in ('idle', 'walk', 'run') and name not in LOCO:
        continue                                          # the preview's copies of the locomotion clips
    if only and name not in only:
        continue
    frames = anim_frames(path) if path.endswith('.anim') else glb_frames(path)
    if frames:
        clips.append((name, frames))
clips.sort(key=lambda c: (c[0] not in LOCO, LOCO.index(c[0]) if c[0] in LOCO else 0, c[0].startswith('showcase_'), c[0].lower()))
names = [c[0] for c in clips]
gate = set(names) - set(csv(A.exempt)) if A.gate == 'all' else set(csv(A.gate)) & set(names)
if not clips:
    sys.exit(f'no clips in {A.anims}: run fetch_dcl_animations.py first')
for g in [g for g in csv(A.gate) if A.gate != 'all' and g not in names and not only]:
    print(f'warning: gated clip {g} not found in {A.anims}')


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
def pieces(label, pairs, sa, sb, top=int(os.environ.get('CLIP_TOP', '8'))):
    a_name, b_name = label.split(' x ')
    oa = bpy.data.objects[a_name]
    ob = oa if b_name == 'itself' else bpy.data.objects[b_name]
    for o in (oa, ob):
        if o.name not in _pieces:
            _pieces[o.name] = piece_info(o)
    ia, da = _pieces[oa.name]
    ib, db = _pieces[ob.name]
    groups = collections.defaultdict(list)
    for a, b in pairs:
        groups[(ia[a], ib[b])].append((a, b))
    ranked = sorted(groups.items(), key=lambda kv: -depth(kv[1], sa, sb))
    lines = [f'{len(ps):>4} pairs, {depth(ps, sa, sb) * 100:.1f} cm deep: {da[x]}  x  {db[y]}' for (x, y), ps in ranked[:top]]
    if len(groups) > top:
        lines.append(f'... and {len(groups) - top} more piece pairs')
    return lines


# ---- rest: seams + the overlaps someone has to judge ----
reset()
rest = measure(at_rest=True)
SEAM = {}
report = {'glb': A.glb, 'category': A.category, 'visible_body': sorted(visible), 'depth_cm': A.depth,
          'gated': sorted(gate), 'rest': {}, 'clips': {}}
print(f'CLIP {os.path.basename(A.glb)} ({A.category}) vs body parts {sorted(visible)}; '
      f'{len(clips)} clips at {A.fps:g} fps; clips deeper than {A.depth} cm')
for label, (pairs, sa, sb) in rest.items():
    oa = bpy.data.objects[label.split(' x ')[0]]
    other = label.split(' x ')[1]
    ob = oa if other == 'itself' else visible.get(other) or bpy.data.objects.get(other)
    SEAM[label] = (grow(oa, {a for a, b in pairs}), grow(ob, {b for a, b in pairs}))
    if pairs:
        is_item = other == 'itself' or other in [o.name for o in items]
        d = depth(pairs, sa, sb) * 100
        if is_item:
            print(f'  REST  {label:<44} {len(pairs):>4} triangle pairs, up to {d:.1f} cm deep, by piece:')
            for line in pieces(label, pairs, sa, sb):
                print('          ' + line)
            print('          -> judge each: a strap/plate/buckle passing through another piece is a bug; '
                  'a piece lying on cloth it is sewn to is fine')
        else:
            print(f'  REST  {label:<44} {len(pairs):>4} triangle pairs, up to {d:.1f} cm deep near '
                  f'{where(label, pairs, sa)}  -> a tuck into the body (collar, cuff, hem)? fine if the item covers it')
        report['rest'][label] = {'pairs': len(pairs), 'depth_cm': round(d, 2), 'near': where(label, pairs, sa),
                                 'pieces': pieces(label, pairs, sa, sb) if is_item else []}

# ---- every frame of every clip ----
failed = []
hands, lbody = body.get('hands'), body.get('lbody')   # hidden or not: is Decentraland's own bare hand in its thigh?
for name, frames in clips:
    bad, grazes, worst = [], 0, 0.0
    for i, (local, hips_loc) in enumerate(frames):
        apply_pose(local, hips_loc)
        m = measure(at_rest=False)
        bare_hand_thigh = None
        hits = {}
        for label, (pairs, sa, sb) in m.items():
            seam_a, seam_b = SEAM[label]
            new_pairs = {(a, b) for a, b in pairs if a not in seam_a or b not in seam_b}
            if not new_pairs:
                continue
            d = depth(new_pairs, sa, sb)
            if d * 100 <= A.depth:
                grazes += 1
                continue
            if bare_hand_thigh is None:
                bare_hand_thigh = bool(hands and lbody and Snap(hands).tree.overlap(Snap(lbody).tree))
            tag = ' (bare hand already in thigh)' if bare_hand_thigh and ('hands' in label or 'lbody' in label) else ''
            hits[label + tag] = (len(new_pairs), d * 100, where(label, new_pairs, sa))
            worst = max(worst, d * 100)
        if hits:
            bad.append((i, hits))
    real = [b for b in bad if any('bare hand' not in k for k in b[1])]
    must = name in gate
    status = ('FAIL' if real else 'PASS') if must else ('REPORT' if bad else 'PASS')
    if must and real:
        failed.append(name)
    print(f'  {status:<6} {name:<28} {len(bad):>3}/{len(frames):<3} frames clip  deepest {worst:.1f} cm'
          + (f'  ({grazes} grazes under {A.depth} cm)' if grazes else ''))
    for i, hits in sorted(bad, key=lambda b: -max(h[1] for h in b[1].values()))[:4]:
        for label, (n, d, near) in hits.items():
            print(f'         frame {i:>3}: {label:<44} {d:4.1f} cm deep, {n:>3} pairs near {near}')
    report['clips'][name] = {'status': status, 'gated': must, 'frames': len(frames), 'deepest_cm': round(worst, 2),
                             'grazes': grazes,
                             'clipping': [{'frame': i, 'hits': {k: {'pairs': n, 'depth_cm': round(d, 2), 'near': w}
                                                                 for k, (n, d, w) in h.items()}} for i, h in bad]}
reset()
print('CLIP GATE ' + ('FAIL: ' + ', '.join(failed) if failed else f'PASS ({len(gate)} gated clips)') +
      ' | REST overlaps above need a judgment | ungated clips are reported')
if A.json:
    json.dump(report, open(A.json, 'w'), indent=1)
sys.exit(1 if failed else 0)
