---
name: shaping-dcl-item-ideas
description: Use when someone has an idea for a Decentraland wearable, skin, emote, building, furniture or decor piece (or a set of them) that isn't specified enough to build yet - before modelling or animating starts, when the request is a concept, a vibe, a reference image or a one-liner like "make me a cyberpunk jacket", "an emote where my head turns into a pumpkin" or "a cute coffee shop for my scene".
---

# Shaping a Decentraland Item Idea

## Overview

Turn an idea into a short, buildable brief by asking questions, **one at a time**, before any building starts. Most expensive corrections in DCL work trace back to a question nobody asked up front: an arm pose curation rejects, a prop that can't stay in the hand, a 12-second emote, a budget blown by a hidden slot, a client who wanted it darker.

The output is a `BRIEF.md` the person has confirmed. Then hand off to `creating-dcl-wearables`, `creating-dcl-emotes`, `creating-dcl-buildings` or `creating-dcl-furnishings`.

## How to ask

- One question per message. Prefer 2–4 concrete options with a recommendation first ("A (recommended): …"), plus "or something else".
- Skip anything the idea or the person has already answered. Don't ask what you can decide with a sensible default; state the default instead.
- When the idea or an answer runs into a platform rule, say so at once, one line each with the alternative (see "Constraints to raise early"). Several of these can go in one message; they're statements, not questions.
- If a conflict changes the whole design (an IP character, a pet or vehicle), make settling it your first question. Otherwise go in the order below.
- Ask for reference images whenever looks are being described in words; one picture settles ten questions.
- Stop when the brief can be written. Usually 5–10 questions; a set of items shares most answers.

## Questions, in order

**1. What and why**
- Wearable, emote, a scene piece (building, furniture, decor), or a set?
- Whose release is it: the person's own collection, a client's, an event giveaway? (A client means their taste rules and you'll want their approval at each draft.)
- The one-line concept, plus any references (images, existing items, a mood).

**2. Wearable specifics**
- Slot (category), and what it hides or replaces. This sets the triangle budget: an item that hides a slot adds that slot's budget.
- Both body shapes, or one? (Default both; a single shape needs a reason.)
- Silhouette and fit: snug or loose, length, and anything at hip or hand height. The female idle rests her hands at her thighs, so wide hips and skirts collide.
- Moving parts: straps, tails, hair or chains that should swing (spring bones: up to 6 chains and 12 bones). Should they trail behind at speed or stay with the body?
- Surface: palette, finish (matte, shiny, worn), logos, text or decals, glow. The toon shader is flat and darker than Blender, and there's no bloom.
- Does the player's skin, hair or eye colour need to show through or tint it?

**3. Emote specifics**
- The beat-by-beat action, start to end. Length ≤10 s.
- Play once or loop? (Props freeze when an emote stops, so anything held "the whole time" needs a loop.)
- Props: what, held or free, and does any prop replace a body part (a head swap)?
- Travel: the hips stay within 1 m sideways, everything inside a 4×4 m box and ≤4 m high.
- Sound? It must be original, the same length as the emote, and fits in the 3 MB total.
- Category (dance, stunt, greetings, fun, poses, reactions, horror, miscellaneous) and the feeling (chill, hype, creepy, comedic).

**4. Scene piece specifics** (buildings, furniture, decor: static models placed in a scene, not worn or sold)
- Building: footprint in parcels (0.5×0.5, 1×1, 1×2, 2×2, 4×4; one parcel is 16 m square), floors, rooms, where the
  entrance is. Visitors walk in, so doorways, stairs and upper floors need colliders.
- Furnished? Furniture is separate pieces (each its own model, placeable on its own), designed with the building.
  List them: what, how many, rough sizes.
- Seating: which pieces people sit on, and how many seats each. Sitting works through the `dcl-sittables` kit.
- Behaviour beyond sitting (doors that open, lamps that switch, a jukebox): say it's not modelled in; the model is
  built ready for a kit (a door leaf as its own piece).
- Style and palette, with references. Scene pieces are low-poly: soft, chunky shapes, one colour palette.
- Where it goes: the scene's size, so the building's share of its triangle budget makes sense.

Scene pieces skip section 5's release questions (no rarity, Marketplace name or thumbnail rules) unless they'll be
sold as something else.

**5. Release**
- Item name (≤32 characters) and a one-line description (≤64).
- Rarity and supply (unique 1 … common 100,000; fixed after publishing).
- Thumbnail: the item alone on a transparent background; any logo kept small in a corner, bottom right preferred.
- Deadline, and what "done" means (a draft to show, or submitted to curation).

## Constraints to raise early

| If the idea… | Say | Offer |
|---|---|---|
| poses the arms on an upper_body (holding something) | Curation rejects posed arms | Make the prop its own accessory worn on the body: rigged to the spine or hips but filed in a free accessory slot (earring, tiara or top_head, 500 triangles), or make it an emote |
| is a held object as hands_wear (sword, shield) | Curation rejects held objects as hands_wear | An emote with the prop, or worn on the body |
| copies a real character, brand or logo | Sold items get rejected or taken down for IP | An original parody or homage |
| is a pet or vehicle | Wearables must be humanoid | An emote with a prop (riding, walking it) |
| runs over 10 s, or travels far | Hard limits | A tighter beat sheet, or a loop |
| wants a prop in hand from start to finish | Props freeze when the emote stops | Loop it, and end where it starts |
| wants the real head to come off | The neck skin can't detach | Collapse the neck and swap in a prop head |
| needs lots of detail in one slot | 2 materials, 2 textures, tight triangle budgets | Hide another slot to pool budgets, or split it into two items |
| bakes furniture into a building | It can't be moved, sat on or reused, and spends the building's budget | Separate furniture pieces, designed together |
| wants a door that opens or a working lamp | Scene models are static; behaviour comes from kits | A door leaf modelled as its own piece, ready for a kit |
| is bigger than a 4×4 footprint | Studio footprints stop at 4×4 parcels | Split it into buildings, or a 4×4 core |

## The brief

Write `BRIEF.md` in the project folder, then ask the person to confirm or correct it before building:

```markdown
# <Item name> — brief
Type: wearable (<category>, hides …) | emote (<category>, loop/once, ~N s) | building (<footprint>, N floors) | furniture/decor (<type>, seats N)
For: <own collection | client: name> · Rarity/supply: … · Deadline: …
Concept: <2–3 sentences>
References: <links/files>
Look: palette, finish, decals/logos, glow, what tints with the player
Fit / motion: <silhouette, both body shapes, spring parts and how they move> | <beat sheet with timings, props, start/end pose, travel> | <rooms, entrance, stairs; furniture pieces and seats>
Constraints raised: <each rule that shaped the design, and the choice made>
Open questions: <anything to settle at the first draft>
Done means: <draft renders | Builder upload | curation submission>
```

Once it's confirmed, start the build skill.
