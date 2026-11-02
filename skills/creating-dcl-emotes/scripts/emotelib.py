# Shared helpers for building Decentraland emotes on the official avatar .blend files (run inside Blender 3.6 or 4.x).
#   import sys; sys.path.insert(0, '<skill-dir>/scripts'); from emotelib import *
# Grown out of curation-approved emote builds, with two guards for past pitfalls:
#   * hands are posed from an explicit frame (finger direction + palm direction), and the forearm takes the roll,
#     so a palm can't silently end up facing the wrong way; check_palm() measures it afterwards.
#   * every prop face is wound outward when it's built, open sheets are made two-sided, and check_normals()
#     ray-tests the finished meshes, because Decentraland culls back faces on emote props.
# Armature space: cm, +Y up, +Z is where the avatar faces, +X is the avatar's left.
import bpy, math, os, sys
import numpy as np
from mathutils import Vector, Matrix, Quaternion
from mathutils.bvhtree import BVHTree

TAU = math.pi * 2
X, Y, Z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))
SIDES = (('Left', 1), ('Right', -1))

def ss(a, b, t):
    x = min(1.0, max(0.0, (t - a) / (b - a)))
    return x * x * (3 - 2 * x)

def window(t, a, b, c, d):
    """0 before a, eases to 1 over a..b, holds, eases back to 0 over c..d."""
    return ss(a, b, t) * (1 - ss(c, d, t))

def V(*a):
    return Vector(a[0] if len(a) == 1 else a)

