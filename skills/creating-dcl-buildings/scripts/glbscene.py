"""Reads a scene GLB's geometry in world space (node transforms applied), for the scene checkers. Pure Python + numpy."""
import json
import re
import struct
from dataclasses import dataclass

import numpy as np

COMP = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NCOMP = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}
# Decentraland: a mesh is an invisible collider when its name ends in `_collider`, optionally followed by a primitive
COLLIDER = re.compile(r'_collider(_(box|sphere|capsule))?$', re.IGNORECASE)


@dataclass
class Part:
    name: str           # the node's name (Blender's object name), else the mesh's
    verts: np.ndarray   # (n, 3) world-space metres, Y up
    faces: np.ndarray   # (m, 3) vertex indices
    material: int | None

    @property
    def collider(self) -> bool:
        return bool(COLLIDER.search(self.name))


def load(path):
    data = open(path, 'rb').read()
    if data[:4] != b'glTF':
        raise ValueError(f'{path} is not a binary glTF (.glb)')
    n = struct.unpack('<I', data[12:16])[0]
    return json.loads(data[20:20 + n]), data, 20 + n + 8


def accessor(g, data, bs, idx):
    a = g['accessors'][idx]
    bv = g['bufferViews'][a['bufferView']]
    dt = np.dtype(COMP[a['componentType']]).newbyteorder('<')
    k = NCOMP[a['type']]
    stride = bv.get('byteStride', dt.itemsize * k)
    off = bs + bv.get('byteOffset', 0) + a.get('byteOffset', 0)
    raw = np.lib.stride_tricks.as_strided(np.frombuffer(data, np.uint8, offset=off),
                                          (a['count'], dt.itemsize * k), (stride, 1))
    return np.frombuffer(raw.tobytes(), dt).reshape(a['count'], k)


