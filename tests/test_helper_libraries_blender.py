"""Runs the helper libraries' self-tests (tests/blender/*_selftest.py) inside Blender on each official avatar .blend.

Needs Blender (BLENDER, `blender` on PATH, or the macOS app) and the official avatar files: set DCL_AVATAR_DIR to the
folder holding AvatarShape_A.blend and AvatarShape_B.blend (from the Decentraland docs). Skipped when either is missing.
"""
import os
import shutil
import subprocess

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS = os.path.join(os.path.dirname(HERE), 'skills')
SUITES = {
    'emotelib': (os.path.join(HERE, 'blender', 'emotelib_selftest.py'), os.path.join(SKILLS, 'creating-dcl-emotes', 'scripts')),
    'wearlib': (os.path.join(HERE, 'blender', 'wearlib_selftest.py'), os.path.join(SKILLS, 'creating-dcl-wearables', 'scripts')),
}
MAC_BLENDER = '/Applications/Blender.app/Contents/MacOS/Blender'
BLENDER = os.environ.get('BLENDER') or shutil.which('blender') or (MAC_BLENDER if os.path.exists(MAC_BLENDER) else None)
AVATAR_DIR = os.environ.get('DCL_AVATAR_DIR')


@pytest.mark.parametrize('suite', sorted(SUITES))
@pytest.mark.parametrize('shape', ['A', 'B'])
def test_helper_library_selftest(suite, shape, tmp_path):
    if not BLENDER:
        pytest.skip('Blender not found (set BLENDER)')
    avatar = os.path.join(AVATAR_DIR or '', f'AvatarShape_{shape}.blend')
    if not AVATAR_DIR or not os.path.exists(avatar):
        pytest.skip('set DCL_AVATAR_DIR to the folder with AvatarShape_A.blend and AvatarShape_B.blend')
    selftest, scripts = SUITES[suite]
    proc = subprocess.run([BLENDER, '-b', avatar, '--python-exit-code', '1', '--python', selftest, '--',
                           str(tmp_path), scripts, shape], capture_output=True, text=True, timeout=600)
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith('SELFTEST')]
    assert 'SELFTEST RESULT PASS' in proc.stdout, '\n'.join(lines) + '\n' + proc.stderr[-2000:]
