"""Tiny GLB writer for the checker tests: boxes, planes, materials and embedded PNGs, nothing else."""
import json
import struct
import zlib

import numpy as np

# 12 triangles, outward winding, unit cube corners indexed as bits (x, y, z)
_BOX_FACES = [(0, 2, 3), (0, 3, 1), (4, 5, 7), (4, 7, 6), (0, 1, 5), (0, 5, 4),
              (2, 6, 7), (2, 7, 3), (0, 4, 6), (0, 6, 2), (1, 3, 7), (1, 7, 5)]


def box(name, lo, hi, material=0, translation=None):
    """A closed axis-aligned box from corner `lo` to corner `hi` (metres, Y up)."""
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    verts = np.array([[hi[0] if i & 4 else lo[0], hi[1] if i & 2 else lo[1], hi[2] if i & 1 else lo[2]]
                      for i in range(8)])
    return {'name': name, 'verts': verts, 'faces': np.array(_BOX_FACES), 'material': material,
            'translation': translation}


def mesh(name, verts, faces, material=0, translation=None):
    return {'name': name, 'verts': np.asarray(verts, float), 'faces': np.asarray(faces), 'material': material,
            'translation': translation}


def plane(name, lo, hi, material=None):
    """A one-sided horizontal quad at height lo[1], from (lo.x, lo.z) to (hi.x, hi.z)."""
    y = lo[1]
    verts = [[lo[0], y, lo[2]], [hi[0], y, lo[2]], [hi[0], y, hi[2]], [lo[0], y, hi[2]]]
    return mesh(name, verts, [(0, 2, 1), (0, 3, 2)], material)


def png(w, h):
    raw = b''.join(b'\x00' + b'\x80\x80\x80' * w for _ in range(h))
    chunk = lambda t, d: struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xFFFFFFFF)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) + \
        chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')


def write(path, nodes, materials=None, images=None):
    """nodes: dicts from box()/mesh()/plane(). materials: list of dicts merged into glTF materials (default one
    plain material). images: list of (w, h); image i becomes material i's base colour texture when both exist."""
    materials = [{'name': 'Mat'}] if materials is None else materials
    images = images or []
    blob = bytearray()
    views, accessors, meshes, gnodes = [], [], [], []

    def add(arr, target):
        while len(blob) % 4:
            blob.append(0)
        views.append({'buffer': 0, 'byteOffset': len(blob), 'byteLength': arr.nbytes, **({'target': target} if target else {})})
        blob.extend(arr.tobytes())
        return len(views) - 1

    for n in nodes:
        v = n['verts'].astype(np.float32)
        f = n['faces'].astype(np.uint32).reshape(-1)
        accessors.append({'bufferView': add(v, 34962), 'componentType': 5126, 'count': len(v), 'type': 'VEC3',
                          'min': v.min(0).tolist(), 'max': v.max(0).tolist()})
        accessors.append({'bufferView': add(f, 34963), 'componentType': 5125, 'count': len(f), 'type': 'SCALAR'})
        prim = {'attributes': {'POSITION': len(accessors) - 2}, 'indices': len(accessors) - 1}
        if n['material'] is not None:
            prim['material'] = n['material']
        meshes.append({'name': n['name'], 'primitives': [prim]})
        node = {'name': n['name'], 'mesh': len(meshes) - 1}
        if n.get('translation') is not None:
            node['translation'] = list(n['translation'])
        gnodes.append(node)

    gimages, textures = [], []
    for i, (w, h) in enumerate(images):
        gimages.append({'bufferView': add(np.frombuffer(png(w, h), np.uint8), None), 'mimeType': 'image/png'})
        textures.append({'source': i})
    gmats = []
    for i, m in enumerate(materials):
        m = {'pbrMetallicRoughness': {'baseColorFactor': [0.8, 0.8, 0.8, 1]}, **m}
        if i < len(textures):
            m['pbrMetallicRoughness'] = {**m['pbrMetallicRoughness'], 'baseColorTexture': {'index': i}}
        gmats.append(m)

    gltf = {'asset': {'version': '2.0'}, 'scene': 0, 'scenes': [{'nodes': list(range(len(gnodes)))}],
            'nodes': gnodes, 'meshes': meshes, 'accessors': accessors, 'bufferViews': views,
            'buffers': [{'byteLength': len(blob)}], 'materials': gmats}
    if gimages:
        gltf['images'], gltf['textures'] = gimages, textures
    js = json.dumps(gltf).encode()
    js += b' ' * (-len(js) % 4)
    while len(blob) % 4:
        blob.append(0)
    out = struct.pack('<III', 0x46546C67, 2, 28 + len(js) + len(blob)) + struct.pack('<II', len(js), 0x4E4F534A) + js + \
        struct.pack('<II', len(blob), 0x004E4942) + bytes(blob)
    with open(path, 'wb') as fh:
        fh.write(out)
    return path
