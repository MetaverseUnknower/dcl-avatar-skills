"""Runs the curator's check_clipping.py on one wearable (one body shape) exactly as the skill does, watches every frame
it measures, and picks + renders the frames a person should label:

  pos-deep     the detector's deepest clip in a clip          -> is the clip real?          (false positives)
  pos-shallow  the detector's shallowest clip above --depth   -> is the clip real?          (false positives)
  rest         a REST overlap the skill asks the agent to judge -> bug or fine?
  seam         overlap inside the rest-pose seams, grown during motion: the detector masks these out (misses)
  graze        the deepest contact under --depth                (misses near the threshold)
  control      a random frame of a gated clip the detector calls clean                        (misses, base rate)

usage: blender -b AvatarShape_A.blend --python probe.py -- --item <corpus>/<slug> --shape female --out <dir>
           [--checker .../check_clipping.py] [--depth 0.3] [--gate ...] [--only Idle,Walk] [--no-render]

Writes <out>/detector.json (the checker's own --json report), detector.log (its printed output), signals.json
(per clip and body part: deepest new overlap, shallowest clip, seam growth, deepest graze) and candidates.json with
the renders in <out>/img/. The checker's source is run unmodified except for one hook line after its per-frame
measure() call; if that line moves, this script stops and says so.
"""
import bpy, collections, contextlib, io, json, math, os, random, subprocess, sys
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CHECKER = os.path.join(HERE, '..', '..', 'skills', 'curating-dcl-wearables', 'scripts', 'check_clipping.py')
ANCHOR = '        m = measure(at_rest=False)\n'
SHOWCASE = {'upper_body': ['Outfit_Upper_v01', 'Outfit_Upper_v02', 'Outfit_Upper_v03'],
            'lower_body': ['Outfit_Lower_v01', 'Outfit_Lower_v02', 'Outfit_Lower_v03'],
            'feet': ['Outfit_Shoes_v01', 'Outfit_Shoes_v02'],
            'hands_wear': ['Outfit_Hand_v01', 'Outfit_Hand_v02'],
            'skin': ['Outfit_Upper_v01', 'Outfit_Lower_v01']}
ACCESSORY = ['Accessories_v01', 'Accessories_v02', 'Accessories_v03']


def default_gate(category):
    """The gate the skill tells the curator to use: Idle, Walk, Jog + the category's showcase clips."""
    return ','.join(['Idle', 'Walk', 'Jog'] + ['showcase_' + s for s in SHOWCASE.get(category, ACCESSORY)])


argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
import argparse
ap = argparse.ArgumentParser()
ap.add_argument('--item', required=True, help='corpus folder with item.json and <shape>.glb')
ap.add_argument('--shape', required=True, choices=['female', 'male'])
ap.add_argument('--out', required=True)
ap.add_argument('--checker', default=DEFAULT_CHECKER)
ap.add_argument('--anims', default=os.path.expanduser('~/.cache/dcl-animations'))
ap.add_argument('--depth', type=float, default=0.3)
ap.add_argument('--gate', default='', help='default: what the skill prescribes for the category')
ap.add_argument('--only', default='')
ap.add_argument('--max-pos', type=int, default=6)
ap.add_argument('--max-seam', type=int, default=3)
ap.add_argument('--max-rest', type=int, default=2)
ap.add_argument('--controls', type=int, default=2)
ap.add_argument('--seam-growth', type=float, default=0.5, help='cm a masked seam overlap must deepen to be probed')
ap.add_argument('--size', type=int, default=480)
ap.add_argument('--no-render', action='store_true')
A = ap.parse_args(argv)

item = json.load(open(os.path.join(A.item, 'item.json')))
shape = item['shapes'][A.shape]
glb = os.path.join(A.item, shape['glb'])
os.makedirs(os.path.join(A.out, 'img'), exist_ok=True)
gate = A.gate or default_gate(item['category'])
checker_args = ['--glb', glb, '--category', item['category'], '--anims', A.anims, '--gate', gate,
                '--depth', str(A.depth), '--json', os.path.join(A.out, 'detector.json')]
if shape['hides']:
    checker_args += ['--hides', ','.join(shape['hides'])]
if A.only:
    checker_args += ['--only', A.only]

# ---- the checker, with one hook line ----
src = open(A.checker).read()
if src.count(ANCHOR) != 1:
    sys.exit(f'probe: expected exactly one line {ANCHOR.strip()!r} in {A.checker}; update ANCHOR in probe.py')
