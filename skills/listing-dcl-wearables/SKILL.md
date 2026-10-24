---
name: listing-dcl-wearables
description: Use when built Decentraland wearables are being uploaded to the Builder or listed in a collection - choosing each piece's rarity and supply, writing item names, descriptions and utility text, picking Marketplace tags, naming the collection, or filling in the Builder's item fields.
---

# Listing Decentraland Wearables

## Overview

Turn finished wearables into a complete Builder listing: one rarity per piece, plus a name, description, utility line and tags written for the Marketplace. Then upload and fill in every field. These words are what buyers search and read, and some choices are permanent once the collection is published (collection name, item count, rarity), so settle them with the person first. Never invent them silently.

Keep it all in a `listing.json` in the project, check it with `python3 <skill-dir>/scripts/check_listing.py listing.json --sheet` (`<skill-dir>` is this SKILL.md's folder), and enter the fields from the sheet that prints.

Upload only items that have passed review (`curating-dcl-wearables`). Publishing, pricing and paying are the person's decisions.

## 1. Rarity, piece by piece

Ask one question at a time, with a recommendation. Start with the plan for the whole collection:
- **Sell, give away, or both?** How many people should be able to own each piece (a giveaway list sets a minimum supply)?
- **Which piece is the hero?** The standout piece usually gets a rarer tier than the basics in the same set.

| Rarity | Max supply | Fits |
|---|---|---|
| unique | 1 | a one-off, commissioned or auction piece |
| mythic | 10 | a tiny drop for collectors |
| exotic | 50 | a limited hero piece |
| legendary | 100 | limited drops, small events |
| epic | 1,000 | a solid default for a creator's set |
| rare | 5,000 | broad sales |
| uncommon | 10,000 | mass giveaways, events |
| common | 100,000 | very wide giveaways |

Say this up front: rarity is permanent once published, the listing fee is per item whatever the rarity, and supply is a cap (it can mint fewer). Then confirm each piece: "Pants: epic (1,000)? Jacket: legendary (100) as the hero?"

## 2. Names

- ≤32 characters, no `:`. The collection name is ≤32 too and can't change after publishing.
- In a set, use one pattern: `<Set> <Piece>` ("Techwear Strap Pants"). Each name must be unique in the collection.
- Say what it is: a buyer searching "jacket" should find the jacket.
- No real brands, characters or other IP. Parody names should read as original.
- Offer 2–3 options per piece and let the person pick.

## 3. Description (≤64 characters, no `:`)

It shows in the Marketplace and the Backpack. Use it for what the name doesn't already say: material, the detail that moves or glows, the attitude. Don't repeat the name, don't promise effects the item doesn't have, and don't use IP names.
- "Matte black cargo pants rigged with straps that swing" (52)
- "A toy revolver that only ever fires one thing, a flag" (53)

Write 2–3 options per piece in the set's voice, show the character count, and let the person choose or edit.

## 4. Utility (≤64 characters, optional)

The Builder's prompt is "Describe the in-world utility of the Wearable". Fill it in **only when the item really does something**, such as:
- a smart wearable's effect;
- access the person controls (a scene that recognizes the item, a members' area, an event perk);
- an in-game role in their own experience.

Ask what it unlocks and where, then write it concretely: "Opens the members-only lounge in the Night Market scene". Leave it **empty** for a cosmetic item. A made-up perk misleads buyers and invites rejection. If the utility is a secret, keep the line a teaser, not instructions.

## 5. Tags (≤20; single words; no `#`)

A space or comma ends a tag in the Builder, so each tag is **one word**; join multi-word ideas (`streetwear`, `scifi`). Keep them lowercase and relevant, aiming for 8–15, built from:
- **What it is:** the category and synonyms (`pants`, `trousers`, `cargo`).
- **Style and theme:** `techwear`, `cyberpunk`, `goth`, `clown`, `horror`.
- **Colour and material:** `black`, `leather`, `denim`, `neon`.
- **The set or collection name**, so every piece shows up together.
- **Notable features:** `straps`, `glow`, `animated` (if spring bones swing).
- **Season or event,** only if the person is entering it. The Builder shows an official event tag when one is running; use that exact tag.

Avoid brand names and IP (the same rejection risk as in names) and anything that isn't true of the item.

## 6. Upload and fill in (decentraland.org/builder)

The person signs in with their wallet. Drive the browser if you can; otherwise give them the sheet and walk them through it.
1. **Collections → New collection** (name from the listing), or open the existing one.
2. Per item: **New item → Single item**, upload the first body shape's GLB. Enter the name, rarity, category and body shape from the sheet, then save.
3. In the item editor:
   - **… → Add male/female representation** for the other GLB.
   - Right panel: description, utility, tags (type each, press Enter), Overrides (hides/replaces from the build's hand-off sheet), VRM export permission, outline.
   - Spring bones, for both body shapes.
   - Custom thumbnail via the camera icon, if there is one.
4. Click each item in the left list and check its id before editing: loading an editor URL doesn't change the selected item. Re-uploading a GLB resets its spring-bone settings.
5. Price: ask, then set it or **Make it free**. Check that each item shows **Ready to submit**.
6. Read back every field against the sheet (character counts, tags, rarity) and show the person the collection page before they publish.

Record anything that changed during upload in `listing.json` so the file stays the source of truth.
