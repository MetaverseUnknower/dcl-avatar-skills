# Decentraland scene model requirements (digest)

Compiled 2026-11-01, for buildings, furniture and decor placed in SDK7 scenes and Worlds. Sources: **D** =
docs.decentraland.org/creator (scenes-sdk7/optimizing/scene-limitations, 3d-modeling/colliders, materials, textures,
meshes); **S** = the `dcl-sittables` package (`dcl-lounge-kit`, docs/custom-furniture.md). The other skills in this
repo (wearables, emotes) don't apply: scene models aren't skinned, curated or sold through the Builder.

## What's enforced, and what only warns (D scene-limitations)

`n` = parcels in the scene. Only **file size and file count stop a deploy**; the rest are soft (the Creator Hub warns;
the scene runs slower). The render limits count only what's rendered at once.

| Limit | Formula | 1 parcel | Enforced |
|---|---|---|---|
| Triangles | n × 10,000 | 10,000 | warns |
| Entities | n × 200 | 200 | warns |
| Bodies (meshes) | n × 300 | 300 | warns |
| Materials | log2(n+1) × 20 | 20 | warns |
| Textures | log2(n+1) × 10 | 10 | warns |
| Height | 330 m | 330 m | warns (sync issues above 200 m) |
| Total files | 15 MB a parcel, 300 MB max | 15 MB | **deploy refused** |
| File count | 200 a parcel | 200 | **deploy refused** |
| One file | 50 MB | 50 MB | **deploy refused** |

Worlds: 100 MB per NAME (and per LAND parcel, per 2,000 MANA) shared by the wallet; ENS-domain Worlds 36 MB. Anything
outside the scene's parcels isn't rendered and is cut at the boundary.

A building is one piece of a scene that also holds furniture, people's own models and kit props, so these skills
recommend (never require) a piece takes a share: a building about 30% of its footprint's triangles.

## Colliders (D colliders)

- A mesh is an invisible collider when its **name ends in `_collider`**. `tree_collider_1` is NOT a collider (it renders).
  `_box`, `_sphere`, `_capsule` after the suffix mark a primitive (`Pot_collider_box`), the cheapest kind.
- Colliders have **no material**. They block the avatar and take pointer events (clicks) and raycasts. They don't stop
  models overlapping each other.
- Fewest triangles possible; prefer boxes, spheres, capsules, and approximate shapes with several. An arbitrary mesh
  collider must be **convex** (concave ones stutter and snag).
- **A plane blocks from one side only.** Walls are boxes (or two opposed planes).
- Without collider meshes, scene code can give the visible mesh collision (`GltfContainer` masks) or add a
  `MeshCollider`; a model meant to be placed by others should carry its own colliders.
- **Stepping:** an avatar steps up about 40 cm without jumping; 45 cm or more needs a jump.
- **Stairs:** steps ≤ 25 cm high and ≥ 30 cm deep; put a **ramp collider over the stairs** (same space) so players walk
  up smoothly instead of hopping each step. 25 × 30 cm steps make a ramp of about 40°.
- **Slopes:** walkable up to 46°; ≤ 30° is easy walking.
- The docs say nothing about doors (see SKILL.md for the convention used here).

## Meshes (D meshes)

- Apply rotation and scale (Ctrl+A → All Transforms) and keep bounding boxes tight.
- Face normals point outward (inward faces may not render). Delete hidden faces: they still count.
- Smooth shading for rounded shapes instead of more faces. Mirror symmetric parts. Decimate breaks topology.
- Linked duplicates (Alt+D) share mesh data and shrink the file; joining (Ctrl+J) cuts draw calls but culls as one.
- Names: PascalSnake_case, meaningful (`TramWheelLeft`, `FountainStatue01`).
- Units and axes aren't documented: glTF is metres, Y up, and Blender's glTF exporter converts Z-up to Y-up (Blender's
  −Y, its "front" view direction, becomes glTF +Z). `dcl-sittables` treats a model facing glTF +Z as `yawOffset` 0;
  that's the convention these skills use for a piece's front.

## Materials (D materials)

- Supported: base colour, metallic, roughness, specular, emissive (+ strength), alpha, normal. **No vertex colours.**
- Each material is a draw call per object: share materials, atlas textures.
- **Alpha clip (MASK) over blend**; blend only for partial transparency (glass). Don't mix clip and blend on one mesh.
- Emission glows but lights nothing nearby; strength 1.0 makes it shadeless.
- **Backface culling on** except true two-sided geometry (leaf cards). Blender's default is off, and the exporter
  writes `doubleSided: true` for it.
- Scene code can't change a model's materials except through `GltfNodeModifiers`.
- Names: `<Object>_<Class>_MAT`, e.g. `Wood_Oak_MAT`.

## Textures (D textures)

- **Each side a power of two, at most 1024 px** (the explorer compresses to 1024 anyway). 1024² is the recommended max.
- Non-power-of-two may render wrong. 72 ppi is enough.
- Types by suffix: `T_<Name>_D` (diffuse), `_A`, `_MT`, `_R`, `_N`, `_E`. Never one image as both albedo and normal.
- Embedded textures are duplicated per model; a texture shared by several models can be an external file (same name and
  hash) so it loads once.

## Seating (S)

- `dcl-sittables` seats people with Decentraland's `sittingChair1/2` emotes, made for an avatar standing on the floor
  just in front of the seat: the hips end **0.64 m up and 0.37 m back** from where the avatar stands, facing away.
- A seat's `position` is that standing spot: on the floor when the seat top is ~0.47 m; lifted by the difference when
  higher (a bar stool's ~0.97 m top → `position` ~0.5 m up). It's 0.3–0.45 m in front of the seat's middle (couches:
  just past the cushion's front edge, ~0.1 m).
- `FurnitureModel`: `file`, `scale`, `uprightX` (0 for Y-up), `yawOffset` (0 when the model faces +Z), `collision`
  (`'model'` the visible mesh collides, `'colliders'` its `*_collider` meshes, `'stool'` the kit adds a pole collider and
  a 0.3 m step), `kind` (`'stool' | 'couch' | 'bench'`, picks the sitting emote), `seats`: `across` (sitter's right),
  `forward` (the way they face), `rise` (up): the seat's `position`, measured from the furniture's origin; and
  `orbForward`, `orbRise`: the click orb, also from the origin. Origin on the floor under the middle.
- **Nothing may collide where the sitter stands**, or Decentraland's physics shoves them off a different way each time:
  a seat collider stops short of the standing spot. Tall, thin seats use `'stool'`.
