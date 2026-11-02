#!/usr/bin/env python3
"""Walk a route through a building's colliders the way a Decentraland avatar moves, and report where it can't.

usage: python3 check_walk.py <building.glb> --route route.json [--place <furniture.glb> <x> <z> <yaw-degrees>]...

route.json: {"waypoints": [[x, z], [x, z, y], ...]} in the building's frame (metres, origin on the floor under its
middle, front facing +Z). The walker starts on the floor below the first waypoint and walks straight from each to the
next. Give a waypoint a y (the floor height you expect to be standing on there) to assert it reached that floor.

The walker: a capsule 0.6 m wide and 1.8 m tall, steps up at most 0.4 m without jumping, can't stand on slopes over 46
degrees, falls when the floor drops away. It stands on *_collider meshes and on the parcel's ground (y 0). Visible
meshes don't count: in Decentraland the collider meshes are what you collide with.

FAIL = the route can't be walked (blocked, a step too high, too steep, a waypoint's floor never reached). WARN = it
can, but badly (hopping up stairs that have no ramp collider, a long fall). Exit 1 on any FAIL.
"""
import argparse
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glbscene  # noqa: E402

RADIUS, HEIGHT = 0.3, 1.8
STEP_UP = 0.40           # Decentraland: ~40 cm without jumping, 45 cm needs a jump
MAX_SLOPE = 46.0         # degrees: walkable slopes go up to 46
RAMP_SLOPE = 40.0        # stairs under a ramp collider at 25 cm x 30 cm come to about 40
STRIDE = 0.05            # metres between samples
HOP = 0.05               # a rise bigger than this in one stride is a hop up a step, not a ramp
FLOOR_TOL = 0.3          # a waypoint's y is reached within this
FALL_WARN = 1.0


def closest_on_triangles(p, a, b, c):
    """The closest point to p on each triangle (a, b, c are (n, 3)): Ericson's region test, vectorised."""
    ab, ac, ap = b - a, c - a, p - a
    d1, d2 = np.einsum('ij,ij->i', ab, ap), np.einsum('ij,ij->i', ac, ap)
    bp, cp = p - b, p - c
    d3, d4 = np.einsum('ij,ij->i', ab, bp), np.einsum('ij,ij->i', ac, bp)
    d5, d6 = np.einsum('ij,ij->i', ab, cp), np.einsum('ij,ij->i', ac, cp)
    va, vb, vc = d3 * d6 - d5 * d4, d5 * d2 - d1 * d6, d1 * d4 - d3 * d2
    denom = va + vb + vc
    safe = np.where(np.abs(denom) > 1e-18, denom, 1.0)
    out = a + ab * (vb / safe)[:, None] + ac * (vc / safe)[:, None]   # inside the face
    ab_t = np.where(np.abs(d1 - d3) > 1e-18, d1 / np.where(np.abs(d1 - d3) > 1e-18, d1 - d3, 1), 0)
    ac_t = np.where(np.abs(d2 - d6) > 1e-18, d2 / np.where(np.abs(d2 - d6) > 1e-18, d2 - d6, 1), 0)
    bc_den = (d4 - d3) + (d5 - d6)
    bc_t = np.where(np.abs(bc_den) > 1e-18, (d4 - d3) / np.where(np.abs(bc_den) > 1e-18, bc_den, 1), 0)
    for cond, val in (((vc <= 0) & (d1 >= 0) & (d3 <= 0), a + ab * ab_t[:, None]),
                      ((vb <= 0) & (d2 >= 0) & (d6 <= 0), a + ac * ac_t[:, None]),
                      ((va <= 0) & (d4 - d3 >= 0) & (d5 - d6 >= 0), b + (c - b) * bc_t[:, None]),
                      ((d6 >= 0) & (d5 <= d6), c), ((d3 >= 0) & (d4 <= d3), b), ((d1 <= 0) & (d2 <= 0), a)):
        out = np.where(cond[:, None], val, out)
    return out


