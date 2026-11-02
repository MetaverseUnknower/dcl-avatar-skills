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

- Rest-pose seam allowances hide real bugs: a clip gate that ignored every overlap present at rest silently
  accepted a webbing strap passing through its own buckle. → List every rest overlap between item pieces and judge
  each one; only tucks into skin or the cloth a piece is sewn to are fine (`check_clipping.py` in
  curating-dcl-wearables prints them piece by piece).

- A belt hugging the cloth only at its columns: the straight edge between two columns cuts inside a round seat, so
  the denim showed through the belt in wedges. → Place each column so the segments to its neighbours clear the cloth
  (largest cast over the span ÷ cos(offset)), capped at ~1 cm.
- That same rule on a thigh strap near the crotch cast its side rays into the OTHER leg: the strap bulged out, took
  that leg's weights and tore through the denim in Walk (0.4 → 4.5 cm). → Leg straps hug their own leg only.
- A cast that misses (the belt's top row above the lower front waistband) fell back to a fixed 8 cm radius and buried
  the whole front of the belt inside the body. → Fall back to the neighbouring row's measured radius, never a constant.
- A strap end hung at an angle within a buckle's width passed through the buckle. → Hang it from just under the
  buckle (the tail coming out below it), shortened so the tip stays put. A rigid buckle on a flexing band needs the
  band's per-corner weights or it cuts in when the hips move.
- **Skirts and tabards on a skin.** Any cloth beside the thigh at 80–93 cm hits the idle hands (male hands rest ~0.2 cm
  off the bare thigh; female wrists rest on the hips at belt height). → Side vents from ~93 cm down, snug sides, thin
  wrist cuffs. Front panels follow the thigh only below the hip joint (~94 cm), or a lifted knee rotates cloth up into
  the belly; the female body needs ~6 cm extra front room vs ~3.5 cm male, and more than that hits her hands in Walk.
  Female hand-to-hip contact at the belt can't be fully cleared.
- **Cross-sections measured on trimmed meshes collapsed a skirt.** After trimming, some heights had no geometry and the
  convex hull silently returned -1e9. → Measure on the untrimmed base meshes, slicing edges, not vertex bands.
- **Skin-tight layers over bare skin showed skin through.** Other lower_body items (shorts, skirts) bring their own leg
  skin on the same surface as the base leg; a layer 0.06–0.25 cm off it showed skin through it in the Builder. → Keep
  at least ~0.3 cm wherever it can be seen bare, end the layer below where your own skinny pants hug the leg instead of
  thinning it there, and check against the base-avatar shorts.
- **A skin-hugging shell needs ~4 mm, not 2.** At 2 mm Blender showed no gap and nothing under the skin in any pose, but
  the Builder's renderer showed skin through it in big triangles. Lifted ~4.5 mm (≥3.5 mm where it's drawn) it
  renders solid. → Check the Builder preview close-up for any shell that sits on skin.
- **A low-poly quad's diagonal reads as a straight crease on curved shapes** (the inner half of a seat was one quad from
  the split to the peak). → Count the verts across a curved region before tuning the shaping function; add an edge line
  there and bow it out to a round profile. Reshaping the falloff alone can't curve a single facet.
- **Denim bridges the cleft; it isn't skin tight.** Cheek to cheek the fabric spans the crack with a shallow dip (under
  1 cm), and the leg split opens below the cheeks, not at crotch height. → Any "move verts toward the back surface"
  pass needs a height limit, or it drags the crotch's front verts back too; check the crotch line front to back.
- **Pieces of a set clipped once combined.** Clip checks that left swinging spring-bone strap ends out missed real
  contacts: a belt-strap end through a glove's backswing in Walk, a shin strap draped over new boots. → When a set
  grows, run an all-pairs overlap check of every worn mesh, springs included, at rest and through Idle/Walk/Jog. Fix
  per body shape (the clear spot differs between the round and flat seat), and re-run motion: a shortened chain needs
  more stiffness or it flails in Run.

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
- **A long cape on chains rooted at Spine2 was sent back by curation.** It sagged onto the seat, and every emote that
  turns or tilts the hips against the chest put the skirt through it (13 of 17 built-in emotes); the cape check had only
  tested legs and hands in the locomotion cycles. → Root the chains of anything hanging below the waist at
  `Avatar_Hips` (upper part on Spine2, blended over the waist), keep gravity well under stiffness (e.g. 2.0 / 0.3), and
  run the spring simulation through the emotes against the whole body. That brought it to 3 of 17, only big leg moves.
