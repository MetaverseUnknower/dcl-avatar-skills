# Decentraland emote requirements (digest)

Compiled 2026-10-24. Sources: **D** = docs.decentraland.org/creator/wearables-and-emotes/emotes/… (github.com/decentraland/docs),
**B** = decentraland/builder (`src/lib/glbValidation/constants.ts`), **CV** = decentraland/content-validator,
**S** = decentraland/schemas. ⚠ marks conflicts.

## Specs (D creating-emotes)
| Spec | Value |
|---|---|
| Frame rate | 30 fps (rig file ships at 24) |
| Max length | 10 s / 300 frames |
| Animations | 1 per file; with props 1 avatar + 1 prop clip |
| Format | .glb with only the deform skeleton + animation (+ prop) |
| File size | 3 MB total incl. props and audio. CV: model files ≤2 MB, thumbnail ≤1 MB |
| Sampling | 1 by default; 2–3 if needed for size |
| Movement | root ≤1 m front/back/left/right (2 m circle); up to 4 m high |
| Bounding box | avatar + props inside a 4×4 m reference cube |

- Rig: official `Avatar_File.blend` / `BaseMale_Rig_1.0.blend` (Rig 1.0) or the Maya rig. Never edit the deform
  skeleton or the rig's object transforms; animate controls. (Posing the
  deform bones of the avatar body files directly from a script also works: same 62 bones.)
- Start/end: Play Once starts and ends on `Starting_Pose` idle. Loops may use any pose but first frame == last frame.
- Key all deform bones (loc, rot, scale) on first and last frame to avoid override bleed (B warns
  `EMOTE_MISSING_KEYFRAMES`).
- No start/loop/end sequences for standard emotes. Delete leftover actions (including `Starting_Pose`) before export.
- Clip naming: capitalized words joined by `_`, no spaces/special chars (`Rainbow_Dance`).

## Blender export
glTF 2.0 → Include: Limit to **Visible Objects**; Data > Armature: **Export Deformation Bones Only**; Animation >
Sampling as needed. Hide meshes and controls first. Export only keyed channels (force sampling of all 62
bones blows the size budget).

## Props, particles, sound (D props-and-sounds, particles-in-emotes)
- Armatures `Armature` and `Armature_Prop`; clips `<Name>_Avatar` and `<Name>_Prop`, identical length.
- Push both to NLA tracks, one per armature. Blender 4.4+: the prop clip needs its own action slot.
- Bone animation only: no object/transform animation, no particle systems. Bake particles to bones with the official
  add-on and merge into `Armature_Prop`.
- Prop limits: 3K tris total, 2 materials, 2 textures ≤1024 px, ≤62 bones in the prop armature.
- Prop objects and armature origins at 0,0,0, transforms applied (scale 1). Hide a prop by scaling to 0.001.
- Props render single-sided regardless of the material's double-sided flag (observed in-world).
- Audio: .mp3 or .ogg, same duration as the emote, original IP, counts toward 3 MB. Upload as .zip with the .glb,
  the audio and optional `emote.json` {name, description ≤64, category, rarity, play_mode simple|loop, tags}.

## Metadata (D uploading-emotes; S)
- Categories: dance, stunt, greetings, fun, poses, reactions, horror, miscellaneous.
- Play mode: Play Once or Loop. Re-uploading resets it.
- Thumbnail: captured from a frame in the Builder's tool. Cylinder icon in the editor checks boundaries.
- Name ≤32, description ≤64. Rarity tiers as wearables (unique 1 … common 100,000), fixed after publishing.
  Fee 25 USD/item since 2026-07-28 (creator pays 5 in Polygon MANA).

## Social / two-person emotes (ADR-287, Draft; not in creator docs)
- Armatures `Armature`, `Armature_Prop`, `Armature_Other`.
- Clips `<Action>_Start`, `_Start_Prop`, `_Avatar`, `_Prop`, `_AvatarOther` (PascalCase action, e.g. `HighFive_AvatarOther`).
- Metadata: `startAnimation{loop, Armature, Armature_Prop?, audio?}`, `randomizeOutcomes`, `outcomes[]` together;
  1–3 outcomes `{title ≤24, loop, clips, audio?}`.

## Builder validation vs docs
- All GLB checks are warnings (fps, frames, clip count, keyframes, prop limits, naming, audio format). Hard errors only
  at import: duration >10 s, file over limit.
- B does not check the 1 m root displacement; curation does.
- ⚠ B estimates fps as keyframes ÷ duration (±5): sampling 2–3 (≈15/10 fps) raises an `EMOTE_FRAME_RATE` warning.
- ⚠ B's clip-name check doesn't know the social suffixes.

## Rejection reasons
Over 10 s / 300 frames; over 1 m root travel or the 4 m box; content policy / IP, including audio.
