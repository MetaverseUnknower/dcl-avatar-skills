---
name: creating-dcl-furnishings
description: Use when building, fixing, exporting or checking furniture or decor for a Decentraland scene or World in Blender (chairs, stools, couches, benches, tables, shelves, beds, lamps, plants, signs, props), including seats people sit on with dcl-sittables, colliders that block without pushing sitters off, triangle and material budgets, texture palettes, or a piece that is too heavy, floats, faces the wrong way or can't be sat on.
---

# Creating Decentraland Furnishings

## Overview

A furnishing is one small static GLB placed in a scene, often many times. It must look right, block people where it's solid, and, if people sit on it, ship a **`dcl-sittables` seat description** whose seats line up with Decentraland's own sitting emotes. Decentraland's limits are soft, but a chair placed twenty times multiplies everything: keep pieces light.

**Done means:** `check_scene_model.py` reports no FAIL (with `--sittables` for anything sittable), and the person has seen fresh renders of the current version.

This skill shares its scripts and rules digest with `creating-dcl-buildings`: `<skills>` below is the folder holding both skills (the scripts are in `<skills>/creating-dcl-buildings/scripts/`, the digest is `<skills>/creating-dcl-buildings/requirements.md`, and its "Seating" section is the seat reference). Read that skill's `lessons.md` too.

## Workflow

1. **Settle the brief:** what it is, rough size, style, how many get placed, whether people sit on it.
2. **Script the build** in Blender Python. Metres; origin on the floor under the middle; the front (the way a sitter faces) toward Blender −Y, which exports as glTF **+Z**. Real-world sizes: seat top ~0.45–0.47 m, table top ~0.75 m, bar top ~1.05 m with stools ~0.75–0.97 m.
3. **Colour with one palette** (`blender_palette.py`): one swatch material, a metallic twin; glass or glow only when the look needs it. Export with `bp.export()` (backface culling on).
4. **Colliders:** simple closed boxes named `*_collider`, no material, roughly the piece's solid volume. Small decor people won't bump into may skip them (check as `--kind decor`).
5. **Seats** (anything sittable): write `<piece>.sittables.json`, a `FurnitureModel`:
   - `file`: the GLB's file name; `scale` 1, `uprightX` 0, `yawOffset` 0 (it faces +Z)
   - `kind`: `couch` (deep cushion), `bench` (chairs, benches), `stool` (tall, thin)
   - `collision`: `colliders` for chair-height pieces with collider boxes; `stool` for tall seats (the kit adds a pole collider and a step); `model` only when the visible mesh is the collider
   - one seat per sitter. **Every number is measured from the piece's origin**, in the sitter's frame: `across` (to their right, which is glTF −X), `forward` (the way they face, glTF +Z: 0.3–0.45 m in front of the seat's middle; on a couch just past the cushion's front edge), `rise` (0 for a ~0.47 m seat top; raise by the difference for higher seats). Together they are the seat's `position`: where the sitter stands before sitting. `orbForward`, `orbRise`: the click orb, also from the origin, over the seat
   - **trim the seat collider short of every standing spot** (the checker FAILs a seat whose standing column is inside a collider)
6. **Check:** `python3 <skills>/creating-dcl-buildings/scripts/check_scene_model.py chair.glb --kind furniture --type chair --sittables chair.sittables.json`
7. **Render** from the front three-quarter, side and back, next to a 1.8 m figure for scale, and show them.
8. **Hand off:** the GLB, its `.sittables.json`, triangle and material counts.

## Quick reference

| Piece (`--type`) | Triangles (recommended) |
|---|---|
| chair, stool, table, shelf | ≤ 800 |
| bench | ≤ 1,000 |
| couch, sofa, bed | ≤ 1,500 |
| lamp | ≤ 400 |
| small decor (`--kind decor`) | ≤ 300 |

Materials ≤ 3 and textures ≤ 2 (recommended); textures power of two, ≤ 1024 (FAIL otherwise); file ≤ 2 MB recommended.

## Low-poly that still looks soft

- Cushions: a box with one bevel segment and smooth shading, not a subdivided blob. Chunky proportions read as cosy.
- Legs: 6–8-sided cylinders. Nobody counts the sides of a chair leg.
- Spend triangles where people look: the seat edge, arms, a backrest silhouette. Delete faces nobody sees (undersides on the floor, faces between cushions).
- A couch is about 3 cushions, a base, 2 arms and a back: 700–1,500 triangles.

## Pitfalls that recur

- **Over budget:** a cosy couch came out at 2,108 triangles with four materials. Bevel once, palette everything.
- **Double-sided faces:** Blender's default; `bp.export()` fixes it.
- **A seat collider reaching the front edge:** sitters get shoved off a different way every time.
- **A stool's own mesh holding the sitter up:** the avatar overlaps it and gets pushed off. Use `collision: 'stool'`.
- **A `file` path the kit won't find:** write the GLB's name; the scene decides the folder.

## Working rules

- Show a fresh render after every change.
- Fix a failing check in the piece, never by dropping the check.
- When you're corrected on something new, add it to `creating-dcl-buildings/lessons.md`.
