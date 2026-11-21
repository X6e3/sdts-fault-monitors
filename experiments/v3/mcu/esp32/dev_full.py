"""MCU-2E: the ESP32 against the PC on every sample of the 1400 DEV rows (plan: MCU-2E-PLAN.md).

Rows: the DEV comparison rows of run_dev.py (seeds 430000-430029, 11 cells, E0/E1, rw/ramp, uniform noise: 1320)
and the edge-noise rows of DIAG-3 amendment 7 (healthy, seeds 430070-430089, E0/E1, rw/ramp, edge noise: 80).
Every row runs all 3600 samples. For each sample the board returns its flag, its cycle count and the first 16 bytes
of the SHA-256 of its state dump; the PC computes the same from host_trace. Results go to OUT/rows.jsonl, one line
per row, written as each row finishes; a restart skips the rows already there.
usage: python -B dev_full.py BUILD_DIR OUT_DIR [--port /dev/ttyUSB0] [--baud 921600] [--batch 256] [--limit N]
       python -B dev_full.py BUILD_DIR OUT_DIR --score      (score OUT_DIR/rows.jsonl only)
"""
import argparse
import hashlib
import json
import os
import struct
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "avr"))
import stream as ST  # noqa: E402

S, T = ST.S, ST.S.T
CELLS = ("healthy", "jump_0.2", "jump_0.5", "drift_0.0005", "drift_0.001", "drift_0.002", "drift_0.005",
         "drift_0.02", "noise_x2", "stuck", "gain_0.01")


def rows():
    out = [(s, c, arm, al, "uniform") for c in CELLS for arm in T.ARMS for al in ("rw", "ramp")
           for s in range(430000, 430030)]
    out += [(s, "healthy", arm, al, "edge") for s in range(430070, 430090) for arm in T.ARMS for al in ("rw", "ramp")]
    assert len(out) == 1400 and len(set(out)) == 1400
    assert all(k[0] in S.DEV for k in out)
    return out