# ---------------------------------------------------------------- avatar rig
class Rig:
    def __init__(self):
        self.AV = bpy.data.objects['Armature']
        self.P = self.AV.pose.bones
        for pb in self.P:
            pb.rotation_mode = 'QUATERNION'
        self.bones = [pb.name for pb in self.P]
        self.reset()

    def upd(self):
        bpy.context.view_layer.update()

    def reset(self):
        for pb in self.P:
            pb.rotation_quaternion = (1, 0, 0, 0)
            pb.location = (0, 0, 0)
            pb.scale = (1, 1, 1)
        self.upd()

    def capture(self):
        return {n: (self.P[n].rotation_quaternion.copy(), self.P[n].location.copy()) for n in self.bones}

    def restore(self, snap):
        for n, (q, l) in snap.items():
            self.P[n].rotation_quaternion = q
            self.P[n].location = l
        self.upd()

    def blend(self, a, b, u):
        """Pose part way from snapshot a to snapshot b (per-bone slerp)."""
        out = {}
        for n in self.bones:
            qa, la = a[n]; qb, lb = b[n]
            qb = qb.copy(); qb.make_compatible(qa)
            out[n] = (qa.slerp(qb, u), la.lerp(lb, u))
        return out

    def pos(self, name, tail=False):
        pb = self.P[name]
        return (pb.tail if tail else pb.head).copy()

    def set_matrix(self, name, m):
        self.P[name].matrix = m
        self.upd()

    def set_rot(self, name, R3):
        """Give a bone an absolute armature-space orientation (3x3 columns = bone x, y, z), head kept in place."""
        m = R3.to_4x4()
        m.translation = self.pos(name)
        self.set_matrix(name, m)

    def aim(self, name, d, twist=0.0):
        pb = self.P[name]
        pb.rotation_quaternion = (1, 0, 0, 0)
        self.upd()
        m = pb.matrix.copy()
        head = m.translation.copy()
        q = m.col[1].xyz.normalized().rotation_difference(Vector(d).normalized())
        R = q.to_matrix().to_4x4()
        if twist:
            R = Matrix.Rotation(math.radians(twist), 4, Vector(d).normalized()) @ R
        self.set_matrix(name, Matrix.Translation(head) @ R @ Matrix.Translation(-head) @ m)

    def rot(self, name, axis, deg, pivot=None):
        if abs(deg) < 1e-6:
            return
        m = self.P[name].matrix.copy()
        pv = Vector(pivot) if pivot is not None else m.translation.copy()
        R = Matrix.Rotation(math.radians(deg), 4, Vector(axis))
        self.set_matrix(name, Matrix.Translation(pv) @ R @ Matrix.Translation(-pv) @ m)

    def move(self, name, offset):
        self.set_matrix(name, Matrix.Translation(Vector(offset)) @ self.P[name].matrix.copy())

    # ---- hands
    def curl(self, side, amount, thumb=None, spread=0.0):
        """Curl the four fingers by amount degrees (85 = fist). The hands' bone rolls are mirrored, so one angle curls both inward."""
        for i, f in enumerate(('Index', 'Middle', 'Ring', 'Pinky')):
            for k in (1, 2, 3):
                q = Quaternion((0, 0, 1), math.radians(amount * (0.8 if k == 1 else 1.0)))
                if k == 1 and spread:
                    q = Quaternion((1, 0, 0), math.radians(spread * (i - 1.5) / 1.5)) @ q
                self.P[f'Avatar_{side}Hand{f}{k}'].rotation_quaternion = q
        th = amount * .45 if thumb is None else thumb
        for k in (2, 3):
            self.P[f'Avatar_{side}HandThumb{k}'].rotation_quaternion = Quaternion((0, 0, 1), math.radians(th))
        self.upd()

    @staticmethod
    def hand_frame(fwd, palm):
        """Hand bone orientation for fingers along fwd and the palm facing palm (on this rig palm = -bone x for both hands)."""
        y = Vector(fwd).normalized()
        x = -Vector(palm)
        x = (x - x.dot(y) * y).normalized()
        z = x.cross(y)
        return Matrix((x, y, z)).transposed()

    def palm(self, side):
        """Measured palm normal: from the knuckles toward where the curled fingertips go, across the hand."""
        h = self.P[f'Avatar_{side}Hand']
        return (-h.matrix.col[0].xyz).normalized()

    def fingers(self, side):
        h = self.P[f'Avatar_{side}Hand']
        return h.matrix.col[1].xyz.normalized()

    def thumb_side(self, side):
        """Direction from the pinky edge of the hand to the index/thumb edge."""
        a = self.pos(f'Avatar_{side}HandIndex1'); b = self.pos(f'Avatar_{side}HandPinky1')
        return (a - b).normalized()

    def grip(self, side):
        """Centre of a closed fist's channel and its axis (index -> pinky). Curl the fingers first."""
        hb = lambda n, tail=False: self.pos(f'Avatar_{side}Hand{n}', tail)
        ch = (hb('Middle1') + hb('Middle1', True) + hb('Middle3', True)) / 3
        ax = (hb('Pinky1') - hb('Index1')).normalized()
        return ch, ax

    def reach(self, side, wrist, pole, fwd, palm, roll_share=1.0):
        """Two-bone IK to put the wrist at `wrist`, then the hand in (fwd, palm). The forearm takes the roll so the
        wrist doesn't candy-wrap; roll_share < 1 leaves some of it to the wrist."""
        arm, fore, hand = f'Avatar_{side}Arm', f'Avatar_{side}ForeArm', f'Avatar_{side}Hand'
        sh = self.pos(arm)
        l1, l2 = self.P[arm].length, self.P[fore].length
        elbow = ik2(sh, Vector(wrist), l1, l2, pole)
        self.aim(arm, elbow - sh)
        e = self.pos(fore)
        self.aim(fore, Vector(wrist) - e)
        Hd = self.hand_frame(fwd, palm)
        F = self.P[fore].matrix.to_3x3()
        fy = F.col[1].normalized()
        # angle about the forearm from its x axis to the wanted hand x axis, minus the same angle at rest
        def ang(a, b):
            a = (a - a.dot(fy) * fy).normalized(); b = (b - b.dot(fy) * fy).normalized()
            return math.degrees(math.atan2(a.cross(b).dot(fy), a.dot(b)))
        tw = ang(F.col[0].xyz, Hd.col[0]) - self.REST_TWIST[side]
        tw = (tw + 180) % 360 - 180
        if abs(tw) > 1e-3:
            self.aim(fore, Vector(wrist) - e, tw * roll_share)
        self.set_rot(hand, Hd)

    def calibrate(self):
        """Rest-pose roll between forearm x and hand x, per side (used by reach)."""
        self.REST_TWIST = {}
        for side, _ in SIDES:
            F = self.AV.data.bones[f'Avatar_{side}ForeArm'].matrix_local.to_3x3()
            H = self.AV.data.bones[f'Avatar_{side}Hand'].matrix_local.to_3x3()
            fy = F.col[1].normalized()
            a = F.col[0] - F.col[0].dot(fy) * fy; b = H.col[0] - H.col[0].dot(fy) * fy
            a.normalize(); b.normalize()
            self.REST_TWIST[side] = math.degrees(math.atan2(a.cross(b).dot(fy), a.dot(b)))

    # ---- legs
    def leg(self, side, ankle, pole, heading=Z, sole_up=Y, toe_bend=0.0):
        """Two-bone IK to put the ankle at `ankle`, then orient the foot: toes along heading, sole facing away from sole_up."""
        up, lo, ft = f'Avatar_{side}UpLeg', f'Avatar_{side}Leg', f'Avatar_{side}Foot'
        hip = self.pos(up)
        l1, l2 = self.P[up].length, self.P[lo].length
        knee = ik2(hip, Vector(ankle), l1, l2, pole)
        self.aim(up, knee - hip)
        self.aim(lo, Vector(ankle) - self.pos(lo))
        # rest foot: toes along +Z, sole down. Map (Z, Y) -> (heading, sole_up).
        u = Vector(sole_up).normalized()
        h = Vector(heading); h = (h - h.dot(u) * u).normalized()
        x = u.cross(h)
        Q = Matrix((x, u, h)).transposed()        # columns: where rest X, Y, Z go
        R0 = self.AV.data.bones[ft].matrix_local.to_3x3()
        self.set_rot(ft, Q @ R0)
        if toe_bend:
            self.rot(f'Avatar_{side}ToeBase', x, toe_bend)

