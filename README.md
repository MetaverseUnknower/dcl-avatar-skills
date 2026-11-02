# Decentraland avatar skills

[Agent Skills](https://agentskills.io) for building and reviewing Decentraland **wearables** and **emotes**, and the
**buildings** and **furnishings** scenes are made of, with an AI coding agent driving Blender. They work in **Claude Code**, **OpenAI Codex** and **xAI Grok Build** (and other agents that
read `SKILL.md` folders):

| Skill | For |
|---|---|
| [`shaping-dcl-item-ideas`](skills/shaping-dcl-item-ideas/SKILL.md) | before building: asks the questions that turn an idea into a buildable brief (slot and budget, fit, motion, emote length and loop, props, IP and curation rules, release details) |
| [`creating-dcl-wearables`](skills/creating-dcl-wearables/SKILL.md) | hair, hats, helmets, masks, upper/lower body, feet, hands_wear, accessories, skins |
| [`creating-dcl-emotes`](skills/creating-dcl-emotes/SKILL.md) | avatar animations, with or without props, sound and baked particles |
| [`creating-dcl-buildings`](skills/creating-dcl-buildings/SKILL.md) | walk-in buildings sized in parcels: colliders, doorways, stairs under ramp colliders, upper floors, one-palette low-poly looks |
| [`creating-dcl-furnishings`](skills/creating-dcl-furnishings/SKILL.md) | chairs, couches, tables, shelves, lamps and decor, with `dcl-sittables` seats people can sit on |
| [`listing-dcl-wearables`](skills/listing-dcl-wearables/SKILL.md) | after review: rarity per piece, names, descriptions, utility and tags written for the Marketplace (checked by `check_listing.py`), then the Builder upload |
| [`curating-dcl-wearables`](skills/curating-dcl-wearables/SKILL.md) | reviewing a built wearable like the Curation Committee: official validator, thumbnail, clipping through Decentraland's animations, Builder upload and checks, in-world self-preview, verdict |

Each of the wearable and emote `creating-*` skills has (the curator has its own `references.md` and scripts, the lister a `check_listing.py`, and the idea-shaper is a single `SKILL.md`):

- **`SKILL.md`**: the workflow, a quick-reference table of limits, rig facts and the pitfalls that keep coming back.
- **`requirements.md`**: every rule from the Decentraland docs, cross-checked against the Builder, content-validator,
  schemas and unity-explorer source, with sources and the places they disagree. The Builder's GLB checks are only
  warnings; curation enforces the docs.
- **`lessons.md`**: mistakes an agent actually made on real wearable and emote projects, and the rule each one taught.
- **`scripts/`**: a checker that validates an exported GLB against the documented rules (pure Python + numpy).

## Checkers

```bash
pip install numpy

# Wearables: triangles per category (with the hides combiner), materials/textures, texture size and alpha,
# forbidden names, skeleton, weights, bounding box, file size, spring-bone rules.
python3 skills/creating-dcl-wearables/scripts/check_wearable.py hat_male.glb hat_female.glb --category hat --hides hair

# Emotes: clip/armature naming, length, frames, fps, first/last keys, hips travel, rotation jumps between keys,
# bone-scale blow-ups on cross-fade, loop seam, prop budget, audio.
python3 skills/creating-dcl-emotes/scripts/check_emote.py Wave.glb --loop --audio Wave.mp3

# Scene models: colliders (named, material-free, solid, convex), origin on the floor, footprint, textures, triangle
# and material recommendations (warnings: scene limits are soft), dcl-sittables seats clear of colliders.
python3 skills/creating-dcl-buildings/scripts/check_scene_model.py cafe.glb --kind building --footprint 1x1
python3 skills/creating-dcl-buildings/scripts/check_scene_model.py couch.glb --kind furniture --type couch --sittables couch.sittables.json

# Buildings: walks a route through the colliders as a 0.6 x 1.8 m avatar that steps 40 cm and stops at 46 degrees.
python3 skills/creating-dcl-buildings/scripts/check_walk.py cafe.glb --route route.json [--place couch.glb 2 -3 90]
```

`skills/creating-dcl-buildings/scripts/blender_palette.py` (run inside Blender) colours a whole model from one swatch
texture, so a piece needs one material instead of one per colour.

The checkers' own tests (good and known-bad models) are in `tests/`: `pip install pytest numpy && pytest tests`.

Curator scripts (`skills/curating-dcl-wearables/scripts/`), each usable on its own:

| Script | Does | Needs |
|---|---|---|
| `package_item.py` | builds the Builder item zip (`wearable.json` + GLBs + thumbnail) that Decentraland's official validator (`npx @dcl-regenesislabs/wearable-validator validate item.zip`) fully checks | Python |
| `check_thumbnail.py` | square / size / transparency like the validator, plus framing and stray graphics or logos (corner, ideally bottom right) | Pillow, numpy |
| `fetch_dcl_animations.py` | downloads 50 of Decentraland's real animations: Idle/Walk/Jog/Run, the explorer's built-in emotes, the emote-wheel emotes and the per-category showcase animations | Python |
| `check_clipping.py` | poses the official avatar through every frame of those clips in Blender and intersects triangles: item vs body and item piece vs piece, with penetration depth, rest overlaps listed piece by piece, and the clips that must pass chosen per item | Blender, the avatar .blend |
| `preview_wearable.py` | renders local GLBs on the avatar in Decentraland's preview (Unity, or `--babylon`), any animation, both body shapes, before uploading | Chrome, Playwright |
| `explorer.py` | cold-starts the desktop explorer with an unpublished Builder collection in self-preview and drives it through the explorer's MCP server (screenshots, camera, walking, emotes, UI) | Decentraland desktop app |

FAIL means a documented rule is broken, WARN means a Builder warning or a known in-world problem, and INFO is a
number to read. The exit code is 1 on any FAIL, so they work in build scripts. They read only the GLB: clipping
against the body still needs a per-frame check in Blender.

## Install

```bash
git clone https://github.com/MetaverseUnknower/dcl-avatar-skills.git
cd dcl-avatar-skills
bash install.sh            # Claude Code + Codex + Grok Build
bash install.sh codex      # or just one: claude | codex | grok
bash install.sh --link     # symlink instead of copy, so `git pull` updates them
bash install.sh --project ~/my-wearables   # into one repository instead of your home folder
```

Where each agent finds them:

| Agent | Personal | Per repository |
|---|---|---|
| Claude Code | `~/.claude/skills/` | `.claude/skills/` |
| Codex | `~/.agents/skills/` | `.agents/skills/` |
| Grok Build | `~/.agents/skills/`, `~/.grok/skills/` (also reads Claude Code skills) | `.grok/skills/` |

The skills load on their own when a task is about a Decentraland wearable, emote, building or furnishing. To call one explicitly: `/creating-dcl-wearables` in Claude Code or Grok Build, `$creating-dcl-wearables` in Codex. Restart the agent if a newly installed skill doesn't show up.

Grok Build reads both `~/.claude/skills` and `~/.agents/skills`, so with both installed it may list each skill twice; the copies are identical.

## Contributing

Hit a new mistake or a rule change? Add it to the skill's `lessons.md` or `requirements.md` (with a source) and open
a pull request.

## License

MIT
