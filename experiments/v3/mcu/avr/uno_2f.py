"""MCU-2F: the Uno's float32 template state against the PC's, decision by decision (plan: MCU-2F-PLAN.md).

Rows: 30 of MCU-2E's 1400 DEV rows, the 30 whose key string has the smallest sha256 (a fixed choice). Each row runs
until both the board and the PC have flagged, plus 3 samples; a row neither flags runs all 3600 samples.
After every sample the board's full state dump is compared with the PC's (host_trace, the unchanged v3_state.c in
float32), and the differences in h are measured in ulps, with their sign (board below or above the PC).
usage: python -B uno_2f.py BUILD_DIR OUT_DIR [--port /dev/ttyACM0]
       python -B uno_2f.py BUILD_DIR OUT_DIR --score
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
sys.path[:0] = [str(HERE), str(HERE.parent / "esp32")]
import stream as ST  # noqa: E402
import dev_full as DF  # noqa: E402

S, T = ST.S, ST.S.T
N_ROWS = 30


def rows():
    return sorted(DF.rows(), key=lambda k: hashlib.sha256(repr(k).encode()).hexdigest())[:N_ROWS]


def ordered(bits, width):
    """the bit pattern of a float as an integer that is monotone in the value (so differences count ulps)"""
    sign = 1 << (width - 1)
    return -(bits & (sign - 1)) if bits & sign else bits


def run_row(fd, host, key, after=3):
    seed, cell_name, arm, al, nl = key
    cell = next(c for c in T.CELLS if c.name == cell_name)
    r = S.run(seed, cell, arm, al, nl)
    y, P = r["y"], r["P"]
    h_init, h_obs = ST.host_dumps(host, y, P)
    n = 42
    dlen = 4 + 8 + 8 + 1 + 4 * n
    os.write(fd, b"I")
    if ST.read_exact(fd, 1) != b"i":
        raise RuntimeError("no init reply")
    b_init = ST.read_exact(fd, dlen)
    res = {"key": list(key), "init_equal": b_init == h_init, "samples": 0, "samples_equal": 0,
           "S_differs": 0, "flag_differs": 0, "h_below": 0, "h_above": 0, "max_ulp_below": 0, "max_ulp_above": 0,
           "board_first": None, "host_first": None, "cycles_max": 0, "cycles": []}
    stop_at = None
    for k, (yy, pp) in enumerate(zip(y, P)):
        os.write(fd, b"O" + struct.pack("<dd", yy, pp))
        hdr = ST.read_exact(fd, 6)
        if hdr[:1] != b"o":
            raise RuntimeError(f"bad reply at {k}: {hdr!r}")
        flag, cyc = hdr[1], struct.unpack("<I", hdr[2:6])[0]
        dump = ST.read_exact(fd, dlen)
        hflag, hdump = h_obs[k]
        res["samples"] += 1
        res["cycles"].append(cyc)
        if dump == hdump and flag == hflag:
            res["samples_equal"] += 1
        if dump[4:20] != hdump[4:20]:
            res["S_differs"] += 1
        if flag != hflag:
            res["flag_differs"] += 1
        hb = struct.unpack(f"<{n}I", dump[21:])
        hh = struct.unpack(f"<{n}I", hdump[21:])
        for a, b in zip(hb, hh):
            d = ordered(a, 32) - ordered(b, 32)
            if d < 0:
                res["h_below"] += 1
                res["max_ulp_below"] = max(res["max_ulp_below"], -d)
            elif d > 0:
                res["h_above"] += 1
                res["max_ulp_above"] = max(res["max_ulp_above"], d)
        if flag and res["board_first"] is None:
            res["board_first"] = k
        if hflag and res["host_first"] is None:
            res["host_first"] = k
        if res["board_first"] is not None and res["host_first"] is not None and stop_at is None:
            stop_at = k + after
        if stop_at is not None and k >= stop_at:
            break
    c = sorted(res.pop("cycles"))
    res["cycles_median"], res["cycles_max"] = c[len(c) // 2], c[-1]
    return res


def score(out_dir):
    recs = [json.loads(l) for l in (out_dir / "rows.jsonl").read_text().splitlines() if l.strip()]
    keys = {tuple(r["key"]) for r in recs}
    expected = set(rows())
    complete = keys == expected and len(recs) == N_ROWS
    differ = [r["key"] for r in recs if r["board_first"] != r["host_first"]]
    s = {"verdict": ("PASS" if not differ else "FAIL") if complete else ("FAIL" if differ else "INCOMPLETE"),
         "rows": len(recs), "first_inconsistent_differs": differ,
         "flagged_rows": sum(r["host_first"] is not None for r in recs),
         "samples": sum(r["samples"] for r in recs), "samples_bit_equal": sum(r["samples_equal"] for r in recs),
         "S_differs_samples": sum(r["S_differs"] for r in recs),
         "h_below_total": sum(r["h_below"] for r in recs), "h_above_total": sum(r["h_above"] for r in recs),
         "max_ulp_below": max(r["max_ulp_below"] for r in recs), "max_ulp_above": max(r["max_ulp_above"] for r in recs),
         "cycles_max": max(r["cycles_max"] for r in recs)}
    (out_dir / "score.json").write_text(json.dumps(s, indent=1) + "\n")
    print(json.dumps(s, indent=1))
    return s


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("build_dir", type=Path)
    ap.add_argument("out_dir", type=Path)
    ap.add_argument("--port", default="/dev/ttyACM0")
    ap.add_argument("--score", action="store_true")
    a = ap.parse_args()
    if a.score:
        score(a.out_dir)
        return
    a.out_dir.mkdir(parents=True, exist_ok=True)
    out = a.out_dir / "rows.jsonl"
    done = {tuple(json.loads(l)["key"]) for l in out.read_text().splitlines() if l.strip()} if out.exists() else set()
    todo = [k for k in rows() if k not in done]
    fd = ST.open_port(a.port, "avr", 500000)
    time.sleep(2.5)
    banner = ST.wait_banner(fd, "SDTS-")
    if not (a.out_dir / "meta.json").exists():
        (a.out_dir / "meta.json").write_text(json.dumps({"banner": banner, "build": (a.build_dir / "build.txt").read_text(),
                                                         "size": (a.build_dir / "size.txt").read_text(),
                                                         "rows": [list(k) for k in rows()],
                                                         "started": time.strftime("%Y-%m-%dT%H:%M:%S%z")}, indent=1) + "\n")
    print(banner, f"rows to do: {len(todo)}", flush=True)
    for key in todo:
        t0 = time.monotonic()
        for attempt in range(3):
            try:
                res = run_row(fd, str(a.build_dir / "host_trace"), key)
                break
            except (TimeoutError, RuntimeError) as e:
                with (a.out_dir / "infrastructure.log").open("a") as f:
                    f.write(f"{time.strftime('%H:%M:%S')} {key} attempt {attempt}: {e!r}\n")
                os.close(fd)
                fd = ST.open_port(a.port, "avr", 500000)
                time.sleep(2.5)
                ST.wait_banner(fd, "SDTS-")
        else:
            raise SystemExit(f"row {key} failed three times: infrastructure")
        res["wall_s"] = round(time.monotonic() - t0, 1)
        with out.open("a") as f:
            f.write(json.dumps(res) + "\n")
        print(json.dumps({k: res[k] for k in ("key", "board_first", "host_first", "samples", "samples_equal",
                                             "h_below", "h_above", "wall_s")}), flush=True)
    if len(done) + len(todo) == N_ROWS:
        score(a.out_dir)


if __name__ == "__main__":
    main()