def ik2(a, c, l1, l2, pole):
    d = c - a
    L = min(d.length, (l1 + l2) * .999)
    dn = d.normalized()
    x = (L * L + l1 * l1 - l2 * l2) / (2 * L)
    h = math.sqrt(max(0.0, l1 * l1 - x * x))
    n = Vector(pole) - Vector(pole).dot(dn) * dn
    n.normalize()
    return a + dn * x + n * h

def palm_geom(rig, side):
    """Palm normal measured from the mesh-driving finger bones (curl the fingers first): knuckles -> fingertips,
    across the hand. Independent of the bone-axis convention reach() uses."""
    h = rig.P[f'Avatar_{side}Hand']
    d = (h.tail - h.head).normalized()
    v = rig.pos(f'Avatar_{side}HandMiddle3', True) - rig.pos(f'Avatar_{side}HandMiddle1')
    v -= v.dot(d) * d
    return v.normalized()

def check_palm(rig, side, want, label='', tol=35.0):
    got = palm_geom(rig, side)
    a = math.degrees(got.angle(Vector(want).normalized()))
    ok = a <= tol
    print(f"HAND {'PASS' if ok else 'FAIL'} {label:<14} {side:<5} palm ({got.x:+.2f},{got.y:+.2f},{got.z:+.2f}) "
          f"wanted ({want[0]:+.2f},{want[1]:+.2f},{want[2]:+.2f}) off {a:5.1f} deg")
    return ok

# ---------------------------------------------------------------- prop meshes
class Part:
    """Prop geometry: verts (armature space), faces, per-vertex UVs and bone weights."""
    def __init__(self):
        self.v, self.f, self.uv, self.w = [], [], [], []

    def add(self, verts, faces, uvs, wts, outward):
        """Append geometry; each face is wound so its normal agrees with outward(centroid)."""
        o = len(self.v)
        for f in faces:
            pts = [Vector(verts[i]) for i in f]
            c = sum(pts, Vector()) / len(pts)
            nrm = Vector()
            for i in range(len(pts)):          # Newell normal: robust for quads and slivers
                p, q = pts[i], pts[(i + 1) % len(pts)]
                nrm += Vector(((p.y - q.y) * (p.z + q.z), (p.z - q.z) * (p.x + q.x), (p.x - q.x) * (p.y + q.y)))
            if nrm.dot(outward(c)) < 0:
                f = tuple(reversed(f))
            self.f.append(tuple(i + o for i in f))
        self.v += [Vector(p) for p in verts]
        self.uv += list(uvs)
        self.w += [dict(x) for x in wts]

    def two_sided(self, start_face, start_vert):
        """Mirror faces added since start_* onto duplicated vertices (DCL culls back faces on props)."""
        o = len(self.v)
        self.v += [p.copy() for p in self.v[start_vert:o]]
        self.uv += self.uv[start_vert:o]
        self.w += [dict(x) for x in self.w[start_vert:o]]
        self.f += [tuple(i - start_vert + o for i in reversed(f)) for f in self.f[start_face:]]

    def merge(self, other):
        o = len(self.v)
        self.v += other.v; self.uv += other.uv; self.w += other.w
        self.f += [tuple(i + o for i in f) for f in other.f]

    def mark(self):
        return len(self.f), len(self.v)

    def transform(self, M, start_vert=0):
        for i in range(start_vert, len(self.v)):
            self.v[i] = M @ self.v[i]

def const(uv):
    return lambda *a: uv

def ellipsoid(part, c, r, rings, segs, uvfn, wfn, frame=None):
    """Closed ellipsoid; r = (rx, ry, rz) along frame's columns (default world axes). uvfn(U around, s pole-to-pole)."""
    c = Vector(c); r = Vector(r)
    R = frame or Matrix.Identity(3)
    verts, uvs, faces, idx = [], [], [], {}
    for k in range(rings + 1):
        s = k / rings
        for j in range(segs + 1):
            if k in (0, rings) and j > 0:
                idx[k, j] = idx[k, 0]; continue
            ph = TAU * j / segs
            rr = math.sin(math.pi * s)
            loc = Vector((r.x * rr * math.sin(ph), -r.y * rr * math.cos(ph), r.z * math.cos(math.pi * s)))
            idx[k, j] = len(verts)
            verts.append(c + R @ loc)
            uvs.append(uvfn(j / segs, s))
    for k in range(rings):
        for j in range(segs):
            f = tuple(dict.fromkeys((idx[k, j], idx[k, j + 1], idx[k + 1, j + 1], idx[k + 1, j])))
            if len(f) >= 3:
                faces.append(f)
    part.add(verts, faces, uvs, [wfn(p) for p in verts], lambda q: q - c)