class World:
    """Collider triangles to stand on and bump into, plus the ground plane at y 0."""

    def __init__(self):
        self.tris = np.zeros((0, 3, 3))
        self.owner = []

    def add(self, parts, yaw=0.0, at=(0.0, 0.0)):
        c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
        rot = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
        shift = np.array([at[0], 0.0, at[1]])
        for p in parts:
            if not p.collider:
                continue
            verts = p.verts @ rot.T + shift
            self.tris = np.concatenate([self.tris, verts[p.faces]])
            self.owner += [p.name] * len(p.faces)

    def ground(self, x, z, below):
        """The highest standing surface under (x, z) at or below `below`: (height, slope degrees, what)."""
        best, slope, what = 0.0, 0.0, 'ground'
        if len(self.tris):
            a, b, c = self.tris[:, 0], self.tris[:, 1], self.tris[:, 2]
            # vertical ray down through (x, z): barycentric test in the XZ plane
            e1, e2, p = b - a, c - a, np.array([x, 0.0, z]) - a
            det = e1[:, 0] * e2[:, 2] - e1[:, 2] * e2[:, 0]
            ok = np.abs(det) > 1e-12
            u = np.where(ok, (p[:, 0] * e2[:, 2] - p[:, 2] * e2[:, 0]) / np.where(ok, det, 1), -1)
            v = np.where(ok, (e1[:, 0] * p[:, 2] - e1[:, 2] * p[:, 0]) / np.where(ok, det, 1), -1)
            hit = ok & (u >= -1e-9) & (v >= -1e-9) & (u + v <= 1 + 1e-9)
            y = a[:, 1] + u * e1[:, 1] + v * e2[:, 1]
            n = np.cross(e1, e2)
            up = np.abs(n[:, 1]) / np.maximum(np.linalg.norm(n, axis=1), 1e-12)
            cand = hit & (y <= below + 1e-6) & (up > 1e-3)
            if cand.any():
                i = np.flatnonzero(cand)[np.argmax(y[cand])]
                if y[i] > best:
                    best, slope, what = float(y[i]), math.degrees(math.acos(min(1.0, up[i]))), 'collider'
        return best, slope, what

    def blocker(self, x, z, feet):
        """The name of a collider the capsule standing at (x, feet, z) touches, or None. The capsule's rounded bottom
        sits STEP_UP above the feet (anything lower is stepped onto); it touches a triangle closer than its radius."""
        if not len(self.tris):
            return None
        lo_y, hi_y = feet + STEP_UP + 0.02 + RADIUS, feet + HEIGHT - RADIUS
        t = self.tris
        near = (t[:, :, 0].min(1) < x + RADIUS) & (t[:, :, 0].max(1) > x - RADIUS) & \
               (t[:, :, 2].min(1) < z + RADIUS) & (t[:, :, 2].max(1) > z - RADIUS) & \
               (t[:, :, 1].min(1) < hi_y + RADIUS) & (t[:, :, 1].max(1) > lo_y - RADIUS)
        if not near.any():
            return None
        idx = np.flatnonzero(near)
        a, b, c = t[idx, 0], t[idx, 1], t[idx, 2]
        for h in np.arange(lo_y, hi_y + 1e-9, 0.05):
            p = np.array([x, h, z])
            gap = np.linalg.norm(closest_on_triangles(p, a, b, c) - p, axis=1)
            if gap.min() < RADIUS - 0.01:
                return self.owner[idx[int(np.argmin(gap))]]
        return None


