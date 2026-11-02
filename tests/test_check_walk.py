import importlib.util
import json
import math
from pathlib import Path

import numpy as np

import glbfactory as gf

SCRIPTS = Path(__file__).parents[1] / 'skills/creating-dcl-buildings/scripts'
spec = importlib.util.spec_from_file_location('check_walk', SCRIPTS / 'check_walk.py')
cw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cw)


def levels(rows, label):
    return [r[0] for r in rows if r[1].startswith(label)]


def fails(rows):
    return [r for r in rows if r[0] == 'FAIL']


def room(door_width=1.2, door=True, extra=()):
    """A 10 x 10 m room, 3 m walls 0.2 m thick, its front wall (z +5) with a doorway 2.4 m high centred on x 0."""
    t, h = 0.2, 3.0
    nodes = [gf.box('Shell', (-5, 0, -5), (5, h, 5)),
             gf.box('Back_collider', (-5, 0, -5), (5, h, -5 + t), material=None),
             gf.box('Left_collider', (-5, 0, -5), (-5 + t, h, 5), material=None),
             gf.box('Right_collider', (5 - t, 0, -5), (5, h, 5), material=None)]
    if door:
        half = door_width / 2
        nodes += [gf.box('FrontL_collider', (-5, 0, 5 - t), (-half, h, 5), material=None),
                  gf.box('FrontR_collider', (half, 0, 5 - t), (5, h, 5), material=None),
                  gf.box('Lintel_collider', (-half, 2.4, 5 - t), (half, h, 5), material=None)]
    else:
        nodes.append(gf.box('Front_collider', (-5, 0, 5 - t), (5, h, 5), material=None))
    return nodes + list(extra)


def wedge(name, x0, x1, z0, z1, y_top):
    """A ramp rising from y 0 at z0 to y_top at z1, between x0 and x1: a closed triangular prism."""
    v = [(x0, 0, z0), (x0, 0, z1), (x0, y_top, z1), (x1, 0, z0), (x1, 0, z1), (x1, y_top, z1)]
    f = [(0, 2, 1), (3, 4, 5), (0, 1, 4), (0, 4, 3), (1, 2, 5), (1, 5, 4), (0, 3, 5), (0, 5, 2)]
    return gf.mesh(name, v, f, material=None)


def route(tmp_path, *points, name='route.json'):
    p = tmp_path / name
    p.write_text(json.dumps({'waypoints': [list(pt) for pt in points]}))
    return p


def walk(tmp_path, nodes, *points, place=()):
    glb = gf.write(tmp_path / 'b.glb', nodes)
    return cw.check(glb, route(tmp_path, *points), place=list(place))


def test_walking_in_through_a_doorway_passes(tmp_path):
    rows = walk(tmp_path, room(), (0, 8), (0, 0), (-3, -3))
    assert fails(rows) == []
    assert levels(rows, 'route') == ['PASS']


def test_a_doorway_too_narrow_for_the_avatar_fails(tmp_path):
    rows = walk(tmp_path, room(door_width=0.5), (0, 8), (0, 0))
    assert levels(rows, 'route') == ['FAIL']
    assert 'Front' in [r for r in rows if r[1] == 'route'][0][2]  # names what blocked it


def test_a_wall_without_a_door_fails(tmp_path):
    assert levels(walk(tmp_path, room(door=False), (0, 8), (0, 0)), 'route') == ['FAIL']


def test_a_ramp_collider_up_to_an_upper_floor_passes(tmp_path):
    # the ramp rises towards +z along the left wall; walk to its foot, climb it onto the upper floor, cross it
    nodes = room(extra=[wedge('Stairs_collider', -4.6, -3.4, -1.0, 3.0, 3.0),
                        gf.box('Upper_collider', (-4.8, 2.8, 3.0), (4.8, 3.0, 4.8), material=None)])
    rows = walk(tmp_path, nodes, (0, 8), (0, 2), (-4.0, -1.6), (-4.0, 3.5, 3.0), (2, 4))
    assert fails(rows) == [], rows
    assert [r for r in rows if r[1] == 'floors reached'][0][2] == 2


