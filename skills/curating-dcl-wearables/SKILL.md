---
name: curating-dcl-wearables
description: Use when a Decentraland wearable has been built and needs reviewing before curation submission - validating the exported GLBs and thumbnail, checking clipping through Decentraland's animations, uploading it to the Builder, checking it there, viewing it in-world in the desktop explorer, or deciding whether it is ready to submit.
---

# Curating Decentraland Wearables

## Overview

The second pair of eyes after a wearable is built (`creating-dcl-wearables` builds it). Act like the Curation Committee: assume the item is not ready until each gate below has evidence, then give a verdict with that evidence. Never call an item ready from renders alone or from "the Builder accepted it": every Builder GLB check is a warning.

`<skill-dir>` is the folder this SKILL.md is in; the scripts are in `<skill-dir>/scripts/`. `references.md` there has the Builder screens, explorer flags and validator details.

**The user stays in charge of anything signed, paid or public.** Uploading to their own unpublished collection is fine once they've asked for a review; publishing, paying the fee, posting or minting is theirs to do or explicitly approve.

## Gates, in order

Run each for **both body shapes**. A FAIL stops the review: report it and hand it back to the builder.

| # | Gate | How | Passes when |
|---|---|---|---|
| 1 | Doc limits | `check_wearable.py` from the sibling `creating-dcl-wearables` skill, then `package_item.py` + the official validator (below) | no FAIL, and the validator says PASSED |
| 2 | Thumbnail | `check_thumbnail.py`, then look at it | no FAIL; WARNs judged |
| 3 | Clipping | `fetch_dcl_animations.py` once, then `check_clipping.py` per body shape | Idle/Walk/Jog PASS; every REST piece overlap judged; Run/emote reports reviewed |
| 4 | Real renderer | `preview_wearable.py` idle/walk/run, both shapes | images look right (hands present, nothing missing, no poke-through) |
| 5 | Builder | upload, set every field, read the validation panel, preview | no FAIL badge, warnings explained, item "Ready to submit" |
| 6 | In-world | `explorer.py` self-preview + MCP screenshots | item equips and looks right from all sides, walking, running, emoting |
| 7 | Verdict | report to the user | everything above has evidence |

### 1. Doc limits and the official validator

```bash
python3 <skill-dir>/../creating-dcl-wearables/scripts/check_wearable.py item_male.glb item_female.glb --category <c> [--hides a,b]
python3 <skill-dir>/scripts/package_item.py item.zip --name "…" --description "…" --category <c> --rarity <r> \
    --male item_male.glb --female item_female.glb --thumbnail thumb.png [--hides a,b] [--tags a,b]
npx -y @dcl-regenesislabs/wearable-validator validate item.zip        # Node >= 22.19
```