- **A cape that cleared the heels in a forward-moving spring sim showed boots through it in the Builder.** The preview
  walks in place, so the cape never trails, and vertex-depth checks miss a boot through the middle of a big triangle. →
  Simulate locomotion in place too, count limb-vs-cape triangle crossings, keep a long hem well back from the heels.
- **Pushing a cape far off the upper back for arm clearance read as a hump.** → One straight slant from the collar to
  the seat, widened only below the swinging hands. Classify a solidified piece's lining per shell, not per face.
- **Facial hair rides the skin under it, and the jaw's underside is partly neck.** A beard weighted 100% to
  `Avatar_Head` cut 0.8 cm into the head in Walk/Jog: the base head weights the underside of the jaw and chin 10–55% to
  `Avatar_Neck`, and that skin hinges up when the head nods. → Copy weights from the head triangle under each vertex
  (barycentric) and keep a strap beard on the front of the jaw and chin. A vertex-only skin-gap check passed while faces
  dipped 0.2 cm under the low-poly head between their corners: sample points inside every face.
  `check_clipping.py` with `CLIP_DUMP=1` prints the clipping polygons and their weights.
- **A full beard is the head's own faces, lifted.** Copying the base head's faces over the beard region and inflating
  them keeps the head's skin weights, so the beard follows the face in every pose (a projected grid needed weight
  transfers and still looked wonky). Paint the outline, mouth gap and details in the alpha by 3D position; trace the
  mouth gap from the base mouth card's opaque texels, and drop big faces that reach outside the outline.

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
- **"hair" in a material name tints it with the player's hair colour.** The explorer matches "hair" anywhere in the
  material name, case-insensitive, and multiplies the base colour (emission is copied untinted). → Fixed-colour hair
  needs a material name without "hair" or "skin". For player-coloured hair with fixed accents: a "hair" material with a
  light-grey shading texture (plus an emissive map for glowing details) and a separate untinted accent material. The
  explorer also forces back-face culling on avatar materials: strands need closed volume.
- **Grey hairs on a hair-tinted item go in emission.** The tint multiplies the whole base texture, so no texel stays
  grey. → Put the grey strands in a glow texture on emission. Fine strands painted straight at 512 turn into square
  pixels: paint at 1024 and area-average down to 512.
- **A logo stamp flattened a strap into a coloured block.** Filling the tag with a flat averaged ground lost the strap's
  own texture. → Copy the old texels into the new UV spot and outline the logo darkly so stripes don't cross it.
- **Facial features (eyes, eyebrows, mouth) are PNG sets, and the mask is inverted.** A 256 px RGBA texture on the base
  eye card's layout (both eyes in the top ~40%) plus a `_mask` PNG in the same representation. **Black in the mask =
  tinted by the player's colour, white = keeps the drawing's own colour.** A white-iris mask shipped once and the eyes
  never took the eye colour. → Test by switching eye colours in the Builder's avatar panel. The official validator's
  mesh checks skip these items; its PNG checks (square, ≤256, alpha) still run. Package with `package_item.py --male
  x.png --male-extra x_mask.png`.

## Builder
- Loading an item-editor URL doesn't change the selected item; the pencil edits whatever is selected. Select by
  clicking in the left list and confirm the item id.
- Builder warnings are not acceptance; curation enforces the docs.
- **The bulk zip import doesn't set `hides`, and can mix up body shapes.** New item → Single item fills name, rarity,
  category, description, tags, both body shapes and the thumbnail from a `package_item.py` zip, but not hides: set
  Overrides → Base body by hand and read it back. It also stored the male GLB as the female representation on 5 of 7
  items, and put a facial item's four PNGs in both representations. → After every zip upload, read the item's
  representations back from the Builder API and hash each stored file against the local ones. For facial features,
  upload one zip per body shape.
- **Springs are stored per bone and per body shape.** The spring panel has Male / Female tabs, and a tab you don't
  fill stays on the defaults (2 / 0 / 0.5); read-backs that only read the active tab missed it for a day. → Fill both
  tabs, save, reload, and read both back. Set the Center by hovering the bone-tree node and clicking Select. The first
  spring save after a file swap doesn't stick: save again and read it back after a reload.