src = src.replace(ANCHOR, ANCHOR + '        __probe__(name, i, m)\n')

G = {'__name__': '__main__', '__file__': A.checker}
SIG = collections.defaultdict(dict)          # (clip, label) -> {'deep': rec, 'shallow': rec, 'seam': rec, 'graze': rec}
REST_D = {}


def deepest_pair(pairs, sa, sb):
    best = (0.0, None, None)
    cross = G['crossing']
    for a, b in pairs:
        pa = [sa.vs[i] for i in sa.polys[a]]
        pb = [sb.vs[i] for i in sb.polys[b]]
        d = min(cross(pa, pb), cross(pb, pa))
        if d > best[0]:
            best = (d, a, b)
    return best


def poly_normal(s, p):
    v = [s.vs[i] for i in s.polys[p]]
    n = (v[1] - v[0]).cross(v[2] - v[0])
    return n.normalized() if n.length > 1e-12 else Vector((0, -1, 0))


def record(d, a, b, sa, sb, clip, frame):
    pt = (sa.centres[a] + sb.centres[b]) / 2
    return {'depth_cm': round(d * 100, 3), 'clip': clip, 'frame': frame, 'point': list(pt),
            'normal': list(poly_normal(sb, b))}


def hook(name, i, m):
    seams = G['SEAM']
    for label, (pairs, sa, sb) in m.items():
        if not pairs:
            continue
        if label not in REST_D:
            rp, ra, rb = G['rest'][label]
            REST_D[label] = deepest_pair(rp, ra, rb)[0] if rp else 0.0
        seam_a, seam_b = seams[label]
        new = [(a, b) for a, b in pairs if a not in seam_a or b not in seam_b]
        masked = [(a, b) for a, b in pairs if a in seam_a and b in seam_b]
        s = SIG[(name, label)]
        if new:
            d, a, b = deepest_pair(new, sa, sb)
            if a is not None:
                if d * 100 > A.depth:
                    if d * 100 > s.get('deep', {}).get('depth_cm', -1):
                        s['deep'] = record(d, a, b, sa, sb, name, i)
                    if d * 100 < s.get('shallow', {}).get('depth_cm', 1e9):
                        s['shallow'] = record(d, a, b, sa, sb, name, i)
                elif d * 100 > s.get('graze', {}).get('depth_cm', -1):
                    s['graze'] = record(d, a, b, sa, sb, name, i)
        if masked:
            d, a, b = deepest_pair(masked, sa, sb)
            if a is not None:
                growth = (d - REST_D[label]) * 100
                if growth > s.get('seam', {}).get('growth_cm', -1e9):
                    s['seam'] = record(d, a, b, sa, sb, name, i) | {'growth_cm': round(growth, 3),
                                                                     'rest_depth_cm': round(REST_D[label] * 100, 3)}


class CheckerExit(Exception):
    pass


def fake_exit(code=0):
    if isinstance(code, str):
        raise CheckerExit(code)
    G['__exit_code__'] = code


G['__probe__'] = hook
log = io.StringIO()
real_exit, real_argv = sys.exit, sys.argv
sys.exit, sys.argv = fake_exit, [real_argv[0], '--'] + checker_args
try:
    with contextlib.redirect_stdout(log):
        exec(compile(src, A.checker, 'exec'), G)
except CheckerExit as e:
    log.write(f'\nCHECKER EXIT: {e}\n')
finally:
    sys.exit, sys.argv = real_exit, real_argv
open(os.path.join(A.out, 'detector.log'), 'w').write(log.getvalue())
print(log.getvalue())
if 'report' not in G or 'clips' not in G:
    sys.exit('probe: the checker stopped early, see detector.log')
report = G['report']

# ---- pick candidates ----
rng = random.Random(f"{item['slug']}/{A.shape}")
gated = set(report['gated'])
clip_frames = dict(G['clips'])


def bare_hand(clip, frame, label):
    for c in report['clips'].get(clip, {}).get('clipping', []):
        if c['frame'] == frame:
            return any(k.startswith(label) and 'bare hand' in k for k in c['hits'])
    return False


def body_label(label):
    if ' x ' not in label:
        return 'any'
    other = label.split(' x ')[1]
    return 'self' if other == 'itself' or other in [o.name for o in G['items']] else 'body'


