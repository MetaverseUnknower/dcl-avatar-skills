# Clipping eval

Measures how well the curator's clipping check (`skills/curating-dcl-wearables/scripts/check_clipping.py`) tells real
clipping from noise, on published Marketplace wearables. It answers four questions:

- **False positives.** When the check reports a clip, is anything visible? Is it the item's fault or the animation's?
- **Misses.** The check masks out overlaps that already exist at rest (seams) and ignores contacts under `--depth`.
  How often is visible clipping hiding there, or in frames it calls clean?
- **REST lines.** The skill tells the agent to judge each rest overlap. How many are real bugs, and how many are noise?
- **Settings.** Which `--depth` and gate would get the verdicts right, and do Blender versions change them?

Published items have all passed curation, so they make a realistic mix: mostly clean work, some clipping that got past
the curators, and many awkward shapes (layered shoes, rigid helmets, loose hair) that stress the detector.

## Run it

Needs Blender (3.6 is what the skill was built on), the official `AvatarShape_A.blend` (BaseFemale) and
`AvatarShape_B.blend` (BaseMale), and the animations from `fetch_dcl_animations.py`.

```bash
python3 skills/curating-dcl-wearables/scripts/fetch_dcl_animations.py          # once
python3 evals/clipping/sample_marketplace.py                 # ~40 items, seeded, per category; --per feet=10 for more
python3 evals/clipping/run_eval.py --blender /Applications/Blender.app/Contents/MacOS/Blender   # ~1 min per pair
python3 evals/clipping/review.py ~/.cache/dcl-clip-eval/runs/blender-3.6.1     # label in the browser
python3 evals/clipping/score.py  ~/.cache/dcl-clip-eval/runs/blender-3.6.1     # -> report.md
```

Everything downloaded or generated lives in `~/.cache/dcl-clip-eval/` (corpus, runs, `labels.json`), outside the repo.

Compare Blender versions or checker revisions by running again under another name and scoring with `--compare`:

```bash
python3 evals/clipping/run_eval.py --blender "/Applications/Blender 4.4.app/Contents/MacOS/Blender"
python3 evals/clipping/score.py ~/.cache/dcl-clip-eval/runs/blender-4.4.3 --compare ~/.cache/dcl-clip-eval/runs/blender-3.6.1
```

Labels are keyed by candidate id (item/shape/kind/clip/frame/pair), so a rerun reuses every label whose frame is
picked again and only asks for the new ones.

## How it works

`probe.py` runs inside Blender on one item and one body shape. It runs `check_clipping.py` from the skill unchanged,
with the gate the skill prescribes for the category (Idle, Walk, Jog + the category's showcase clips), plus one hook
line after the checker's per-frame `measure()`. Through that hook it sees every overlap the checker sees, including the
ones it masks out. From that it picks up to 14 frames to label and renders each one with the Workbench engine
(textured, four views: two close-ups aimed at the overlap, one from the other side, one in context):

| kind | the detector said | what it measures |
|---|---|---|
| `pos-deep` | clip | its deepest hit per clip: real or not |
| `pos-shallow` | clip | its shallowest hit above `--depth` per clip: where false positives cluster |
| `rest` | judge | the deepest REST overlaps the agent is told to judge |
| `seam` | clean | a rest-seam overlap that deepened by ≥ 0.5 cm in motion: masked, so never reported |
| `graze` | clean | its deepest contact under `--depth` |
| `control` | clean | a random clean frame of a gated clip, viewed from four sides: base rate of misses |

`review.py` shows them one at a time with blind mode on (the detector's verdict stays hidden until you label), and
saves each keypress to `labels.json`. `score.py` turns the labels into precision by kind, depth, overlap type and
category; miss rates per probe; item-level gate verdicts checked against the labels; and a `--depth` sweep.

If `probe.py` stops with "expected exactly one line `m = measure(at_rest=False)`", the checker's loop changed: update
`ANCHOR` in `probe.py`.

## Limits

- Sampling picks frames per clip, so rates are directional; the sweep is for choosing a threshold, not a published number.
- Spring-bone geometry is still at its rest pose in motion frames (as in the checker); judge it in the real renderer.
- The renders are Blender's, not Decentraland's: shading and the hands/hiding defaults can differ. For a disputed
  frame, confirm with `preview_wearable.py` or in-world.
- `.gltf` (non-GLB) representations are skipped.
