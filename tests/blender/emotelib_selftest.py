# Self-test for skills/creating-dcl-emotes/scripts/emotelib.py, run inside Blender on an official avatar .blend:
#   blender -b AvatarShape_A.blend --python-exit-code 1 --python tests/blender/emotelib_selftest.py -- <outdir> <scripts dir>
# Prints one "SELFTEST PASS|FAIL <name>" line per check and "SELFTEST RESULT PASS|FAIL" at the end.
# tests/test_helper_libraries_blender.py runs it for each body shape when Blender and the avatar files are available.
import bpy, math, os, subprocess, sys
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index('--') + 1:]
OUT, SCRIPTS = argv[0], argv[1]
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, SCRIPTS)
from emotelib import *   # noqa: E402,F403

fails = []
def check(name, ok, info=''):
    print(f"SELFTEST {'PASS' if ok else 'FAIL'} {name} {info}".rstrip())
    if not ok:
        fails.append(name)

def lowest_point(rig):
    dg = bpy.context.evaluated_depsgraph_get()
    to_arm, low = rig.AV.matrix_world.inverted(), 1e9
    for o in rig.AV.children:
        if o.type == 'MESH':
            e = o.evaluated_get(dg); me = e.to_mesh(); M = to_arm @ e.matrix_world
            low = min([low] + [(M @ v.co).y for v in me.vertices])
            e.to_mesh_clear()
    return low

print('SELFTEST blender', bpy.app.version_string)

# ---- easing
check('ss and window', abs(ss(0, 1, .5) - .5) < 1e-9 and ss(0, 1, -1) == 0 and ss(0, 1, 2) == 1
      and window(5, 0, 1, 8, 9) == 1 and window(10, 0, 1, 8, 9) == 0)

rig = Rig()
rig.calibrate()

# ---- materials (the Emission input was renamed in Blender 4.0; transparency settings changed in 4.2)
mat = make_material('SelfTest_Mat', (1, .5, .2))
make_material('SelfTest_Glow', (.2, 1, .2), emit=2.0)
img = image_from_array('SelfTest_Tex', __import__('numpy').ones((8, 8, 4)) * .5, OUT)
make_material('SelfTest_Alpha', image=img, alpha=True, emit=1.0, emit_image=True)
check('make_material on this Blender', True)

# ---- prop geometry and the normals check
prop = PropRig(rig, [('Prop_Root', (0, 0, 0), (0, 10, 0), (1, 0, 0), None)], follow=['Avatar_RightHand'])
w = W('C_RightHand')
good = Part()
ellipsoid(good, (0, 120, 30), (6, 9, 6), 8, 12, const((.5, .5)), w)
tube(good, [(10, 100, 20), (10, 110, 25), (12, 120, 30)], [2, 3, 2], 10, const((.5, .5)), w)
lathe(good, (-10, 100, 20), (0, 1, 0), [(3, 0), (4, 5), (2, 10)], 12, const((.5, .5)), w)
box(good, (0, 90, 25), (3, 2, 4), None, lambda *a: (.5, .5), w)
quad(good, [(-5, 130, 25), (5, 130, 25), (5, 140, 25), (-5, 140, 25)], [(0, 0), (1, 0), (1, 1), (0, 1)], w, (0, 0, 1),
     two_sided=True)
ob_good = mesh_object('SelfTest_Good', good, mat, prop.ob)
check('check_normals passes closed, outward and two-sided parts', check_normals([ob_good]))

bad = Part()
ellipsoid(bad, (0, 120, 60), (5, 5, 5), 6, 10, const((.5, .5)), w)
bad.f = [tuple(reversed(f)) for f in bad.f]
ob_bad = mesh_object('SelfTest_InsideOut', bad, mat, prop.ob)
check('check_normals fails an inside-out part', not check_normals([ob_bad]))

sheet = Part()
quad(sheet, [(-5, 150, 25), (5, 150, 25), (5, 160, 25), (-5, 160, 25)], [(0, 0), (1, 0), (1, 1), (0, 1)], w, (0, 0, 1))
ob_open = mesh_object('SelfTest_OpenSheet', sheet, mat, prop.ob)
check('check_normals fails an open single-sided sheet', not check_normals([ob_open]))
for ob in (ob_bad, ob_open):
    bpy.data.objects.remove(ob, do_unlink=True)

# ---- hands: two-bone IK lands the wrist and the palm faces where asked
for side, sgn in SIDES:
    rig.reset()
    wrist = rig.pos(f'Avatar_{side}Arm') + Vector((sgn * 5, -30, 30))
    rig.reach(side, wrist, (sgn, -1, -.5), (0, 0, 1), (0, -1, 0))
    rig.curl(side, 40)
    off = (rig.pos(f'Avatar_{side}Hand') - wrist).length
    check(f'reach {side} puts the wrist on target', off < 1.0, f'({off:.2f} cm off)')
    check(f'reach {side} turns the palm down', check_palm(rig, side, (0, -1, 0), 'selftest'))

# ---- floor guard
rig.reset()
rig.move('Avatar_Hips', (0, -60, 0))
lift = floor_guard(rig)
low = lowest_point(rig)
check('floor_guard lifts a sunk pose back above the floor', lift > 50 and low >= .25, f'(lift {lift:.1f}, low {low:.2f} cm)')

# ---- limb overlaps: none at rest, found when the hands are pushed through each other
groups = {'L': [b for b in rig.bones if b.startswith('Avatar_LeftHand')],
          'R': [b for b in rig.bones if b.startswith('Avatar_RightHand')]}
rig.reset()
rest = limb_overlaps(rig, groups, [('L', 'R')]).get(('L', 'R'), 0)
mid = (rig.pos('Avatar_LeftArm') + rig.pos('Avatar_RightArm')) / 2 + Vector((0, -25, 30))
for side, sgn in SIDES:
    rig.reach(side, mid, (sgn, -1, -.5), (0, 0, 1), (-sgn, 0, 0))
crossed = limb_overlaps(rig, groups, [('L', 'R')]).get(('L', 'R'), 0)
check('limb_overlaps: no hand overlap at rest', rest == 0, f'({rest})')
check('limb_overlaps finds hands pushed through each other', crossed > 0, f'({crossed} triangle pairs)')

# ---- bake and export a 1 s looping emote with a hand-held prop, then run the skill's emote checker on it
sh = rig.pos('Avatar_RightArm')
def pose(t):
    rig.reset()
    u = .5 - .5 * math.cos(TAU * t)
    rig.reach('Right', sh + Vector((-5, -30 + 15 * u, 30)), (-1, -1, -.5), (0, 0, 1), (0, -1, 0))
    rig.curl('Right', 60)
    prop.place('Prop_Root', Matrix.Identity(4))
bake(rig, prop, 'SelfTest', 30, 30, pose)
export(rig, prop, [ob_good], OUT, 'SelfTest')
glb = os.path.join(OUT, 'SelfTest.glb')
checker = os.path.join(SCRIPTS, 'check_emote.py')
proc = subprocess.run([sys.executable, checker, glb, '--loop'], capture_output=True, text=True)
print(proc.stdout)
check('exported emote passes check_emote.py --loop', os.path.exists(glb) and proc.returncode == 0,
      '' if proc.returncode == 0 else proc.stderr[-300:])

print(f"SELFTEST RESULT {'FAIL' if fails else 'PASS'}" + (f" ({', '.join(fails)})" if fails else ''))
