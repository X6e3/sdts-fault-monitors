/* AVR floating-point check (exploratory): does the board round like IEEE 754 round-to-nearest-even?
   Serial 500000 8N1. PC -> board: op(1) a b  -> board: result. Little-endian.
     'm' 'a' 's'  float  a(4) b(4) -> a*b, a+b, a-b (4)
     'M' 'A' 'S'  double a(8) b(8) -> a*b, a+b, a-b (8)   (needs -mdouble=64)
     'c'          double a(8)      -> (float)a (4)
   At reset: one line "FPTEST double=8". */
#include <avr/io.h>
#include <stdint.h>
#include <string.h>

_Static_assert(sizeof(double) == 8, "build with -mdouble=64");

static void tx(uint8_t c) { while (!(UCSR0A & (1 << UDRE0))) {} UDR0 = c; }
static uint8_t rx(void) { while (!(UCSR0A & (1 << RXC0))) {} return UDR0; }
static void tx_buf(const void *p, uint8_t n) { const uint8_t *b = p; while (n--) tx(*b++); }
static void rx_buf(void *p, uint8_t n) { uint8_t *b = p; while (n--) *b++ = rx(); }

int main(void) {
    UBRR0H = 0; UBRR0L = 3; UCSR0A = (1 << U2X0);
    UCSR0B = (1 << RXEN0) | (1 << TXEN0); UCSR0C = (1 << UCSZ01) | (1 << UCSZ00);
    const char *s = "FPTEST double=8\n";
    while (*s) tx((uint8_t)*s++);
    for (;;) {
        uint8_t op = rx();
        if (op == 'm' || op == 'a' || op == 's') {
            volatile float a, b; float r;
            float ta, tb;
            rx_buf(&ta, 4); rx_buf(&tb, 4); a = ta; b = tb;
            r = op == 'm' ? a * b : op == 'a' ? a + b : a - b;
            tx_buf(&r, 4);
        } else if (op == 'M' || op == 'A' || op == 'S') {
            volatile double a, b; double r;
            double ta, tb;
            rx_buf(&ta, 8); rx_buf(&tb, 8); a = ta; b = tb;
            r = op == 'M' ? a * b : op == 'A' ? a + b : a - b;
            tx_buf(&r, 8);
        } else if (op == 'c') {
            volatile double a; double ta; float r;
            rx_buf(&ta, 8); a = ta;
            r = (float)a;
            tx_buf(&r, 4);
        }
    }
}
