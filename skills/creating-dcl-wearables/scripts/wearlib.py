# Shared helpers for building Decentraland wearables on the official avatar .blend files (run inside Blender 3.6 or 4.x).
#   import sys; sys.path.insert(0, '<skill-dir>/scripts'); from wearlib import *
# Pulled out of curation-approved wearable builds (hair with spring bones, a rigid back accessory with earrings, a
# helmet, a one-piece outfit). Build both body shapes from one script: open AvatarShape_A.blend (BaseFemale) or
# AvatarShape_B.blend (BaseMale), run the same build, export, repeat with the other file.
# Armature space: cm, +Y up, +Z is where the avatar faces, +X is the avatar's left. Select geometry by position, never
# by bone weights (the two bodies differ).
import bpy, math, os
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from mathutils.interpolate import poly_3d_calc

BASE_PARTS = ('Head', 'uBody', 'lBody', 'Hands', 'Feet')


# ---------------------------------------------------------------- the avatar
def armature():
    return bpy.data.objects['Armature']


def body_shape():
    """'A' (BaseFemale) or 'B' (BaseMale), from the base meshes in the open file."""
    return 'A' if any(o.name.startswith('ShapeA_') for o in bpy.data.objects) else 'B'


def shape_suffix():
    """File-name suffix for the open body shape: 'female' (A) or 'male' (B)."""
    return 'female' if body_shape() == 'A' else 'male'


def base(part):
    """A base mesh of the open body shape: 'Head', 'uBody', 'lBody', 'Hands' or 'Feet' (or a full object name)."""
    name = part if part.startswith('Shape') else f'Shape{body_shape()}_{part}_BaseMesh'
    return bpy.data.objects[name]


def reset_pose():
    """Rest pose on every avatar bone. Export from rest: a posed armature bakes the pose into the bind matrices."""
    for pb in armature().pose.bones:
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
        pb.scale = (1, 1, 1)
    bpy.context.view_layer.update()


def arm_space_verts(ob, evaluated=False):
    """Vertex positions of ob in armature space; evaluated=True uses the posed (deformed) mesh."""
    inv = armature().matrix_world.inverted()
    if not evaluated:
        return [inv @ (ob.matrix_world @ v.co) for v in ob.data.vertices]
    dg = bpy.context.evaluated_depsgraph_get()
    e = ob.evaluated_get(dg)
    me = e.to_mesh()
    out = [inv @ (e.matrix_world @ v.co) for v in me.vertices]
    e.to_mesh_clear()
    return out


def bvh_of(obs, evaluated=False):
    """One BVH tree (armature space) over several meshes, e.g. bvh_of([base('Head')]) to project onto the scalp."""
    verts, polys = [], []
    for ob in obs:
        o = len(verts)
        verts += arm_space_verts(ob, evaluated)
        polys += [[o + i for i in p.vertices] for p in ob.data.polygons]
    return BVHTree.FromPolygons(verts, polys)


# ---------------------------------------------------------------- building the item
def new_mesh_obj(name, verts, faces, uvs=None, weights=None, mats=(), face_mats=None):
    """Mesh from armature-space verts, parented to and skinned on the avatar armature.
    uvs: one (u, v) per vertex. weights: one {bone: weight} per vertex (normalised here), or a function p -> dict."""
    av = armature()
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    if uvs is not None:
        uvl = me.uv_layers.new(name='UVMap')
        for poly in me.polygons:
            for li in poly.loop_indices:
                uvl.data[li].uv = uvs[me.loops[li].vertex_index]
    for m in mats:
        me.materials.append(m)
    if face_mats:
        for poly, mi in zip(me.polygons, face_mats):
            poly.material_index = mi
    for poly in me.polygons:
        poly.use_smooth = True
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.parent = av
    ob.matrix_parent_inverse = Matrix.Identity(4)
    if weights is not None:
        if callable(weights):
            weights = [weights(Vector(v)) for v in verts]
        set_weights(ob, weights)
    mod = ob.modifiers.new('Armature', 'ARMATURE')
    mod.object = av
    return ob


def set_weights(ob, weights, keep=4):
    """Replace ob's skin weights: one {bone: weight} per vertex. Keeps the `keep` strongest influences (Decentraland
    allows 4 per vertex) and normalises them."""
    for g in list(ob.vertex_groups):
        ob.vertex_groups.remove(g)
    groups = {}
    for vi, wd in enumerate(weights):
        top = sorted(((w, b) for b, w in wd.items() if w > 0), reverse=True)[:keep]
        tot = sum(w for w, _ in top) or 1.0
        for w, b in top:
            g = groups.get(b) or ob.vertex_groups.new(name=b)
            groups[b] = g
            g.add([vi], w / tot, 'REPLACE')


def rigid(bone):
    """Weights for a rigid piece riding one bone (a back accessory on Avatar_Spine2, an earring on Avatar_Head)."""
    return lambda p: {bone: 1.0}


