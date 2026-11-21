"""Independent scorer of validations 2 and 3 (FREEZE-V2.md and FREEZE-V3.md section 4), from the records only.

Written from section 4 of FREEZE-V2.md alone, for validation 2, and pointed at validation 3 by its constants (the
manifest, the freeze document, the approval date, and the record key F3 read as F). It imports only the Python
standard library: no project module, no simulator, no LP. It scores the run's rows.jsonl again, checks the run's
meta.json and the manifest's files at the approval commit, and compares every number with the run's scores.json.

  python3 independent_score.py --freeze 3 --repo REPO --run REPO/results/v3/freeze3/validation-440400-440599-948b46b0 \
      [--worktree DIR] [--out FILE]

--worktree: a checkout of the approval commit whose files are checked against the manifest as well (optional).
Cleaned for the repository on 2026-11-22 from the two scripts that scored the validations (RECORD-2026-11-19 and
-21-validation.md): only the paths became arguments and the two variants one file; the scoring is unchanged.
"""
import argparse
import hashlib
import itertools
import json
import math
import random
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

FREEZES = {2: {"manifest": "MANIFEST-V2.json", "doc": "FREEZE-V2.md", "date": "2026-11-19",
               "commit": "35b344df61e955eafc18ab722f0ea30c1685fa7d"},
           3: {"manifest": "MANIFEST-V3.json", "doc": "FREEZE-V3.md", "date": "2026-11-20",
               "commit": "948b46b0dd05171478edec87ac9cb821818223dd"}}
_ap = argparse.ArgumentParser(description=__doc__)
_ap.add_argument("--freeze", type=int, choices=(2, 3), required=True)
_ap.add_argument("--repo", required=True)
_ap.add_argument("--run", type=Path, required=True)
_ap.add_argument("--worktree", type=Path)
_ap.add_argument("--out", type=Path, default=Path("independent-score.json"))
ARGS = _ap.parse_args()
FZ = FREEZES[ARGS.freeze]
RUN = ARGS.run
REPO = ARGS.repo
COMMIT = FZ["commit"]

def git_blob(path):
    return subprocess.check_output(['git', '-C', REPO, 'show', COMMIT + ':' + path])

def sha(data):
    return hashlib.sha256(data).hexdigest()

def key(row):
    return tuple(row[k] for k in ('seed', 'cell', 'arm', 'ambient', 'noise'))

def pick_quantile(xs, p):
    a = sorted(xs)
    return a[int(p * (len(a) - 1) + .5)] if a else None

manifest_bytes = git_blob('experiments/v3/frozen/' + FZ['manifest'])
manifest = json.loads(manifest_bytes)
meta = json.loads((RUN / 'meta.json').read_text())
rows = [json.loads(line) for line in (RUN / 'rows.jsonl').read_text().splitlines() if line.strip()]
official = json.loads((RUN / 'scores.json').read_text())
if ARGS.freeze == 3:   # freeze 3: the candidate's record key is F3; read it as F (rows and the official scores)
    for _r in rows:
        _r['F'] = _r['F3']
    official['F'] = official['F3']
    official['by_cell'] = {c: {('F' if m == 'F3' else m): v for m, v in d.items()} for c, d in official['by_cell'].items()}
checks = {}
checks['manifest_sha256'] = sha(manifest_bytes)
checks['freeze_document_sha256'] = sha(git_blob('experiments/v3/' + FZ['doc']))
checks['input_sha256'] = {n: sha((RUN / n).read_bytes()) for n in ('rows.jsonl', 'meta.json', 'scores.json')}
checks['manifest_file_mismatches'] = [p for p, h in manifest['files'].items() if sha(git_blob(p)) != h]
checks['local_validation_source_mismatches'] = (None if ARGS.worktree is None else
    [p for p, h in manifest['files'].items() if sha((ARGS.worktree / p).read_bytes()) != h])