def _local(node):
    if 'matrix' in node:
        return np.array(node['matrix'], float).reshape(4, 4).T
    t = np.array(node.get('translation', [0, 0, 0]), float)
    x, y, z, w = node.get('rotation', [0, 0, 0, 1])
    s = np.array(node.get('scale', [1, 1, 1]), float)
    r = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                  [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                  [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    m = np.eye(4)
    m[:3, :3] = r * s
    m[:3, 3] = t
    return m


def parts(path):
    """Every triangle primitive of every node in the default scene, in world space."""
    g, data, bs = load(path)
    out = []
    scene = g.get('scenes', [{}])[g.get('scene', 0)] if g.get('scenes') else {'nodes': range(len(g.get('nodes', [])))}

    def walk(i, parent):
        node = g['nodes'][i]
        world = parent @ _local(node)
        if 'mesh' in node:
            mesh = g['meshes'][node['mesh']]
            name = node.get('name') or mesh.get('name') or f'node{i}'
            for prim in mesh['primitives']:
                if prim.get('mode', 4) != 4:
                    continue
                v = accessor(g, data, bs, prim['attributes']['POSITION']).astype(float)
                v = (np.c_[v, np.ones(len(v))] @ world.T)[:, :3]
                f = accessor(g, data, bs, prim['indices']).reshape(-1) if 'indices' in prim else np.arange(len(v))
                out.append(Part(name, v, f.reshape(-1, 3).astype(np.int64), prim.get('material')))
        for c in node.get('children', []):
            walk(c, world)

    for i in scene['nodes']:
        walk(i, np.eye(4))
    return out, g, data, bs


def welded(part):
    """(positions, faces) with vertices closer than 0.1 mm merged: exporters split vertices along UV and normal seams."""
    key = np.round(part.verts / 1e-4).astype(np.int64)
    _, weld = np.unique(key, axis=0, return_inverse=True)
    weld = weld.reshape(-1)
    pos = np.zeros((int(weld.max()) + 1 if len(weld) else 0, 3))
    pos[weld] = part.verts
    return pos, weld[part.faces]


def winding(points, tris, chunk=2048):
    """Generalized winding number of each point with respect to a triangle soup: ~1 inside a closed solid (either
    winding: the magnitude is used), ~0 outside, ~0.5 beside a lone sheet. Robust to touching boxes, shared internal
    faces and T-junctions (Van Oosterom and Strackee's solid angle, summed)."""
    out = np.zeros(len(points))
    for i in range(0, len(points), chunk):
        p = points[i:i + chunk, None, :]
        a, b, c = tris[None, :, 0] - p, tris[None, :, 1] - p, tris[None, :, 2] - p
        la, lb, lc = (np.linalg.norm(x, axis=2) for x in (a, b, c))
        det = np.einsum('ijk,ijk->ij', a, np.cross(b, c))
        div = la * lb * lc + np.einsum('ijk,ijk->ij', a, b) * lc + np.einsum('ijk,ijk->ij', b, c) * la + \
            np.einsum('ijk,ijk->ij', c, a) * lb
        out[i:i + chunk] = (2 * np.arctan2(det, div)).sum(1) / (4 * np.pi)
    return np.abs(out)


def sheets(part, offset=1e-3):
    """Collider faces with open space on both sides: one-sided planes, which block from one side only. Returns the
    bounding boxes of the free faces (empty when every face bounds a solid)."""
    pos, faces = welded(part)
    tris = pos[faces]
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    length = np.linalg.norm(n, axis=1)
    keep = length > 1e-12
    if not keep.any():
        return []
    tris_k, n = tris[keep], n[keep] / length[keep, None]
    centre = tris_k.mean(1)
    w = winding(np.vstack([centre + n * offset, centre - n * offset]), tris)
    free = (w[:len(centre)] < 0.75) & (w[len(centre):] < 0.75)
    return [(t.min(0), t.max(0)) for t in tris_k[free]]


def components(part):
    """The part split into its separate solids, each as (verts, faces). Faces two touching solids share (the same
    triangle twice) are dropped as inside the union, and triangles join across an edge only when exactly two share
    it, so boxes that touch along an edge stay separate instead of reading as one broken shape."""
    pos, faces = welded(part)
    key = [tuple(sorted(f)) for f in faces.tolist()]
    seen = {}
    for k in key:
        seen[k] = seen.get(k, 0) + 1
    faces = faces[[seen[k] == 1 for k in key]] if len(faces) else faces
    edges = {}
    for fi, (a, b, c) in enumerate(faces):
        for x, y in ((a, b), (b, c), (c, a)):
            edges.setdefault((min(x, y), max(x, y)), []).append(fi)
    parent = list(range(len(faces)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for shared in edges.values():
        if len(shared) == 2:
            ra, rb = find(shared[0]), find(shared[1])
            if ra != rb:
                parent[ra] = rb
    groups = {}
    for fi in range(len(faces)):
        groups.setdefault(find(fi), []).append(fi)
    return [(pos, faces[idx]) for idx in groups.values()]


def planes(pos, faces):
    """Each face's plane (unit normal n, offset d) oriented so the piece's centre is behind it (n·p - d < 0)."""
    a, b, c = pos[faces[:, 0]], pos[faces[:, 1]], pos[faces[:, 2]]
    n = np.cross(b - a, c - a)
    length = np.linalg.norm(n, axis=1)
    keep = length > 1e-12
    n, a = n[keep] / length[keep, None], a[keep]
    d = np.einsum('ij,ij->i', n, a)
    centre = pos[np.unique(faces)].mean(0)
    flip = n @ centre - d > 0
    n[flip], d[flip] = -n[flip], -d[flip]
    return n, d


def is_convex(pos, faces, tol=1e-4):
    used = pos[np.unique(faces)]
    if len(faces) < 4:
        return True
    n, d = planes(pos, faces)
    size = max(float(np.ptp(used, axis=0).max()), 1e-6)
    return bool(np.all(used @ n.T - d <= tol * size))


def inside_any(points, solids, margin=0.0):
    """For each point, whether it's inside any convex solid (given as (normals, offsets)), shrunk by `margin`."""
    hit = np.zeros(len(points), bool)
    for n, d in solids:
        hit |= np.all(points @ n.T - d < -margin, axis=1)
    return hit
