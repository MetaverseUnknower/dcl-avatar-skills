import json
import os
import shutil
import struct
import subprocess
import textwrap
from pathlib import Path

import numpy as np
import pytest

SCRIPTS = Path(__file__).parents[1] / 'skills/creating-dcl-buildings/scripts'
BLENDER = os.environ.get('BLENDER') or shutil.which('blender') or '/Applications/Blender.app/Contents/MacOS/Blender'
pytestmark = pytest.mark.skipif(not Path(BLENDER).exists() and not shutil.which(BLENDER), reason='no Blender')


def build(tmp_path, body):
    script = tmp_path / 'build.py'
    script.write_text(textwrap.dedent(f'''
        import sys, bpy
        sys.path.insert(0, {str(SCRIPTS)!r})
        import blender_palette as bp
        bpy.ops.wm.read_factory_settings(use_empty=True)
        ''') + textwrap.dedent(body))
    run = subprocess.run([BLENDER, '-b', '--factory-startup', '--python-exit-code', '1', '--python', str(script)],
                         capture_output=True, text=True, timeout=180)
    assert run.returncode == 0, run.stdout[-2000:] + run.stderr[-2000:]
    return run


def gltf(path):
    data = path.read_bytes()
    n = struct.unpack('<I', data[12:16])[0]
    return json.loads(data[20:20 + n]), data, 20 + n + 8


def uvs(g, data, bs, mesh_name):
    mesh = next(m for m in g['meshes'] if m['name'] == mesh_name)
    a = g['accessors'][mesh['primitives'][0]['attributes']['TEXCOORD_0']]
    bv = g['bufferViews'][a['bufferView']]
    off = bs + bv.get('byteOffset', 0) + a.get('byteOffset', 0)
    return np.frombuffer(data[off:off + a['count'] * 8], '<f4').reshape(-1, 2)


def test_one_palette_texture_and_one_material_colour_a_whole_model(tmp_path):
    out = tmp_path / 'm.glb'
    build(tmp_path, f'''
        pal = bp.Palette({{'oak': (176, 134, 88), 'teal': (31, 128, 122), 'brass': (201, 164, 92)}})
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.5)); a = bpy.context.object; a.name = 'Seat'; a.data.name = 'Seat'
        bpy.ops.mesh.primitive_cube_add(size=1, location=(2, 0, 0.5)); b = bpy.context.object; b.name = 'Back'; b.data.name = 'Back'
        bpy.ops.mesh.primitive_cube_add(size=0.2, location=(4, 0, 0.1)); c = bpy.context.object; c.name = 'Knob'; c.data.name = 'Knob'
        pal.paint(a, 'oak')
        pal.paint(b, 'teal', faces=[0, 1, 2])
        pal.paint(b, 'oak', faces=[3, 4, 5])
        pal.paint(c, 'brass', metal=True)
        bp.export(r'{out}')
        ''')
    g, data, bs = gltf(out)
    assert sorted(m['name'] for m in g['materials']) == ['Palette_MAT', 'Palette_Metal_MAT']
    assert len(g['images']) == 1
    assert not any(m.get('doubleSided') for m in g['materials'])
    w, h = struct.unpack('>II', data[bs + g['bufferViews'][g['images'][0]['bufferView']].get('byteOffset', 0):][16:24])
    assert (w, h) == (256, 256)
    seat = uvs(g, data, bs, 'Seat')
    assert np.allclose(seat, seat[0], atol=1e-4)  # every corner of every face samples one swatch centre
    assert len({tuple(np.round(u, 3)) for u in uvs(g, data, bs, 'Back')}) == 2


def test_an_unknown_colour_name_says_so(tmp_path):
    script = tmp_path / 'build.py'
    with pytest.raises(AssertionError) as e:
        build(tmp_path, '''
            pal = bp.Palette({'oak': (176, 134, 88)})
            bpy.ops.mesh.primitive_cube_add(); pal.paint(bpy.context.object, 'walnut')
            ''')
    assert 'walnut' in str(e.value)
