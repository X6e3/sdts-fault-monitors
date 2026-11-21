"""Copy a frozen v3 table header for AVR: every table goes to flash (PROGMEM). Nothing else changes.

The frozen header is read, never written. The copy names the source file and its sha256 in its first line, and
check() confirms that removing the PROGMEM words gives back the source byte for byte (apart from that line and the
pgmspace include).
usage: python -B make_progmem.py FROZEN_HEADER OUT_HEADER
"""
import hashlib
import re
import sys
from pathlib import Path

ARRAY = re.compile(r"^(static const \w+ V3_\w+(?:\[[^\]]*\])+)( = \{)", re.M)


def convert(src_text, src_name, src_sha):
    body, n = ARRAY.subn(r"\1 PROGMEM\2", src_text)
    if n != 7:
        raise SystemExit(f"expected 7 tables, found {n}")
    head = f"/* AVR copy of {src_name} (sha256 {src_sha}); tables in PROGMEM; made by make_progmem.py */\n"
    body = body.replace("#include <stdint.h>\n", "#include <stdint.h>\n#include <avr/pgmspace.h>\n", 1)
    return head + body


def check(src_text, out_text):
    lines = out_text.split("\n", 1)[1]
    lines = lines.replace("#include <avr/pgmspace.h>\n", "", 1).replace(" PROGMEM = {", " = {")
    if lines != src_text:
        raise SystemExit("the copy differs from the frozen header beyond PROGMEM")


def main():
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    raw = src.read_bytes()
    text = raw.decode()
    out_text = convert(text, src.name, hashlib.sha256(raw).hexdigest())
    check(text, out_text)
    out.write_text(out_text)
    print(f"{out}: from {src.name} sha256 {hashlib.sha256(raw).hexdigest()}")


if __name__ == "__main__":
    main()
