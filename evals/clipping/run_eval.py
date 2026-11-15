#!/usr/bin/env python3
"""Run probe.py (check_clipping.py + candidate renders) over the whole corpus, both body shapes, in parallel.

usage: python3 run_eval.py [--corpus ~/.cache/dcl-clip-eval/corpus] [--run NAME] [--blender PATH] [-j 4]
                           [--avatars DIR] [--items slug,slug] [--force] [-- extra probe.py args]

Results go to ~/.cache/dcl-clip-eval/runs/<run>/<slug>/<shape>/ (run defaults to blender-<version>). Finished
item/shape pairs are skipped unless --force, so an interrupted run picks up where it stopped. Run it once per
Blender version to see how much the importer changes the verdicts.
"""
import argparse, concurrent.futures as cf, json, os, re, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.expanduser('~/.cache/dcl-clip-eval')
AVATAR = {'female': 'AvatarShape_A.blend', 'male': 'AvatarShape_B.blend'}
GUESS_AVATARS = ['~/-Decentraland', '~/Documents/Virvi/studio-worker-assets']


def find_blender(path):
    for c in [path, os.environ.get('BLENDER'), shutil.which('blender'), '/Applications/Blender.app/Contents/MacOS/Blender']:
        if c and os.path.exists(c):
            return c
    sys.exit('Blender not found: pass --blender or set BLENDER')


def find_avatars(path):
    for d in [path, os.environ.get('DCL_AVATAR_DIR')] + GUESS_AVATARS:
        if d and all(os.path.exists(os.path.join(os.path.expanduser(d), f)) for f in AVATAR.values()):
            return os.path.expanduser(d)
    sys.exit('AvatarShape_A.blend / AvatarShape_B.blend not found: pass --avatars or set DCL_AVATAR_DIR')


def main():
    argv = sys.argv[1:]
    extra = argv[argv.index('--') + 1:] if '--' in argv else []
    argv = argv[:argv.index('--')] if '--' in argv else argv
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--corpus', default=os.path.join(ROOT, 'corpus'))
    ap.add_argument('--run')
    ap.add_argument('--blender')
    ap.add_argument('--avatars')
    ap.add_argument('-j', type=int, default=max(1, (os.cpu_count() or 4) // 2))
    ap.add_argument('--items', default='')
    ap.add_argument('--force', action='store_true')
    A = ap.parse_args(argv)
    blender, avatars = find_blender(A.blender), find_avatars(A.avatars)
    ver = re.search(r'Blender (\S+)', subprocess.run([blender, '--version'], capture_output=True, text=True).stdout)
    run = A.run or f'blender-{ver.group(1) if ver else "unknown"}'
    out_root = os.path.join(ROOT, 'runs', run)
    manifest = json.load(open(os.path.join(A.corpus, 'manifest.json')))['items']
    only = set(filter(None, A.items.split(',')))
    jobs = [(slug, shape) for slug, it in sorted(manifest.items()) if not only or slug in only for shape in it['shapes']]
    todo = [j for j in jobs if A.force or not os.path.exists(os.path.join(out_root, j[0], j[1], 'candidates.json'))]
    print(f'{run}: {len(jobs)} item/shape pairs, {len(todo)} to do, {A.j} at a time ({blender})')

    def one(job):
        slug, shape = job
        out = os.path.join(out_root, slug, shape)
        os.makedirs(out, exist_ok=True)
        cmd = [blender, '-b', os.path.join(avatars, AVATAR[shape]), '--python-exit-code', '1',
               '--python', os.path.join(HERE, 'probe.py'), '--',
               '--item', os.path.join(A.corpus, slug), '--shape', shape, '--out', out] + extra
        t = time.time()
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        open(os.path.join(out, 'blender.log'), 'w').write(p.stdout + '\n--- stderr ---\n' + p.stderr)
        line = next((ln for ln in p.stdout.splitlines() if ln.startswith('PROBE')), None)
        return job, p.returncode, line or (p.stderr.strip().splitlines() or ['?'])[-1], time.time() - t

    fails = []
    with cf.ThreadPoolExecutor(A.j) as ex:
        for k, ((slug, shape), rc, line, dt) in enumerate(ex.map(one, todo), 1):
            print(f'[{k}/{len(todo)}] {dt:5.0f}s {slug} {shape}: {line}', flush=True)
            if rc or not line.startswith('PROBE'):
                fails.append(f'{slug}/{shape}')
    json.dump({'run': run, 'blender': blender, 'avatars': avatars, 'corpus': os.path.abspath(A.corpus),
               'probe_args': extra}, open(os.path.join(out_root, 'run.json'), 'w'), indent=1)
    print(f'done: {out_root}' + (f'; failed: {", ".join(fails)} (see blender.log)' if fails else ''))
    print(f'next: python3 {os.path.join(HERE, "review.py")} {out_root}')


if __name__ == '__main__':
    main()
