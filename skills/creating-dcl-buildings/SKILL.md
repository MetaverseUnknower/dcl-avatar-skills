---
name: creating-dcl-buildings
description: Use when building, fixing, exporting or checking a walk-in building for a Decentraland scene or World in Blender (a shop, café, house, tower, kiosk, pavilion sized in parcels), including colliders visitors walk on and bump into, doors and doorways, stairs, ramps and upper floors, triangle and material budgets, texture palettes, or a GLB that people walk through, get stuck in or float up.
---

# Creating Decentraland Buildings

## Overview

A building is one static GLB that visitors **walk into**: through a doorway, round the rooms, up stairs to upper floors. In Decentraland you collide only with meshes named `*_collider`, so a building is two models in one file: what people see, and the invisible boxes they stand on and bump into. Both have to be right.

Decentraland's triangle, material and texture limits are **soft** (the Creator Hub warns; the scene runs slower). Only file size and file count stop a deploy. The budgets here are recommendations for a building that leaves room for everything else in the scene.

**Done means:** `check_scene_model.py` reports no FAIL, `check_walk.py` walks a route through every room and up every stair with no FAIL, and the person has seen fresh renders of the current version, outside and in.

`<skill-dir>` is the folder this SKILL.md is in. `requirements.md` there has every documented rule with its source; `lessons.md` has mistakes agents made on real buildings. Read `lessons.md` first. Furniture and decor are a separate skill, `creating-dcl-furnishings`, which uses the same scripts.

## Workflow

1. **Settle the brief** (or run `shaping-dcl-item-ideas`): footprint in parcels (0.5×0.5, 1×1, 1×2, 2×2, 4×4), floors, rooms, the doorway, style. **Furniture is not part of the building**: tables, chairs, sofas and shelves are separate pieces (they get moved, sat on through `dcl-sittables`, and reused). The building keeps fixed fittings only: stairs, rails, a counter, built-in benches, shelving fixed to a wall.
2. **Script the build** in Blender Python, so every fix is a re-run. Model in metres; the exporter turns Blender's Z-up into glTF Y-up, and Blender's −Y (the front view) becomes glTF **+Z**: put the entrance on the **front, glTF +Z**. Origin on the floor under the **middle of the footprint**.
3. **Colour with one palette** (`scripts/blender_palette.py`): one 256 px swatch texture, one material, a metallic twin; glass and glow get their own. Export with `bp.export()`, which turns backface culling on (Blender's default exports every face double-sided).
4. **Build the colliders as their own boxes**, named `*_collider`, no material:
   - walls: closed boxes (a plane blocks from one side only), the doorway left open
   - every floor and landing a box; railings round stairwells and open edges
   - **stairs: a ramp collider over the steps**, a wedge along the step nosings meeting the upper floor flush (≤ 40°), or visitors hop each step
   - keep each piece convex (split L shapes into boxes)
5. **Write `route.json`**: waypoints from outside, in through the doorway, round every room, up every stair, across every upper floor. Give each waypoint on an upper floor its floor height (`[x, z, y]`).
6. **Check:**

   | Check | Command |
   |---|---|
   | Colliders, placement, footprint, textures, weight | `python3 <skill-dir>/scripts/check_scene_model.py building.glb --kind building --footprint 1x1` |
   | Walkability | `python3 <skill-dir>/scripts/check_walk.py building.glb --route route.json` |
   | With its furniture placed | add `--place chair.glb <x> <z> <yaw>` per piece |

   A blocked route names the collider and where: move the route if it hugged a wall, fix the building if a person couldn't pass there either.
7. **Render** the outside from several angles and the inside at eye height (1.6 m), and show them. Light interiors
   flatly (a bright world colour, or Eevee): Decentraland's toon lighting is flat, and a dark Cycles interior reads as
   a modelling problem that isn't there.
8. **Hand off:** `building.glb`, `route.json`, any door leaf GLB, triangle and material counts, footprint.

## Quick reference

| Item | Value |
|---|---|
| Footprints | 0.5×0.5 = 8×8 m, 1×1 = 16×16, 1×2 = 16×32 (X×Z), 2×2 = 32×32, 4×4 = 64×64 |
| Triangles (recommended) | ~30% of 10,000 a parcel: 1×1 ≈ 3,000, 2×2 ≈ 12,000, 4×4 ≈ 48,000 (visible; colliders separate) |
| Materials / textures | ≤ 3 / ≤ 2 recommended; textures power of two, ≤ 1024 (FAIL otherwise) |
| Doorway | ≥ 1.0 m wide, ≥ 2.2 m high |
| Steps | ≤ 25 cm high, ≥ 30 cm deep, ramp collider over them; avatars step 40 cm, jump 45 cm |
| Slopes | walkable ≤ 46°, comfortable ≤ 30–40° |
| Headroom | ≥ 2.2 m everywhere a route goes, stairwells included |
| Walker | capsule 0.6 m wide × 1.8 m tall |
| Height | 330 m (soft); no 20 m rule any more |
| One file | ≤ 50 MB (deploy refused above); a scene 15 MB a parcel |

## Doors

Open doorways by default. A door leaf, when wanted, is a **separate GLB** with its origin on the hinge axis at floor level (so a future door kit can swing it), its own `Door_collider`, and the building's doorway left clear. Don't animate it.

## Pitfalls that recur

- **Blender 4.x removed APIs agents still write** (check `bpy.app.version`; Virvi's worker runs 4.4):
  `mesh.use_auto_smooth` / `auto_smooth_angle` are gone (4.1): select the object and call
  `bpy.ops.object.shade_smooth_by_angle(angle=...)`. `material.shadow_method` is gone (4.2): set
  `material.surface_render_method = 'BLENDED'` (or `'DITHERED'`) for transparency; `blend_method` still exports
  glass as BLEND. Eevee is `'BLENDER_EEVEE_NEXT'` in 4.2–4.4.

- **Blender's `.001` copies:** `Wall_collider.001` is not a collider; it renders as a grey slab and blocks nothing. The checker FAILs it.
- **Everything double-sided:** Blender's culling is off by default; export through `bp.export()`.
- **A material per colour:** twelve materials is twelve draw calls per object. Use the palette.
- **Furniture baked in:** it can't be sat on, moved or reused, and spends the building's budget.
- **Visible stairs with no ramp:** players hop up 20 steps. **A ramp with no headroom:** they climb into the slab above.
- **Upper floor with no collider:** visitors fall through it (the route's `y` catches this).
- **Railless landings and stairwells:** visitors drop through the opening.

## Working rules

- Show a fresh render after every change.
- A failing check gets fixed in the building, never by dropping the check or bending the route through a wall.
- When you're corrected on something new, add it to `lessons.md`.