def test_bare_step_colliders_warn_that_players_hop(tmp_path):
    steps = [gf.box(f'Step{i}_collider', (-4.6, 0, -1 + i * 0.3), (-3.4, 0.25 * (i + 1), -1 + (i + 1) * 0.3), material=None)
             for i in range(6)]
    rows = walk(tmp_path, room(extra=steps), (0, 8), (0, 2), (-4.0, -1.6), (-4.0, 0.65, 1.5))
    assert fails(rows) == []
    assert levels(rows, 'stairs') == ['WARN']


def test_steps_too_high_to_step_up_fail(tmp_path):
    steps = [gf.box(f'Step{i}_collider', (-4.6, 0, -1 + i * 0.5), (-3.4, 0.5 * (i + 1), -1 + (i + 1) * 0.5), material=None)
             for i in range(4)]
    rows = walk(tmp_path, room(extra=steps), (0, 8), (0, 2), (-4.0, -1.6), (-4.0, 1.5, 2.0))
    assert levels(rows, 'route') == ['FAIL']


def test_a_ramp_steeper_than_46_degrees_fails(tmp_path):
    # 3 m up over 2 m: 56 degrees
    nodes = room(extra=[wedge('Stairs_collider', -4.6, -3.4, 1.0, 3.0, 3.0)])
    rows = walk(tmp_path, nodes, (0, 8), (0, 2), (-4.0, 0.6), (-4.0, 2.9, 3.0))
    assert levels(rows, 'route') == ['FAIL']


def test_a_waypoint_on_a_floor_it_never_reached_fails(tmp_path):
    # an upper floor with no stairs up to it: the walker stays below
    nodes = room(extra=[gf.box('Upper_collider', (-4.8, 2.8, -4.8), (4.8, 3.0, -1.0), material=None)])
    rows = walk(tmp_path, nodes, (0, 8), (0, 0), (0, -3, 3.0))
    assert levels(rows, 'route') == ['FAIL']


def test_furniture_placed_in_the_doorway_blocks_the_route(tmp_path):
    couch = gf.write(tmp_path / 'couch.glb', [gf.box('Couch', (-1, 0, -0.4), (1, 0.8, 0.4)),
                                              gf.box('Couch_collider', (-1, 0, -0.4), (1, 0.8, 0.4), material=None)])
    clear = walk(tmp_path, room(), (0, 8), (0, 0), place=[(couch, 3.0, -3.0, 0)])
    assert fails(clear) == []
    blocked = walk(tmp_path, room(), (0, 8), (0, 0), place=[(couch, 0.0, 4.0, 90)])
    assert levels(blocked, 'route') == ['FAIL']


def test_the_cli_reads_route_and_placements(tmp_path):
    import subprocess, sys
    glb = gf.write(tmp_path / 'b.glb', room())
    r = route(tmp_path, (0, 8), (0, 0))
    ok = subprocess.run([sys.executable, str(SCRIPTS / 'check_walk.py'), str(glb), '--route', str(r)],
                        capture_output=True, text=True)
    assert ok.returncode == 0 and ok.stdout.strip().endswith('NO FAILS'), ok.stdout + ok.stderr


def two_course(name, lo, hi):
    """A wall box built as two stacked courses whose shared face is split along different diagonals."""
    mid = (lo[1] + hi[1]) / 2
    a, b = gf.box('a', lo, (hi[0], mid, hi[2])), gf.box('b', (lo[0], mid, lo[2]), hi)
    fb = b['faces'].copy()
    fb[4], fb[5] = (0, 1, 4), (1, 5, 4)
    return gf.mesh(name, np.vstack([a['verts'], b['verts']]), np.vstack([a['faces'], fb + 8]), None)


def test_walls_built_from_stacked_courses_block_and_let_through_the_door(tmp_path):
    t, h = 0.2, 3.0
    walls = [gf.box('Shell', (-5, 0, -5), (5, h, 5)),
             two_course('Back_collider', (-5, 0, -5), (5, h, -5 + t)),
             two_course('Left_collider', (-5, 0, -5), (-5 + t, h, 5)),
             two_course('Right_collider', (5 - t, 0, -5), (5, h, 5)),
             two_course('FrontL_collider', (-5, 0, 5 - t), (-0.6, h, 5)),
             two_course('FrontR_collider', (0.6, 0, 5 - t), (5, h, 5))]
    assert fails(walk(tmp_path, walls, (0, 8), (0, 0), (-3, -3))) == []
    assert levels(walk(tmp_path, walls, (0, 0), (-7, 0)), 'route') == ['FAIL']