cands = []
def add(kind, detector, label, rec, **extra):
    cands.append({'id': f"{item['slug']}/{A.shape}/{kind}/{rec.get('clip', 'REST')}/{rec.get('frame', 0)}/{label}",
                  'kind': kind, 'detector': detector, 'label': label, 'pair': body_label(label),
                  'clip': rec.get('clip'), 'frame': rec.get('frame'), 'gated': rec.get('clip') in gated,
                  'depth_cm': rec.get('depth_cm'), 'point': rec.get('point'), 'normal': rec.get('normal'),
                  **{k: v for k, v in rec.items() if k in ('growth_cm', 'rest_depth_cm')}, **extra})


pos = []
for (clip, label), s in SIG.items():
    for k in ('deep', 'shallow'):
        if k in s and not (k == 'shallow' and s['shallow']['frame'] == s['deep']['frame']):
            pos.append((k, label, s[k]))
pos.sort(key=lambda p: (p[2]['clip'] not in gated, -p[2]['depth_cm'] if p[0] == 'deep' else p[2]['depth_cm']))
seen = collections.Counter()
for k, label, rec in pos:                 # spread over clips: at most one deep + one shallow per clip
    if sum(1 for c in cands if c['kind'].startswith('pos')) >= A.max_pos:
        break
    if seen[(rec['clip'], k)]:
        continue
    seen[(rec['clip'], k)] += 1
    add('pos-' + k, 'clip', label, rec, bare_hand=bare_hand(rec['clip'], rec['frame'], label))

seam = sorted(((label, s['seam']) for (clip, label), s in SIG.items()
               if 'seam' in s and s['seam']['growth_cm'] >= A.seam_growth), key=lambda x: -x[1]['growth_cm'])
used = set()
for label, rec in seam:
    if len([c for c in cands if c['kind'] == 'seam']) >= A.max_seam:
        break
    if rec['clip'] in used:
        continue
    used.add(rec['clip'])
    add('seam', 'clean', label, rec)

grazes = sorted(((label, s['graze']) for (clip, label), s in SIG.items() if 'graze' in s),
                key=lambda x: -x[1]['depth_cm'])
for label, rec in grazes[:1]:
    add('graze', 'clean', label, rec)

clean = []
for clip in sorted(gated):
    bad = {c['frame'] for c in report['clips'].get(clip, {}).get('clipping', [])}
    clean += [(clip, f) for f in range(len(clip_frames.get(clip, []))) if f not in bad]
for clip, f in rng.sample(clean, min(A.controls, len(clean))):
    add('control', 'clean', 'whole item', {'clip': clip, 'frame': f})

for label, r in sorted(report['rest'].items(), key=lambda kv: -kv[1]['depth_cm'])[:A.max_rest]:
    rp, ra, rb = G['rest'][label]
    d, a, b = deepest_pair(rp, ra, rb)
    if a is not None:
        add('rest', 'judge', label, record(d, a, b, ra, rb, None, None) | {'clip': None, 'frame': None})

# ---- render ----
def setup_render():
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.render.resolution_x = sc.render.resolution_y = A.size
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'
    sh = sc.display.shading
    sh.light, sh.color_type = 'STUDIO', 'TEXTURE'
    sh.show_backface_culling = False
    sh.show_cavity = True
    sh.background_type = 'VIEWPORT'
    sh.background_color = (0.16, 0.17, 0.19)
    hidden = set(G['body']) - set(G['visible'])
    for o in bpy.data.objects:
        if o.type != 'MESH' or o in G['items']:
            continue
        n = o.name.lower()
        o.hide_render = (G['part_key'](o) in hidden) or ('mask' in n and 'head' in hidden)
        o.hide_set(o.hide_render)                 # ray casts for camera placement skip hidden parts too
    cam = bpy.data.objects.new('ProbeCam', bpy.data.cameras.new('ProbeCam'))
    sc.collection.objects.link(cam)
    cam.data.lens, cam.data.clip_start = 40, 0.005
    sc.camera = cam
    return cam


def shoot(cam, eye, target, path):
    cam.location = eye
    cam.rotation_euler = (Vector(target) - Vector(eye)).to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def free_distance(pt, d, limit):
    """How far the line of sight from just off `pt` along `d` runs before hitting a visible mesh."""
    dg = bpy.context.evaluated_depsgraph_get()
    hit, loc, *_ = bpy.context.scene.ray_cast(dg, pt + d * 0.012, d, distance=limit)
    return (loc - pt).length if hit else limit


