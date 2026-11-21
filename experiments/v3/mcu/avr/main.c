/* SDTS v3 template state on an AVR board, driven over the serial port (exploratory; DEV seeds only).

   Serial 500000 baud 8N1 (U2X, UBRR 3: exact at 16 MHz). Little-endian binary.
   PC -> board:
     'I'                      v3_init; reply 'i' + dump
     'O' y(8) power(8)        v3_observe with binary64 y and power; reply 'o' + flag(1) + cycles(4) + dump
     'M'                      reply 'm' + stack high-water bytes(2) + static RAM bytes(2) + total RAM bytes(2)
   dump = k(4) + tc(8) + ts(8) + inconsistent(1) + h[V3_N] (sizeof v3_real each)
   cycles: Timer1 at the CPU clock, counted around v3_observe only.
   At reset the board prints one text line "SDTS-AVR ..." with its build facts. */
#include <avr/interrupt.h>
#include <avr/io.h>
#include <stdint.h>
#include <string.h>
#include "v3_state.h"

#ifndef SRC_TAG
#define SRC_TAG "unknown"
#endif

static volatile uint16_t ovf;
ISR(TIMER1_OVF_vect) { ovf++; }

static void uart_init(void) {
    UBRR0H = 0;
    UBRR0L = 3;
    UCSR0A = (1 << U2X0);
    UCSR0B = (1 << RXEN0) | (1 << TXEN0);
    UCSR0C = (1 << UCSZ01) | (1 << UCSZ00);
}
static void tx(uint8_t c) {
    while (!(UCSR0A & (1 << UDRE0))) {}
    UDR0 = c;
}
static uint8_t rx(void) {
    while (!(UCSR0A & (1 << RXC0))) {}
    return UDR0;
}
static void tx_buf(const void *p, uint16_t n) {
    const uint8_t *b = p;
    while (n--) tx(*b++);
}
static void rx_buf(void *p, uint16_t n) {
    uint8_t *b = p;
    while (n--) *b++ = rx();
}
static void tx_str(const char *s) {
    while (*s) tx((uint8_t)*s++);
}
static void tx_dec(uint32_t v) {
    char b[11];
    int i = 10;
    b[i] = 0;
    do { b[--i] = (char)('0' + v % 10); v /= 10; } while (v);
    tx_str(&b[i]);
}

static uint32_t cycles_now(void) {
    uint8_t sreg = SREG;
    cli();
    uint16_t lo = TCNT1, hi = ovf;
    if ((TIFR1 & (1 << TOV1)) && lo < 0x8000) hi++;
    SREG = sreg;
    return ((uint32_t)hi << 16) | lo;
}

/* stack high-water: paint the free RAM at start, count what stays painted */
extern uint8_t _end, __stack;
#define PAINT 0xc5
/* runs in .init1, before the C runtime is set up, so it is written in assembly (avr-libc stack-painting idiom) */
static void paint(void) __attribute__((naked, used, section(".init1")));
static void paint(void) {
    __asm volatile("    ldi r30,lo8(_end)\n"
                   "    ldi r31,hi8(_end)\n"
                   "    ldi r24,lo8(0xc5)\n"
                   "    ldi r25,hi8(__stack)\n"
                   "    rjmp 2f\n"
                   "1:  st Z+,r24\n"
                   "2:  cpi r30,lo8(__stack)\n"
                   "    cpc r31,r25\n"
                   "    brlo 1b\n"
                   "    breq 1b\n" ::);
}
static uint16_t untouched(void) {
    const uint8_t *p = &_end;
    uint16_t n = 0;
    while (p <= &__stack && *p == PAINT) { p++; n++; }
    return n;
}

static v3_state st;

static void dump(void) {
    tx_buf(&st.k, 4);
    tx_buf(&st.tc, 8);
    tx_buf(&st.ts, 8);
    tx_buf(&st.inconsistent, 1);
    tx_buf(st.h, sizeof st.h);
}

int main(void) {
    uart_init();
    TCCR1A = 0;
    TCCR1B = (1 << CS10);
    TIMSK1 = (1 << TOIE1);
    sei();
    v3_init(&st);
    tx_str("SDTS-AVR src=" SRC_TAG " double=");
    tx_dec(sizeof(double));
    tx_str(" real=");
    tx_dec(sizeof(v3_real));
    tx_str(" N=");
    tx_dec(V3_N);
    tx_str(" entries=");
    tx_dec(V3_ENTRIES);
    tx_str(" state_bytes=");
    tx_dec(sizeof(v3_state));
    tx_str("\n");
    for (;;) {
        uint8_t c = rx();
        if (c == 'I') {
            v3_init(&st);
            tx('i');
            dump();
        } else if (c == 'O') {
            double y, p;
            rx_buf(&y, 8);
            rx_buf(&p, 8);
            uint32_t t0 = cycles_now();
            uint8_t f = (uint8_t)v3_observe(&st, y, p);
            uint32_t t1 = cycles_now();
            uint32_t dt = t1 - t0;
            tx('o');
            tx(f);
            tx_buf(&dt, 4);
            dump();
        } else if (c == 'M') {
            uint16_t free_b = untouched();
            uint16_t static_b = (uint16_t)((uintptr_t)&_end - RAMSTART);
            uint16_t total_b = (uint16_t)(RAMEND - RAMSTART + 1);
            tx('m');
            tx_buf(&free_b, 2);
            tx_buf(&static_b, 2);
            tx_buf(&total_b, 2);
        }
    }
}