def _closest_on_polyline(q, pts):
    best, bd = None, 1e18
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        ab = b - a
        t = 0.0 if ab.length_squared < 1e-12 else max(0.0, min(1.0, (q - a).dot(ab) / ab.length_squared))
        p = a + ab * t
        d = (q - p).length_squared
        if d < bd:
            best, bd = p, d
    return best

def tube(part, pts, radii, sides, uvfn, wfn, caps=(True, True), side_hint=None):
    """Closed tube along a polyline (radius per point; a 0 radius makes a point). uvfn(U around, t along)."""
    pts = [Vector(p) for p in pts]
    n = len(pts)
    L = [0.0]
    for i in range(1, n):
        L.append(L[-1] + (pts[i] - pts[i - 1]).length)
    ref = Vector(side_hint) if side_hint is not None else Y
    verts, uvs, faces, rings = [], [], [], []
    prev_a = None
    for i, p in enumerate(pts):
        d = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
        a = (prev_a if prev_a is not None else ref)
        a = a - a.dot(d) * d
        if a.length < 1e-4:
            a = X - X.dot(d) * d
        a.normalize(); prev_a = a          # parallel-transport the frame so the tube doesn't twist
        b = d.cross(a)
        ring = []
        for j in range(sides + 1):
            if radii[i] < 1e-3 and j > 0:
                ring.append(ring[0]); continue
            if j == sides and radii[i] >= 1e-3:
                ring.append(ring[0]); continue   # weld the seam (UV seam is fine: both ends map near each other)
            ang = TAU * j / sides
            ring.append(len(verts))
            verts.append(p + (a * math.cos(ang) + b * math.sin(ang)) * radii[i])
            uvs.append(uvfn(j / sides, L[i] / max(L[-1], 1e-9)))
        rings.append(ring)
    body = []
    for i in range(n - 1):
        for j in range(sides):
            f = tuple(dict.fromkeys((rings[i][j], rings[i][j + 1], rings[i + 1][j + 1], rings[i + 1][j])))
            if len(f) >= 3:
                body.append(f)
    part.add(verts, body, uvs, [wfn(p) for p in verts], lambda q: q - _closest_on_polyline(q, pts))
    for end, ok in ((0, caps[0]), (n - 1, caps[1])):
        if ok and radii[end] >= 1e-3:
            dirv = (pts[0] - pts[1]) if end == 0 else (pts[-1] - pts[-2])
            ring = rings[end][:sides]
            cv = [verts[k] for k in ring] + [pts[end].copy()]
            cuv = [uvs[k] for k in ring] + [uvfn(.5, 0.0 if end == 0 else 1.0)]
            cf = [(sides, j, (j + 1) % sides) for j in range(sides)]
            part.add(cv, cf, cuv, [wfn(p) for p in cv], lambda q, dv=dirv: dv)

def lathe(part, origin, axis, profile, segs, uvfn, wfn, caps=(True, True), ref=None):
    """Surface of revolution: profile = [(radius, height along axis)], closed with flat caps at both ends."""
    o = Vector(origin); a = Vector(axis).normalized()
    u = Vector(ref) if ref is not None else (X if abs(a.dot(X)) < .9 else Y)
    u = (u - u.dot(a) * a).normalized(); w = a.cross(u)
    verts, uvs, faces, rings = [], [], [], []
    n = len(profile)
    for i, (r, h) in enumerate(profile):
        ring = []
        for j in range(segs + 1):          # seam column duplicated so a label texture wraps once
            ang = TAU * j / segs
            ring.append(len(verts))
            verts.append(o + a * h + (u * math.cos(ang) + w * math.sin(ang)) * r)
            uvs.append(uvfn(j / segs, i / (n - 1)))
        rings.append(ring)
    for i in range(n - 1):
        for j in range(segs):
            faces.append((rings[i][j], rings[i][j + 1], rings[i + 1][j + 1], rings[i + 1][j]))
    def outward(q):
        rad = (q - o) - (q - o).dot(a) * a
        return rad
    part.add(verts, faces, uvs, [wfn(p) for p in verts], outward)
    for end, ok, sgn in ((0, caps[0], -1), (n - 1, caps[1], 1)):
        if ok:
            r, h = profile[end]
            cv = [verts[k] for k in rings[end][:segs]] + [o + a * h]
            cuv = [uvs[k] for k in rings[end][:segs]] + [uvfn(.5, end / (n - 1))]
            cf = [(segs, j, (j + 1) % segs) for j in range(segs)]
            part.add(cv, cf, cuv, [wfn(p) for p in cv], lambda q, s=sgn: a * s)

