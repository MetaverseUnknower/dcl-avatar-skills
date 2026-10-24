---
name: creating-dcl-emotes
description: Use when building, fixing, exporting, verifying or uploading a Decentraland emote (avatar animation GLB, with or without props, sound or particles) in Blender, including hand/palm poses, limb or prop clipping, loops and seams, head/neck scale tricks, file size, Builder preview or curation issues, or emotes triggered from a scene.
---

# Creating Decentraland Emotes

## Overview

An emote is a GLB holding one avatar clip on the deform skeleton (`Armature`, 62 `Avatar_*` bones), plus optionally one prop clip on `Armature_Prop`. The female and male bodies share one skeleton, so one GLB serves both, but clipping must be checked on **both** meshes. Builder GLB checks are **warnings**; only >10 s and file size are hard errors. Curation enforces the rest.

**Done means:** the bundled checker (`scripts/check_emote.py`) reports no FAIL, hand-orientation and prop-normal checks pass, clipping checks pass on every frame for both bodies, and the person you're working with has seen a fresh render of the current version.

`<skill-dir>` below is the folder this SKILL.md is in. Reference files there: `requirements.md` (every documented rule, with sources and conflicts) and `lessons.md` (mistakes made in real emote projects and their fixes). Read `lessons.md` before starting a new emote.

## Workflow

1. **Settle the brief before animating.**
   - Length ≤10 s / 300 frames at 30 fps. Say so up front if the idea runs longer.
   - Play Once or Loop. A prop that must stay in hand needs Loop: when an emote stops, props freeze at their last key while the avatar blends back to idle.
   - Hips stay within 1 m horizontally; everything inside a 4×4 m box, ≤4 m high.
   - Audio must be original (.mp3/.ogg, same length as the clip). Particle systems aren't allowed.
   - Category: dance, stunt, greetings, fun, poses, reactions, horror, miscellaneous.
2. **Script the animation** (Blender Python) on the official avatar rig, so every fix is repeatable. Build small helpers once: aim a bone at a direction, two-bone arm/leg IK that takes an explicit **palm** direction, finger curl, and a floor guard.
3. **Props** live on a separate `Armature_Prop`. For a prop held or worn, add prop bones that copy the avatar bone (Copy Transforms), then bake them to keys at export.
4. **Export only keyed channels.** Force-sampling writes T/R/S for all 62 bones and pushed a 9.5 s emote past 1 MB. Key all 62 bones on the first and last frame.
5. **Check:**

   | Check | How |
   |---|---|
   | Doc limits, names, fps, keys, hips travel, frame jumps, prop budget, loop seam | `python3 <skill-dir>/scripts/check_emote.py <glb> [--loop] [--audio <file>]` |
   | 4×4 m box on real meshes | evaluate every frame in Blender; bounds of avatar + props |
   | Limb vs limb, arm vs chest, prop vs body | BVH triangle overlap per frame on the evaluated meshes, both bodies; list intended overlaps explicitly |
   | Hands | measure palm/finger direction from the posed bones each frame against the intent |
   | Prop normals | signed volume per closed part (inside-out = fail), no open single-sided parts |
   | Loop seam | per bone: step and change of speed across the seam vs the largest elsewhere |
   | Real player blending | play the GLB in the Builder preview (Unity renderer) for scale tricks and fast props |

   New checker? Run it on a known-bad file first and watch it fail.
6. **Render** after every change, props seen from front, below, above and mid-action, and show that render.
7. **Upload:** in the Builder, select the item by clicking it in the list and confirm the id, then set every field (a re-upload resets Play mode). The editor plays emotes **once** even on Loop, so loops are only verifiable in-world.

## Quick reference

| Item | Limit |
|---|---|
| Frame rate / length | 30 fps (rig ships at 24) / ≤10 s, ≤300 frames |
| Clips | 1 avatar clip; with props exactly `<Name>_Avatar` + `<Name>_Prop`, identical length, Capitalized_Words |
| Armatures | `Armature`, `Armature_Prop` (social, ADR-287 draft: `Armature_Other`) |
| File | model ≤2 MB server, 3 MB item total incl. audio |
| Props | ≤3K tris, 2 materials, 2 textures (square, ≤1024), ≤62 bones; bone animation only; origins at 0, scale 1; hide by scaling to 0.001 |
| Start/end | Play Once: start and end on the rig's `Starting_Pose`. Loop: first key = last key on avatar AND prop bones |
| Name / description | ≤32 / ≤64 chars |

## Rig facts (official avatar rig, cm)

- Palm = hand bone −X on both hands; thumb side −Z (left) / +Z (right).
- Shoulder (±17.7, 146.6, 0); upper arm 27.3, forearm 26.7. Low fists >20 cm forward are out of reach without a spine lean.
- Hanging wrists at x ±20.5 sink into the thighs; ±24.5 is clear. Female hips x ~19–20 at y 100–105.
- Neck base y 149.2; neck verts are weighted Head+Neck, so the real head can't detach.
- The eye mesh sits much lower than a guessed head centre: measure it.
- Reference motion: Decentraland's real locomotion and built-in emotes are in `decentraland/unity-explorer` (`Explorer/Assets/DCL/AvatarRendering/AvatarShape/Assets/Animations/` and `.../Emotes/EmbeddedEmotes/CommonEmotes/`); Unity `.anim` rotations map to the Blender rig with `Quaternion((w, x, -y, -z))`.

## Pitfalls that recur

- **Players interpolate between keys;** Blender renders only keys. A 180° flip sweeps through 90° in-world. `check_emote.py` flags >90° steps on visible bones.
- **Props render single-sided,** even with the double-sided flag. Build closed, outward-wound meshes or real back faces.
- **Cross-fade blends local bone scale linearly.** A big counter-scale balloons (a 1150× head peaked ~290× mid-blend). Collapse limbs at their roots, torso ~0.3, split the counter-scale over neck+head; simulate the blend peak ≈ (s+1)/2 · ((c+1)/2)².
- **Head swaps:** collapse the NECK bone to 0.001 about its base (scale keys only) and show a prop head that follows the head bone. Grow back 0.001 → 1 with an ease-out-back.
- **Particles:** small closed meshes on prop bones, scale-animated, eased in and out (hidden at 0.001 they still sweep through in-between sizes).
- **Female body:** a straight arm across to the crotch passes through the breast. Turn the chest and roll the shoulder; don't hunch.
- **Pose scale drift:** restoring only rot/loc after setting `pose_bone.matrix` drifts bone scale. Reset scale and assert 1.
- **Optimisers cheat:** constrain the intended motion explicitly (e.g. the foot must pass *over* a link, not the link over the foot).
- **In-world vs Builder:** in-world uses Unity asset bundles. If the Builder looks right and in-world doesn't, suspect a stale upload. Scene-triggered emotes wait until the avatar is grounded, and the GLB ships with the scene.

## Working rules

- Show a fresh render after **every** change.
- Prove geometric fixes with per-frame numbers. If a fix is questioned, show a same-camera before/after of every version.
- Fix clipping locally (shoulder, elbow, grip). A restyled pose gets rejected.
- When you're corrected on something new, add it to `lessons.md`.
