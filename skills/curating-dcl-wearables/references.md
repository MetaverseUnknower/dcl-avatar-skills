# Curator reference

Checked 2026-10-24 against decentraland/builder (a2b61b8), decentraland/unity-explorer (333aa88),
decentraland/wearable-preview (bf674f7), decentraland/wearable-validator (0.6.3) and the docs. The docs page for
"See in World" still describes the retired browser flow; the explorer flags below are the current mechanism.

## Builder
- Collections: `https://decentraland.org/builder/collections`; collection page `/builder/collections/<uuid>`.
- Item editor: `/builder/item-editor?item=<itemId>&collection=<collectionId>`.
- New item: **Single item** (GLTF/GLB/PNG) or **Multiple items** (a zip per item: `wearable.json` + models +
  optional `thumbnail.png`; documented for linked/programmatic collections).
- Blocks saving: missing name/thumbnail/category/rarity/body shape; item over 3 MB (skin 8 MB); thumbnail over 1 MB;
  bad files. Everything from the GLB validator is a **warning**: TRIANGLE_COUNT_EXCEEDED, DIMENSIONS_EXCEEDED,
  MATERIALS_EXCEEDED, TEXTURES_EXCEEDED, BONE_INFLUENCES_EXCEEDED, LEAF_BONES_FOUND, NON_DEFORM_BONES_FOUND,
  ARMATURE_BONE_NAMES, UNRIGGED_VERTICES, CAMERAS_FOUND, LIGHTS_FOUND, ANIMATIONS_IN_WEARABLE,
  FORBIDDEN_MATERIAL_NAME, SPRING_BONE_COUNT_EXCEEDED.
- Item states: Ready to submit (price set or free) · Not ready · Under review · Published · Unsynced (edited after
  publishing: **Publish updates** sends it back through review).
- At most 50 items per collection. Collection name, item count and rarity are fixed after publishing.
- Preview animations: idle, walk, run, jump, clap, dab, dance, fashion, fashion-2/3/4, love, money, fist-pump,
  head-explode, wave, plus the collection's own emotes.

## wearable-preview (preview_wearable.py)
`https://wearable-preview.decentraland.org/?unity=true&mode=builder&profile=default&bodyShape=<urn>&emote=<anim>`
plus `skin`, `hair`, `eyes` (hex), `zoom`, `background`, `disableAutoRotate`. Items arrive as base64
WearableDefinitions via `postMessage({type: 'update', payload: {options: {base64s: [...]}}})`, with GLB contents as
in-page blob URLs (loopback URLs are blocked by Chrome's local-network rules).

## Desktop explorer
- macOS: `/Applications/Decentraland.app` is the launcher (it owns the `decentraland://` scheme); the explorer is
  `~/Library/Application Support/DecentralandLauncherLight/latest/Decentraland.app` (process `Explorer`).
  Logs: `~/Library/Logs/Decentraland/Explorer/Player.log`.
- Unpublished collections: `--self-preview-builder-collections <uuid>[,<uuid>]` + `--dclenv org|zone`
  (`zone` = the dev Builder) + `--position x,y`. Read only at a cold start. Wallet must own, collaborate on or curate
  the collection. Wearables and emotes both. Deep link form (what the Builder's "See in Decentraland" opens):
  `decentraland://?self-preview-builder-collections=<uuid>&dclenv=org&position=150,-150`.
- `--self-preview-wearables` / `--self-force-wearables` take URNs of **published** items only.
- `--mcp` / `--mcp-port <n>`: MCP server at `http://127.0.0.1:<port>/unity-explorer-mcp` (command line only for
  remote realms). Tools include screenshot, get_player_state, get_scene_state, teleport, move_to, walk, look_at,
  set_camera_mode, set_camera_pose, trigger_emote, send_chat, ui_list, ui_click, ui_set_text, ui_scroll, ui_drag.
  Claude Code can add it as an MCP server:
  `claude mcp add --transport http --scope user explorer http://127.0.0.1:8123/unity-explorer-mcp`;
  `explorer.py call` works from any shell.
- `--force-open-backpack true` opens the Backpack on arrival.

## Official validator
`@dcl-regenesislabs/wearable-validator` (CLI `wearable-validator validate <zip|glb|png> [--category c]
[--item-type wearable|emote] [--groups files,model,emote,content] [--json]`). 35 deterministic checks with rule ids
(S-xx files, M-xx model, E-xx emote, C-xx content) and four visual checks (render-valid, thumbnail-honesty,
visual-quality, emote-quality) that need its Linux render server and model credentials. Thumbnail rule: PNG,
square, ≤1024 px, ≤1 MB, ≥90% of the outermost pixel ring with alpha ≤8. Hiding the hands adds 500 tris; hiding the
whole head caps at 4,000.

## Clipping animations (fetch_dcl_animations.py)
- decentraland/unity-explorer `Explorer/Assets/DCL/AvatarRendering/AvatarShape/Assets/Animations/{Idle,Walk,Jog,Run}.anim`
  and `.../Emotes/EmbeddedEmotes/CommonEmotes/<Emote>/<file>` (.glb files are Git LFS: fetch from
  media.githubusercontent.com). Unity local rotations map to the Blender rig with `Quaternion((w, x, -y, -z))` and
  `pose = rest_local⁻¹ @ q`.
- decentraland/wearable-preview `public/emotes/<name>.glb` (emote wheel) and `public/emotes/character/<name>.glb`
  (category showcase), also served from `cdn.decentraland.org/@dcl/wearable-preview/<version>/emotes/`. These are what
  the preview's Babylon renderer plays; its Unity mode and the explorer use their own embedded versions.
- The emote-wheel files are **unskinned** and store their **first frame** as node TRS, so they carry no bind pose.
  check_clipping.py measures them against the wearable's own node TRS (wearables export in the rest pose, same rig).
  Checked: on a skinned emote (KO) both methods agree to 0 degrees on every bone; posed renders of clap/dance match the
  Babylon preview of the same files.
