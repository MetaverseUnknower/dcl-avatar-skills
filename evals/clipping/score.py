#!/usr/bin/env python3
"""Score check_clipping.py against the labels: false positives, misses, gate verdicts, the best --depth.

usage: python3 score.py ~/.cache/dcl-clip-eval/runs/<run> [--labels ~/.cache/dcl-clip-eval/labels.json]
                        [--compare ~/.cache/dcl-clip-eval/runs/<other run>]

Writes <run>/report.md and prints it. The first section needs no labels: how often published (curated) items fail
the gate the skill prescribes, which clips and which overlap kinds cause it. Everything after uses labels.json from
review.py. Label meanings: clip = visible clip that is the item's fault; clean = nothing visible; anim = the
animation itself clips (the bare avatar would too); unsure = left out of every rate.
"""
import argparse, collections, glob, json, os

ROOT = os.path.expanduser('~/.cache/dcl-clip-eval')
POS = ('pos-deep', 'pos-shallow')
BINS = [(0.3, 0.5), (0.5, 1), (1, 2), (2, 5), (5, 1e9)]


def load(run):
    out = {}
    for p in sorted(glob.glob(os.path.join(run, '*', '*', 'candidates.json'))):
        s = json.load(open(p))
        out[(s['item']['slug'], s['shape'])] = s
    return out


def pct(a, b):
    return f'{100 * a / b:.0f}% ({a}/{b})' if b else '–'


def table(head, rows):
    out = ['| ' + ' | '.join(head) + ' |', '|' + '---|' * len(head)]
    out += ['| ' + ' | '.join(str(x) for x in r) + ' |' for r in rows]
    return '\n'.join(out)


