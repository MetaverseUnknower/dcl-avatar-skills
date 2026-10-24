---
name: creating-dcl-wearables
description: Use when building, fixing, exporting, verifying or uploading a Decentraland wearable or skin (hair, hat, helmet, mask, upper_body, lower_body, feet, hands_wear, earring, eyewear, tiara, top_head, facial features, skin) in Blender, including clipping, weight painting, spring bones, textures, thumbnails, hides/replaces, or Builder/curation issues.
---

# Creating Decentraland Wearables

## Overview

A wearable is a skinned GLB on Decentraland's 62-bone `Avatar_*` skeleton, one per body shape (BaseFemale and BaseMale; get the official avatar `.blend` files from the docs). Builder GLB checks are only **warnings**; curation is the real gate. "The Builder accepted it" proves nothing.

**Done means:** the bundled checker (`scripts/check_wearable.py`) reports no FAIL, a clipping check passes on every frame of Decentraland's real locomotion for **both** body shapes, and the person you're working with has seen a fresh render of the current version.

`<skill-dir>` below is the folder this SKILL.md is in. Reference files there: `requirements.md` (every documented rule, with sources and conflicts) and `lessons.md` (mistakes made in real wearable projects and their fixes). Read `lessons.md` before starting a new item.

## Workflow

1. **Settle the brief before modelling.**
   - Slot: held objects (sword, shield) as hands_wear and **posed arms** on upper_body are rejected. A carried prop becomes its own item on a free accessory slot (e.g. a bat on the back filed as an earring, 500 tris). Vehicles and pets aren't wearables.
   - IP: sold items must be original designs. Decline "exactly like <real character>" and offer a parody.
   - Hides/replaces: decide now (a full helmet: head, hair, facial_hair, hat, eyewear, earring, tiara, top_head). They change the triangle budget and what must be rendered.
   - Budget: the category's tris (+ hidden categories'), 2 materials, 2 textures, per item.
2. **Script the build** (Blender Python) so both body shapes come from one source and every fix is repeatable. Select geometry by position, never by bone weights (the two bodies differ). Delete and recreate Blender images each build.
3. **Check the export:**

   | Check | How |
   |---|---|
   | Doc limits, skinning, names, alpha, bbox, spring rules | `python3 <skill-dir>/scripts/check_wearable.py <glb>... --category <c> [--hides a,b] [--strict]` |
   | Clipping vs the body | pose the rig, evaluate both meshes, BVH triangle-overlap test; ignore overlaps inside the rest-pose seam regions (dilated ~2 rings) |
   | Real locomotion | Idle/Walk/Jog/Run `.anim` files from decentraland/unity-explorer (see below), every frame |
   | Hand/hip items vs emotes | the built-in emotes from unity-explorer (see below) |
   | Spring motion | simulate VRM spring bones with the Center you'll enter; check tips stay off the body |

   New checker? Run it on a known-bad file first and watch it fail. A zero is suspicious until proven.
4. **Render** with the base body visible under the item, the way the Builder shows it, after every change, and show that render, not a close-up from an untextured test scene.
5. **Hand off** a sheet per item: category, hides, files per body shape, tri counts, spring table (root bone, stiffness, gravity power, drag, Center), thumbnail, description ≤64 chars. Thumbnail: 256 px square PNG, transparent background, item only.

## Decentraland's real animations

- Locomotion: `decentraland/unity-explorer` → `Explorer/Assets/DCL/AvatarRendering/AvatarShape/Assets/Animations/` (Idle, Walk, Jog, Run as Unity text `.anim`).
- Built-in emotes: `Explorer/Assets/DCL/AvatarRendering/Emotes/EmbeddedEmotes/CommonEmotes/` (`.anim` and `.glb`; the GLBs are Git LFS, fetch from `https://media.githubusercontent.com/media/decentraland/unity-explorer/main/<path>`).
- `.anim` per-bone local rotations map onto the official rig's bones directly with the Unity→Blender flip `Quaternion((w, x, -y, -z))`; set `pose_bone.rotation_quaternion = rest_local.inverted() @ q`. Never invent an idle pose: the real idle rolls the right fist ~28°, which changes where a held item points.

## Quick reference

| Item | Limit |
|---|---|
| Tris: mask, eyewear, earring, tiara, top_head, facial_hair | 500 |
| Tris: hands_wear accessory / hiding hands | 1,000 / 1,500 (docs) |
| Tris: hat, helmet, hair, upper_body, lower_body, feet | 1,500 |
| Tris: skin | 5,000 (5 materials, 5 textures, model 8 MB) |
| Materials / textures | 2 / 2, `AvatarSkin_MAT` not counted |
| Texture | square, power of 2, ≤1024 |
| Bounding box | 2.42 h × 2.42 w × 1.4 d m |
| Model file | ≤2 MB (server); item total 3 MB incl. thumbnail |
| Influences | ≤4 per vertex, every vertex weighted |
| Spring bones | names contain `springbone`; ≤6 chains, ≤12 bones incl. end bones, depth ≤6; linear, connected, end bone unweighted |
| Name / description | ≤32 / ≤64 chars |
| Seams 100% on one bone | neck → Neck, upper/lower → Hips, lower/feet → Leg, hands → ForeArm |

## Pitfalls that recur

- **Female idle** hangs bare hands into her thighs; male hands hang at |x| 19–20 cm, y 73–86 cm. Nothing wide at hand height: snug hips, vented coats.
- **Clip gating:** the bare avatar self-intersects in some Run frames (don't gate Run). Gate on overlaps outside rest-pose seams, not raw counts.
- **Spring Center:** `Avatar_Hips` when the chain must swing with the body (leg straps, held flags); none when trailing at speed is the look (coat tails). Dangles on the outer side or back, ending above the knee. Re-enter params after every re-upload.
- **Fingers:** the checker warns when non-hand items weight finger bones; previews must pose fingers from real clips or a broken fist stays invisible.
- **Rigid plates over skinned fabric:** the fabric under each plate follows that plate's bone.
- **Texturing low-poly base meshes:** bake per texel from 3D position; never fit flat art per vertex. Draw text in real cm.
- **Looks:** toon shader, flat light, no bloom, so in-world reads darker than Blender. Only base color, emission and alpha are used; MASK over BLEND. Only the base color of `hair`/`skin`-named materials tints.
- **lower_body hides the real legs:** see-through rips need base-leg patches in `AvatarSkin_MAT` behind them.

## Working rules

- Show a fresh render after **every** change.
- Prove geometric fixes with per-frame numbers and report them. If a fix is questioned, show a same-camera before/after of every version.
- Fix clipping locally (one bone, one region); restyling the whole item to dodge it gets rejected.
- When you're corrected on something new, add it to `lessons.md`.
