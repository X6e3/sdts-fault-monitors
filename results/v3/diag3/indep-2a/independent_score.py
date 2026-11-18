
"""Independent DEV scoring for DIAG-3 phase 2a. Never scores an unfinished run."""
import argparse
import csv
import hashlib
import json
import math
import random
import re
import subprocess
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path("/home/x6e3/Research/sdts-v3-codex")
RUN = Path("/home/x6e3/Research/sdts-runs/v3-diag3/dev2a-6c1190f")
BASELINE = ROOT / "results/v3/dev-45cff1d/rows.jsonl"
N = 3600
METHODS = ("v2", "cyl16p", "S128", "S256")
DIAG = {
    (430007, "drift_0.002", "rw"), (430027, "drift_0.002", "rw"),
    (430000, "drift_0.001", "ramp"), (430010, "drift_0.0005", "ramp"),
    (430019, "drift_0.001", "ramp"),
}


def digest(blob):
    return hashlib.sha256(blob).hexdigest()


def wait_for_exit(wait):
    previous = None
    while True:
        log = (RUN / "run.log").read_text(errors="replace").rstrip().splitlines()
        last = log[-1] if log else ""
        match = re.fullmatch(r"EXIT=(-?[0-9]+)", last.strip())
        if match and int(match[1]) == 0:
            return last.strip()
        if match:
            raise RuntimeError(f"The read-only run exited unsuccessfully: {last}")
        if not wait:
            raise RuntimeError("Run log has no terminal EXIT=0")
        count = sum(1 for _ in RUN.glob("dev-*.json"))
        if count != previous:
            print(f"Waiting for EXIT=0 ({count} of 1320 row files)", flush=True)
            previous = count
        time.sleep(60)


def connect_inputs():
    reference = BASELINE.read_bytes()
    rows = [json.loads(line) for line in reference.splitlines() if line.strip()]
    assert len(rows) == 1320
    keyed = {}
    outputs_digest = hashlib.sha256()
    for row in rows:
        assert 430000 <= row["seed"] <= 430029
        key = "-".join(str(row[k]) for k in ("seed", "cell", "arm", "ambient", "noise"))
        assert key not in keyed, f"Duplicate reference row {key}"
        keyed[key] = row
    expected = {f"dev-{key}.json" for key in keyed}
    observed = {path.name for path in RUN.glob("dev-*.json")}
    if expected != observed:
        raise RuntimeError(f"Row file set mismatch. Missing: {sorted(expected - observed)}; extra: {sorted(observed - expected)}")
    for key, row in sorted(keyed.items()):
        path = RUN / f"dev-{key}.json"
        blob = path.read_bytes()
        outputs_digest.update(f"{digest(blob)}  {path.name}\n".encode())
        result = json.loads(blob)
        assert key == result["key"]
        found = {"v2": row["v2"], "cyl16p": result["cyl16p"],
                 "S128": result["S128"]["detect"], "S256": result["S256"]["detect"]}
        for time_index in found.values():
            if time_index is not None:
                assert type(time_index) is int and 0 <= time_index < N, (key, time_index)
        for method in ("S128", "S256"):
            if found[method] is not None:
                margin = result[method]["margin_at_detect_mC"]
                assert isinstance(margin, (int, float)) and math.isfinite(margin), (key, method, margin)
        row["key"] = key
        row["detect"] = found
        row["lp"] = {m: result[m] for m in ("S128", "S256")}
    assert len(keyed) == 1320
    return list(keyed.values()), digest(reference), outputs_digest.hexdigest()


def reference_sets(rows):
    faults = [r for r in rows if r["cell"] != "healthy" and r["noise"] == "uniform"]
    events = [r for r in faults if r["oracle"]["status"] == "certified" and r["oracle"]["t_star"] is not None]
    uncertified = [r for r in faults if r["oracle"]["status"] != "certified"]
    # Healthy runs of every noise law are admissible, as are certified model-consistent uniform-fault runs.
    admissible = [r for r in rows if r["cell"] == "healthy"] + [
        r for r in faults if r["oracle"]["status"] == "certified" and r["oracle"]["t_star"] is None]
    paired = [r for r in events if r["v2"] is not None]
    return faults, events, uncertified, admissible, paired


def lag(r, method):
    finding = r["detect"][method]
    return (N if finding is None else finding) - r["oracle"]["t_star"]


def sum_lag(rows, method):
    return sum(lag(r, method) for r in rows)


def ratio(total, v2_lag):
    return 1 - total / v2_lag if v2_lag else None