def box(part, c, half, frame, uvfn, wfn):
    """Closed box: half extents along frame columns. uvfn(face_index, U, V)."""
    c = Vector(c); R = frame or Matrix.Identity(3)
    ax = [R.col[i].xyz.normalized() for i in range(3)]
    for fi, (k, s) in enumerate(((0, 1), (0, -1), (1, 1), (1, -1), (2, 1), (2, -1))):
        nrm = ax[k] * s
        e1, e2 = ax[(k + 1) % 3] * half[(k + 1) % 3], ax[(k + 2) % 3] * half[(k + 2) % 3]
        ctr = c + nrm * half[k]
        vs = [ctr - e1 - e2, ctr + e1 - e2, ctr + e1 + e2, ctr - e1 + e2]
        uv = [uvfn(fi, 0, 0), uvfn(fi, 1, 0), uvfn(fi, 1, 1), uvfn(fi, 0, 1)]
        part.add(vs, [(0, 1, 2, 3)], uv, [wfn(p) for p in vs], lambda q, nn=nrm: nn)

def quad(part, corners, uvs, wfn, normal, two_sided=False):
    """One flat quad (corners in order), facing `normal`; two_sided duplicates it facing back."""
    m = part.mark()
    part.add([Vector(p) for p in corners], [(0, 1, 2, 3)], uvs, [wfn(Vector(p)) for p in corners], lambda q: Vector(normal))
    if two_sided:
        part.two_sided(*m)

def W(bone):
    return lambda p: {bone: 1.0}

# ---------------------------------------------------------------- materials and textures
def image_from_array(name, arr, out_dir):
    """arr: (H, W, 3|4) float 0..1, row 0 = bottom (Blender convention)."""
    h, w = arr.shape[:2]
    if arr.shape[2] == 3:
        arr = np.concatenate([arr, np.ones((h, w, 1))], 2)
    im = bpy.data.images.new(name, w, h, alpha=False)
    im.pixels = np.clip(arr, 0, 1).astype(np.float32).ravel()
    im.filepath_raw = os.path.join(out_dir, name + '.png')
    im.file_format = 'PNG'
    im.save()
    return im

def make_material(name, color=(1, 1, 1), image=None, emit=0.0, emit_image=False, rough=.5, metal=0.0, alpha=False):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.use_backface_culling = True       # preview the way Decentraland draws props
    bsdf = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    emission = bsdf.inputs.get('Emission Color') or bsdf.inputs['Emission']   # renamed in Blender 4.0
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Roughness'].default_value = rough
    bsdf.inputs['Metallic'].default_value = metal
    tex = None
    if image:
        tex = m.node_tree.nodes.new('ShaderNodeTexImage')
        tex.image = image
        m.node_tree.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
        if alpha:                       # see-through parts from the texture's alpha (glTF alphaMode BLEND)
            m.node_tree.links.new(tex.outputs['Alpha'], bsdf.inputs['Alpha'])
            m.blend_method = 'BLEND'
            if hasattr(m, 'surface_render_method'):       # Blender 4.2+ (EEVEE Next)
                m.surface_render_method = 'BLENDED'
            if hasattr(m, 'shadow_method'):               # removed in 4.2
                m.shadow_method = 'HASHED'
            if hasattr(m, 'show_transparent_back'):       # renamed use_transparency_overlap in 4.2
                m.show_transparent_back = False
            elif hasattr(m, 'use_transparency_overlap'):
                m.use_transparency_overlap = False
    if emit:
        bsdf.inputs['Emission Strength'].default_value = emit
        if emit_image and tex:
            m.node_tree.links.new(tex.outputs['Color'], emission)
        else:
            emission.default_value = (*color, 1)
    return m

# ---------------------------------------------------------------- prop armature
def seg_matrix(p, q, side):
    y = (Vector(q) - Vector(p)).normalized()
    x = Vector(side) - Vector(side).dot(y) * y
    if x.length < 1e-6:
        x = X - X.dot(y) * y
    x.normalize()
    z = x.cross(y)
    M = Matrix((x, y, z)).transposed().to_4x4()
    M.translation = Vector(p)
    return M

