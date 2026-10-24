# Wearable lessons

Mistakes made while building real Decentraland wearables with an AI agent in Blender, and the rule each one taught.
Each entry: what went wrong → the rule. Add your own as you hit them.

## Curation, scope, design
- **Posed arms rejected.** An upper_body with the arm posed holding a bat came back: "wearables with posed arms are no
  longer approved". → Keep normal base skinning on arms. A carried prop becomes its own accessory on a free slot (a
  bat on the back shipped as an **earring** with small real earrings, inside 500 tris).
- **Vehicles/pets aren't wearables** (a rideable spider). → Build an emote with a prop instead.
- **IP replicas.** "Make it look like the real <character>" for a sold item risks rejection or a DMCA notice. →
  Original, cartoony parodies. Settle before modelling.
- **Over-correcting.** A fix for one clip that restyles the whole item gets rejected. → Fix locally.

## Seeing what the player sees
- **Base head hidden in renders**, so skin/hair bumps poked through a helmet in-world. → Set Hides (head, hair,
  facial_hair, hat, eyewear, earring, tiara, top_head) and render with the base body present.
- **Invented preview pose.** A guessed hand rotation sent a held knife "out to the side" in-world, twice. → Pose only
  from the real unity-explorer `Idle.anim`.
- **Fingers never posed in previews**, so a fist over a knife went "all spiky" in-world. → Previews use real clips;
  assert the exported GLB has no item vertices on finger bones unless intended.
- **In-world darker than Blender** (a creature skin read near-black). → Lighter albedo; don't rely on glow/bloom.
- **Stale preview.** The person reviewing saw an old render and no change. → Re-render after every change; restart a
  local scene preview after a GLB rebuild.

## Fit and clipping
- Female idle hangs bare hands into the thighs (several Idle frames). Male idle hands: |x| 19–20 cm, y 80–86 cm, min y
  ≈ 73 cm. → Snug outer hip, coat side vents, nothing wide at hand height.
- The bare avatar self-intersects in some Run samples. → Don't gate Run.
- Raw overlap counts can't tell a designed tuck from a poke. → Gate on overlaps outside each pair's rest-pose seam
  polygons dilated ~2 rings.
- Too tight ("too skin tight", neck clipping through). → ≥~1.5 cm off skin; copy the avatar's own neck weights; run a
  mask's base down to the neck/shoulder join, not flared.
- Trousers clear of the shirt at rest still meet its hem in the Jog lean. → Count the upper body's bottom 2 cm as
  seam; waistband ~0.45 cm.
- Rigid glove plates over blended fabric clipped when fingers curl. → Fabric under each plate follows that plate's
  bone; test Idle/Walk/Jog/Run and built-in emotes.
- Selecting faces by bone weight cut a square notch into the male chest. → Select by position; check both bodies.
- Deforming the base foot into a shoe pinches the toes into claws. → Loft shoes from measured sections.
- Rigid hand props can't pass the sitting/KO/hands-together emotes. → Report which emotes fail; don't claim none.
- Vertex-inside tests miss long props through limbs. → Triangle overlap (BVH).

## Weights and rig
- A loop that edited weights while iterating them silently dropped most edits. → Read all, then write; re-check the GLB.
- Straps/decals snapped to the nearest 3 vertices' weights drift in Jog. → Interpolate the underlying polygon's
  weights (`find_nearest` + `poly_3d_calc`).
- Spring chains with Center none stream straight back with locomotion speed (VRM world-space inertia). → Center
  `Avatar_Hips` for leg/held chains; hang dangles on the outer side or back, ending above the knee.
- Builder re-upload resets spring params. → Keep them in a hand-off sheet and re-enter.
- Creature skins on stock locomotion: model in the Idle pose and bake to rest
  (`(Σ w·(pose @ bone.matrix_local⁻¹))⁻¹ @ v`); forelegs on the arm bones swing like lances, so weight a lower foreleg
  down the **opposite** leg chain (Walk swings each arm with the opposite leg → diagonal trot). Keep foot tips within
  ~10 cm of the human foot's height.

## Textures and materials
- 2 materials / 2 textures: a third slipped in unnoticed. → Atlas; count before reporting.
- The base `AvatarSkin_MAT` exports its placeholder skin PNG (shows as an extra image); it doesn't count.
- A face tattoo showed as "a blonde box": Blender re-embedded an old RGB copy without alpha. → Delete/recreate images
  each build; verify the PNG inside the GLB has alpha (the checker does).
- Emissive map not rebuilt after a UV change came out blotchy. → Rebuild every map sharing the UVs.
- Flat front/back art fitted per vertex on the low-poly base legs came out "squished" with diagonal seams. → Bake per
  texel from 3D position into the item's own UV layout; stamp decals (pockets) flat afterwards, never across the
  crotch line.
- A design cut along mesh face edges stair-stepped (box collar, barcode rips). → Paint seams by distance from real
  edges or cut along a smooth curve.
- Lettering squished in a square texture. → Draw in real cm for the object's size; blocky glyphs; small text on
  alpha-cut grids ~0.3 cm over the cloth at ~11 px/cm.
- Fine detail averages away at 512 px. Docs allow 1024.
- Tint: only base color of materials named with `hair`/`skin` follows the player's colour; emission doesn't; eye
  colour can't be read. Assign faces by coverage or edges half-tint.
- See-through rips on lower_body show the hollow inside (legs are hidden). → Base-leg patches in `AvatarSkin_MAT`
  ≥10 cm around the rips.
- Flat-shaded cloth gives a checkerboard of sheen. → Smooth-shade cloth.
- Face paint: copy the front of the base head mesh, lift ~0.15 cm, MASK texture, cut holes where the eye/mouth cards
  are opaque, ship in a hair-slot item (1.5K) so the real head shows.

## Builder
- Loading an item-editor URL doesn't change the selected item; the pencil edits whatever is selected. Select by
  clicking in the left list and confirm the item id.
- Builder warnings are not acceptance; curation enforces the docs.
