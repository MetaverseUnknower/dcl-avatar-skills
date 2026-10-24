#!/usr/bin/env python3
"""Download Decentraland's real avatar animations from decentraland/unity-explorer: the Idle/Walk/Jog/Run locomotion
clips (Unity .anim) and the built-in emotes (.anim and .glb). check_clipping.py poses the avatar with them.

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


def url(path):
    # .glb files are Git LFS objects: the raw URL would return the pointer, the media URL returns the file
    host = 'media.githubusercontent.com/media' if path.endswith('.glb') else 'raw.githubusercontent.com'
    return f'https://{host}/{REPO}/{REF}/{path}'


def main():
    out = os.path.expanduser(sys.argv[1] if len(sys.argv) > 1 else '~/.cache/dcl-animations')
    os.makedirs(out, exist_ok=True)
    for path in FILES:
        dest = os.path.join(out, os.path.basename(path))
        if os.path.exists(dest) and os.path.getsize(dest) > 1000:
            continue
        try:
            data = urllib.request.urlopen(url(path), timeout=120).read()
        except Exception as e:
            print(f'skip {path}: {e}')
            continue
        if data.startswith(b'version https://git-lfs'):
            print(f'skip {path}: got an LFS pointer, not the file')
            continue
        open(dest, 'wb').write(data)
        print(f'{dest} ({len(data) // 1024} KB)')
    print(out)


if __name__ == '__main__':
    main()
