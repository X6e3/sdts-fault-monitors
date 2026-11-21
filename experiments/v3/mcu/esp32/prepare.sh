#!/bin/bash
# Prepare and build the ESP32 sketch for one frozen table header, and the PC reference (exploratory; DEV only).
# usage: prepare.sh TABLE OUTDIR      TABLE: cyl16p_float, cyl16p_double, inv4p_float, inv4p_double
# Copies the unchanged c/v3_state.c and c/v3_state.h and the frozen header into a build copy of the sketch,
# checks their sha256 against the sources, compiles with -ffp-contract=off, and checks the object for fused
# multiply-adds (madd.s / msub.s), which would change the arithmetic.
set -euo pipefail
TABLE=$1
mkdir -p "$2"; OUT=$(cd "$2" && pwd)
HERE=$(cd "$(dirname "$0")" && pwd)
V3=${V3:-$(cd "$HERE/../.." && pwd)}
FROZEN=$V3/frozen/c/tables_$TABLE.h
SK=$OUT/sdts_esp32
rm -rf "$SK"; mkdir -p "$SK"
cp "$HERE/sdts_esp32/sdts_esp32.ino" "$HERE/sdts_esp32/v3_wrap.c" "$SK/"
cp "$V3/c/v3_state.c" "$SK/v3_state.c.inc"
cp "$V3/c/v3_state.h" "$SK/v3_state.h"
cp "$FROZEN" "$SK/tables.h"
for p in "$V3/c/v3_state.c:$SK/v3_state.c.inc" "$V3/c/v3_state.h:$SK/v3_state.h" "$FROZEN:$SK/tables.h"; do
  a=$(sha256sum "${p%%:*}" | cut -d' ' -f1); b=$(sha256sum "${p##*:}" | cut -d' ' -f1)
  [ "$a" = "$b" ] || { echo "copy differs: $p"; exit 1; }
done
TAG="$(cd "$V3" && git rev-parse --short=8 HEAD 2>/dev/null || echo nogit)-$TABLE"
{ echo "#define V3_TABLES \"tables.h\""; [[ $TABLE == *_float ]] && echo "#define V3_FLOAT"; echo "#define SRC_TAG \"$TAG\""; } > "$SK/build_cfg.h"
FLAGS="-ffp-contract=off -fno-fast-math"
arduino-cli compile --fqbn esp32:esp32:esp32 --build-path "$OUT/build" \
  --build-property "compiler.c.extra_flags=$FLAGS" --build-property "compiler.cpp.extra_flags=$FLAGS" \
  "$SK" 2>&1 | grep -E '^(Sketch uses|Global variables)' | tee "$OUT/size.txt"
OBJ=$(find "$OUT/build" -name 'v3_wrap.c.o' | head -1)
OBJDUMP=$(find ~/.arduino15/packages/esp32/tools -name 'xtensa-esp32-elf-objdump' -o -name 'xtensa-esp-elf-objdump' | head -1)
FUSED=$("$OBJDUMP" -d "$OBJ" | grep -c -E '\s(madd|msub|maddn|msubn)\.s\s' || true)
echo "fused multiply-adds in v3_state: $FUSED"
[ "$FUSED" = "0" ] || { echo "the build fuses multiply-adds: refuse"; exit 1; }
FLOAT=(); [[ $TABLE == *_float ]] && FLOAT=(-DV3_FLOAT)
cc -O2 -std=c99 -ffp-contract=off -fno-fast-math "${FLOAT[@]}" -DV3_TABLES="\"$FROZEN\"" -I"$V3/c" \
  -o "$OUT/host_trace" "$HERE/../avr/host_trace.c" "$V3/c/v3_state.c" -lm
{ echo "board=esp32 table=$TABLE tag=$TAG"; arduino-cli version; arduino-cli core list | grep esp32; cc --version | head -1;
  echo "extra flags: $FLAGS"; echo "fused multiply-adds: $FUSED";
  sha256sum "$FROZEN" "$V3/c/v3_state.c" "$V3/c/v3_state.h" "$SK"/* "$OUT/build/sdts_esp32.ino.bin" "$OUT/host_trace"; } > "$OUT/build.txt"
ls -la "$OUT/build/sdts_esp32.ino.bin"
