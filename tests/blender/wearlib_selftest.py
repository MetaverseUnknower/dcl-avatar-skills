# Self-test for skills/creating-dcl-wearables/scripts/wearlib.py, run inside Blender on an official avatar .blend:
#   blender -b AvatarShape_A.blend --python-exit-code 1 --python tests/blender/wearlib_selftest.py -- <outdir> <scripts dir> <A|B>
# Prints one "SELFTEST PASS|FAIL <name>" line per check and "SELFTEST RESULT PASS|FAIL" at the end.
import bpy, math, os, subprocess, sys
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:]
OUT, SCRIPTS, SHAPE = argv[0], argv[1], argv[2]
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, SCRIPTS)
from wearlib import *   # noqa: E402,F403

fails = []
def check(name, ok, info=''):
    print(f"SELFTEST {'PASS' if ok else 'FAIL'} {name} {info}".rstrip())
    if not ok:
        fails.append(name)

def run_checker(glb, category, hides=None):
    cmd = [sys.executable, os.path.join(SCRIPTS, 'check_wearable.py'), glb, '--category', category]
    if hides:
        cmd += ['--hides', hides]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    print(proc.stdout)
    return proc.returncode == 0, proc

def ring_tube(path, radius, sides=8):
    """Closed tube (verts, faces) along path with a tapering radius, for test geometry."""
    verts, faces, rings = [], [], []
    n = len(path)
    for i, p in enumerate(path):
        d = (path[min(i + 1, n - 1)] - path[max(i - 1, 0)]).normalized()
        a = Vector((1, 0, 0)); a = (a - a.dot(d) * d).normalized(); b = d.cross(a)
        r = radius * (1 - .7 * i / (n - 1))
        rings.append([len(verts) + j for j in range(sides)])
        verts += [p + (a * math.cos(math.tau * j / sides) + b * math.sin(math.tau * j / sides)) * r for j in range(sides)]
    for i in range(n - 1):
        for j in range(sides):
            faces.append((rings[i][j], rings[i][(j + 1) % sides], rings[i + 1][(j + 1) % sides], rings[i + 1][j]))
    for end, ring in ((0, rings[0]), (1, rings[-1])):
        c = len(verts); verts.append(path[0] if end == 0 else path[-1])
        faces += [(c, ring[(j + 1) % sides], ring[j]) if end == 0 else (c, ring[j], ring[(j + 1) % sides]) for j in range(sides)]
    return verts, faces

print('SELFTEST blender', bpy.app.version_string)

# ---- the avatar
check('body_shape matches the file', body_shape() == SHAPE, f'({body_shape()})')
check('shape_suffix', shape_suffix() == ('female' if SHAPE == 'A' else 'male'))
head = base('Head')
check('base() finds every base mesh', all(base(p).type == 'MESH' for p in BASE_PARTS))
hv = arm_space_verts(head)
top = max(v.y for v in hv)
front = max(v.z for v in hv)
tree = bvh_of([head])
hit = tree.ray_cast(Vector((0, top - 12, front + 20)), Vector((0, 0, -1)))
check('bvh_of: a ray from in front of the face hits the head', hit[0] is not None)

# ---- barycentric weight copy reproduces the base mesh's own weights at its vertices
names = {g.index: g.name for g in head.vertex_groups}
sample = weights_from(head)
worst = 0.0
for i in range(0, len(hv), max(1, len(hv) // 40)):
    own = {names[g.group]: g.weight for g in head.data.vertices[i].groups if g.weight > 0}
    tot = sum(own.values()) or 1.0
    got = sample(hv[i])
    for b in set(own) | set(got):
        worst = max(worst, abs(own.get(b, 0) / tot - got.get(b, 0)))
check('weights_from returns the base weights at base vertices', worst < 1e-3, f'(max diff {worst:.2e})')
check('weights_from blends neck into the jaw underside',
      any('Avatar_Neck' in sample(v) for v in hv if v.y < top - 15), '(Avatar_Neck present low on the head)')

# ---- set_weights keeps the 4 strongest influences, normalised
tmp = new_mesh_obj('SelfTest_Tmp', [(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2)],
                   weights=[{'Avatar_Hips': .1, 'Avatar_Spine': .2, 'Avatar_Spine1': .3, 'Avatar_Spine2': .4,
                             'Avatar_Neck': .5, 'Avatar_Head': .6}] * 3)
vw = [g.weight for g in tmp.data.vertices[0].groups]
check('set_weights keeps 4 influences, normalised', len(vw) == 4 and abs(sum(vw) - 1) < 1e-5, f'({len(vw)}, sum {sum(vw):.3f})')
bpy.data.objects.remove(tmp, do_unlink=True)

# ---- hair tuft on a spring chain: build, weight along the chain, export, check
back = min((v for v in hv if v.y > top - 8), key=lambda v: v.z)
path = [back + Vector((0, 0, 1.5)) + Vector((0, -5.0 * k, -2.5 * k)) for k in range(5)]
bones = add_spring_chain('Tuft_springbone', path)
check('add_spring_chain makes deform bones + an end bone',
      bones == ['Tuft_springbone_01', 'Tuft_springbone_02', 'Tuft_springbone_03'] and
      'Tuft_springbone_end' in armature().data.bones and not armature().data.bones['Tuft_springbone_end'].use_deform)
verts, faces = ring_tube(path, 2.0)
w = chain_weights(path, [(.15, 'Avatar_Head'), (.35, bones[0]), (.6, bones[1]), (.85, bones[2])])
tuft = new_mesh_obj('SelfTest_Tuft', verts, faces, uvs=[(.5, .5)] * len(verts), weights=w,
                    mats=[bpy.data.materials.new('SelfTest_Hair')])
reset_pose()
glb = export_wearable([tuft], OUT, 'SelfTestTuft')
ok, proc = run_checker(glb, 'hair')
check('spring-chain hair passes check_wearable.py --category hair', ok, proc.stdout[-400:] if not ok else '')
check('checker sees the spring chain', 'chains have an end bone' in proc.stdout and 'end bones unweighted' in proc.stdout)

# ---- rigid back pendant filed as an earring (a carried prop becomes its own accessory)
for o in (tuft,):
    bpy.data.objects.remove(o, do_unlink=True)
av = armature()
bpy.context.view_layer.objects.active = av
bpy.ops.object.mode_set(mode='EDIT')
for b in [b for b in av.data.edit_bones if 'springbone' in b.name]:
    av.data.edit_bones.remove(b)
bpy.ops.object.mode_set(mode='OBJECT')
ub = arm_space_verts(base('uBody'))
spine_back = min((v for v in ub if abs(v.x) < 4 and 125 < v.y < 140), key=lambda v: v.z)
c = spine_back + Vector((0, 0, -3))
bx = [c + Vector((sx * 3, sy * 4, sz * 1.5)) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
bf = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
pend = new_mesh_obj('SelfTest_Pendant', bx, bf, uvs=[(.5, .5)] * 8, weights=rigid('Avatar_Spine2'),
                    mats=[bpy.data.materials.new('SelfTest_Steel')])
glb2 = export_wearable([pend], OUT, 'SelfTestPendant')
ok2, proc2 = run_checker(glb2, 'earring')
check('rigid back piece passes check_wearable.py --category earring', ok2, proc2.stdout[-400:] if not ok2 else '')

print(f"SELFTEST RESULT {'FAIL' if fails else 'PASS'}" + (f" ({', '.join(fails)})" if fails else ''))
