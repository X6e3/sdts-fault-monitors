// ESP32 floating-point check (exploratory), same protocol as mcu/avr/fptest.c:
//   'm' 'a' 's' float a b -> a*b, a+b, a-b; 'M' 'A' 'S' double; 'c' double -> float. 500000 baud.
// Built with -ffp-contract=off. Operands go through volatile variables so nothing is folded at compile time.
#include <Arduino.h>

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
  Serial.printf("\nFPTEST board=esp32 double=%u\n", (unsigned)sizeof(double));
}

void loop() {
  int op = Serial.read();
  if (op < 0) return;
  if (op == 'm' || op == 'a' || op == 's') {
    float ta, tb;
    rx_buf(&ta, 4); rx_buf(&tb, 4);
    volatile float a = ta, b = tb;
    float r = op == 'm' ? a * b : op == 'a' ? a + b : a - b;
    Serial.write((const uint8_t *)&r, 4);
  } else if (op == 'M' || op == 'A' || op == 'S') {
    double ta, tb;
    rx_buf(&ta, 8); rx_buf(&tb, 8);
    volatile double a = ta, b = tb;
    double r = op == 'M' ? a * b : op == 'A' ? a + b : a - b;
    Serial.write((const uint8_t *)&r, 8);
  } else if (op == 'c') {
    double ta;
    rx_buf(&ta, 8);
    volatile double a = ta;
    float r = (float)a;
    Serial.write((const uint8_t *)&r, 4);
  }
}