approval_text = git_blob('experiments/v3/' + FZ['doc']).decode()
checks['metadata_matches'] = {
    'manifest': meta['manifest_sha256'] == sha(manifest_bytes),
    'document': meta['freeze_doc_sha256'] == checks['freeze_document_sha256'],
    'rows': meta['rows_sha256'] == checks['input_sha256']['rows.jsonl'],
    'git_head': meta['git_head'] == COMMIT,
    'clean_tracked': meta['git_dirty_tracked'] is False,
    'approval': bool(re.search(r'^Status: APPROVED by Can Koç on ' + FZ['date'] + '$', approval_text, re.M))
        and meta['approval'] == 'Status: APPROVED by Can Koç on ' + FZ['date'],
    'mode': meta['mode'] == 'validation',
    'finished': bool(meta.get('finished')),
    'seeds': meta['seeds'] == manifest['validation_block'],
    'candidate': meta['candidate'] == manifest['candidate'],
    'environment': all(meta['env'].get(k) == v for k, v in
        {'python': '3.12.13', 'implementation': 'CPython', 'numpy': '2.5.5',
         'scipy': '1.18.1', 'highs': '1.12.0'}.items()),
}
expected = set()
for seed in range(manifest['validation_block'][0], manifest['validation_block'][1] + 1):
    for cell, arm, law in itertools.product(manifest['cells'], manifest['arms'], manifest['laws_all_cells']):
        expected.add((seed, cell, arm, *law))
    for arm, law in itertools.product(manifest['arms'], manifest['laws_healthy_extra']):
        expected.add((seed, 'healthy', arm, *law))
counts = Counter(map(key, rows))
checks['identity'] = {'expected': len(expected), 'actual': len(rows), 'unique': len(counts),
    'missing': sorted(expected - counts.keys()), 'extra': sorted(counts.keys() - expected),
    'duplicate_excess': sum(n - 1 for n in counts.values() if n > 1)}
fault = [r for r in rows if r['cell'] != 'healthy' and r['noise'] == 'uniform']
unknown = [r for r in fault if r['oracle']['status'] != 'certified']
events = [r for r in fault if r['oracle']['status'] == 'certified' and r['oracle']['t_star'] is not None]
admissible = [r for r in rows if r['cell'] == 'healthy' or
    (r in fault and r['oracle']['status'] == 'certified' and r['oracle']['t_star'] is None)]
paired = [r for r in events if r['v2'] is not None]
N = manifest['record_length']

def detection(row, method):
    return row['v2'] if method == 'v2' else row['F']['detect']

def score_method(method):
    lag = lambda r: N - r['oracle']['t_star'] if detection(r, method) is None else detection(r, method) - r['oracle']['t_star']
    delays = [lag(r) for r in events if detection(r, method) is not None]
    return {'L_paired': sum(lag(r) for r in paired), 'L_censored': sum(lag(r) for r in events),
        'detected': len(delays), 'misses': len(events) - len(delays),
        'equal_to_oracle': delays.count(0), 'lag_median': pick_quantile(delays, .5),
        'lag_p90': pick_quantile(delays, .9), 'lag_max': max(delays, default=None),
        'lag_sum_detected': sum(delays)}

v2, cand = score_method('v2'), score_method('F')
cand['D_paired'] = 1 - cand['L_paired'] / v2['L_paired'] if v2['L_paired'] else None
cand['D_censored'] = 1 - cand['L_censored'] / v2['L_censored'] if v2['L_censored'] else None
bad_sound = [r for r in admissible if r['F']['detect'] is not None] + [r for r in events
    if r['F']['detect'] is not None and r['F']['detect'] < r['oracle']['t_star']]
bad_certificate = [r for r in rows if r['F']['detect'] is not None and not
    (r['F'].get('alarm_certificate') or {}).get('certified')]
later = [r for r in rows if r['v2'] is not None and
    (r['F']['detect'] is None or r['F']['detect'] > r['v2'])]
certified = [r for r in rows if r['F']['detect'] is not None and
    (r['F'].get('alarm_certificate') or {}).get('certified')]
bad_certified_margin = [key(r) for r in certified if not
    (math.isfinite(r['F']['alarm_certificate']['certified_margin_mC']) and
     r['F']['alarm_certificate']['certified_margin_mC'] < 0)]
seed_lags = defaultdict(lambda: [0, 0])
for r in paired:
    ts = r['oracle']['t_star']
    seed_lags[r['seed']][0] += (r['F']['detect'] if r['F']['detect'] is not None else N) - ts
    seed_lags[r['seed']][1] += r['v2'] - ts