def pack_row(r, method):
    return {"key": r["key"], "seed": r["seed"], "cell": r["cell"], "arm": r["arm"], "ambient": r["ambient"],
            "noise": r["noise"], "oracle_status": r["oracle"]["status"], "t_f": r["t_f"],
            "t_star": r["oracle"]["t_star"], "v2": r["v2"], "detect": r["detect"][method]}


def quantile(values, q):
    return values[min(len(values) - 1, int((len(values) - 1) * q + .5))] if values else None


def bootstrap(events, method):
    clusters = defaultdict(lambda: [0, 0])
    for r in events:
        n = clusters[r["seed"]]
        if r["v2"] is not None:
            n[0] += lag(r, "v2")
            n[1] += lag(r, method)
    groups = [clusters[seed] for seed in sorted(clusters)]
    random_generator = random.Random(20261118)
    values = []
    for _ in range(2000):
        base, candidate = 0, 0
        for _ in groups:
            den, num = random_generator.choice(groups)
            base += den
            candidate += num
        if base:
            values.append(1 - candidate / base)
    values.sort()
    return [quantile(values, .025), quantile(values, .975)]


def per_group(events, split_ambient):
    grouped = defaultdict(list)
    for r in events:
        name = f"{r['cell']}/{r['ambient']}" if split_ambient else r["cell"]
        grouped[name].append(r)
    group_metrics = {}
    for label, group in sorted(grouped.items()):
        paired = [r for r in group if r["v2"] is not None]
        base = sum_lag(paired, "v2")
        group_metrics[label] = {"certified_events": len(group), "paired_events": len(paired), "methods": {}}
        for m in METHODS:
            detected = [r for r in group if r["detect"][m] is not None]
            lp = sum_lag(paired, m)
            group_metrics[label]["methods"][m] = {
                "detected": len(detected), "misses": len(group) - len(detected),
                "lag_sum_detected_s": sum_lag(detected, m), "lag_sum_paired_s": lp,
                "lag_sum_all_certified_censored_s": sum_lag(group, m), "D_paired": ratio(lp, base),
            }
    return group_metrics


def score(rows):
    faults, events, uncertified, admissible, paired = reference_sets(rows)
    v2_lag = sum_lag(paired, "v2")
    output = {
        "rows": len(rows), "fault_uniform_rows": len(faults), "uncertified_fault_rows": len(uncertified),
        "uncertified_keys": [r["key"] for r in uncertified], "certified_detection_events": len(events),
        "admissible_rows": len(admissible), "paired_events": len(paired), "L_v2_paired_s": v2_lag, "methods": {},
    }
    for method in METHODS:
        detected = [r for r in events if r["detect"][method] is not None]
        misses = [pack_row(r, method) for r in events if r["detect"][method] is None]
        early = [pack_row(r, method) for r in detected if lag(r, method) < 0]
        inadmissible_alarm = [pack_row(r, method) for r in admissible if r["detect"][method] is not None]
        later = [pack_row(r, method) for r in rows if r["v2"] is not None
                 and (r["detect"][method] is None or r["detect"][method] > r["v2"])]
        paired_keys = {r["key"] for r in paired}
        late_paired = [r for r in later if r["key"] in paired_keys]
        lc = sum_lag(paired, method)
        delays = sorted(lag(r, method) for r in detected)
        output["methods"][method] = {
            "L_paired_s": lc, "D_paired": ratio(lc, v2_lag),
            "D_censored": ratio(sum_lag(events, method), sum_lag(events, "v2")),
            "D_paired_bootstrap95_descriptive": bootstrap(events, method) if method != "v2" else None,
            "detected": len(detected), "equal_to_oracle": delays.count(0),
            "misses": len(misses), "miss_rows": misses,
            "before_t_star": len(early), "before_t_star_rows": early,
            "admissible_alarms": len(inadmissible_alarm), "admissible_alarm_rows": inadmissible_alarm,
            "soundness_findings": len(early) + len(inadmissible_alarm),
            "later_than_v2_including_misses_all_rows": len(later), "later_than_v2_rows": later,
            "later_than_v2_including_misses_on_paired_rows": len(late_paired),
            "late_detection_only_all_rows": sum(r["detect"] is not None for r in later),
            "missed_when_v2_detects_all_rows": sum(r["detect"] is None for r in later),
            "lag_sum_detected_s": sum(delays), "lag_median_s": quantile(delays, .5),
            "lag_p90_s": quantile(delays, .9), "lag_max_s": max(delays, default=None),
        }
    output["by_cell"] = per_group(events, False)
    output["by_cell_ambient"] = per_group(events, True)
    s256 = output["methods"]["S256"]
    output["reading_rule_S256_met"] = bool(s256["D_paired"] is not None
                                           and s256["D_paired"] >= .8 and s256["soundness_findings"] == 0)
    return output