class PropRig:
    """Armature_Prop with bones given as (name, head, tail, side, parent). follow=[avatar bones] adds C_<bone>
    bones that copy those avatar bones (baked at the end), for props held in a hand."""
    def __init__(self, rig, specs, follow=()):
        self.rig = rig
        scene = bpy.context.scene
        self.data = bpy.data.armatures.new('Armature_Prop')
        self.ob = bpy.data.objects.new('Armature_Prop', self.data)
        scene.collection.objects.link(self.ob)
        self.ob.matrix_world = rig.AV.matrix_world.copy()
        self.REST = {}
        bpy.context.view_layer.objects.active = self.ob
        bpy.ops.object.mode_set(mode='EDIT')
        eb = self.data.edit_bones
        for name, p, q, side, parent in specs:
            b = eb.new(name)
            b.head, b.tail = Vector(p), Vector(q)
            M = seg_matrix(p, q, side)
            b.matrix = M
            if parent:
                b.parent = eb[parent]
            self.REST[name] = M
        root = specs[0][0]
        for n in follow:
            m, ln = rig.P[n].matrix.copy(), rig.P[n].length
            b = eb.new('C_' + n.replace('Avatar_', ''))
            b.head = Vector((0, 0, 0)); b.tail = Vector((0, ln, 0))
            b.matrix = m
            b.parent = eb[root]
            self.REST[b.name] = m
        bpy.ops.object.mode_set(mode='OBJECT')
        self.P = self.ob.pose.bones
        for pb in self.P:
            pb.rotation_mode = 'QUATERNION'
        for pb in self.P:
            if pb.name.startswith('C_'):
                c = pb.constraints.new('COPY_TRANSFORMS')
                c.target = rig.AV
                c.subtarget = 'Avatar_' + pb.name[2:]
        self.own = [pb.name for pb in self.P if not pb.name.startswith('C_')]

    def set(self, name, M):
        self.P[name].matrix = M
        bpy.context.view_layer.update()

    def place(self, name, M_world_delta, scale=None):
        """Bone at rest transformed by M (armature space), optional scale (x, y, z) in bone space."""
        M = M_world_delta @ self.REST[name]
        if scale is not None:
            M = M @ Matrix.Diagonal((*scale, 1))
        self.set(name, M)

def mesh_object(name, part, material, parent):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in part.v], [], part.f)
    uvl = me.uv_layers.new(name='UVMap')
    for poly in me.polygons:
        for li in poly.loop_indices:
            uvl.data[li].uv = part.uv[me.loops[li].vertex_index]
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.parent = parent
    ob.matrix_parent_inverse = Matrix.Identity(4)
    me.materials.append(material)
    for poly in me.polygons:
        poly.use_smooth = True
    groups = {}
    for vi, wd in enumerate(part.w):
        tot = sum(wd.values()) or 1
        for bn, w in wd.items():
            if w / tot < .002:
                continue
            g = groups.get(bn) or ob.vertex_groups.new(name=bn)
            groups[bn] = g
            g.add([vi], w / tot, 'REPLACE')
    mod = ob.modifiers.new('Armature', 'ARMATURE')
    mod.object = parent
    print('PROP', name, 'tris', sum(len(p.vertices) - 2 for p in me.polygons))
    return ob

# ---------------------------------------------------------------- normals check
def check_normals(objs):
    """Every prop face must face out: each loose part must be closed and consistently wound (or a two-sided sheet),
    with a positive signed volume. Open single-sided parts fail: their back faces vanish in Decentraland."""
    all_ok = True
    for ob in objs:
        me = ob.data
        verts = [v.co.copy() for v in me.vertices]
        polys = [tuple(p.vertices) for p in me.polygons]
        # loose parts by shared vertex positions (two-sided copies count as the same part)
        key = {}
        for i, v in enumerate(verts):
            key.setdefault((round(v.x, 3), round(v.y, 3), round(v.z, 3)), []).append(i)
        par = list(range(len(verts)))
        def find(a):
            while par[a] != a:
                par[a] = par[par[a]]; a = par[a]
            return a
        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb: par[ra] = rb
        for ids in key.values():
            for i in ids[1:]: union(ids[0], i)
        for p in polys:
            for i in p[1:]: union(p[0], i)
        parts = {}
        for fi, p in enumerate(polys):
            parts.setdefault(find(p[0]), []).append(fi)
        bad_in, bad_open = 0, 0
        for fids in parts.values():
            # edge use by position, per winding direction
            edges = {}
            pk = lambda i: (round(verts[i].x, 3), round(verts[i].y, 3), round(verts[i].z, 3))
            for fi in fids:
                p = polys[fi]
                for k in range(len(p)):
                    e = (pk(p[k]), pk(p[(k + 1) % len(p)]))
                    edges[e] = edges.get(e, 0) + 1
            # closed & consistently wound: every directed edge has its reverse
            closed = all(edges.get((b, a), 0) == c for (a, b), c in edges.items())
            if closed:
                # closed and consistently wound, so all faces point the same way: the signed volume says which.
                # A two-sided sheet is also "closed" (each face has a reversed twin) with ~zero volume: both sides drawn.
                vol, area = 0.0, 0.0
                for fi in fids:
                    pts = [verts[i] for i in polys[fi]]
                    for k in range(1, len(pts) - 1):
                        vol += pts[0].dot(pts[k].cross(pts[k + 1])) / 6
                        area += (pts[k] - pts[0]).cross(pts[k + 1] - pts[0]).length / 2
                if vol < -1e-4 * max(area, 1e-9) ** 1.5:
                    bad_in += len(fids)
                    c = verts[polys[fids[0]][0]]
                    print(f'NORMALS   inside-out part of {len(fids)} faces near ({c.x:.1f}, {c.y:.1f}, {c.z:.1f}), volume {vol:.2f}')
            else:
                bad_open += len(fids)
                c = verts[polys[fids[0]][0]]
                print(f'NORMALS   open single-sided part of {len(fids)} faces near ({c.x:.1f}, {c.y:.1f}, {c.z:.1f})')
        ok = bad_in == 0 and bad_open == 0
        all_ok &= ok
        print(f"NORMALS {'PASS' if ok else 'FAIL'} {ob.name:<16} parts {len(parts):3d}  inward faces {bad_in}  faces in open single-sided parts {bad_open}")
        if not ob.active_material.use_backface_culling:
            print(f'NORMALS WARN {ob.name} material preview is not backface-culled')
    return all_ok

