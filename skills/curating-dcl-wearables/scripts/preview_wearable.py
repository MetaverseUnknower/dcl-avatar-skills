#!/usr/bin/env python3
"""Render local wearable GLBs on the real Decentraland avatar, in the hosted wearable-preview (Unity renderer, the one
the Builder and the explorer use), before anything is uploaded. Screenshots each body shape x animation.

usage:
  python3 preview_wearable.py --category upper_body --male coat_male.glb --female coat_female.glb --out previews/coat \
      [--hides lower_body] [--anims idle,walk,run] [--skin 8d5524] [--hair 2b1b0f] [--frames 4] [--size 640] [--show]

Writes <out>_<female|male>_<anim>_<n>.png and <out>_console.log. Animations are the preview's built-in ones: idle,
walk, run, jump, clap, dab, dance, fashion, fashion-2, fashion-3, fashion-4, love, money, fist-pump, head-explode,
wave. Needs Google Chrome and `pip install playwright` (uses the installed Chrome channel, WebGPU on).
"""
import argparse, asyncio, base64, json, os, sys

MALE = 'urn:decentraland:off-chain:base-avatars:BaseMale'
FEMALE = 'urn:decentraland:off-chain:base-avatars:BaseFemale'
PAGE = 'https://wearable-preview.decentraland.org/'

# Builds the item the way the Builder hands one to the preview: GLBs as in-page blob URLs inside a base64 item.
JS = """([files, item]) => {
  const reps = item.representations.map(r => {
    const bin = Uint8Array.from(atob(files[r.mainFile]), c => c.charCodeAt(0));
    const url = URL.createObjectURL(new Blob([bin], {type: 'model/gltf-binary'}));
    return {bodyShapes: r.bodyShapes, mainFile: r.mainFile, contents: [{key: r.mainFile, url}],
            overrideHides: [], overrideReplaces: []};
  });
  const def = {id: 'urn:decentraland:off-chain:local-preview:' + item.name.toLowerCase().replace(/[^a-z0-9]+/g, '-'),
    name: item.name, description: '', i18n: [{code: 'en', text: item.name}], thumbnail: '', image: '',
    rarity: 'epic', data: {category: item.category, hides: item.hides, replaces: [], tags: [], representations: reps,
            removesDefaultHiding: item.removesDefaultHiding}};
  window.postMessage({type: 'update', payload: {options: {base64s: [btoa(JSON.stringify(def))]}}}, '*');
}"""


async def shoot(pw, args, shape, anim, files, item):
    br = await pw.chromium.launch(channel='chrome', headless=not args.show,
                                  args=['--enable-unsafe-webgpu', '--enable-features=Vulkan,WebGPU', '--use-angle=metal'])
    pg = await br.new_page(viewport={'width': args.size, 'height': args.size})
    log = open(args.out + '_console.log', 'a')
    pg.on('console', lambda m: log.write(f'[{shape} {anim}] {m.type} {m.text[:400]}\n'))
    q = f'?unity=true&mode=builder&profile=default&disableAutoRotate=true&bodyShape={MALE if shape == "male" else FEMALE}&emote={anim}'
    if args.skin:
        q += f'&skin={args.skin}'
    if args.hair:
        q += f'&hair={args.hair}'
    await pg.goto(PAGE + q)
    await pg.wait_for_timeout(args.boot * 1000)
    await pg.evaluate(JS, [files, item])
    await pg.wait_for_timeout(args.settle * 1000)
    out = []
    for i in range(args.frames):
        p = f'{args.out}_{shape}_{anim}_{i}.png'
        await pg.screenshot(path=p)
        out.append(p)
        await pg.wait_for_timeout(int(args.gap * 1000))
    await br.close()
    return out


async def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--category', required=True)
    ap.add_argument('--male')
    ap.add_argument('--female')
    ap.add_argument('--unisex')
    ap.add_argument('--hides', default='')
    ap.add_argument('--anims', default='idle,walk,run')
    ap.add_argument('--skin')
    ap.add_argument('--hair')
    ap.add_argument('--out', required=True)
    ap.add_argument('--frames', type=int, default=4)
    ap.add_argument('--gap', type=float, default=0.35, help='seconds between frames')
    ap.add_argument('--size', type=int, default=640)
    ap.add_argument('--boot', type=int, default=25, help='seconds for the Unity player to start')
    ap.add_argument('--settle', type=int, default=12, help='seconds for the item to load')
    ap.add_argument('--raw-hiding', action='store_true', help="don't mirror the Builder's removesDefaultHiding=['hands'] on upper_body")
    ap.add_argument('--show', action='store_true', help='visible browser window (if headless renders blank)')
    args = ap.parse_args()
    from playwright.async_api import async_playwright

    files, reps = {}, []
    for path, shapes in ((args.unisex, [MALE, FEMALE]), (args.male, [MALE]), (args.female, [FEMALE])):
        if path:
            key = os.path.basename(path)
            files[key] = base64.b64encode(open(path, 'rb').read()).decode()
            reps.append({'bodyShapes': shapes, 'mainFile': key})
    if not reps:
        sys.exit('give --male/--female or --unisex')
    item = {'name': os.path.basename(args.out), 'category': args.category,
            'hides': [h for h in args.hides.split(',') if h], 'representations': reps,
            # The Builder sets this on new upper_body items so the base hands still show.
            'removesDefaultHiding': [] if args.raw_hiding or args.category != 'upper_body' else ['hands']}
    shapes = [s for s, p in (('female', args.female or args.unisex), ('male', args.male or args.unisex)) if p]
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    open(args.out + '_console.log', 'w').close()
    async with async_playwright() as pw:
        for shape in shapes:
            for anim in [a for a in args.anims.split(',') if a]:
                for p in await shoot(pw, args, shape, anim, files, item):
                    print(p)
    errors = [l for l in open(args.out + '_console.log') if ' error ' in l.lower()]
    if errors:
        print(f'{len(errors)} console errors, see {args.out}_console.log')


if __name__ == '__main__':
    asyncio.run(main())
