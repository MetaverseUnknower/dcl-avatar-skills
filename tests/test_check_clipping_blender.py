"""check_clipping.py inside Blender on small built items: items with no rig, Blender 4.x's bone-shape mesh, and meshes
the creator kept from the base body.

Needs Blender (BLENDER, `blender` on PATH, or the macOS app), DCL_AVATAR_DIR (the folder with AvatarShape_A.blend), and
the animations from fetch_dcl_animations.py (DCL_ANIMS or ~/.cache/dcl-animations). The Blender 4.x test also needs
BLENDER4 or /Applications/Blender 4.4.app. Skipped when any is missing.
"""
import json
import os
import shutil
import subprocess

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS = os.path.join(os.path.dirname(HERE), 'skills')
CHECKER = os.path.join(SKILLS, 'curating-dcl-wearables', 'scripts', 'check_clipping.py')
WEARLIB = os.path.join(SKILLS, 'creating-dcl-wearables', 'scripts')
MAC_BLENDER = '/Applications/Blender.app/Contents/MacOS/Blender'
MAC_BLENDER4 = '/Applications/Blender 4.4.app/Contents/MacOS/Blender'
BLENDER = os.environ.get('BLENDER') or shutil.which('blender') or (MAC_BLENDER if os.path.exists(MAC_BLENDER) else None)
BLENDER4 = os.environ.get('BLENDER4') or (MAC_BLENDER4 if os.path.exists(MAC_BLENDER4) else None)
AVATAR = os.path.join(os.environ.get('DCL_AVATAR_DIR', ''), 'AvatarShape_A.blend')
ANIMS = os.environ.get('DCL_ANIMS') or os.path.expanduser('~/.cache/dcl-animations')
# Idle (gated), an unskinned emote-wheel file (needs the bind pose) and a skinned emote (carries one)
CLIPS = ('Idle.anim', 'clap.glb', 'Get_Hit.glb')

needs = pytest.mark.skipif(
    not BLENDER or not os.path.exists(AVATAR) or not all(os.path.exists(os.path.join(ANIMS, c)) for c in CLIPS),
    reason='needs Blender, DCL_AVATAR_DIR with AvatarShape_A.blend, and the DCL animations')


@pytest.fixture(scope='module')
def built(tmp_path_factory):
    d = tmp_path_factory.mktemp('clip')
    items, anims = d / 'items', d / 'anims'
    items.mkdir()
    anims.mkdir()
    for c in CLIPS:
        shutil.copy(os.path.join(ANIMS, c), anims / c)
    p = subprocess.run([BLENDER, '-b', AVATAR, '--python-exit-code', '1', '--python',
                        os.path.join(HERE, 'blender', 'clip_items.py'), '--', str(items), WEARLIB],
                       capture_output=True, text=True, timeout=300)
    assert 'CLIP_ITEMS DONE' in p.stdout, p.stdout[-2000:] + p.stderr[-2000:]
    return items, anims


def check(blender, built, item, category, tmp_path):
    items, anims = built
    report = tmp_path / 'report.json'
    p = subprocess.run([blender, '-b', AVATAR, '--python', CHECKER, '--', '--glb', str(items / item),
                        '--category', category, '--anims', str(anims), '--gate', 'Idle', '--json', str(report)],
                       capture_output=True, text=True, timeout=600)
    out = p.stdout + p.stderr
    assert 'Traceback' not in out, out[-3000:]
    return p.returncode, out, json.loads(report.read_text())


def labels(report):
    out = set(report['rest'])
    for c in report['clips'].values():
        for f in c['clipping']:
            out |= set(f['hits'])
    return out


@needs
def test_an_item_with_no_rig_is_checked(built, tmp_path):
    code, out, report = check(BLENDER, built, 'rigid.glb', 'top_head', tmp_path)
    assert code == 0, out[-3000:]
    assert 'CLIP GATE PASS' in out
    assert 'clap' in report['clips']        # the unskinned emote still gets its bind pose


@needs
@pytest.mark.skipif(not BLENDER4, reason='needs Blender 4.x (BLENDER4)')
def test_blender4_bone_shapes_are_not_part_of_the_item(built, tmp_path):
    code, out, report = check(BLENDER4, built, 'skinned.glb', 'hat', tmp_path)
    assert not [lb for lb in labels(report) if 'Icosphere' in lb], sorted(labels(report))
    assert code == 0, out[-3000:]


@needs
def test_a_mesh_kept_from_the_base_body_is_not_checked_against_the_body(built, tmp_path):
    code, out, report = check(BLENDER, built, 'bodycopy.glb', 'hat', tmp_path)
    body = {'ubody', 'lbody', 'feet', 'hands', 'head'}
    against_body = [lb for lb in labels(report)
                    if lb.startswith('M_lBody_BaseMesh x ') and lb.split(' x ')[1].split(' (')[0] in body]
    assert not against_body, sorted(labels(report))
    assert code == 0, out[-3000:]


@needs
def test_a_garment_named_like_a_body_mesh_is_still_checked_against_the_body(built, tmp_path):
    # creators leave body names on garments (pants, shirts, a whole skin's outfit): only skin material is body
    code, out, report = check(BLENDER, built, 'garment.glb', 'hat', tmp_path)
    assert [lb for lb in labels(report) if lb.startswith('M_uBody_BaseMesh x ubody')], sorted(labels(report))
