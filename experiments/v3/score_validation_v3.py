"""Score a run_validation_v3.py output with the rules frozen in FREEZE-V3.md (section 4). Nothing here is tunable.

The rules are freeze 2's, unchanged: score_validation_v2.score() is called on the rows, with F3's record put where F's
was. Sets, the verdict order, D_paired, the bootstrap and the reported quantities are those of FREEZE-V2.md section 4,
with F3 in place of F. In the output, every "F" of score_validation_v2 reads "F3".
Added, reported and not deciding: F3's failsafe counters (DIAG-3 amendment 10), summed over the scored rows, and the
number of rows with any fallback (box-proved alarms are not fallbacks and are counted apart).
usage: python -B score_validation_v3.py RUN_DIR [--manifest frozen/MANIFEST-V3.json] [--out scores.json]
"""
import argparse
import hashlib
import json
from pathlib import Path

import score_validation_v2 as SV2

HERE = Path(__file__).resolve().parent
FALLBACKS = ("fold_dir_fallbacks", "fold_implied", "fold_apriori_fallbacks", "fold_full_resets", "range_fallbacks",
             "range_failures", "cert_fallbacks", "measurements_not_kept")


def failsafe_report(rows):
    """sums of F3's failsafe counters over rows; dict counters are summed key by key"""
    tot, rows_with_fallback = {}, 0
    for r in rows:
        any_fb = False
        for k, v in r["F3"]["failsafe"].items():
            if isinstance(v, dict):
                d = tot.setdefault(k, {})
                for kk, n in v.items():
                    d[kk] = d.get(kk, 0) + n
                    any_fb |= k in FALLBACKS and n > 0
            else:
                tot[k] = tot.get(k, 0) + v
                any_fb |= k in FALLBACKS and v > 0
        rows_with_fallback += any_fb
    slab = sum(v.get("slab", 0) for v in tot.values() if isinstance(v, dict))
    return {"totals": tot, "rows_with_fallback": rows_with_fallback, "slab_failures": slab}


def as_f3(s):
    """rename score_validation_v2's "F" to "F3" in its output"""
    s["F3"] = s.pop("F")
    s["by_cell"] = {c: {("F3" if m == "F" else m): v for m, v in d.items()} for c, d in s["by_cell"].items()}
    return s


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--manifest", type=Path, default=HERE / "frozen" / "MANIFEST-V3.json")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    manifest = json.loads(a.manifest.read_text())
    manifest_sha = hashlib.sha256(a.manifest.read_bytes()).hexdigest()
    meta = json.loads((a.run_dir / "meta.json").read_text())
    rows_path = a.run_dir / "rows.jsonl"
    rows = [json.loads(l) for l in rows_path.read_text().splitlines() if l.strip()]
    lo, hi = manifest["validation_block"] if meta.get("mode") == "validation" else meta["seeds"]
    ident, exp = SV2.identity(rows, manifest, lo, hi)
    problems = SV2.integrity(meta, manifest, manifest_sha, hashlib.sha256(rows_path.read_bytes()).hexdigest())
    s = as_f3(SV2.score([{**r, "F": r["F3"]} for r in rows], manifest, expected=exp, problems=problems))
    s["F3"]["failsafe"] = failsafe_report([r for r in rows if SV2.KEY(r) in exp])
    s["mode"], s["identity"] = meta.get("mode"), ident
    (a.out or a.run_dir / "scores.json").write_text(json.dumps(s, indent=1) + "\n")
    c = s["F3"]
    print(f"F3: {c['verdict']}  D_paired={c['D_paired']}  target={c['target_paired_lag_reduction']}  "
          f"misses={c['misses']} (v2 {s['v2']['misses']})  soundness={len(c['soundness_violations'])}  "
          f"uncertified={len(c['uncertified_alarms'])}  later_than_v2={len(c['later_than_v2_reported'])} "
          f"(largest {c['later_than_v2_largest_s']} s)  unproved={c['unproved_primal_alarms']}  "
          f"fallback rows={c['failsafe']['rows_with_fallback']}  slab={c['failsafe']['slab_failures']}  "
          f"{c['fail_reasons']}")
    print(f"identity {ident}  integrity problems {problems}")
    print(f"runs {s['runs']}  fault {s['fault_runs']}  uncertified oracle {s['uncertified_oracle']}  "
          f"events {s['detection_events']}")


if __name__ == "__main__":
    main()
