#include <math.h>
#include "v3_state.h"

#define CC 30.0
#define CS 12.0
#define KK 2.0
#define HH 0.8
#define P0 20.0
#define SHIFT 25.0
#define DELTA 0.3
#define ETA 1e-9   /* c1: allowance for the float error of S and of the data, F3's value (C1-PLAN.md) */

#if defined(V3_FLOAT)
#define UP(x) nextafterf((x), INFINITY)
#define DOWN(x) nextafterf((x), -INFINITY)
#else
#define UP(x) nextafter((x), INFINITY)
#define DOWN(x) nextafter((x), -INFINITY)
#endif

/* upper bound on the support of the template set in the direction of group g */
static v3_real support(const v3_real *h, int g) {
    v3_real best = (v3_real)INFINITY;
    for (uint16_t e = V3_START[g]; e < V3_START[g + 1]; e++) {
        const uint8_t *i = V3_IDX[e];
        const v3_real *l = V3_LAM[e];
        v3_real v = l[0] * h[i[0]] + l[1] * h[i[1]] + l[2] * h[i[2]];
        if (v < best) best = v;
    }
    return UP(best + V3_PAD[g]);
}

void v3_init(v3_state *s) {
    for (int i = 0; i < V3_N; i++) s->h[i] = V3_H0[i];
    s->ts = P0 / HH;              /* steady state at command P0 and zero ambient */
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
    v3_real lo = DOWN((v3_real)nextafter(nextafter(zs, -INFINITY) - (DELTA + ETA), -INFINITY));
    v3_real hi = UP((v3_real)nextafter(nextafter(zs, INFINITY) + (DELTA + ETA), INFINITY));
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
        v3_real v = UP(support(h, i) + V3_RHOPAD[i]);
        s->h[i] = v < V3_CAP[i] ? v : V3_CAP[i];
    }
    return 0;
}
