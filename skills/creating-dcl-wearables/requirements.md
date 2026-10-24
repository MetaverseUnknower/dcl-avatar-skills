# Decentraland wearable requirements (digest)

Compiled 2026-10-24. Sources: **D** = docs.decentraland.org/creator/wearables-and-emotes/… (github.com/decentraland/docs),
**B** = decentraland/builder (`src/lib/glbValidation/constants.ts`), **CV** = decentraland/content-validator (server side),
**S** = decentraland/schemas, **UE** = decentraland/unity-explorer. Builder GLB checks are warnings only; hard errors
come from import (file size) and CV. Curation is the real gate. ⚠ marks conflicts between sources.

## Categories (S)
body_shape, hair, eyes, eyebrows, facial_hair, mouth, upper_body, lower_body, feet, hands_wear, hat, helmet, mask,
tiara, top_head, earring, eyewear, skin. Extra hideable base parts: `head`, `hands`.

## Triangles (D creating-wearables; B TRIANGLE_LIMITS)
| Category | Tris |
|---|---|
| mask, eyewear, earring, tiara, top_head, facial_hair | 500 |
| hands_wear accessory (watch, ring) | 1,000 |
| hands_wear hiding base hands | 1,500 (docs only) |
| hat, helmet, hair, upper_body, lower_body, feet | 1,500 |
| skin | 5,000 |

Combiner: a wearable that hides other slots adds their budgets (upper_body hiding lower_body = 3K; docs: helmet hiding
all head slots = 4K, 2 mats, 2 tex). ⚠ B sums every hidden category (helmet ≈ 7.5K). `hands` isn't in B's table, so
hands_wear hiding hands stays 1K in B.

## Materials, textures, size
- ≤2 materials excluding `AvatarSkin_MAT` (skin: 5 in B).
- ≤2 textures (skin: 5), square, ≤1024×1024, 72 ppi. Power-of-two stated for scenes, not wearables; use it anyway.
- Bounding box 2.42 m tall × 2.42 m wide × 1.4 m deep (D, B MAX_DIMENSIONS). Exceeding = rejection.
- File: D says 3 MB per item. B upload: wearable 3 MB, skin 8 MB, thumbnail 1 MB. CV: total 3 MB, thumbnail ≤1 MB,
  **model ≤2 MB**; skin total 9 MB (model 8). ⚠ docs omit the 2 MB model cap.

## Format and export (D)
- glTF 2.0 / GLB: mesh + armature, skinned. No animations, shape keys, cameras, lights, empties (B warns).
- Single-sided rendering: check normals (backface culling / face orientation).
- Representations: BaseMale / BaseFemale (`urn:decentraland:off-chain:base-avatars:BaseMale|BaseFemale`), one GLB each
  or one unisex. Each has bodyShapes, mainFile, contents, overrideHides, overrideReplaces.

## Rig and skinning
- Don't change bone names, hierarchy or transforms. Remove `_end`/`_neutral` leaf bones (B warns LEAF_BONES_FOUND).
- 62 `Avatar_*` bones: Hips, Spine, Spine1, Spine2, Neck, Head; L/R Shoulder, Arm, ForeArm, Hand;
  `Avatar_{Left|Right}Hand{Thumb|Index|Middle|Ring|Pinky}{1-4}`; L/R UpLeg, Leg, Foot, ToeBase.
- ≤4 influences per vertex; no unrigged vertices.
- Seams 100% on one bone: neck → Neck; upper/lower body → Hips; lower body/feet → Left/Right Leg; hands → Left/Right ForeArm.
- Don't move base-body seam vertices; keep caps. Preserve avatar UVs on exposed skin (rejection reason).

## Materials and shading
- Toon shader. Used maps: Base Color, Emission (separate material), Alpha. Normal/roughness unused: bake into base color.
- Prefer alpha clip (MASK) with a B/W cutout over BLEND.
- Skin tint: material named exactly `AvatarSkin_MAT`, grayscale texture. Hair tint: material name contains `Hair`,
  grayscale texture. Only base color tints; emission stays as-is.
- Never use `_mouth`, `_eyebrows`, `_eyes` in names (facial shader). ⚠ D says mesh names, B checks material names: avoid in both.
- Eyes/eyebrows/mouth: PNG only, 256×256 transparent; optional `*_mask` PNG in a zip for tint. Mouth tints with skin,
  eyebrows with hair; irises grayscale.
- Outline toggle defaults on; turn off for hand-made outlines / inverted normals.

## Hides and replaces
- `hides` hides categories but leaves them equipped; `replaces` unequips. Per-representation overrides win.
- Builder splits into Base Body (head, hands) and Wearables. Players can force-show from the Backpack.
- UE implicit rules: skin hides eyes, mouth, eyebrows, hair, upper_body, lower_body, feet, hands, hands_wear, head,
  facial_hair (⚠ docs/B lists differ slightly). upper_body hides `hands` unless `removesDefaultHiding: ["hands"]`
  (B sets this for new upper_body). A wearable never hides its own category.
- Priority: skin > upper_body > hands_wear > lower_body > feet > helmet > hat > top_head > mask > eyewear > earring >
  tiara > hair > eyebrows > eyes > mouth > facial_hair.
- Tip: a hat can carry its own hair and hide `hair`.

## Spring bones (D wearables/spring-bones; S spring-bones.ts)
- Every bone in a chain, end bone included, has `springbone` in its name (case-insensitive).
- Linear, connected, ≥2 bones, root parented to an `Avatar_*` bone, end bone unweighted.
- ≤6 chains, ≤12 spring bones total, depth ≤6. B only enforces 12 (counts end bones).
- Parameters live in Builder metadata, not the GLB: stiffness 0–4 (2.0), gravityPower 0–2 (0), gravityDir axes
  −10…10 ([0,−1,0]), drag 0–1 (0.5), center (optional non-spring base bone). Re-uploading the GLB resets them.
- No colliders, no wind. Far avatars and older clients show bones static.

## Thumbnail and metadata
- Thumbnail: 256 px square PNG, transparent background, item only (rejection reasons). ⚠ CV accepts ≤1024 px, ≤1 MB.
- Name ≤32 chars, description ≤64, utility ≤64. Collection name ≤32. ≤50 items per collection.
- Rarity → max supply: unique 1, mythic 10, exotic 50, legendary 100, epic 1,000, rare 5,000, uncommon 10,000,
  common 100,000. Rarity, collection name and item count are immutable after publishing.
- Fee: 25 USD/item since 2026-07-28 (Foundation covers 20, creator pays 5 in Polygon MANA), non-refundable. 2.5% DAO
  fee on primary sales.

## Smart / linked wearables
- Smart: folder ≤3 MB uncompressed (`npm run pack`), `wearable.json` + root `thumbnail.png` 256×256, both body shapes,
  video .mp4 ≤15 s (⚠ ≤4 MB docs vs 250 MB B). Effects visible only to the wearer, except avatar animations.
- Linked: same model rules, zip with root `wearable.json` + optional `thumbnail.png`, no rarity, not sellable.

## Curation rejection reasons (D publishing-collections)
Bad skin weighting; avatar UVs not preserved; face textures >256 px or not transparent; hands_wear that is a held
object (sword, shield); over tri/material/texture budgets; duplicates or copies of published items; QR codes; over
size limits; misleading category; non-humanoid items (vehicles, pets); thumbnail not transparent or with extra
graphics; content policy / IP infringement. Also seen: **posed arms** on upper_body (curator note).
