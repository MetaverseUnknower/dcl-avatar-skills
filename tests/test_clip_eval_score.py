"""score.py from evals/clipping on a synthetic run: precision, misses, gate verdicts, depth sweep, run comparison."""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCORE = os.path.join(os.path.dirname(HERE), 'evals', 'clipping', 'score.py')


def cand(slug, shape, kind, depth=None, gated=True, pair='body', clip='Walk', frame=3):
    det = {'rest': 'judge'}.get(kind, 'clip' if kind.startswith('pos') else 'clean')
    return {'id': f'{slug}/{shape}/{kind}/{clip}/{frame}/x', 'kind': kind, 'detector': det, 'label': 'a x b',
            'pair': pair, 'clip': clip, 'frame': frame, 'gated': gated, 'depth_cm': depth, 'images': []}


def write_run(root, name, pairs):
    for (slug, shape), (gate, failed, cands) in pairs.items():
        d = os.path.join(root, name, slug, shape)
        os.makedirs(d)
        json.dump({'item': {'slug': slug, 'category': 'feet' if slug == 'shoe' else 'hat', 'name': slug},
                   'shape': shape, 'blender': '3.6.1', 'checker_rev': 'abc', 'depth_cm': 0.3, 'gate_result': gate,
                   'failed_clips': failed, 'candidates': cands, 'clips': {}, 'rest': {}},
                  open(os.path.join(d, 'candidates.json'), 'w'))
    return os.path.join(root, name)


def run_score(run, labels, *extra):
    p = subprocess.run([sys.executable, SCORE, run, '--labels', labels, *extra], capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    return p.stdout


def test_score_counts(tmp_path):
    real = cand('shoe', 'female', 'pos-deep', 2.0)
    fake = cand('hat', 'female', 'pos-shallow', 0.4, pair='self')
    anim = cand('hat', 'female', 'pos-deep', 1.2, clip='Jog', pair='self')
    seam = cand('shoe', 'female', 'seam', 1.5)
    ctrl = cand('hat', 'male', 'control')
    run = write_run(str(tmp_path), 'r1', {
        ('shoe', 'female'): ('FAIL', ['Walk'], [real, seam]),
        ('hat', 'female'): ('FAIL', ['Walk', 'Jog'], [fake, anim]),
        ('hat', 'male'): ('PASS', [], [ctrl]),
    })
    labels = tmp_path / 'labels.json'
    labels.write_text(json.dumps({real['id']: {'v': 'clip'}, fake['id']: {'v': 'clean', 'note': 'brim on crown'},
                                  anim['id']: {'v': 'anim'}, seam['id']: {'v': 'clip'}, ctrl['id']: {'v': 'clean'}}))
    out = run_score(run, str(labels))
    assert '67% (2/3) of item/shape pairs FAIL the gate' in out
    assert 'Precision: 33% (1/3)' in out
    assert 'False positives: 1 clean, 1 the animation' in out
    assert 'brim on crown' in out
    assert '| rest-seam overlap that grew in motion (masked) | 100% (1/1) |' in out
    assert '| FAIL, justified | 1 |' in out
    assert '| FAIL, false (every labelled gated hit is clean or the animation) | 1 |' in out
    # at --depth 0.5 the 0.4 cm false hit drops out; the real 2.0 cm hit stays
    assert '| 0.5 | 1 | 1 | 0 | 50% (1/2) | 100% (1/1) |' in out
    assert os.path.exists(os.path.join(run, 'report.md'))


def test_score_without_labels_and_compare(tmp_path):
    a = write_run(str(tmp_path), 'a', {('shoe', 'female'): ('PASS', [], [])})
    b = write_run(str(tmp_path), 'b', {('shoe', 'female'): ('FAIL', ['Idle'], [])})
    out = run_score(a, str(tmp_path / 'none.json'), '--compare', b)
    assert 'Label some frames' in out
    assert '1 of 1 pairs change verdict' in out
    assert '| shoe/female | PASS | FAIL | – | Idle |' in out
