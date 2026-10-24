# Emote lessons

Mistakes made while building real Decentraland emotes with an AI agent in Blender, and the rule each one taught.
Each entry: what went wrong → the rule. Add your own as you hit them.

## Seeing what the player sees
- **Stale preview.** The reviewer opened an old render and saw no change. → Re-render after every change.
- **A local scene served the old GLB for a day.** → Restart the scene preview after rebuilding.
- **Three "fixes" judged from untextured test renders** (chain links on a prop), none real. → Per-frame numeric
  check first (a linking test + minimum wire gap), crops from the real textured camera, report numbers.
- **One-view checks.** Prop legs "still not attached": fixed only from the front. → Render the prop alone from front,
  below, above and mid-action.
- **Blender vs real players.** Blender renders only keys; players interpolate. → Check bone-scale tricks and fast
  props in the Builder preview (Unity renderer).

## Hands and limbs
- Hands rotated wrong. → Palm = hand bone −X both hands; thumb side −Z left / +Z right; pose from finger + palm
  direction with the forearm taking the roll; measure it every frame.
- Limbs through limbs. → Triangle-overlap check between limb meshes; for designed contortions, score capsule clearance
  between limbs and optimise for it.
- Limb checks usually skip upper arm × chest (they meet at the armpit). → Separate arm-vs-chest check from ~9 cm past
  the shoulder; standing frames show 1–2 contacts even at rest, so judge the active frames.
- Female body: a near-straight arm across to the crotch runs through the breast; no pole fixes it. → Drop the
  cross-body reach, turn the chest toward the working hand (Spine2 ~30°, neck counter-turned), roll that shoulder (~26°).
- Over-correcting: a deep hunch to clear the chest, then even a slight lean, were rejected ("the earlier one was more
  chill"). → Local fix only.
- A hand on the hip that reads well: closed fist, knuckles on the waist (female hips x ~19–20 cm at y 100–105). An
  open palm on the hip looked odd. Offset the wrist from the palm away from the body.
- Hanging wrists at x ±20.5 cm sink into the thighs; ±24.5 (wide stance 27–28) is clear.
- Fists low and >20 cm forward are out of reach unless the spine leans and the clavicles protract.
- Second hand on a prop held by the first: place it from where the first hand actually ended up, not its IK target.
- An optimiser "passed" by swinging the hand-foot link over the foot instead of hopping the foot over it. → Constrain
  the intended motion.
- Pose scale drift: restoring only rot/loc after setting `matrix` drifted hand scale to (0.70, 1.52, 0.95). → Reset
  scale; assert 1.

## Props
- See-through props: back faces are culled and the double-sided flag is ignored for emote props; a cocoon rendered
  inside out. → Closed, outward-wound geometry or duplicated back faces; fail the build on inside-out (signed volume)
  or open single-sided parts. Preview with backface culling on.
- Props through the body. → Prop-vs-body triangle check each frame (hands excluded); list intended overlaps
  explicitly. Plan prop paths with waypoints/arcs.
- Per-frame 180° flips on a prop bone (TV static) swung through 90° between keys and stuck out of the cabinet. → No
  discrete jumps; every keyed change becomes a sweep.
- Liquid in a held bottle: bone TRS can't tilt a surface → a scaled cylinder whose spread follows the bottle angle
  linearly; only the slosh goes through a spring (~1.7 Hz, damping .35, 35% direct push, low-passed). A pure spring
  read as lag.
- Props stay at their last key while the avatar blends back. Popping a bottle in/out was rejected → Loop it, and
  restore any changed prop state before the seam.

## Head, neck, scale tricks
- The real head can't detach (neck verts weighted Head+Neck); moving the head drags a sheet of neck. → Scale the NECK
  bone to 0.001 about its base (y 149.2), scale keys only; show a prop head. Flying the real head on a tiny neck is
  not achievable on either body.
- Shrinking the head bone about a low neck point left a pinched cone; about its own origin, a tall spike.
- Cross-fade ballooning: hips 0.001 + head 1150× peaked ~290× ("huge head"). → Collapse limbs at their roots, torso
  ~0.3, split the counter-scale over neck+head; peak ≈ (s+1)/2 · ((c+1)/2)²; print the simulated peak each build.
- Grow a head back: the same neck scale 0.001 → 1 with an ease-out-back overshoot.

## Size, length, export
- Force sampling exported T/R/S for all 62 bones; a 9.5 s emote went past 1 MB. → Export keyed channels only.
- Length limits were forgotten until late. → Check ≤10 s/300 frames and the 4 m box every build.
- Blended in-between poses dip below the floor. → A floor guard that lifts frames so no vertex goes under 0.

## Builder and scenes
- The item editor plays once and returns to idle even on Loop; loops are only verifiable in-world.
- A re-upload resets Play mode (and other fields): select the item by clicking it in the list, confirm the URL's item
  id, set every field again. Escape closes the whole Add-item modal.
- A published collection is locked: new items need a new collection.
- A scene-triggered emote didn't play: the explorer waits for the avatar to be grounded, so locking movement first
  blocked it; the GLB must be included in the scene.