# ---------------------------------------------------------------- bake and export
def bake(rig, prop, name, nfr, fps, pose_fn, scale_bones=(), avatar_scale=(), avatar_loc=()):
    """Key every frame: all avatar bones (+ hips location), all prop bones (location, rotation, scale where asked),
    then bake the hand-follow bones. Frame nfr repeats frame 0 so the clip loops."""
    scene = bpy.context.scene
    scene.render.fps = fps
    scene.frame_start, scene.frame_end = 0, nfr
    av_act = bpy.data.actions.new(name + '_Avatar')
    rig.AV.animation_data_create(); rig.AV.animation_data.action = av_act
    if prop:
        pr_act = bpy.data.actions.new(name + '_Prop')
        prop.ob.animation_data_create(); prop.ob.animation_data.action = pr_act
    prevq = {}
    def key(pb, fr, loc, scl=False):
        q = pb.rotation_quaternion.copy()
        if pb.id_data.name + pb.name in prevq:
            q.make_compatible(prevq[pb.id_data.name + pb.name])
        pb.rotation_quaternion = q
        prevq[pb.id_data.name + pb.name] = q
        pb.keyframe_insert('rotation_quaternion', frame=fr, group=pb.name)
        if loc:
            pb.keyframe_insert('location', frame=fr, group=pb.name)
        if scl:
            pb.keyframe_insert('scale', frame=fr, group=pb.name)
    for fr in range(nfr + 1):
        t = (fr % nfr) / fps
        pose_fn(t)
        for n in rig.bones:
            key(rig.P[n], fr, n == 'Avatar_Hips' or n in avatar_loc, n in avatar_scale)
        if prop:
            for n in prop.own:
                key(prop.P[n], fr, True, True)
    acts = [av_act] + ([pr_act] if prop else [])
    for a in acts:
        for fc in a.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'
    scene.frame_set(0)
    if prop and any(n.startswith('C_') for n in prop.P.keys()):
        bpy.context.view_layer.objects.active = prop.ob
        bpy.ops.object.mode_set(mode='POSE')
        bpy.ops.pose.select_all(action='SELECT')
        bpy.ops.nla.bake(frame_start=0, frame_end=nfr, only_selected=True, visual_keying=True,
                         clear_constraints=True, use_current_action=True, bake_types={'POSE'})
        bpy.ops.object.mode_set(mode='OBJECT')
        prop.ob.animation_data.action.name = name + '_Prop'
    print('ACTIONS', [(a.name, tuple(a.frame_range), len(a.fcurves)) for a in bpy.data.actions])

def export(rig, prop, props, out_dir, name):
    for o in bpy.context.scene.objects:
        o.select_set(False)
    rig.AV.select_set(True)
    if prop:
        prop.ob.select_set(True)
        for o in props:
            o.select_set(True)
    bpy.context.view_layer.objects.active = rig.AV
    path = os.path.join(out_dir, name + '.glb')
    opts = dict(filepath=path, export_format='GLB', use_selection=True,
                export_animations=True, export_animation_mode='ACTIONS', export_force_sampling=False,
                export_def_bones=False, export_reset_pose_bones=True, export_optimize_animation_size=False,
                export_anim_single_armature=False, export_frame_range=True, export_image_format='AUTO')
    known = {p.identifier for p in bpy.ops.export_scene.gltf.get_rna_type().properties}
    dropped = sorted(k for k in opts if k not in known)
    if dropped:                                           # exporter options differ between Blender versions
        print('EXPORT options not in this Blender, skipped:', dropped)
    bpy.ops.export_scene.gltf(**{k: v for k, v in opts.items() if k in known})
    dedupe_textures(path)
    print('EXPORTED', path)