def is_diagnosis(r):
    return (r["seed"], r["cell"], r["ambient"]) in DIAG


def close_detections(rows):
    for r in rows:
        record = r["lp"]["S256"]
        m = record["margin_at_detect_mC"]
        if record["detect"] is not None and m > -0.5:
            yield {**pack_row(r, "S256"), "diagnosis_row": is_diagnosis(r),
                   "margin_at_detect_mC": m, "margin_at_t_star_mC": record["margin_at_t_star_mC"],
                   "n_retry": record["n_retry"]}


def save(path, value):
    pending = path.with_name("." + path.name + ".tmp")
    pending.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    pending.replace(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--wait", action="store_true")
    args = parser.parse_args()
    status = wait_for_exit(args.wait)
    rows, row_sha, run_sha = connect_inputs()
    meta_bytes = (RUN / "meta.json").read_bytes()
    meta = json.loads(meta_bytes)
    commit = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    assert meta["git_head"] == "6c1190f0bc5fc16fa4f1204d3f0e6e14aa2cc785" and not meta["git_dirty_tracked"]
    reduced = [r for r in rows if not is_diagnosis(r)]
    excluded = sorted(r["key"] for r in rows if is_diagnosis(r))
    assert len(reduced) == 1310 and len(excluded) == 10
    near = sorted(close_detections(rows), key=lambda r: (-r["margin_at_detect_mC"], r["key"]))
    all_scores, reduced_scores = score(rows), score(reduced)
    d = all_scores["methods"]["cyl16p"]["D_paired"]
    result = {
        "task": "DIAG3-2a / DIAG3-T3b", "scorer_checkout_commit": commit, "run": meta,
        "run_log_terminal_line": status, "metadata_sha256": digest(meta_bytes),
        "reference_rows_sha256": row_sha,
        "row_outputs_manifest_sha256": run_sha,
        "row_outputs_manifest_order": "lexicographic row key; sha256sum-format lines with one LF after each row file",
        "definitions": {
            "paired_population": "certified non-healthy uniform-noise oracle detections with v2 detection",
            "admissible_population": "every healthy row and certified non-healthy uniform-noise rows with no oracle detection",
            "miss_lag": "3600 - t_star",
            "v2_dominance": "every v2 detection; candidate miss is late, actual late detection also separately counted",
            "bootstrap": "2000 descriptive seed-cluster draws with random seed 20261118",
        },
        "cyl16p_DEV_reference": {"expected_rounded_to_3dp": .386, "observed": d,
                                 "rounded_match": d is not None and round(d, 3) == .386},
        "excluded_diagnosis_rows": excluded,
        "all": all_scores, "without_diagnosis_runs": reduced_scores,
        "S256_near_boundary": {"criterion": "margin_at_detect_mC > -0.5 for S256 detected rows",
                               "all_count": len(near), "without_diagnosis_count": sum(not r["diagnosis_row"] for r in near)},
    }
    score_path = args.output / "scores.json"
    save(score_path, result)
    list_path = args.output / "s256-close-detections.csv"
    pending = list_path.with_name("." + list_path.name + ".tmp")
    fields = ("key", "seed", "cell", "arm", "ambient", "noise", "oracle_status", "t_f", "t_star", "v2", "detect",
              "diagnosis_row", "margin_at_detect_mC", "margin_at_t_star_mC", "n_retry")
    with pending.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(near)
    pending.replace(list_path)
    assert sum(1 for _ in csv.DictReader(list_path.open(newline=""))) == len(near)
    done = args.output / "DONE.txt"
    artifacts = sorted((Path(__file__).resolve(), score_path, list_path))
    header = ("# Sol — DIAG3-2a / DIAG3-T3b\n"
              f"# OBSERVED checkout commit {commit}; input run commit {meta['git_head']}; {status}\n"
              "# OBSERVED SHA-256 digests of output files\n")
    temp_done = done.with_name("." + done.name + ".tmp")
    temp_done.write_text(header + "".join(f"{digest(p.read_bytes())}  {p.name}\n" for p in artifacts))
    temp_done.replace(done)
    for label, scores in (("all", all_scores), ("without diagnosis", reduced_scores)):
        print(label, "paired", scores["paired_events"], "v2 lag", scores["L_v2_paired_s"], flush=True)
        for name, result in scores["methods"].items():
            print(name, result["D_paired"], result["misses"], result["soundness_findings"],
                  result["later_than_v2_including_misses_all_rows"], flush=True)
    print("S256 close detections", len(near), flush=True)


if __name__ == "__main__":
    main()

