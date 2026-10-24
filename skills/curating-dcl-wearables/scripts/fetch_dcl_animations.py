#!/usr/bin/env python3
"""Download Decentraland's real avatar animations for check_clipping.py:
  - decentraland/unity-explorer: Idle/Walk/Jog/Run locomotion (Unity .anim) and the explorer's built-in emotes;
  - decentraland/wearable-preview: the emote-wheel emotes the Builder and Marketplace previews play (dance, clap, dab,
    wave, money, love, fashion, fist-pump, head-explode, jump) and the per-category showcase animations shoppers see
    (saved as showcase_<name>.glb).

usage: python3 fetch_dcl_animations.py [out_dir]      (default ~/.cache/dcl-animations; skips files already there)
"""
import os, sys, urllib.request

REPO = 'decentraland/unity-explorer'
REF = 'main'
LOCO = 'Explorer/Assets/DCL/AvatarRendering/AvatarShape/Assets/Animations/'
EMOTES = 'Explorer/Assets/DCL/AvatarRendering/Emotes/EmbeddedEmotes/CommonEmotes/'
FILES = [LOCO + n for n in ('Idle.anim', 'Walk.anim', 'Jog.anim', 'Run.anim')] + [EMOTES + n for n in (
    'Waving/Waving.anim', 'Victory/Victory.anim', 'HandsAir/handsair.anim', 'FistPumpSimple/fistpump_short.anim',
    'Crafting/crafting.anim', 'PointForward.glb', 'Punch/Punch.glb', 'Push/Push.glb', 'Throw/Throw.glb',
    'GetHit/Get_Hit.glb', 'KnockOut/KO.glb', 'OpenDoor/OpenDoor.glb', 'Lever/Lever.glb', 'OpenChest/OpenChest.glb',
    'SwingWeaponOneHand/Swing_OneHand.glb', 'SwingWeaponTwoHands/Swing_DoubleHanded.glb',
    'SittingChair1/SittingChair_v01.glb', 'SittingGround1/SittingGround_v01.glb')]
PREVIEW = 'decentraland/wearable-preview'
WHEEL = ['clap', 'dab', 'dance', 'fashion', 'fashion-2', 'fashion-3', 'fashion-4', 'fist-pump', 'head-explode',
         'jump', 'love', 'money', 'wave']
SHOWCASE = ['Accessories_v01', 'Accessories_v02', 'Accessories_v03', 'Outfit_Hand_v01', 'Outfit_Hand_v02',
            'Outfit_Lower_v01', 'Outfit_Lower_v02', 'Outfit_Lower_v03', 'Outfit_Shoes_v01', 'Outfit_Shoes_v02',
            'Outfit_Upper_v01', 'Outfit_Upper_v02', 'Outfit_Upper_v03', 'Wave_Female', 'Wave_Male']


def preview_url(path):
    return f'https://raw.githubusercontent.com/{PREVIEW}/master/public/emotes/{path}'


def url(path):
    # .glb files are Git LFS objects: the raw URL would return the pointer, the media URL returns the file
    host = 'media.githubusercontent.com/media' if path.endswith('.glb') else 'raw.githubusercontent.com'
    return f'https://{host}/{REPO}/{REF}/{path}'


def main():
    out = os.path.expanduser(sys.argv[1] if len(sys.argv) > 1 else '~/.cache/dcl-animations')
    os.makedirs(out, exist_ok=True)
    jobs = [(url(p), os.path.basename(p)) for p in FILES]
    jobs += [(preview_url(f'{n}.glb'), f'{n}.glb') for n in WHEEL]
    jobs += [(preview_url(f'character/{n}.glb'), f'showcase_{n}.glb') for n in SHOWCASE]
    for src, name in jobs:
        dest = os.path.join(out, name)
        path = src
        if os.path.exists(dest) and os.path.getsize(dest) > 1000:
            continue
        try:
            data = urllib.request.urlopen(src, timeout=120).read()
        except Exception as e:
            print(f'skip {path}: {e}')
            continue
        if data.startswith(b'version https://git-lfs') or not (data[:4] == b'glTF' or name.endswith('.anim')):
            print(f'skip {path}: not an animation file (LFS pointer or missing)')
            continue
        open(dest, 'wb').write(data)
        print(f'{dest} ({len(data) // 1024} KB)')
    print(out)


if __name__ == '__main__':
    main()