This is Decentraland's own curation rule book as code (DAO-mandated). A bare GLB gives only a partial verdict and can't see hides; the zip (`wearable.json` + GLBs + `thumbnail.png`, the Builder's bulk format) gives a full one. Its visual checks (`--groups rendering`) need its Linux render server and model credentials; skip them locally and do gates 4 and 6 instead.

### 2. Thumbnail

`python3 <skill-dir>/scripts/check_thumbnail.py thumb.png`. Hard rules: square PNG, ≤1024 px, ≤1 MB, transparent background (≥90% of the border ring clear). Curation: 256 px per the docs (larger passes the validator; resize to 256 rather than argue it), the item alone, filling the frame, an honest picture of the item, and **no extra graphics**. Keep it simple: at most a small logo pinned to a corner, preferably bottom right (curator guidance; not written in the public docs). The script lists every separate element with its position; look at the image too.

### 3. Clipping, by the numbers

The avatar .blend: the official base avatar file for that body shape, with meshes named like `*uBody*`, `*lBody*`, `*Feet*`, `*Hands*`, `*Head*` on the 62-bone `Armature` (tested with the BaseFemale/BaseMale avatar shape files; the emote rig `Avatar_File.blend` hasn't been tried).

```bash
python3 <skill-dir>/scripts/fetch_dcl_animations.py              # Idle/Walk/Jog/Run + built-in emotes
blender -b <BaseFemale avatar .blend> --python <skill-dir>/scripts/check_clipping.py -- \
    --glb item_female.glb --category <c> [--hides a,b] --json clip_female.json
# then the same with the BaseMale .blend and item_male.glb
```

It poses the official avatar through Decentraland's real clips and intersects triangles every frame: item vs each visible body part, and **item piece vs item piece**.
- **REST lines are the trap.** Overlaps present at rest are not counted in motion, so the script lists them for you to judge, piece by piece with sizes and positions. A collar in the neck, or a strap lying on the cloth it's sewn to, is fine. A strap, plate or tab through a buckle or another hard piece is a bug, even if nothing moves. Name each one in the report.
- **Gate:** Idle/Walk/Jog must PASS. Contacts tagged `bare hand already in thigh` are Decentraland's own female idle and are not the item's fault.
- **Run and emotes** are reported, not gated: the bare avatar clips itself in some Run frames, and rigid items can't clear every emote. Summarize which ones clip and where.
- Spring-bone pieces are checked at rest only; the explorer simulates them, so look at them in motion in gates 4 and 6.

### 4. The real renderer, before uploading

`python3 <skill-dir>/scripts/preview_wearable.py --category <c> --male … --female … --out previews/item --anims idle,walk,run [--hides a,b]` plays the local GLBs in Decentraland's hosted preview (the Unity renderer the Builder and explorer use). Look at every image. It mirrors the Builder's default of keeping the base hands visible on upper_body items; `--raw-hiding` shows them hidden, which is how the item would behave without that Builder setting.

### 5. The Builder (decentraland.org/builder)

Drive it in the user's browser with whatever browser automation you have; the user signs in with their wallet. Uploading to their own unpublished collection is part of the review; nothing here is public.
1. **Collections → the collection → New item → Single item.** Upload one body shape's GLB (or one unisex GLB). Fill name (≤32), rarity, category, and choose the body shape.
2. Thumbnail: the Builder renders one; to use yours, click the camera icon and choose the 256 px PNG.
3. Save, then in the item editor: **… → Add male/female representation** for the other body shape.
4. Right panel: description (≤64), tags, **Overrides** (Replaces and Hides), VRM export permission, outline compatible.
5. **Spring bones** panel (appears when bones contain `springbone`): enter stiffness, gravity power, gravity direction, drag and Center for each chain, on **both** body-shape tabs, from the build's hand-off sheet.
6. Read the validation badge in the centre panel: open **Validation Results**. Every line is a warning; explain each one or send the item back.
7. Preview: switch the body shape, play idle, walk, run and a few emotes (dance, wave, fist-pump), and try different skin and hair colours. Hides apply live.
8. Price is the user's decision: ask, then set it (or **Make it free**) and check that the collection page shows the item as **Ready to submit**.

Gotchas: loading an item-editor URL doesn't change the selected item; click it in the left list and confirm the id. Re-uploading a GLB resets the spring-bone settings: enter them again.

### 6. In-world, before publishing

```bash
python3 <skill-dir>/scripts/explorer.py launch <collection-uuid>     # cold-starts the explorer (quits a running one)
python3 <skill-dir>/scripts/explorer.py wait                         # user signs in if asked
python3 <skill-dir>/scripts/explorer.py call ui_list '{"stack":"ugui"}'
python3 <skill-dir>/scripts/explorer.py screenshot shot.png
```

Ask before quitting a running explorer. The signed-in wallet must own the collection, or be a collaborator on it. Unpublished items appear in the **Backpack** beside your owned ones; equipping them is local only, so nobody else sees them. Open the Backpack (`SidebarBackpackButton`), search with the `SearchBar` field (`ui_set_text`), click the item to equip it, then close the Backpack. Then:
- `set_camera_pose` (or `look_at`) for front, back, both sides and three-quarter views; take a screenshot of each.
- `walk` with `kind` walk, jog and run; `trigger_emote` a few emotes. Watch spring bones swing and check nothing pokes through.
- To see the other body shape, change the Body Shape slot in the Backpack and repeat.
- `explorer.py tools` lists every MCP tool. The port is full local control of the client while it's open.

### 7. Verdict

Report a table: gate, result, evidence (numbers, file paths, screenshots shown to the user), and what needs a human decision. **Ready for submission** only when gates 1–6 pass and every judged item is accepted. Submission itself: collection page → **Publish** → confirm the name (it's final) → accept the content policy → pay (25 USD per item; the Foundation currently covers 20) → a forum thread opens for the curators' feedback. That's the user's step. After a rejection, edit the items and resubmit through the forum thread.

## Common rejection reasons to look for

Bad skin weights; avatar UVs not preserved; posed arms; a held object (sword, shield) filed as hands_wear; over the triangle, material or texture budget; non-transparent or busy thumbnails; a thumbnail that doesn't match the item; duplicates of published items; QR codes; IP or content-policy problems; a misleading category; non-humanoid items (pets, vehicles).
