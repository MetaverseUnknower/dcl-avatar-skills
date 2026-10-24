# Decentraland avatar skills

Two [agent skills](https://docs.claude.com/en/docs/claude-code/skills) for building Decentraland **wearables** and
**emotes** with an AI coding agent driving Blender:

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

Claude Code (personal skills):

```bash
git clone https://github.com/MetaverseUnknower/dcl-avatar-skills.git
mkdir -p ~/.claude/skills
cp -R dcl-avatar-skills/skills/* ~/.claude/skills/
```

Other agents that read `SKILL.md` folders (Codex, Gemini CLI, Copilot CLI): copy the same folders into
`~/.agents/skills/`.

The skills load on their own when a task is about a Decentraland wearable or emote.

## Contributing

Hit a new mistake or a rule change? Add it to the skill's `lessons.md` or `requirements.md` (with a source) and open
a pull request.

## License

MIT
