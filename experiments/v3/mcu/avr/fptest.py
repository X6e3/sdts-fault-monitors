"""Compare the board's float and double arithmetic with IEEE 754 round-to-nearest-even (numpy on the PC).

Operands are drawn the way the template state uses them: table weights in [0, 1], supports in [-4, 4], plus random
bit patterns of normal floats. Reports, per operation, how many results are bit-equal and, for the others, the
signed error in ulps of the PC result and whether the board's result is nearer to zero (truncation-like).
usage: python -B fptest.py OUT_JSON [--port /dev/ttyACM0] [--board avr|esp32] [--n 2000] [--seed 1]
"""
import argparse
import json
import random
import struct
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stream as ST  # noqa: E402


def f32(x):
    return np.float32(x)


def bits32(x):
    return struct.unpack("<i", struct.pack("<f", float(x)))[0]


def bits64(x):
    return struct.unpack("<q", struct.pack("<d", float(x)))[0]


def operands(rng, n, kind):
    out = []
    for i in range(n):
        if i % 3 == 0:
            a, b = rng.uniform(0, 1), rng.uniform(-4, 4)
        elif i % 3 == 1:
            a, b = rng.uniform(-4, 4), rng.uniform(-4, 4)
        else:
            while True:
                e = rng.randint(-20, 20)
                a, b = rng.uniform(1, 2) * 2.0 ** e * rng.choice((-1, 1)), rng.uniform(1, 2) * 2.0 ** rng.randint(-20, 20)
                break
        if kind == "f":
            a, b = float(f32(a)), float(f32(b))
        out.append((a, b))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("out_json", type=Path)
    ap.add_argument("--port", default="/dev/ttyACM0")
    ap.add_argument("--n", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--board", choices=("avr", "esp32"), default="avr")
    a = ap.parse_args()
    rng = random.Random(a.seed)
    fd = ST.open_port(a.port, a.board)
    time.sleep(2.5 if a.board == "avr" else 0.2)
    banner = ST.wait_banner(fd, "FPTEST")
    report = {"banner": banner, "n": a.n, "seed": a.seed, "ops": {}}
    with np.errstate(all="ignore"):
        for op, kind in (("m", "f"), ("a", "f"), ("s", "f"), ("M", "d"), ("A", "d"), ("S", "d"), ("c", "d")):
            stats, examples = Counter(), []
            for x, y in operands(rng, a.n, kind):
                if kind == "f":
                    os_ = struct.pack("<ff", x, y)
                    ref = {"m": f32(x) * f32(y), "a": f32(x) + f32(y), "s": f32(x) - f32(y)}[op]
                    ST.os.write(fd, op.encode() + os_)
                    got = struct.unpack("<f", ST.read_exact(fd, 4))[0]
                    d = bits32(got) - bits32(ref)
                elif op == "c":
                    ref = f32(x)
                    ST.os.write(fd, b"c" + struct.pack("<d", x))
                    got = struct.unpack("<f", ST.read_exact(fd, 4))[0]
                    d = bits32(got) - bits32(ref)
                else:
                    ref = {"M": x * y, "A": x + y, "S": x - y}[op]
                    ST.os.write(fd, op.encode() + struct.pack("<dd", x, y))
                    got = struct.unpack("<d", ST.read_exact(fd, 8))[0]
                    d = bits64(got) - bits64(ref)
                if d == 0:
                    stats["equal"] += 1
                else:
                    toward_zero = abs(got) < abs(float(ref))
                    stats[f"ulp {d:+d}, {'toward zero' if toward_zero else 'away from zero'}"] += 1
                    if len(examples) < 5:
                        examples.append({"a": x, "b": y, "board": got, "ieee_rne": float(ref)})
            report["ops"][op] = {"stats": dict(stats), "examples": examples}
            print(op, dict(stats), flush=True)
    a.out_json.write_text(json.dumps(report, indent=1) + "\n")


if __name__ == "__main__":
    main()