def clear_views(pt, n, close=0.45):
    """Three close-ups from directions with a clear line of sight to the overlap (an armpit overlap seen from the
    surface normal puts the camera inside the arm), then a context shot from outside the body."""
    n = n.normalized() if n.length > 1e-6 else Vector((0, -1, 0))
    dirs = []
    for tilt in (0, 35, -35, 70):
        for spin in range(0, 360, 30):
            d = Matrix.Rotation(math.radians(spin), 3, 'Z') @ Matrix.Rotation(math.radians(tilt), 3, 'X') @ n
            dirs.append(d.normalized())
    scored = sorted(((free_distance(pt, d, close + 0.1), d.dot(n), d) for d in dirs), key=lambda s: (-min(s[0], close), -s[1]))
    picks = []
    for free, _, d in scored:                    # clearest first, then most face-on; keep picks >= 50° apart
        if all(d.angle(p[0]) > math.radians(50) for p in picks):
            picks.append((d, max(0.12, min(close, free - 0.02))))
        if len(picks) == 3:
            break
    flat = Vector((picks[0][0].x, picks[0][0].y, 0.15))
    flat = flat.normalized() if flat.length > 0.2 else Vector((0, -1, 0.15)).normalized()
    return picks + [(flat, 1.8)]


def item_bounds():
    pts = []
    dg = bpy.context.evaluated_depsgraph_get()
    for o in G['items']:
        e = o.evaluated_get(dg)
        me = e.to_mesh()
        pts += [e.matrix_world @ v.co for v in me.vertices]
        e.to_mesh_clear()
    lo = Vector([min(p[k] for p in pts) for k in range(3)])
    hi = Vector([max(p[k] for p in pts) for k in range(3)])
    return (lo + hi) / 2, (hi - lo).length


if not A.no_render and cands:
    cam = setup_render()
    for c in cands:
        if c['clip'] is None:
            G['reset']()
        else:
            G['apply_pose'](*clip_frames[c['clip']][c['frame']])
        stem = c['id'].split('/', 2)[2].replace('/', '_').replace(' ', '')
        stem = ''.join(ch for ch in stem if ch.isalnum() or ch in '._-')[:120]
        c['images'] = []
        if c['kind'] == 'control':
            centre, size = item_bounds()
            dist = max(0.6, size * 1.3)
            for k, ang in enumerate((0, 90, 180, 270)):
                d = Matrix.Rotation(math.radians(ang), 3, 'Z') @ Vector((0, -1, 0.25)).normalized()
                p = os.path.join('img', f'{stem}_{k}.png')
                shoot(cam, centre + d * dist, centre, os.path.join(A.out, p))
                c['images'].append(p)
            continue
        pt, n = Vector(c['point']), Vector(c['normal'])
        views = clear_views(pt, n)
        for k, (d, dist) in enumerate(views):
            p = os.path.join('img', f'{stem}_{k}.png')
            shoot(cam, pt + d * dist, pt, os.path.join(A.out, p))
            c['images'].append(p)
    G['reset']()

try:
    checker_rev = subprocess.run(['git', '-C', os.path.dirname(A.checker), 'log', '-1', '--format=%h', '--',
                                  os.path.basename(A.checker)], capture_output=True, text=True).stdout.strip()
except Exception:
    checker_rev = ''
summary = {'item': item, 'shape': A.shape, 'blender': bpy.app.version_string, 'checker': os.path.abspath(A.checker),
           'checker_rev': checker_rev, 'depth_cm': A.depth, 'gate': gate,
           'gate_result': 'FAIL' if G.get('failed') else 'PASS', 'failed_clips': G.get('failed', []),
           'clips': {k: {kk: v[kk] for kk in ('status', 'gated', 'frames', 'deepest_cm', 'grazes')}
                     | {'clip_frames': len(v['clipping'])} for k, v in report['clips'].items()},
           'rest': report['rest'], 'candidates': cands}
json.dump(summary, open(os.path.join(A.out, 'candidates.json'), 'w'), indent=1)
json.dump({f'{c} | {l}': s for (c, l), s in SIG.items()}, open(os.path.join(A.out, 'signals.json'), 'w'), indent=1)
print(f"PROBE {item['slug']} {A.shape}: gate {summary['gate_result']}, {len(cands)} candidates -> {A.out}")
