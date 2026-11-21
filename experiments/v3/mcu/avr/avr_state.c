/* The v3 template state of experiments/v3/c/v3_state.c, for AVR (exploratory; DEV seeds only).

   Same arithmetic, same order of operations. Only two things differ:
   - the tables are in flash (PROGMEM) and are read with pgm_read_* / memcpy_P;
   - nextafter/nextafterf are written out on the bit patterns (avr-libc has no nextafter), with the IEEE 754 meaning:
     the next representable value towards +inf or -inf.
   The command part S must be binary64 (V3_NOTES.md: in float32 its recursion error is unbounded). The build needs
   -mdouble=64; the static assert below refuses anything else. */
#include <math.h>
#include <string.h>
#include <avr/pgmspace.h>
#include "v3_state.h"

_Static_assert(sizeof(double) == 8, "S must be binary64: build with -mdouble=64");

#define CC 30.0
#define CS 12.0
#define KK 2.0
#define HH 0.8
#define P0 20.0
#define SHIFT 25.0
#define DELTA 0.3

static float up_f(float x) {
    uint32_t u;
    memcpy(&u, &x, 4);
    if ((u & 0x7f800000UL) == 0x7f800000UL && (u & 0x007fffffUL)) return x; /* NaN */
    if (u == 0x7f800000UL) return x;                                         /* +inf */
    if ((u & 0x7fffffffUL) == 0) u = 1;                                      /* +-0 -> smallest positive */
    else if (u >> 31) u--;                                                   /* negative: towards zero */
    else u++;
    memcpy(&x, &u, 4);
    return x;
}
static float down_f(float x) { return -up_f(-x); }

static double up_d(double x) {
    uint64_t u;
    memcpy(&u, &x, 8);
    if ((u & 0x7ff0000000000000ULL) == 0x7ff0000000000000ULL && (u & 0x000fffffffffffffULL)) return x;
    if (u == 0x7ff0000000000000ULL) return x;
    if ((u & 0x7fffffffffffffffULL) == 0) u = 1;
    else if (u >> 63) u--;
    else u++;
    memcpy(&x, &u, 8);
    return x;
}
static double down_d(double x) { return -up_d(-x); }

#if defined(V3_FLOAT)
_Static_assert(sizeof(v3_real) == 4, "V3_FLOAT needs the float tables");
#define UP(x) up_f(x)
#define DOWN(x) down_f(x)
static inline v3_real rd_real(const v3_real *p) { return pgm_read_float(p); }
#else
_Static_assert(sizeof(v3_real) == 8, "without V3_FLOAT the double tables are needed");
#define UP(x) up_d(x)
#define DOWN(x) down_d(x)
static inline v3_real rd_real(const v3_real *p) { v3_real v; memcpy_P(&v, p, sizeof v); return v; }
#endif

/* upper bound on the support of the template set in the direction of group g */
static v3_real support(const v3_real *h, int g) {
    v3_real best = (v3_real)INFINITY;
    uint16_t e1 = pgm_read_word(&V3_START[g + 1]);
    for (uint16_t e = pgm_read_word(&V3_START[g]); e < e1; e++) {
        uint8_t i0 = pgm_read_byte(&V3_IDX[e][0]), i1 = pgm_read_byte(&V3_IDX[e][1]),
                i2 = pgm_read_byte(&V3_IDX[e][2]);
        v3_real l0 = rd_real(&V3_LAM[e][0]), l1 = rd_real(&V3_LAM[e][1]), l2 = rd_real(&V3_LAM[e][2]);
        v3_real v = l0 * h[i0] + l1 * h[i1] + l2 * h[i2];
        if (v < best) best = v;
    }
    return UP(best + rd_real(&V3_PAD[g]));
}

void v3_init(v3_state *s) {
    for (int i = 0; i < V3_N; i++) s->h[i] = rd_real(&V3_H0[i]);
    s->ts = P0 / HH;
    s->tc = s->ts + P0 / KK;
    s->inconsistent = 0;
    s->k = 0;
}

int v3_observe(v3_state *s, double y, double power) {
    double z = y - s->ts;
    double tc = s->tc, ts = s->ts;
    s->tc = tc + (power - KK * (tc - ts)) / CC;
    s->ts = ts + (KK * (tc - ts) - HH * ts) / CS;
    s->k++;
    if (s->inconsistent) return 1;
    double zs = z - SHIFT;
    v3_real lo = DOWN((v3_real)down_d(down_d(zs) - DELTA));
    v3_real hi = UP((v3_real)up_d(up_d(zs) + DELTA));
    v3_real top = support(s->h, V3_N), bottom = -support(s->h, V3_N + 1);
    if (top < lo || bottom > hi) {
        s->inconsistent = 1;
        return 1;
    }
    v3_real h[V3_N];
    for (int i = 0; i < V3_N; i++) h[i] = s->h[i];
    if (hi < h[V3_IP2]) h[V3_IP2] = hi;
    if (-lo < h[V3_IM2]) h[V3_IM2] = -lo;
    for (int i = 0; i < V3_N; i++) {
        v3_real v = UP(support(h, i) + rd_real(&V3_RHOPAD[i]));
        v3_real cap = rd_real(&V3_CAP[i]);
        s->h[i] = v < cap ? v : cap;
    }
    return 0;
}