def binname(d):
    for lo, hi in BINS:
        if lo < d <= hi:
            return f'{lo}–{hi:g} cm' if hi < 1e9 else f'> {lo} cm'
    return f'≤ {BINS[0][0]} cm'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('run')
    ap.add_argument('--labels', default=os.path.join(ROOT, 'labels.json'))
    ap.add_argument('--compare')
    A = ap.parse_args()
    run = os.path.expanduser(A.run)
    S = load(run)
    L = json.load(open(A.labels)) if os.path.exists(A.labels) else {}
    md = [f'# Clipping eval: {os.path.basename(run.rstrip("/"))}', '']
    if not S:
        print('no results in', run)
        return
    any_s = next(iter(S.values()))
    md += [f'{len(S)} item/shape pairs from {len({k[0] for k in S})} Marketplace items · Blender {any_s["blender"]} · '
           f'checker {any_s.get("checker_rev") or "?"} · --depth {any_s["depth_cm"]} cm', '']

    # ---- no labels needed ----
    md += ['## Gate verdicts on published items (no labels needed)', '',
           'Every item here passed curation, so a FAIL is either clipping that slipped past the curators or a false '
           'positive. The labelled sections below tell those apart.', '']
    by_cat = collections.defaultdict(lambda: [0, 0])
    clip_fails, kind_fails = collections.Counter(), collections.Counter()
    for (slug, shape), s in S.items():
        by_cat[s['item']['category']][0] += s['gate_result'] == 'FAIL'
        by_cat[s['item']['category']][1] += 1
        for c in s['failed_clips']:
            clip_fails[c] += 1
        pairs = {c['pair'] for c in s['candidates'] if c['kind'] in POS and c['gated']}
        for p in pairs:
            kind_fails[p] += 1
    total_fail = sum(v[0] for v in by_cat.values())
    md += [f'**{pct(total_fail, len(S))} of item/shape pairs FAIL the gate.**', '',
           table(['category', 'FAIL'], [(k, pct(*v)) for k, v in sorted(by_cat.items())]), '',
           table(['gated clip', 'pairs failing it'], clip_fails.most_common()), '',
           table(['overlap kind in gated clips', 'pairs'], [('item vs body' if k == 'body' else 'item vs itself', v)
                                                            for k, v in kind_fails.most_common()]), '']

    cands = [c | {'_key': k} for k, s in S.items() for c in s['candidates']]
    lab = lambda c: (L.get(c['id']) or {}).get('v')
    labeled = [c for c in cands if lab(c) and lab(c) != 'unsure']
    md += ['## Labels', '', f'{len([c for c in cands if lab(c)])} of {len(cands)} candidates labelled '
           f'({len([c for c in cands if lab(c) == "unsure"])} unsure).', '']
    if not labeled:
        md += ['_Label some frames with review.py, then run this again._']
    else:
        # ---- false positives ----
        pos = [c for c in labeled if c['kind'] in POS]
        def prec_rows(key):
            g = collections.defaultdict(collections.Counter)
            for c in pos:
                g[key(c)][lab(c)] += 1
            return [(k, pct(v['clip'], sum(v.values())), v['clean'], v['anim']) for k, v in sorted(g.items())]
        cnt = collections.Counter(lab(c) for c in pos)
        md += ['### When the detector says clip (false positives)', '',
               f'**Precision: {pct(cnt["clip"], len(pos))}.** False positives: {cnt["clean"]} clean, '
               f'{cnt["anim"]} the animation\'s fault.', '']
        H = ['', 'real clips', 'clean', "animation's fault"]
        for title, key in (('by kind', lambda c: c['kind']), ('by overlap', lambda c: 'item vs ' + ('body' if c['pair'] == 'body' else 'itself')),
                           ('by depth', lambda c: binname(c['depth_cm'])), ('by clip type', lambda c: 'gated' if c['gated'] else 'reported'),
                           ('by category', lambda c: c['category'] if 'category' in c else S[c['_key']]['item']['category'])):
            md += [f'**{title}**', '', table([title.split()[-1]] + H[1:], prec_rows(key)), '']
        fps = [c for c in pos if lab(c) in ('clean', 'anim')]
        if fps:
            md += ['False positives, deepest first:', '']
            md += [f'- `{c["id"]}` {c["depth_cm"]} cm, {lab(c)}' + (f' — {L[c["id"]]["note"]}' if L[c['id']].get('note') else '')
                   for c in sorted(fps, key=lambda c: -c['depth_cm'])[:15]]
            md += ['']

        # ---- misses ----
        miss = [c for c in labeled if c['kind'] in ('seam', 'graze', 'control')]
        g = collections.defaultdict(collections.Counter)
        for c in miss:
            g[c['kind']][lab(c)] += 1
        md += ['### When the detector says clean (misses)', '',
               table(['probe', 'visible clip missed', 'clean', "animation's fault"],
                     [({'seam': 'rest-seam overlap that grew in motion (masked)', 'graze': 'deepest graze under --depth',
                        'control': 'random clean gated frame'}[k], pct(v['clip'], sum(v.values())), v['clean'], v['anim'])
                      for k, v in sorted(g.items())]), '']
        missed = [c for c in miss if lab(c) == 'clip']
        if missed:
            md += ['Missed clips:', ''] + [f'- `{c["id"]}`' + (f' grew {c["growth_cm"]} cm' if c.get('growth_cm') else '')
                                           + (f' — {L[c["id"]]["note"]}' if L[c['id']].get('note') else '') for c in missed] + ['']

        # ---- REST lines ----
        rest = [c for c in labeled if c['kind'] == 'rest']
        if rest:
            n = sum(lab(c) == 'clip' for c in rest)
            md += ['### REST lines the agent must judge', '', f'{pct(n, len(rest))} were bugs; the rest are noise the '
                   'agent has to read past.', '']

        # ---- gate verdicts ----
        rows = collections.Counter()
        for k, s in S.items():
            gp = [c for c in s['candidates'] if c['kind'] in POS and c['gated'] and lab(c)]
            gm = [c for c in s['candidates'] if c['kind'] in ('seam', 'graze', 'control') and c['gated'] and lab(c)]
            if s['gate_result'] == 'FAIL':
                if any(lab(c) == 'clip' for c in gp):
                    rows['FAIL, justified'] += 1
                elif gp and all(lab(c) in ('clean', 'anim') for c in gp):
                    rows['FAIL, false (every labelled gated hit is clean or the animation)'] += 1
                else:
                    rows['FAIL, not enough labels'] += 1
            else:
                rows['PASS, but a gated frame has a missed clip' if any(lab(c) == 'clip' for c in gm) else 'PASS'] += 1
        md += ['### Gate verdicts, checked against the labels', '', table(['verdict', 'pairs'], rows.most_common()), '']

        # ---- depth threshold ----
        sweep = [c for c in labeled if c['kind'] in POS + ('graze',) and lab(c) in ('clip', 'clean', 'anim')]
        if sweep:
            rows = []
            for t in (0.1, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0):
                tp = sum(lab(c) == 'clip' and c['depth_cm'] > t for c in sweep)
                fp = sum(lab(c) != 'clip' and c['depth_cm'] > t for c in sweep)
                fn = sum(lab(c) == 'clip' and c['depth_cm'] <= t for c in sweep)
                rows.append((t, tp, fp, fn, pct(tp, tp + fp), pct(tp, tp + fn)))
            md += ['### --depth threshold sweep', '', 'Over labelled detector hits and grazes (the sample is chosen '
                   'per clip, so read it as a direction, not exact rates).', '',
                   table(['--depth cm', 'real flagged', 'false flagged', 'real missed', 'precision', 'recall'], rows), '']

    # ---- cross-run ----
    if A.compare:
        O = load(os.path.expanduser(A.compare))
        diff = [(k, S[k]['gate_result'], O[k]['gate_result'], S[k]['failed_clips'], O[k]['failed_clips'])
                for k in sorted(set(S) & set(O)) if S[k]['gate_result'] != O[k]['gate_result']
                or S[k]['failed_clips'] != O[k]['failed_clips']]
        md += [f'## Compared with {os.path.basename(A.compare.rstrip("/"))} '
               f'(Blender {next(iter(O.values()))["blender"]})', '',
               f'{len(diff)} of {len(set(S) & set(O))} pairs change verdict or failing clips.', '']
        if diff:
            md += [table(['item/shape', 'this run', 'other run', 'fails here', 'fails there'],
                         [(f'{k[0]}/{k[1]}', a, b, ', '.join(fa) or '–', ', '.join(fb) or '–') for k, a, b, fa, fb in diff]), '']
    text = '\n'.join(md)
    open(os.path.join(run, 'report.md'), 'w').write(text)
    print(text)


if __name__ == '__main__':
    main()