def run_row(fd, host, key, batch):
    seed, cell_name, arm, al, nl = key
    cell = next(c for c in T.CELLS if c.name == cell_name)
    r = S.run(seed, cell, arm, al, nl)
    y, P = r["y"], r["P"]
    h_init, h_obs = ST.host_dumps(host, y, P)
    os.write(fd, b"I")
    if ST.read_exact(fd, 1) != b"i":
        raise RuntimeError("no init reply")
    b_init = ST.read_exact(fd, len(h_init))
    res = {"key": list(key), "init_equal": b_init == h_init, "samples": 0, "mismatches": 0, "first_mismatch": None,
           "flag_mismatches": 0, "board_first": None, "host_first": None}
    cycles = []
    for start in range(0, len(y), batch):
        n = min(batch, len(y) - start)
        payload = b"".join(struct.pack("<dd", y[k], P[k]) for k in range(start, start + n))
        os.write(fd, b"B" + struct.pack("<H", n) + payload)
        if ST.read_exact(fd, 1, 30.0) != b"b":
            raise RuntimeError(f"no batch reply at {start}")
        rep = ST.read_exact(fd, 21 * n, 60.0)
        for i in range(n):
            k = start + i
            flag, cyc, hb = rep[21 * i], struct.unpack("<I", rep[21 * i + 1:21 * i + 5])[0], rep[21 * i + 5:21 * i + 21]
            hflag, hdump = h_obs[k]
            hh = hashlib.sha256(hdump).digest()[:16]
            res["samples"] += 1
            cycles.append(cyc)
            if flag and res["board_first"] is None:
                res["board_first"] = k
            if hflag and res["host_first"] is None:
                res["host_first"] = k
            if flag != hflag:
                res["flag_mismatches"] += 1
            if flag != hflag or hb != hh:
                res["mismatches"] += 1
                if res["first_mismatch"] is None:
                    res["first_mismatch"] = k
    c = sorted(cycles)
    res["cycles"] = {"median": c[len(c) // 2], "p99": c[int(0.99 * (len(c) - 1))], "max": c[-1], "min": c[0]}
    return res


def score(out_dir):
    recs = [json.loads(l) for l in (out_dir / "rows.jsonl").read_text().splitlines() if l.strip()]
    keys = {tuple(r["key"]) for r in recs}
    expected = set(rows())
    bad = [r for r in recs if r["mismatches"] or not r["init_equal"] or r["samples"] != 3600]
    samples = sum(r["samples"] for r in recs)
    cyc_max = max(r["cycles"]["max"] for r in recs)
    verdict = "PASS" if keys == expected and len(recs) == 1400 and not bad else (
        "INCOMPLETE" if keys != expected else "FAIL")
    s = {"verdict": verdict, "rows": len(recs), "expected_rows": 1400, "missing": len(expected - keys),
         "extra": len(keys - expected), "samples": samples, "rows_with_any_difference": len(bad),
         "first_inconsistent_equal_rows": sum(r["board_first"] == r["host_first"] for r in recs),
         "flagged_rows_board": sum(r["board_first"] is not None for r in recs),
         "cycles_max": cyc_max, "cycles_median_of_row_medians": sorted(r["cycles"]["median"] for r in recs)[len(recs) // 2],
         "bad_examples": [{k: r[k] for k in ("key", "mismatches", "first_mismatch", "init_equal", "samples")} for r in bad[:20]]}
    (out_dir / "score.json").write_text(json.dumps(s, indent=1) + "\n")
    print(json.dumps(s, indent=1))
    return s


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("build_dir", type=Path)
    ap.add_argument("out_dir", type=Path)
    ap.add_argument("--port", default="/dev/ttyUSB0")
    ap.add_argument("--baud", type=int, default=921600)
    ap.add_argument("--batch", type=int, default=256)
    ap.add_argument("--limit", type=int, help="only the first N rows not yet done (rehearsal)")
    ap.add_argument("--score", action="store_true")
    a = ap.parse_args()
    if a.score:
        score(a.out_dir)
        return
    a.out_dir.mkdir(parents=True, exist_ok=True)
    out = a.out_dir / "rows.jsonl"
    done = set()
    if out.exists():
        done = {tuple(json.loads(l)["key"]) for l in out.read_text().splitlines() if l.strip()}
    todo = [k for k in rows() if k not in done]
    if a.limit:
        todo = todo[:a.limit]
    fd = ST.open_port(a.port, "esp32", a.baud)
    time.sleep(0.2)
    banner = ST.wait_banner(fd, "SDTS-")
    meta_path = a.out_dir / "meta.json"
    if not meta_path.exists():
        meta_path.write_text(json.dumps({"banner": banner, "build": (a.build_dir / "build.txt").read_text(),
                                         "size": (a.build_dir / "size.txt").read_text(), "batch": a.batch,
                                         "baud": a.baud, "started": time.strftime("%Y-%m-%dT%H:%M:%S%z")},
                                        indent=1) + "\n")
    print(banner, f"rows to do: {len(todo)} (done before: {len(done)})", flush=True)
    host = str(a.build_dir / "host_trace")
    retries = a.out_dir / "infrastructure.log"
    for i, key in enumerate(todo):
        t0 = time.monotonic()
        for attempt in range(3):
            try:
                res = run_row(fd, host, key, a.batch)
                break
            except (TimeoutError, RuntimeError) as e:
                with retries.open("a") as f:
                    f.write(f"{time.strftime('%H:%M:%S')} {key} attempt {attempt}: {e!r}\n")
                os.close(fd)
                fd = ST.open_port(a.port, "esp32", a.baud)
                time.sleep(0.2)
                ST.wait_banner(fd, "SDTS-")
        else:
            raise SystemExit(f"row {key} failed three times: infrastructure, see {retries}")
        res["wall_s"] = round(time.monotonic() - t0, 1)
        with out.open("a") as f:
            f.write(json.dumps(res) + "\n")
        if res["mismatches"] or i % 50 == 0:
            print(i + len(done), json.dumps({k: res[k] for k in ("key", "mismatches", "board_first", "host_first",
                                                                 "wall_s")}), flush=True)
    os.write(fd, b"M")
    if ST.read_exact(fd, 1) == b"m":
        free_h, heap, min_free, stack_unused = struct.unpack("<IIII", ST.read_exact(fd, 16))
        (a.out_dir / "memory.json").write_text(json.dumps({"heap_size": heap, "free_heap": free_h,
                                                           "min_free_heap": min_free,
                                                           "loop_stack_unused": stack_unused}) + "\n")
    if len(done) + len(todo) == 1400 and not a.limit:
        score(a.out_dir)
        (a.out_dir / "done").write_text(time.strftime("%Y-%m-%dT%H:%M:%S%z") + "\n")


if __name__ == "__main__":
    main()
