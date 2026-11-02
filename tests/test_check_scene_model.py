import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

import glbfactory as gf

SCRIPT = Path(__file__).parents[1] / 'skills/creating-dcl-buildings/scripts/check_scene_model.py'
spec = importlib.util.spec_from_file_location('check_scene_model', SCRIPT)
csm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(csm)


def levels(rows, label):
    """Every level reported for rows whose label starts with `label`."""
    return [r[0] for r in rows if r[1].startswith(label)]


def fails(rows):
    return [r for r in rows if r[0] == 'FAIL']


def chair(tmp_path, collider_front=0.2, extra=(), name='chair.glb', **kw):
    """A chair facing +Z: seat top 0.47 m, seat from z -0.25 to 0.25, back at the rear, origin on the floor under
    the middle. Its collider stops at `collider_front`."""
    nodes = [gf.box('Seat', (-0.25, 0.40, -0.25), (0.25, 0.47, 0.25)),
             gf.box('Legs', (-0.22, 0.0, -0.22), (0.22, 0.40, 0.22)),
             gf.box('Back', (-0.25, 0.47, -0.25), (0.25, 1.0, -0.18)),
             gf.box('Chair_collider', (-0.25, 0.0, -0.25), (0.25, 0.47, collider_front), material=None),
             *extra]
    return gf.write(tmp_path / name, nodes, **kw)


SEAT = {'file': 'models/chair.glb', 'scale': 1, 'uprightX': 0, 'yawOffset': 0, 'collision': 'colliders',
        'kind': 'bench', 'seats': [{'across': 0, 'forward': 0.38, 'rise': 0, 'orbForward': 0, 'orbRise': 0.7}]}


def test_a_well_made_chair_passes(tmp_path):
    rows = csm.check(chair(tmp_path), 'furniture')
    assert fails(rows) == []
    assert levels(rows, 'colliders') == ['PASS']


def test_furniture_without_a_collider_fails_but_decor_may_have_none(tmp_path):
    p = gf.write(tmp_path / 'vase.glb', [gf.box('Vase', (-0.1, 0, -0.1), (0.1, 0.4, 0.1))])
    assert levels(csm.check(p, 'furniture'), 'colliders') == ['FAIL']
    assert fails(csm.check(p, 'decor')) == []


def test_a_collider_with_a_material_fails(tmp_path):
    p = chair(tmp_path, extra=[gf.box('Box_collider', (-1, 0, -1), (-0.6, 0.3, -0.6), material=0)])
    assert levels(csm.check(p, 'furniture'), 'collider Box_collider material') == ['FAIL']


def test_a_one_sided_plane_collider_fails(tmp_path):
    p = chair(tmp_path, extra=[gf.plane('Floor_collider', (-1, 0, -1), (1, 0, 1))])
    assert levels(csm.check(p, 'furniture'), 'collider Floor_collider closed') == ['FAIL']


def test_a_blender_duplicate_suffix_is_not_a_collider(tmp_path):
    # Blender names a copy `Seat_collider.001`: Decentraland renders it as a visible mesh and it collides with nothing
    p = chair(tmp_path, extra=[gf.box('Seat_collider.001', (-1, 0, -1), (-0.6, 0.3, -0.6), material=None)])
    assert levels(csm.check(p, 'furniture'), 'collider names') == ['FAIL']


def test_primitive_suffixes_count_as_colliders(tmp_path):
    p = gf.write(tmp_path / 'p.glb', [gf.box('Pot', (-0.2, 0, -0.2), (0.2, 0.5, 0.2)),
                                      gf.box('Pot_collider_box', (-0.2, 0, -0.2), (0.2, 0.5, 0.2), material=None)])
    rows = csm.check(p, 'furniture')
    assert levels(rows, 'colliders') == ['PASS'] and levels(rows, 'collider names') != ['FAIL']


def l_prism(name):
    """A closed L-shaped prism: one collider mesh that isn't convex."""
    pts = [(0, 0), (2, 0), (2, 1), (1, 1), (1, 2), (0, 2), (0, 1)]
    verts = [(x, 0, z) for x, z in pts] + [(x, 1, z) for x, z in pts]
    n = len(pts)
    faces = []
    for i in range(n):
        j = (i + 1) % n
        faces += [(i, j, n + j), (i, n + j, n + i)]
    caps = [(0, 1, 2), (0, 2, 3), (0, 3, 6), (6, 3, 4), (6, 4, 5)]
    faces += [(c, b, a) for a, b, c in caps] + [(n + a, n + b, n + c) for a, b, c in caps]
    return gf.mesh(name, verts, faces, material=None)