def weights_from(ob, drop=(), fallback='Avatar_Spine2'):
    """Weight sampler that copies the skin weights of the nearest point on ob's surface, interpolated over the polygon
    under it (barycentric). Use it for anything that hugs the body (shells, straps, decals, beards): snapping to the
    nearest few vertices drifts in motion, and the jaw's underside is partly Avatar_Neck, which 100% Avatar_Head misses.
    drop: bones to leave out (renormalised); fallback when nothing is left."""
    vs = arm_space_verts(ob)
    tree = BVHTree.FromPolygons(vs, [list(p.vertices) for p in ob.data.polygons])
    names = {g.index: g.name for g in ob.vertex_groups}
    W = [{names[g.group]: g.weight for g in v.groups if g.weight > 0} for v in ob.data.vertices]

    def at(p):
        loc, _n, fi, _d = tree.find_nearest(Vector(p))
        ids = list(ob.data.polygons[fi].vertices)
        acc = {}
        for i, f in zip(ids, poly_3d_calc([vs[i] for i in ids], loc)):
            for b, w in W[i].items():
                if b not in drop:
                    acc[b] = acc.get(b, 0.0) + w * max(f, 0.0)
        tot = sum(acc.values())
        if tot < 1e-6:
            return {fallback: 1.0}
        return {b: w / tot for b, w in acc.items() if w / tot > 1e-4}
    return at


# ---------------------------------------------------------------- spring bones
def add_spring_chain(prefix, points, parent='Avatar_Head'):
    """A connected spring-bone chain through points (armature space): bones <prefix>_01, _02, ... and an unweighted
    <prefix>_end marking the tip, parented to an Avatar_* bone. Names must contain 'springbone' (e.g.
    'Pigtail_springbone_L') for Decentraland to treat them as springs. Max 12 spring bones per wearable, counting end
    bones; chains up to 6 deep. Returns the deform bone names in order (enter the root's parameters in the Builder)."""
    if 'springbone' not in prefix.lower():
        raise ValueError(f"spring bone names must contain 'springbone': {prefix}")
    if len(points) < 3:
        raise ValueError('a chain needs at least 3 points (one deform bone and its end bone)')
    av = armature()
    bpy.context.view_layer.objects.active = av
    av.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = av.data.edit_bones
    prev, names = eb[parent], []
    n = len(points) - 1
    for k in range(n):
        last = k == n - 1
        b = eb.new(f'{prefix}_end' if last else f'{prefix}_{k + 1:02d}')
        b.head, b.tail = Vector(points[k]), Vector(points[k + 1])
        b.roll = 0.0
        b.parent = prev
        b.use_connect = k > 0
        b.use_deform = not last
        if not last:
            names.append(b.name)
        prev = b
    bpy.ops.object.mode_set(mode='OBJECT')
    return names


def chain_weights(path, stations):
    """Weights that blend along a chain: path = points along the piece's centreline (armature space); stations =
    [(t, bone), ...] with t the fraction along the path where that bone owns the mesh fully, e.g.
    [(0.2, 'Avatar_Head'), (0.32, 'X_springbone_L_01'), (0.56, '..._02'), (0.77, '..._03')]: rigid on the head through
    the first fifth (less leverage, less trailing when running), then blended down the chain."""
    path = [Vector(p) for p in path]
    lengths = [0.0]
    for a, b in zip(path, path[1:]):
        lengths.append(lengths[-1] + (b - a).length)
    total = lengths[-1] or 1.0

    def param(p):
        best, bd = 0.0, 1e18
        for i in range(len(path) - 1):
            a, b = path[i], path[i + 1]
            ab = b - a
            u = 0.0 if ab.length_squared < 1e-12 else max(0.0, min(1.0, (p - a).dot(ab) / ab.length_squared))
            d = (p - (a + ab * u)).length_squared
            if d < bd:
                best, bd = (lengths[i] + u * ab.length) / total, d
        return best

    def at(p):
        t = param(Vector(p))
        if t <= stations[0][0]:
            return {stations[0][1]: 1.0}
        if t >= stations[-1][0]:
            return {stations[-1][1]: 1.0}
        for (ta, a), (tb, b) in zip(stations, stations[1:]):
            if ta <= t <= tb:
                f = (t - ta) / (tb - ta)
                return {a: 1 - f, b: f} if a != b else {a: 1.0}
        return {stations[-1][1]: 1.0}
    return at


# ---------------------------------------------------------------- export
def export_wearable(objs, out_dir, name):
    """Export the item meshes + the avatar armature as a skinned GLB from the rest pose: <out_dir>/<name>_<female|male>.glb.
    Exports no animations, no non-deforming avatar bones, and only options this Blender version knows."""
    reset_pose()
    av = armature()
    for o in bpy.context.scene.objects:
        o.select_set(False)
    av.select_set(True)
    for o in objs:
        o.hide_set(False)
        o.select_set(True)
    bpy.context.view_layer.objects.active = av
    path = os.path.join(out_dir, f'{name}_{shape_suffix()}.glb')
    opts = dict(filepath=path, export_format='GLB', use_selection=True, export_animations=False, export_skins=True,
                export_def_bones=False, export_image_format='AUTO')
    known = {p.identifier for p in bpy.ops.export_scene.gltf.get_rna_type().properties}
    bpy.ops.export_scene.gltf(**{k: v for k, v in opts.items() if k in known})
    print('EXPORTED', path, os.path.getsize(path), 'bytes')
    return path
