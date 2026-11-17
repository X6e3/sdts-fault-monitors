"""Score a run_final.py output against protocol v2 section 5 with addendum A1 (no tuning, no new rules).

P1-P6 and P8 get holds/fails as defined. P7 E0 is scored. P7 E1 is reported under both readings of the
frozen text (A1.6); neither is designated. Everything else is reported, not predicted.
usage: python -B score_final.py RUN_DIR      (writes RUN_DIR/scores.json)
"""
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ADDITIVE = ("offset", "jump", "drift", "noise")
P8_CELLS = ("drift_0.0005", "drift_0.001", "drift_0.002")
P8_PRIMARY = ("cusum_a0", "dmreda_native")


def kind(cell):
    return cell.split("_")[0]


def inside(iv, R):
    return iv is not None and -R <= iv[0] and iv[1] <= R


def machine_key(m):
    return (m["first_inconsistent"] is None, m["R1"], m["R3"])


def quantiles(xs):
    if not xs:
        return None
    xs = sorted(xs)
    return {"n": len(xs), "min": xs[0], "median": statistics.median(xs), "max": xs[-1]}


def score(run_dir):
    run_dir = Path(run_dir)
    runs = [json.loads(l) for l in (run_dir / "runs.jsonl").read_text().splitlines() if l.strip()]
    twins = [json.loads(l) for l in (run_dir / "twins.jsonl").read_text().splitlines() if l.strip()]
    meta = json.loads((run_dir / "meta.json").read_text())
    by = {(r["seed"], r["cell"], r["arm"]): r for r in runs}
    S = {"meta": {k: meta.get(k) for k in ("kind", "git_head", "thresholds_sha256", "runs", "twin_pairs", "seconds")}}

    # P1
    diff = Counter()
    for t in twins:
        a, b = t["members"]
        diff["oracle"] += a["oracle"] != b["oracle"]
        diff["machine"] += machine_key(a["machine"]) != machine_key(b["machine"])
        for k in a["baselines"]:
            diff[k] += a["baselines"][k] != b["baselines"][k]
    gen = max((t["max_abs_y_diff"] for t in twins), default=None)
    S["P1"] = {"pairs": len(twins), "max_abs_y_diff": gen, "differing_verdicts": dict(diff),
               "holds": gen is not None and gen <= 1e-9 and not any(diff.values())}

    # P2
    pairs = [(by[(s, c, "E0")], by[(s, c, "E1")]) for (s, c, arm) in by
             if arm == "E0" and kind(c) in ADDITIVE and (s, c, "E1") in by]
    o = sum(a["oracle"]["full"]["verdict"] != b["oracle"]["full"]["verdict"] for a, b in pairs)
    m = sum(machine_key(a["machine"]["full"]) != machine_key(b["machine"]["full"]) for a, b in pairs)
    und = sum("undetermined" in (a["oracle"]["full"]["verdict"], b["oracle"]["full"]["verdict"]) for a, b in pairs)
    S["P2"] = {"pairs": len(pairs), "oracle_differing": o, "machine_differing": m, "oracle_undetermined_pairs": und,
               "holds": o == 0 and m == 0}

    # P3
    healthy = [r for r in runs if r["cell"] == "healthy"]
    h_inc = sum(r["machine"]["full"]["first_inconsistent"] is not None for r in healthy)
    contra, corro, open_ = Counter(), Counter(), Counter()
    for r in runs:
        for R in (1, 3):
            if r["machine"]["full"][f"R{R}"] != "TUTARLI":
                continue
            if r["cell"] == "healthy":
                inner, outer = r["P6"]["interval"], r["P6"]["outer_interval"]
                if inner is not None and not inside(inner, R):
                    contra[R] += 1
                elif inside(outer, R):
                    corro[R] += 1
                else:
                    open_[R] += 1
            elif inside(r["offset_box_bound"], R):
                corro[R] += 1
            else:
                open_[R] += 1
    S["P3"] = {"healthy_runs": len(healthy), "healthy_TUTARSIZ": h_inc, "TUTARLI_contradicted": dict(contra),
               "TUTARLI_corroborated": dict(corro), "TUTARLI_not_checkable": dict(open_),
               "holds": h_inc == 0 and not contra}

    # P4
    jumps = [r for r in runs if r["cell"] in ("jump_2", "jump_5")]
    bad4 = [(r["seed"], r["cell"], r["arm"]) for r in jumps
            if not (r["P4"]["before"] == "consistent" and r["P4"]["at"] == "inconsistent"
                    and r["machine"]["full"]["first_inconsistent"] == r["t_f"])]
    S["P4"] = {"runs": len(jumps), "failing": bad4, "holds": not bad4}

    # P5
    offs = [r for r in runs if kind(r["cell"]) == "offset"]
    bad5 = [(r["seed"], r["cell"], r["arm"]) for r in offs
            if r["oracle"]["no_c"]["verdict"] != "consistent" or r["machine"]["no_c"]["first_inconsistent"] is not None]
    S["P5"] = {"runs": len(offs), "failing": bad5, "holds": not bad5}

    # P6
    p6 = {}
    for R in (1, 3):
        tab = Counter()
        for r in healthy:
            rule = r["P6"]["rule"][str(R)]
            inner, outer = r["P6"]["interval"], r["P6"]["outer_interval"]
            label = ("certifiable" if inside(outer, R) else
                     "not_certifiable" if inner is not None and not inside(inner, R) else "undetermined")
            tab[(rule, label)] += 1
        scored = {k: v for k, v in tab.items() if k[0] != 0}
        agree = sum(v for (rule, lab), v in scored.items()
                    if (rule, lab) in ((1, "certifiable"), (-1, "not_certifiable")))
        p6[str(R)] = {"table": {f"{k[0]}|{k[1]}": v for k, v in sorted(tab.items())},
                      "scored": sum(scored.values()), "agree": agree, "boundary": sum(v for k, v in tab.items() if k[0] == 0)}
    S["P6"] = {**p6, "holds": all(p6[R]["agree"] == p6[R]["scored"] for R in p6)}

    # P7
    st0 = [r for r in runs if r["cell"] == "stuck" and r["arm"] == "E0"]
    st1 = [r for r in runs if r["cell"] == "stuck" and r["arm"] == "E1"]
    e0_ok = sum(r["oracle"]["full"]["verdict"] == "consistent" for r in st0)
    with_k = [r for r in st1 if r["P7"]["k_change"] is not None]
    deadline = sum(r["P7"]["by_k_plus_30"] == "inconsistent" for r in with_k)
    window = sum(r["P7"]["before_change"] == "consistent" and r["P7"]["by_k_plus_30"] == "inconsistent" for r in with_k)
    n = len(with_k)
    S["P7"] = {"E0": {"runs": len(st0), "consistent": e0_ok, "holds": e0_ok == len(st0)},
               "E1": {"runs": len(st1), "without_a_5W_change": len(st1) - n,
                      "deadline_reading": {"inconsistent_by_k_plus_30": deadline, "fraction": deadline / n if n else None,
                                           "meets_95": bool(n) and deadline / n >= 0.95},
                      "window_reading": {"first_inconsistency_in_k_to_k_plus_30": window,
                                         "fraction": window / n if n else None, "meets_95": bool(n) and window / n >= 0.95},
                      "already_inconsistent_before_k": sum(r["P7"]["before_change"] == "inconsistent" for r in with_k),
                      "note": "both readings reported (A1.6); the Proposition 3 E1 timing clause was falsified on CAL"}}

    # P8
    p8 = {}
    for variant in sorted({k for r in runs for k in r["baselines"]}):
        for arm in ("E0", "E1"):
            rows = [r for r in runs if r["cell"] in P8_CELLS and r["arm"] == arm]
            flagged = sum(r["baselines"][variant]["flagged"] for r in rows)
            per_cell = {c: sum(r["baselines"][variant]["flagged"] for r in rows if r["cell"] == c) for c in P8_CELLS}
            p8[f"{variant}/{arm}"] = {"runs": len(rows), "flagged": flagged,
                                       "fraction": flagged / len(rows) if rows else None, "per_cell": per_cell,
                                       "pre_onset_alarms": sum(r["baselines"][variant]["pre_onset_alarm"] for r in rows)}
    scored = [p8[f"{v}/{a}"]["fraction"] for v in P8_PRIMARY for a in ("E0", "E1")]
    S["P8"] = {"by_variant_arm": p8, "scored_on": list(P8_PRIMARY),
               "holds": all(f is not None and f <= 0.10 for f in scored),
               "clause_2": "category statement, recorded not scored (A1.4)"}

    # reported maps
    maps = defaultdict(dict)
    for (cell, arm), rows in sorted(_group(runs).items()):
        key = f"{cell}/{arm}"
        for v in ("full", "no_b", "no_c", "no_d"):
            maps[key][f"oracle_{v}"] = dict(Counter(r["oracle"][v]["verdict"] for r in rows))
        lat = [r["oracle"]["full"]["t_star"] - r["t_f"] for r in rows if r["oracle"]["full"]["t_star"] is not None]
        maps[key]["oracle_latency"] = quantiles(lat)
        maps[key]["oracle_latency_uncertified"] = sum(r["oracle"]["full"]["t_star_status"] != "certified" for r in rows)
        mlag = [r["machine"]["full"]["first_inconsistent"] - r["oracle"]["full"]["t_star"] for r in rows
                if r["machine"]["full"]["first_inconsistent"] is not None and r["oracle"]["full"]["t_star"] is not None]
        maps[key]["machine_inconsistent"] = sum(r["machine"]["full"]["first_inconsistent"] is not None for r in rows)
        maps[key]["machine_lag_vs_oracle"] = quantiles(mlag)
        for v in ("no_b", "no_c"):
            maps[key][f"machine_{v}_inconsistent"] = sum(r["machine"][v]["first_inconsistent"] is not None for r in rows)
        maps[key]["TUTARLI"] = {R: sum(r["machine"]["full"][R] == "TUTARLI" for r in rows) for R in ("R1", "R3")}
        tut = [r["sensor_error"]["end"] for r in rows if cell != "healthy" and r["machine"]["full"]["R1"] == "TUTARLI"
               or cell != "healthy" and r["machine"]["full"]["R3"] == "TUTARLI"]
        if tut:
            maps[key]["TUTARLI_true_end_error"] = quantiles([abs(e) for e in tut])
        for v in sorted(rows[0]["baselines"]):
            out = [r["baselines"][v] for r in rows]
            entry = {"alarm": sum(o["alarm"] for o in out)}
            if cell != "healthy":
                entry["flagged"] = sum(o["flagged"] for o in out)
                entry["pre_onset_alarm"] = sum(o["pre_onset_alarm"] for o in out)
                entry["latency"] = quantiles([o["first_alarm_after_onset"] - r["t_f"] for o, r in zip(out, rows)
                                              if o["first_alarm_after_onset"] is not None])
            maps[key][v] = entry
    S["reported"] = maps
    (run_dir / "scores.json").write_text(json.dumps(S, indent=1) + "\n")
    return S


def _group(runs):
    g = defaultdict(list)
    for r in runs:
        g[(r["cell"], r["arm"])].append(r)
    return g


if __name__ == "__main__":
    s = score(sys.argv[1])
    print(json.dumps({k: v.get("holds", v) if isinstance(v, dict) else v for k, v in s.items() if k.startswith("P")}, indent=1))
