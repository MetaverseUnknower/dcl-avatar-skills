"""One shared swatch texture for a whole scene model (run inside Blender: 3.6 and 4.x).

Every solid-coloured face samples the centre of a colour swatch in one 256 px image, so a model needs one material
(`Palette_MAT`) plus a metallic twin (`Palette_Metal_MAT`) for brass and chrome, instead of a material per colour.
Each material is a draw call per object, so this keeps a scene far inside Decentraland's material and texture caps.

    import sys; sys.path.insert(0, '<skill-dir>/scripts')
    import blender_palette as bp
    pal = bp.Palette({'oak': (176, 134, 88), 'teal': (31, 128, 122), 'brass': (201, 164, 92)})
    pal.paint(seat, 'oak')                       # every face of the object
    pal.paint(sofa, 'teal', faces=[0, 1, 2])     # chosen polygons (by index)
    pal.paint(knob, 'brass', metal=True)
    bp.export('/path/model.glb')                 # backface culling on, then a GLB

Colours are 0-255 sRGB. Up to 64 swatches. Glass, glow and anything that needs a real texture get their own material.
"""
import bpy

GRID = 8      # 8 x 8 swatches
CELL = 32     # px a swatch: wide enough that mipmaps don't bleed neighbours into each other


def _principled(mat):
    return next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')


class Palette:
    def __init__(self, colours, name='T_Palette_D'):
        if len(colours) > GRID * GRID:
            raise ValueError(f'at most {GRID * GRID} swatches')
        self.names = list(colours)
        size = GRID * CELL
        self.image = bpy.data.images.new(name, size, size, alpha=False)
        px = [0.0] * (size * size * 4)
        for k, cname in enumerate(self.names):
            col, row = k % GRID, k // GRID
            rgb = [c / 255.0 for c in colours[cname]]  # image pixels are stored as sRGB for a colour texture
            for y in range(row * CELL, (row + 1) * CELL):
                for x in range(col * CELL, (col + 1) * CELL):
                    i = (y * size + x) * 4
                    px[i:i + 4] = [rgb[0], rgb[1], rgb[2], 1.0]
        self.image.pixels[:] = px
        self.image.update()
        self.image.pack()
        self._mats = {}

    def material(self, metal=False):
        key = 'Palette_Metal_MAT' if metal else 'Palette_MAT'
        if key not in self._mats:
            mat = bpy.data.materials.new(key)
            mat.use_nodes = True
            mat.use_backface_culling = True
            bsdf = _principled(mat)
            tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
            tex.image = self.image
            tex.interpolation = 'Closest'
            mat.node_tree.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
            bsdf.inputs['Metallic'].default_value = 1.0 if metal else 0.0
            bsdf.inputs['Roughness'].default_value = 0.35 if metal else 0.9
            self._mats[key] = mat
        return self._mats[key]

    def uv(self, cname):
        if cname not in self.names:
            raise KeyError(f'no swatch named {cname!r}; the palette has {", ".join(self.names)}')
        k = self.names.index(cname)
        return ((k % GRID + 0.5) / GRID, (k // GRID + 0.5) / GRID)

    def paint(self, obj, cname, faces=None, metal=False):
        """Colour `faces` (polygon indices; all when None) of a mesh object with a swatch."""
        u, v = self.uv(cname)
        mat = self.material(metal)
        me = obj.data
        if mat.name not in [m.name for m in me.materials if m]:
            me.materials.append(mat)
        slot = [m.name if m else None for m in me.materials].index(mat.name)
        layer = me.uv_layers.active or me.uv_layers.new(name='UVMap')
        polys = me.polygons if faces is None else [me.polygons[i] for i in faces]
        for poly in polys:
            poly.material_index = slot
            for li in poly.loop_indices:
                layer.data[li].uv = (u, v)
        me.update()


def cull_backfaces():
    """Blender's default is culling off, which the glTF exporter writes as doubleSided: two draws for every face.
    Leave it off only on materials named *_TwoSided_MAT (leaf cards)."""
    for mat in bpy.data.materials:
        if not mat.name.endswith('_TwoSided_MAT'):
            mat.use_backface_culling = True


def export(path):
    cull_backfaces()
    bpy.ops.export_scene.gltf(filepath=str(path), export_format='GLB', export_apply=True)
