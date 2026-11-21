// SDTS v3 template state on an ESP32, driven over the serial port (exploratory; DEV seeds only).
// The state code is the unchanged experiments/v3/c/v3_state.c, compiled through v3_wrap.c; prepare.sh copies it and
// the frozen table header into this folder and writes build_cfg.h.
// Protocol as mcu/avr/main.c (SDTS_BAUD, little-endian), except 'M', plus 'B':
//   'M' -> 'm' + free_heap(4) + heap_size(4) + min_free_heap(4) + loop_stack_unused(4)
//   'B' n(2) then n x (y(8) power(8)) -> 'b' + n x (flag(1) + cycles(4) + sha256(dump)[0:16])
//       the same v3_observe per sample; the dump is hashed instead of sent (MCU-2E-PLAN.md)
#include <Arduino.h>
#include "SHA2Builder.h"
extern "C" {
#include "build_cfg.h"
#include "v3_state.h"
}

static v3_state st;

static void dump() {
  Serial.write((const uint8_t *)&st.k, 4);
  Serial.write((const uint8_t *)&st.tc, 8);
  Serial.write((const uint8_t *)&st.ts, 8);
  Serial.write((const uint8_t *)&st.inconsistent, 1);
  Serial.write((const uint8_t *)st.h, sizeof st.h);
}

static size_t dump_to(uint8_t *b) {
  size_t o = 0;
  memcpy(b + o, &st.k, 4); o += 4;
  memcpy(b + o, &st.tc, 8); o += 8;
  memcpy(b + o, &st.ts, 8); o += 8;
  memcpy(b + o, &st.inconsistent, 1); o += 1;
  memcpy(b + o, st.h, sizeof st.h); o += sizeof st.h;
  return o;
}

static void rx_buf(void *p, size_t n) {
  uint8_t *b = (uint8_t *)p;
  while (n) {
    int c = Serial.read();
    if (c >= 0) { *b++ = (uint8_t)c; n--; }
  }
}

void setup() {
  Serial.setRxBufferSize(8192);
  Serial.begin(SDTS_BAUD);
  delay(100);
  v3_init(&st);
  Serial.printf("\nSDTS-MCU board=esp32 src=%s double=%u real=%u N=%u entries=%u state_bytes=%u cpu_hz=%lu baud=%lu\n",
                SRC_TAG, (unsigned)sizeof(double), (unsigned)sizeof(v3_real), (unsigned)V3_N,
                (unsigned)V3_ENTRIES, (unsigned)sizeof(v3_state), (unsigned long)getCpuFrequencyMhz() * 1000000UL, (unsigned long)SDTS_BAUD);
}

void loop() {
  int c = Serial.read();
  if (c < 0) return;
  if (c == 'I') {
    v3_init(&st);
    Serial.write('i');
    dump();
  } else if (c == 'O') {
    double y, p;
    rx_buf(&y, 8);
    rx_buf(&p, 8);
    uint32_t t0 = ESP.getCycleCount();
    uint8_t f = (uint8_t)v3_observe(&st, y, p);
    uint32_t t1 = ESP.getCycleCount();
    uint32_t dt = t1 - t0;
    Serial.write('o');
    Serial.write(f);
    Serial.write((const uint8_t *)&dt, 4);
    dump();
  } else if (c == 'B') {
    static uint8_t out[512 * 21];
    static uint8_t buf[4 + 8 + 8 + 1 + sizeof(st.h)];
    uint16_t n;
    rx_buf(&n, 2);
    if (n > 512) n = 512;
    for (uint16_t i = 0; i < n; i++) {
      double y, p;
      rx_buf(&y, 8);
      rx_buf(&p, 8);
      uint32_t t0 = ESP.getCycleCount();
      uint8_t f = (uint8_t)v3_observe(&st, y, p);
      uint32_t t1 = ESP.getCycleCount();
      uint32_t dt = t1 - t0;
      uint8_t hash[32];
      size_t len = dump_to(buf);
      SHA2Builder sha(32);
      sha.begin();
      sha.add(buf, len);
      sha.calculate();
      sha.getBytes(hash);
      uint8_t *o = out + 21 * i;
      o[0] = f;
      memcpy(o + 1, &dt, 4);
      memcpy(o + 5, hash, 16);
    }
    Serial.write('b');
    Serial.write(out, 21 * (size_t)n);
  } else if (c == 'M') {
    uint32_t v[4] = {ESP.getFreeHeap(), ESP.getHeapSize(), ESP.getMinFreeHeap(),
                     (uint32_t)uxTaskGetStackHighWaterMark(NULL)};
    Serial.write('m');
    Serial.write((const uint8_t *)v, sizeof v);
  }
}
