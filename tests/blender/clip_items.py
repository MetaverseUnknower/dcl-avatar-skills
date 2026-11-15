"""Builds small test wearables for check_clipping.py on an official avatar .blend.

blender -b AvatarShape_A.blend --python clip_items.py -- <out_dir> <wearlib scripts dir>
Writes, in <out_dir>:
  rigid.glb      an unrigged box (no armature, no Avatar_* nodes) 60 cm in front of the chest
  skinned.glb    a box skinned to Avatar_Head, 25 cm above the head
  bodycopy.glb   a full copy of the avatar's lBody named M_lBody_BaseMesh, skinned like the original (AvatarSkin_MAT)
  garment.glb    a cloth strip through the chest (material 'pants') named M_uBody_BaseMesh
"""
import os
import sys

import bpy
from mathutils import Vector

out_dir, scripts = sys.argv[sys.argv.index('--') + 1:][:2]
sys.path.insert(0, scripts)
from wearlib import armature, base, export_wearable, new_mesh_obj, rigid  # noqa: E402


def cube(c, h):
    x, y, z = c
    v = [(x + dx * h, y + dy * h, z + dz * h) for dx in (-1, 1) for dy in (-1, 1) for dz in (-1, 1)]
    f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    return v, f


def export_plain(obj, path):
    for o in bpy.context.scene.objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True)


def rename(src, dst):
    os.replace(os.path.join(out_dir, src), os.path.join(out_dir, dst))


# rigid: a plain mesh object, not parented, no armature modifier
v, f = cube((0, -0.6, 1.3), 0.05)
me = bpy.data.meshes.new('free_box')
me.from_pydata(v, [], f)
box = bpy.data.objects.new('free_box', me)
bpy.context.scene.collection.objects.link(box)
export_plain(box, os.path.join(out_dir, 'rigid.glb'))
bpy.data.objects.remove(box, do_unlink=True)

def arm(points):
    """World points -> armature space (the avatar armature is scaled 0.01 and rotated: cm, Y up)."""
    inv = armature().matrix_world.inverted()
    return [tuple(inv @ Vector(p)) for p in points]


def top(part):
    return max((base(part).matrix_world @ p.co).z for p in base(part).data.vertices)


# skinned: a head-riding box well clear of the head
v, f = cube((0, 0, top('Head') + 0.25), 0.05)
hat = new_mesh_obj('Test_Hat', arm(v), f, weights=rigid('Avatar_Head'))
export_wearable([hat], out_dir, 'skinned')
for fn in os.listdir(out_dir):
    if fn.startswith('skinned_'):
        rename(fn, 'skinned.glb')
bpy.data.objects.remove(hat, do_unlink=True)

# bodycopy: the base lBody duplicated, keeping its weights and armature modifier
src = base('lBody')
cp = src.copy()
cp.data = src.data.copy()
cp.name = 'M_lBody_BaseMesh'
bpy.context.scene.collection.objects.link(cp)
export_wearable([cp], out_dir, 'bodycopy')
for fn in os.listdir(out_dir):
    if fn.startswith('bodycopy_'):
        rename(fn, 'bodycopy.glb')
bpy.data.objects.remove(cp, do_unlink=True)

# garment: a strip through the chest with a cloth material, but named like a body mesh
chest = top('uBody') - 0.25
v = [(x, y, z) for x in (-0.4, 0.4) for y in (-0.01, 0.01) for z in (chest - 0.01, chest + 0.01)]
f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
cloth = bpy.data.materials.new('pants')
strip = new_mesh_obj('M_uBody_BaseMesh', arm(v), f, weights=rigid('Avatar_Spine2'), mats=(cloth,))
export_wearable([strip], out_dir, 'garment')
for fn in os.listdir(out_dir):
    if fn.startswith('garment_'):
        rename(fn, 'garment.glb')
print('CLIP_ITEMS DONE')
