# Lessons from real scene-model builds

Mistakes agents made on real buildings and furniture, and the rule each taught. Add to this when you're corrected.

## Weight

- **A 1×1 café came out at 7,788 triangles**, 78% of the parcel's 10,000, leaving 1,700 for every chair, sign, prop
  and person's model in the scene. Budget the building at ~30% of its footprint (1×1 ≈ 3,000) and spend detail where
  people look: the entrance and the counter, not the back wall or the roof's underside.
- **Twelve flat-colour materials** on one building and four on one couch. Every material is a draw call per object.
  One palette texture (`blender_palette.py`) colours a whole model with one material.
- **Everything exported double-sided**, because Blender's backface culling is off by default and the glTF exporter
  writes that as `doubleSided: true`. Export through `bp.export()`; leave culling off only on `*_TwoSided_MAT` cards.
- **Glass as alpha BLEND, double-sided:** use MASK where it doesn't need to be see-through, and if it does, keep it
  one-sided and on its own mesh (blend sorting is per object).

## Structure

- **Tables and chairs baked into the building** as part of its GLB, with one collider box per group. They can't be sat
  on, moved or reused, and they spend the building's budget. Furniture is its own piece (`creating-dcl-furnishings`).
- **The stair ramp that worked:** a wedge collider through the treads' midpoints, rising the full flight, with the
  stairwell's slab opening starting where headroom drops under 2.2 m. Visitors walk up smoothly instead of hopping.
- **Unsure facts, settled:** walkable slopes go to 46° (docs); collider triangles aren't rendered, so the checker
  reports them separately from the visible count; the old 20 m height cap is gone (330 m, soft).

## Checking

- **A route that hugs a wall** gets blocked by a shelf or rail the building is right to have. A blocked route names the
  collider and the point: if a person could walk there, the building is wrong; if the route squeezed past a corner,
  move the waypoint into the open (leave 0.3 m either side of the walker's centre).
- **Furniture in the walk:** check the building alone first, then with its furniture placed (`--place`); a sofa in the
  doorway is a layout problem, not a building one.