def test_a_concave_collider_warns_but_separate_boxes_in_one_mesh_pass(tmp_path):
    # the docs recommend convex colliders (concave ones stutter); Decentraland still uses a concave one
    p = chair(tmp_path, extra=[l_prism('Corner_collider')])
    assert levels(csm.check(p, 'furniture'), 'collider Corner_collider convex') == ['WARN']
    a, b = gf.box('x', (2, 0, 0), (3, 1, 1)), gf.box('y', (4, 0, 0), (5, 1, 1))
    two = gf.mesh('Pair_collider', np.vstack([a['verts'], b['verts']]), np.vstack([a['faces'], b['faces'] + 8]), None)
    q = chair(tmp_path, extra=[two], name='q.glb')
    assert levels(csm.check(q, 'decor'), 'collider Pair_collider convex') == ['PASS']


def test_origin_must_be_on_the_floor_under_the_middle(tmp_path):
    lifted = gf.write(tmp_path / 'l.glb', [gf.box('T', (-0.4, 0.5, -0.4), (0.4, 1.2, 0.4)),
                                           gf.box('T_collider', (-0.4, 0.5, -0.4), (0.4, 1.2, 0.4), material=None)])
    assert levels(csm.check(lifted, 'furniture'), 'origin on the floor') == ['FAIL']
    shifted = gf.write(tmp_path / 's.glb', [gf.box('T', (0.6, 0, -0.4), (1.4, 0.7, 0.4)),
                                            gf.box('T_collider', (0.6, 0, -0.4), (1.4, 0.7, 0.4), material=None)])
    assert levels(csm.check(shifted, 'furniture'), 'origin under the middle') == ['FAIL']


def test_node_translation_is_applied(tmp_path):
    # vertices from y -0.5, moved up by the node's translation: on the floor
    down = gf.write(tmp_path / 'd.glb', [gf.box('T', (-0.4, -0.5, -0.4), (0.4, 0.2, 0.4), translation=(0, 0.5, 0))])
    assert levels(csm.check(down, 'decor'), 'origin on the floor') == ['PASS']
    up = gf.write(tmp_path / 'u.glb', [gf.box('T', (-0.4, 0, -0.4), (0.4, 0.7, 0.4), translation=(0, 0.5, 0))])
    assert levels(csm.check(up, 'decor'), 'origin on the floor') == ['FAIL']


def test_a_building_must_stay_inside_its_footprint(tmp_path):
    ok = gf.write(tmp_path / 'b.glb', [gf.box('Walls', (-7, 0, -7), (7, 6, 7)),
                                       gf.box('Walls_collider', (-7, 0, -7), (7, 6, 7), material=None)])
    assert fails(csm.check(ok, 'building', footprint='1x1')) == []
    out = gf.write(tmp_path / 'o.glb', [gf.box('Walls', (-7, 0, -7), (9, 6, 7)),
                                        gf.box('Walls_collider', (-7, 0, -7), (7, 6, 7), material=None)])
    assert levels(csm.check(out, 'building', footprint='1x1'), 'inside the footprint') == ['FAIL']
    # 1x2 is 16 m wide (X) by 32 m deep (Z)
    deep = gf.write(tmp_path / 'd.glb', [gf.box('Walls', (-7, 0, -15), (7, 6, 15)),
                                         gf.box('Walls_collider', (-7, 0, -15), (7, 6, 15), material=None)])
    assert levels(csm.check(deep, 'building', footprint='1x2'), 'inside the footprint') == ['PASS']
    assert levels(csm.check(deep, 'building', footprint='1x1'), 'inside the footprint') == ['FAIL']


def test_a_building_needs_a_footprint():
    with pytest.raises(ValueError):
        csm.parse_footprint('3x3')
    assert csm.parse_footprint('0.5x0.5') == (8.0, 8.0)
    assert csm.parse_footprint('4x4') == (64.0, 64.0)


@pytest.mark.parametrize('size,level', [((512, 512), 'PASS'), ((1000, 1000), 'FAIL'), ((2048, 2048), 'FAIL'),
                                        ((256, 64), 'PASS')])
def test_textures_are_powers_of_two_up_to_1024(tmp_path, size, level):
    p = chair(tmp_path, images=[size])
    assert levels(csm.check(p, 'furniture'), 'texture 0') == [level]