def walk(world, waypoints):
    """Walks the route; returns (problem or None, stats)."""
    x, z = waypoints[0][0], waypoints[0][1]
    start = waypoints[0][2] if len(waypoints[0]) > 2 else 0.0
    feet, _, _ = world.ground(x, z, start + STEP_UP)
    stats = {'length': 0.0, 'hops': 0, 'max_step': 0.0, 'max_fall': 0.0, 'max_slope': 0.0, 'heights': [feet]}
    where = lambda: f'({x:.2f}, {z:.2f}) at y {feet:.2f}'
    name = world.blocker(x, z, feet)
    if name:
        return f'starts inside {name} {where()}', stats
    for i in range(1, len(waypoints)):
        tx, tz = waypoints[i][0], waypoints[i][1]
        dist = math.hypot(tx - x, tz - z)
        n = max(1, int(math.ceil(dist / STRIDE)))
        sx, sz = x, z
        for k in range(1, n + 1):
            x, z = sx + (tx - sx) * k / n, sz + (tz - sz) * k / n
            y, slope, _ = world.ground(x, z, feet + STEP_UP)
            rise = y - feet
            if rise > 1e-6 and slope > MAX_SLOPE:
                return f'too steep to walk up ({slope:.0f} degrees) {where()}', stats
            if rise > HOP:
                stats['hops'] += 1
            stats['max_step'] = max(stats['max_step'], rise)
            stats['max_fall'] = max(stats['max_fall'], -rise)
            if rise > 1e-6:
                stats['max_slope'] = max(stats['max_slope'], slope)
            feet = y
            stats['length'] += dist / n
            stats['heights'].append(feet)
            name = world.blocker(x, z, feet)
            if name:
                return f'blocked by {name} {where()}', stats
        if len(waypoints[i]) > 2 and abs(feet - waypoints[i][2]) > FLOOR_TOL:
            return f'waypoint {i} expects floor y {waypoints[i][2]:g} but the walker stands at y {feet:.2f} ({x:.2f}, {z:.2f})', stats
    return None, stats


def floors(heights):
    """Distinct floor heights the walker stood on for at least a metre (ramps in between don't count)."""
    run, out, last = 0, [], None
    for h in heights:
        if last is not None and abs(h - last) < 0.01:
            run += 1
            if run == int(1.0 / STRIDE) and not any(abs(h - f) < 0.5 for f in out):
                out.append(round(h, 2))
        else:
            run = 0
        last = h
    return sorted(out)


def check(glb, route, place=()):
    rows = []
    add = lambda *r: rows.append(r)
    world = World()
    parts, *_ = glbscene.parts(glb)
    world.add(parts)
    for path, x, z, yaw in place:
        world.add(glbscene.parts(path)[0], yaw, (x, z))
    spec = json.loads(open(route).read())
    wps = spec.get('waypoints') if isinstance(spec, dict) else None
    if not wps or len(wps) < 2 or not all(isinstance(w, list) and len(w) in (2, 3) for w in wps):
        add('FAIL', 'route', os.path.basename(str(route)), 'needs {"waypoints": [[x, z], [x, z, y], ...]}, at least two')
        return rows
    add('INFO', 'colliders', f'{len(set(world.owner))} collider mesh(es), {len(world.tris)} triangles' + (f', {len(place)} placed piece(s)' if place else ''))
    problem, st = walk(world, wps)
    add('FAIL' if problem else 'PASS', 'route', problem or f'{st["length"]:.1f} m walked', 'an avatar can walk every leg')
    found = floors(st['heights'])
    add('INFO', 'floors reached', len(found), ', '.join(f'y {f:g}' for f in found))
    add('INFO', 'highest step up', f'{st["max_step"]:.2f} m', f'<= {STEP_UP} m')
    if st['hops'] >= 3:
        add('WARN', 'stairs', f'{st["hops"]} hops up', 'players hop each step: put a ramp collider over the stairs')
    if st['max_slope'] > RAMP_SLOPE:
        add('WARN', 'ramp slope', f'{st["max_slope"]:.0f} degrees', f'<= {RAMP_SLOPE:g} is comfortable (46 is the limit)')
    if st['max_fall'] > FALL_WARN:
        add('WARN', 'fall', f'{st["max_fall"]:.1f} m', 'the route drops off something: a missing floor or rail collider?')
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('glb')
    ap.add_argument('--route', required=True)
    ap.add_argument('--place', nargs=4, action='append', default=[], metavar=('GLB', 'X', 'Z', 'YAW'),
                    help='a furniture piece placed in the building (its colliders count)')
    a = ap.parse_args(argv)
    place = [(p, float(x), float(z), float(yaw)) for p, x, z, yaw in a.place]
    rows = check(a.glb, a.route, place)
    print(os.path.basename(a.glb))
    for level, label, value, *rule in rows:
        print(f'  {level:<4}  {label:<20} {str(value):<60} {rule[0] if rule else ""}')
    worst = any(r[0] == 'FAIL' for r in rows)
    print('SOME FAILED' if worst else 'NO FAILS')
    return 1 if worst else 0


if __name__ == '__main__':
    sys.exit(main())