seeds = sorted({r['seed'] for r in events})
rng, draws = random.Random(20261118), []
for _ in range(2000):
    lf = lv = 0
    for _ in seeds:
        a, b = seed_lags[rng.choice(seeds)]
        lf, lv = lf + a, lv + b
    if lv:
        draws.append(1 - lf / lv)
cand['D_paired_bootstrap95_descriptive'] = [pick_quantile(draws, .025), pick_quantile(draws, .975)]
by_cell = {}
for r in events:
    cell = r['cell'] + '/' + r['ambient']
    if cell not in by_cell:
        by_cell[cell] = {m: {'n': 0, 'miss': 0, 'lag_sum': 0} for m in ('v2', 'F')}
    for m in ('v2', 'F'):
        a = by_cell[cell][m]
        a['n'] += 1
        d = detection(r, m)
        if d is None:
            a['miss'] += 1
        else:
            a['lag_sum'] += d - r['oracle']['t_star']
integrity_bad = bool(checks['manifest_file_mismatches'] or checks['local_validation_source_mismatches']
    or not all(checks['metadata_matches'].values()))
complete = not any((checks['identity']['missing'], checks['identity']['extra'], checks['identity']['duplicate_excess']))
if integrity_bad:
    verdict = 'INCONCLUSIVE'
elif bad_sound or bad_certificate:
    verdict = 'FAIL'
elif not complete or len(unknown) > .01 * len(fault):
    verdict = 'INCONCLUSIVE'
elif cand['misses'] > v2['misses'] or cand['D_paired'] is None or cand['D_paired'] < manifest['candidate']['target_paired_lag_reduction']:
    verdict = 'FAIL'
else:
    verdict = 'PASS'
comparisons = {k: {'independent': value, 'official': official['F'].get(k), 'equal': value == official['F'].get(k)}
    for k, value in cand.items()}
comparisons['verdict'] = {'independent': verdict, 'official': official['F']['verdict'], 'equal': verdict == official['F']['verdict']}
comparisons['by_cell_equal'] = by_cell == official['by_cell']
comparisons['soundness_keys_equal'] = sorted(key(r) for r in bad_sound) == sorted(tuple(x[1:6]) for x in official['F']['soundness_violations'])
comparisons['uncertified_keys_equal'] = sorted(key(r) for r in bad_certificate) == sorted(tuple(x[:5]) for x in official['F']['uncertified_alarms'])
comparisons['later_count_equal'] = len(later) == len(official['F']['later_than_v2_reported'])
retry = {law: {'retries': sum(r['F']['n_retry'] for r in rows if r['noise'] == law),
    'rows_with_retries': sum(r['F']['n_retry'] > 0 for r in rows if r['noise'] == law)} for law in ('uniform', 'edge')}
report = {'task': 'independent scorer, freeze %d' % ARGS.freeze, 'method': 'Existing JSON records only; independent standard-library scorer; no SDTS module imported; no LP or data regeneration.',
    'commit': COMMIT, 'checks': checks, 'counts': {'runs': len(rows), 'fault': len(fault),
    'oracle_unknown_fault': len(unknown), 'events': len(events), 'paired': len(paired), 'admissible': len(admissible),
    'soundness': len(bad_sound), 'uncertified': len(bad_certificate), 'later_than_v2': len(later),
    'certified_alarms': len(certified), 'bad_certified_margin': bad_certified_margin},
    'verdict': verdict, 'v2': v2, 'F': cand, 'deciding_rows': bad_sound,
    'oracle_unknown_rows': [key(r) for r in unknown], 'by_cell': dict(sorted(by_cell.items())),
    'resources': {'n_lp': sum(r['F']['n_lp'] for r in rows), 'retry_by_noise': retry,
    'evictions': sum(r['F']['evictions'] for r in rows), 'rows_with_evictions': sum(r['F']['evictions'] > 0 for r in rows),
    'folds_raised': sum(r['F']['folds_raised_to_dual_bound'] for r in rows),
    'rows_with_raised_folds': sum(r['F']['folds_raised_to_dual_bound'] > 0 for r in rows),
    'max_rows': max(r['F']['max_rows'] for r in rows), 'max_vars': max(r['F']['max_vars'] for r in rows)},
    'comparisons': comparisons}
ARGS.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
print(json.dumps({'verdict': verdict, 'counts': report['counts'], 'F': cand,
    'comparisons': comparisons, 'resources': report['resources']}, indent=2))
