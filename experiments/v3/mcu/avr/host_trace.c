/* The PC reference for the AVR runs: the unchanged experiments/v3/c/v3_state.c, fed "y power" lines (Python repr,
   exact binary64), printing after each sample the same dump the board sends, as hex of the little-endian bytes:
   flag k tc ts inconsistent h.  First line: the dump after v3_init. */
#include <stdio.h>
#include <string.h>
#include "v3_state.h"

static void hex(const void *p, size_t n) {
    const unsigned char *b = p;
    for (size_t i = 0; i < n; i++) printf("%02x", b[i]);
}
static void dump(const v3_state *s) {
    hex(&s->k, 4);
    hex(&s->tc, 8);
    hex(&s->ts, 8);
    hex(&s->inconsistent, 1);
    hex(s->h, sizeof s->h);
    printf("\n");
}
int main(void) {
    v3_state s;
    v3_init(&s);
    printf("i ");
    dump(&s);
    double y, p;
    while (scanf("%lf %lf", &y, &p) == 2) {
        int f = v3_observe(&s, y, p);
        printf("o %02x ", f);
        dump(&s);
    }
    return 0;
}
