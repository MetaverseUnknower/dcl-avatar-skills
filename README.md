# Decentraland avatar skills

Two [Agent Skills](https://agentskills.io) for building Decentraland **wearables** and **emotes** with an AI coding
agent driving Blender. They work in **Claude Code**, **OpenAI Codex** and **xAI Grok Build** (and other agents that
read `SKILL.md` folders):

| Skill | For |
|---|---|
| [`creating-dcl-wearables`](skills/creating-dcl-wearables/SKILL.md) | hair, hats, helmets, masks, upper/lower body, feet, hands_wear, accessories, skins |
| [`creating-dcl-emotes`](skills/creating-dcl-emotes/SKILL.md) | avatar animations, with or without props, sound and baked particles |

Each skill has:

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
```

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

The skills load on their own when a task is about a Decentraland wearable or emote. To call one explicitly: `/creating-dcl-wearables` in Claude Code or Grok Build, `$creating-dcl-wearables` in Codex. Restart the agent if a newly installed skill doesn't show up.

Grok Build reads both `~/.claude/skills` and `~/.agents/skills`, so with both installed it may list each skill twice; the copies are identical.

## Contributing

Hit a new mistake or a rule change? Add it to the skill's `lessons.md` or `requirements.md` (with a source) and open
a pull request.

## License

MIT