def test_triangles_over_the_recommendation_only_warn(tmp_path):
    cubes = [gf.box(f'Brick{i}', (-7 + (i % 20) * 0.7, 0, -7 + (i // 20) * 0.7),
                    (-6.8 + (i % 20) * 0.7, 0.2, -6.8 + (i // 20) * 0.7)) for i in range(300)]
    p = gf.write(tmp_path / 'b.glb', cubes + [gf.box('Base_collider', (-7, 0, -7), (7, 0.2, 7), material=None)])
    rows = csm.check(p, 'building', footprint='1x1')
    assert levels(rows, 'triangles') == ['WARN'] and fails(rows) == []


def test_heavy_materials_and_blend_warn(tmp_path):
    mats = [{'name': f'M{i}'} for i in range(4)] + [{'name': 'Glass', 'alphaMode': 'BLEND', 'doubleSided': True}]
    p = chair(tmp_path, materials=mats)
    rows = csm.check(p, 'furniture')
    assert levels(rows, 'materials') == ['WARN']
    assert levels(rows, 'material Glass alphaMode') == ['WARN']
    assert levels(rows, 'material Glass doubleSided') == ['WARN']
    assert fails(rows) == []


def test_sittables_seat_must_have_a_clear_standing_spot(tmp_path):
    seats = tmp_path / 'chair.sittables.json'
    seats.write_text(json.dumps(SEAT))
    assert fails(csm.check(chair(tmp_path), 'furniture', sittables=seats)) == []
    long_collider = chair(tmp_path, collider_front=0.6, name='long.glb')
    assert levels(csm.check(long_collider, 'furniture', sittables=seats), 'seat 0 standing spot') == ['FAIL']


def test_a_stool_seat_is_left_to_the_kit(tmp_path):
    seats = tmp_path / 'stool.sittables.json'
    seats.write_text(json.dumps({**SEAT, 'collision': 'stool', 'kind': 'stool',
                                 'seats': [{'across': 0, 'forward': 0.1, 'rise': 0.5}]}))
    rows = csm.check(chair(tmp_path, collider_front=0.6), 'furniture', sittables=seats)
    assert levels(rows, 'seat 0 standing spot') == ['INFO']


def test_a_broken_sittables_file_fails(tmp_path):
    bad = tmp_path / 'bad.sittables.json'
    bad.write_text('{"seats": [}')
    assert levels(csm.check(chair(tmp_path), 'furniture', sittables=bad), 'sittables') == ['FAIL']
    empty = tmp_path / 'empty.sittables.json'
    empty.write_text(json.dumps({**SEAT, 'seats': []}))
    assert levels(csm.check(chair(tmp_path), 'furniture', sittables=empty), 'sittables') == ['FAIL']
    odd = tmp_path / 'odd.sittables.json'
    odd.write_text(json.dumps({**SEAT, 'collision': 'mesh'}))
    assert levels(csm.check(chair(tmp_path), 'furniture', sittables=odd), 'sittables') == ['FAIL']


def test_the_cli_exits_1_on_a_fail(tmp_path):
    import subprocess, sys
    good = chair(tmp_path)
    bad = gf.write(tmp_path / 'v.glb', [gf.box('Vase', (-0.1, 0, -0.1), (0.1, 0.4, 0.1))])
    run = lambda p: subprocess.run([sys.executable, str(SCRIPT), str(p), '--kind', 'furniture'], capture_output=True, text=True)
    ok, ko = run(good), run(bad)
    assert ok.returncode == 0 and ok.stdout.strip().endswith('NO FAILS')
    assert ko.returncode == 1 and 'SOME FAILED' in ko.stdout


def test_touching_boxes_in_one_collider_are_separate_solids(tmp_path):
    # a couch's seat and back boxes meet along an edge and share corners: each is still a closed convex box
    seat, back = gf.box('s', (-1, 0, -0.4), (1, 0.45, 0.3)), gf.box('b', (-1, 0.45, -0.4), (1, 0.9, -0.2))
    arm = gf.box('a', (1, 0, -0.4), (1.2, 0.6, 0.3))
    v = np.vstack([seat['verts'], back['verts'], arm['verts']])
    f = np.vstack([seat['faces'], back['faces'] + 8, arm['faces'] + 16])
    p = gf.write(tmp_path / 'c.glb', [gf.box('Couch', (-1, 0, -0.4), (1.2, 0.9, 0.3)), gf.mesh('Couch_collider', v, f, None)])
    rows = csm.check(p, 'furniture')
    assert levels(rows, 'collider Couch_collider closed') == ['PASS']
    assert levels(rows, 'collider Couch_collider convex') == ['PASS']


def stacked(lower_diag_flip=False):
    """Two boxes stacked so they share a whole face (a wall in two courses), in one collider mesh."""
    a, b = gf.box('a', (-2, 0, -0.1), (2, 1.5, 0.1)), gf.box('b', (-2, 1.5, -0.1), (2, 3, 0.1))
    fb = b['faces'].copy()
    if lower_diag_flip:  # b's bottom face (corners 0, 1, 4, 5) split along the other diagonal
        fb[4], fb[5] = (0, 1, 4), (1, 5, 4)
    return gf.mesh('Wall_collider', np.vstack([a['verts'], b['verts']]), np.vstack([a['faces'], fb + 8]), None)


def test_stacked_boxes_sharing_a_face_are_closed(tmp_path):
    for flip in (False, True):
        p = gf.write(tmp_path / f'w{flip}.glb', [gf.box('Wall', (-2, 0, -0.1), (2, 3, 0.1)), stacked(flip)])
        rows = csm.check(p, 'decor')
        assert levels(rows, 'collider Wall_collider closed') == ['PASS'], (flip, rows)
        assert levels(rows, 'collider Wall_collider convex') == ['PASS'], (flip, rows)