def dedupe_textures(path):
    """The glTF exporter writes a separate texture entry per material slot even when they share one image and sampler
    (base colour + emissive from the same PNG). Merge those so the texture count matches the image count."""
    import json, struct
    b = open(path, 'rb').read()
    n = struct.unpack('<I', b[12:16])[0]
    g = json.loads(b[20:20 + n])
    tex = g.get('textures', [])
    keep, remap = [], {}
    for i, t in enumerate(tex):
        key = (t.get('source'), t.get('sampler'))
        for j, k in enumerate(keep):
            if (k.get('source'), k.get('sampler')) == key:
                remap[i] = j; break
        else:
            remap[i] = len(keep); keep.append(t)
    if len(keep) == len(tex):
        return
    def fix(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k.endswith('Texture') and isinstance(v, dict) and 'index' in v:
                    v['index'] = remap[v['index']]
                else:
                    fix(v)
        elif isinstance(o, list):
            for v in o:
                fix(v)
    fix(g.get('materials', []))
    g['textures'] = keep
    js = json.dumps(g, separators=(',', ':')).encode()
    js += b' ' * ((4 - len(js) % 4) % 4)
    rest = b[20 + n:]
    out = b[:8] + struct.pack('<I', 12 + 8 + len(js) + len(rest)) + struct.pack('<I', len(js)) + b'JSON' + js + rest
    open(path, 'wb').write(out)
    print('TEXTURES merged', len(tex), '->', len(keep))

def args():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    out = argv[0] if argv else os.getcwd()
    stage = argv[1] if len(argv) > 1 else 'full'
    pose_t = float(argv[2]) if len(argv) > 2 else 0.0
    os.makedirs(out, exist_ok=True)
    return out, stage, pose_t

def floor_guard(rig, margin=0.3):
    """Lift the hips so no part of the avatar's evaluated mesh is below the floor (for blended in-between poses,
    where per-bone slerps can swing a foot or knee through the ground). Returns the lift in cm."""
    dg = bpy.context.evaluated_depsgraph_get()
    low = 1e9
    to_arm = rig.AV.matrix_world.inverted()
    for o in rig.AV.children:
        if o.type != 'MESH':
            continue
        e = o.evaluated_get(dg); me = e.to_mesh()
        M = to_arm @ e.matrix_world
        for v in me.vertices:
            low = min(low, (M @ v.co).y)
        e.to_mesh_clear()
    lift = margin - low
    if lift > 0:
        rig.move('Avatar_Hips', (0, lift, 0))
        return lift
    return 0.0

def limb_overlaps(rig, groups, pairs):
    """Mesh-level clipping test: splits the evaluated avatar mesh into limbs by each vertex's strongest bone
    (groups = {limb: [bone names]}) and counts intersecting triangle pairs between the given limb pairs.
    Triangles touching a vertex of the other limb's group are ignored (that's the seam where two limbs join)."""
    dg = bpy.context.evaluated_depsgraph_get()
    to_arm = rig.AV.matrix_world.inverted()
    owner = {b: k for k, bs in groups.items() for b in bs}
    verts = {k: [] for k in groups}; tris = {k: [] for k in groups}
    for o in rig.AV.children:
        if o.type != 'MESH':
            continue
        names = {g.index: g.name for g in o.vertex_groups}
        lab = []
        for v in o.data.vertices:
            g = max(v.groups, key=lambda g: g.weight) if v.groups else None
            lab.append(owner.get(names.get(g.group), None) if g else None)
        e = o.evaluated_get(dg); me = e.to_mesh(); M = to_arm @ e.matrix_world
        co = [M @ v.co for v in me.vertices]
        me.calc_loop_triangles()
        for lt in me.loop_triangles:
            ls = {lab[i] for i in lt.vertices}
            if len(ls) != 1 or None in ls:
                continue                                    # seam triangles between limbs are skipped
            k = ls.pop()
            base = len(verts[k])
            verts[k] += [co[i] for i in lt.vertices]
            tris[k].append((base, base + 1, base + 2))
        e.to_mesh_clear()
    trees = {k: BVHTree.FromPolygons(verts[k], tris[k]) for k in groups if tris[k]}
    out = {}
    for a, b in pairs:
        if a in trees and b in trees:
            out[(a, b)] = len(trees[a].overlap(trees[b]))
    return out
