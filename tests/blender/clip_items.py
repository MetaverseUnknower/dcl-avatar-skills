"""Builds small test wearables for check_clipping.py on an official avatar .blend.

blender -b AvatarShape_A.blend --python clip_items.py -- <out_dir> <wearlib scripts dir>
Writes, in <out_dir>:
  rigid.glb      an unrigged box (no armature, no Avatar_* nodes) 60 cm in front of the chest
  skinned.glb    a box skinned to Avatar_Head, 25 cm above the head
  bodycopy.glb   a full copy of the avatar's lBody named M_lBody_BaseMesh, skinned like the original
"""
import os
import sys

import bpy

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

# skinned: a head-riding box well clear of the head (armature space: the head top is about 1.75 m up)
head_top = max((armature().matrix_world.inverted() @ (base('Head').matrix_world @ p.co)).z for p in base('Head').data.vertices)
v, f = cube((0, 0, head_top + 0.25), 0.05)
hat = new_mesh_obj('Test_Hat', v, f, weights=rigid('Avatar_Head'))
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
print('CLIP_ITEMS DONE')
