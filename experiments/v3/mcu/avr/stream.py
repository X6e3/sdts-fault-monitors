"""Drive the board (AVR or ESP32) with DEV runs and compare it with the PC reference, sample by sample (exploratory; DEV only).

For each run: the generator's y and P (DEV seeds only) go to the board as binary64 over the serial port and, as
Python repr text, to the PC reference (host_trace: the unchanged v3_state.c). After every sample the board's dump and
the reference's dump are compared byte for byte. The board's cycle count per sample is kept.
usage: python -B stream.py BUILD_DIR OUT_JSON --port /dev/ttyACM0 [--board avr|esp32] --run SEED:CELL:ARM:AMBIENT:NOISE [...]
       [--after N]   samples to keep going after both have flagged (default 3); a healthy run goes to the end
"""
import argparse
import fcntl
import json
import os
import select
import struct
import subprocess
import sys
import termios
import time
from pathlib import Path

V3 = Path(os.environ.get("V3", Path(__file__).resolve().parents[2]))
sys.path[:0] = [str(V3), str(V3.parent / "generators")]
import dev_scenarios as S  # noqa: E402

T = S.T
F_CPU = 16_000_000


def open_port(path, board="avr", baud=500000):
    fd = os.open(path, os.O_RDWR | os.O_NOCTTY)
    a = termios.tcgetattr(fd)
    a[0] = 0                                  # iflag
    a[1] = 0                                  # oflag
    a[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
    a[3] = 0                                  # lflag
    a[4] = a[5] = {500000: termios.B500000, 921600: termios.B921600, 115200: termios.B115200}[baud]
    a[6][termios.VMIN], a[6][termios.VTIME] = 0, 0
    termios.tcsetattr(fd, termios.TCSANOW, a)
    dtr, rts = struct.pack("I", termios.TIOCM_DTR), struct.pack("I", termios.TIOCM_RTS)
    if board == "esp32":
        # IO0 high (DTR off), then pulse EN low with RTS: a normal boot, never the download mode
        fcntl.ioctl(fd, termios.TIOCMBIC, dtr)
        fcntl.ioctl(fd, termios.TIOCMBIS, rts)
        time.sleep(0.15)
        termios.tcflush(fd, termios.TCIOFLUSH)
        fcntl.ioctl(fd, termios.TIOCMBIC, rts)
    else:
        # reset the AVR board on purpose: drop DTR, raise it again (the port may have been left with DTR high)
        fcntl.ioctl(fd, termios.TIOCMBIC, dtr)
        time.sleep(0.2)
        termios.tcflush(fd, termios.TCIOFLUSH)
        fcntl.ioctl(fd, termios.TIOCMBIS, dtr)
    return fd


def wait_banner(fd, prefix, timeout=8.0):
    """the first line that contains prefix, from prefix on (an ESP32 prints boot text at another baud rate first)"""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            line = read_line(fd, max(0.1, end - time.monotonic()))
        except TimeoutError:
            break
        if prefix in line:
            return line[line.index(prefix):]
    raise SystemExit(f"no {prefix!r} banner")


def read_exact(fd, n, timeout=10.0):
    buf, end = b"", time.monotonic() + timeout
    while len(buf) < n:
        left = end - time.monotonic()
        if left <= 0:
            raise TimeoutError(f"wanted {n} bytes, got {len(buf)}")
        r, _, _ = select.select([fd], [], [], left)
        if r:
            buf += os.read(fd, n - len(buf))
    return buf


def read_line(fd, timeout=5.0):
    buf = b""
    while not buf.endswith(b"\n"):
        buf += read_exact(fd, 1, timeout)
    return buf.decode(errors="replace").strip()


def host_dumps(binary, y, P):
    text = "".join(f"{a!r} {b!r}\n" for a, b in zip(y, P))
    lines = subprocess.run([binary], input=text, capture_output=True, text=True, check=True).stdout.splitlines()
    init = bytes.fromhex(lines[0].split()[1])
    obs = [(int(l.split()[1], 16), bytes.fromhex(l.split()[2])) for l in lines[1:]]
    return init, obs


def field_of(offset, real):
    names = [("k", 4), ("tc", 8), ("ts", 8), ("inconsistent", 1)]
    o = 0
    for name, n in names:
        if offset < o + n:
            return name
        o += n
    return f"h[{(offset - o) // real}]"


def run_one(fd, info, host, key, after):
    seed, cell_name, arm, al, nl = key
    if seed not in S.DEV:
        raise SystemExit(f"DEV seeds only, got {seed}")
    cell = next(c for c in T.CELLS if c.name == cell_name)
    r = S.run(seed, cell, arm, al, nl)
    y, P = r["y"], r["P"]
    h_init, h_obs = host_dumps(host, y, P)
    real, n = info["real"], info["N"]
    dlen = 4 + 8 + 8 + 1 + n * real
    os.write(fd, b"I")
    if read_exact(fd, 1) != b"i":
        raise RuntimeError("no init reply")
    b_init = read_exact(fd, dlen)
    res = {"key": list(key), "init_equal": b_init == h_init, "samples": 0, "mismatches": 0, "first_mismatch": None,
           "board_first": None, "host_first": None, "cycles": []}
    stop_at = None
    for k, (yy, pp) in enumerate(zip(y, P)):
        os.write(fd, b"O" + struct.pack("<dd", yy, pp))
        hdr = read_exact(fd, 6)
        if hdr[:1] != b"o":
            raise RuntimeError(f"bad reply at {k}: {hdr!r}")
        flag, cyc = hdr[1], struct.unpack("<I", hdr[2:6])[0]
        dump = read_exact(fd, dlen)
        hflag, hdump = h_obs[k]
        res["samples"] += 1
        res["cycles"].append(cyc)
        if flag and res["board_first"] is None:
            res["board_first"] = k
        if hflag and res["host_first"] is None:
            res["host_first"] = k
        if flag != hflag or dump != hdump:
            res["mismatches"] += 1
            if res["first_mismatch"] is None:
                off = next((i for i in range(dlen) if dump[i] != hdump[i]), None)
                res["first_mismatch"] = {"sample": k, "flag_board": flag, "flag_host": hflag,
                                         "field": None if off is None else field_of(off, real)}
        if res["board_first"] is not None and res["host_first"] is not None and stop_at is None:
            stop_at = k + after
        if stop_at is not None and k >= stop_at:
            break
    c = sorted(res["cycles"])
    res["cycles_summary"] = {"median": c[len(c) // 2], "max": c[-1], "min": c[0],
                             "median_ms": c[len(c) // 2] / F_CPU * 1e3, "max_ms": c[-1] / F_CPU * 1e3}
    res["t_f"] = r["t_f"]
    del res["cycles"]
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("build_dir", type=Path)
    ap.add_argument("out_json", type=Path)
    ap.add_argument("--port", default="/dev/ttyACM0")
    ap.add_argument("--run", action="append", required=True)
    ap.add_argument("--after", type=int, default=3)
    ap.add_argument("--board", choices=("avr", "esp32"), default="avr")
    a = ap.parse_args()
    keys = []
    for s in a.run:
        seed, cell, arm, al, nl = s.split(":")
        keys.append((int(seed), cell, arm, al, nl))
    fd = open_port(a.port, a.board)
    time.sleep(2.5 if a.board == "avr" else 0.2)
    banner = wait_banner(fd, "SDTS-")
    info = {kv.split("=")[0]: kv.split("=")[1] for kv in banner.split()[1:]}
    info = {k: (int(v) if v.isdigit() else v) for k, v in info.items()}
    if info["double"] != 8:
        raise SystemExit("board double is not binary64")
    global F_CPU
    F_CPU = int(info.get("cpu_hz", F_CPU))
    out = {"banner": banner, "build": (a.build_dir / "build.txt").read_text(),
           "size": (a.build_dir / "size.txt").read_text(), "runs": []}
    for key in keys:
        t0 = time.monotonic()
        res = run_one(fd, info, str(a.build_dir / "host_trace"), key, a.after)
        res["wall_s"] = round(time.monotonic() - t0, 1)
        out["runs"].append(res)
        print(json.dumps({k: v for k, v in res.items()}), flush=True)
        a.out_json.write_text(json.dumps(out, indent=1) + "\n")
    os.write(fd, b"M")
    if read_exact(fd, 1) == b"m":
        if a.board == "avr":
            free_b, static_b, total_b = struct.unpack("<HHH", read_exact(fd, 6))
            out["ram"] = {"total": total_b, "static": static_b, "never_touched": free_b,
                          "peak_used": total_b - free_b}
        else:
            free_h, heap, min_free, stack_unused = struct.unpack("<IIII", read_exact(fd, 16))
            out["ram"] = {"heap_size": heap, "free_heap": free_h, "min_free_heap": min_free,
                          "loop_stack_unused": stack_unused}
        print(json.dumps(out["ram"]))
    a.out_json.write_text(json.dumps(out, indent=1) + "\n")


if __name__ == "__main__":
    main()
