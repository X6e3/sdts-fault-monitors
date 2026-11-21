// SDTS v3 template state on an ESP32, driven over the serial port (exploratory; DEV seeds only).
// The state code is the unchanged experiments/v3/c/v3_state.c, compiled through v3_wrap.c; prepare.sh copies it and
// the frozen table header into this folder and writes build_cfg.h.
// Protocol as mcu/avr/main.c (500000 baud, little-endian), except 'M':
//   'M' -> 'm' + free_heap(4) + heap_size(4) + min_free_heap(4) + loop_stack_unused(4)
#include <Arduino.h>
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

static void rx_buf(void *p, size_t n) {
  uint8_t *b = (uint8_t *)p;
  while (n) {
    int c = Serial.read();
    if (c >= 0) { *b++ = (uint8_t)c; n--; }
  }
}

void setup() {
  Serial.begin(500000);
  delay(100);
  v3_init(&st);
  Serial.printf("\nSDTS-MCU board=esp32 src=%s double=%u real=%u N=%u entries=%u state_bytes=%u cpu_hz=%lu\n",
                SRC_TAG, (unsigned)sizeof(double), (unsigned)sizeof(v3_real), (unsigned)V3_N,
                (unsigned)V3_ENTRIES, (unsigned)sizeof(v3_state), (unsigned long)getCpuFrequencyMhz() * 1000000UL);
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
  } else if (c == 'M') {
    uint32_t v[4] = {ESP.getFreeHeap(), ESP.getHeapSize(), ESP.getMinFreeHeap(),
                     (uint32_t)uxTaskGetStackHighWaterMark(NULL)};
    Serial.write('m');
    Serial.write((const uint8_t *)v, sizeof v);
  }
}
