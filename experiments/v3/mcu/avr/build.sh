#!/bin/bash
# Build the AVR firmware and the PC reference for one frozen table header (exploratory; DEV only).
# usage: build.sh MCU TABLE OUTDIR      e.g. build.sh atmega328p cyl16p_float out/uno-cyl16p-float
#   MCU   atmega328p (Uno) or atmega2560 (Mega)
#   TABLE cyl16p_float, cyl16p_double, inv4p_float, inv4p_double (from experiments/v3/frozen/c/)
set -euo pipefail
MCU=$1; TABLE=$2; mkdir -p "$3"; OUT=$(cd "$3" && pwd)
HERE=$(cd "$(dirname "$0")" && pwd)
V3=${V3:-$(cd "$HERE/../.." && pwd)}
FROZEN=$V3/frozen/c/tables_$TABLE.h
mkdir -p "$OUT"
python3 -B "$HERE/make_progmem.py" "$FROZEN" "$OUT/tables_progmem.h"
FLOAT=(); [[ $TABLE == *_float ]] && FLOAT=(-DV3_FLOAT)
TAG="$(cd "$V3" && git rev-parse --short=8 HEAD 2>/dev/null || echo nogit)-$TABLE"
FLAGS=(-std=c11 -Os -ffp-contract=off -fno-fast-math -mdouble=64 -mlong-double=64 -Wall -Wextra)
avr-gcc -mmcu="$MCU" -DF_CPU=16000000UL "${FLAGS[@]}" "${FLOAT[@]}" -DSRC_TAG="\"$TAG\"" \
  -DV3_TABLES="\"$OUT/tables_progmem.h\"" -I"$V3/c" \
  -o "$OUT/fw.elf" "$HERE/main.c" "$HERE/avr_state.c" -lm
avr-objcopy -O ihex -R .eeprom "$OUT/fw.elf" "$OUT/fw.hex"
avr-size --format=avr --mcu="$MCU" "$OUT/fw.elf" > "$OUT/size.txt" 2>/dev/null || avr-size -A "$OUT/fw.elf" > "$OUT/size.txt"
cc -O2 -std=c99 -ffp-contract=off -fno-fast-math "${FLOAT[@]}" -DV3_TABLES="\"$FROZEN\"" -I"$V3/c" \
  -o "$OUT/host_trace" "$HERE/host_trace.c" "$V3/c/v3_state.c" -lm
{ echo "mcu=$MCU table=$TABLE tag=$TAG"; avr-gcc --version | head -1; cc --version | head -1;
  echo "avr flags: ${FLAGS[*]} ${FLOAT[*]}"; sha256sum "$FROZEN" "$OUT/tables_progmem.h" "$HERE/main.c" "$HERE/avr_state.c" "$HERE/host_trace.c" "$V3/c/v3_state.c" "$OUT/fw.hex" "$OUT/host_trace"; } > "$OUT/build.txt"
cat "$OUT/size.txt"
