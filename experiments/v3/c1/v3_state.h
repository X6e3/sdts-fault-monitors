/* SDTS v3 template information state: fixed memory, no LP, no allocation. Tables come from
   experiments/v3/codegen_c.py (V3_TABLES selects the generated header). */
#ifndef V3_STATE_H
#define V3_STATE_H
#include <stdint.h>
#include V3_TABLES

typedef struct {
    v3_real h[V3_N];      /* template supports of the physical state (ac, as, TA), shifted by -25 C */
    double tc, ts;        /* the known command part S (core, surface), in double: see V3_NOTES.md */
    uint8_t inconsistent; /* absorbing: no admissible explanation with b = 0 exists */
    uint32_t k;
} v3_state;

void v3_init(v3_state *s);
/* one measurement y and the command applied after it; returns 1 once inconsistent */
int v3_observe(v3_state *s, double y, double power);
#endif
