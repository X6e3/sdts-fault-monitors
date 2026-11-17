/* reads "y power" lines, prints the first inconsistent sample (-1 if none) and the state size */
#include <stdio.h>
#include "v3_state.h"
int main(void) {
    v3_state s;
    v3_init(&s);
    double y, p;
    long first = -1, k = 0;
    while (scanf("%lf %lf", &y, &p) == 2) {
        if (v3_observe(&s, y, p) && first < 0) first = k;
        k++;
    }
    printf("first=%ld samples=%ld state_bytes=%zu table_entries=%d\n", first, k, sizeof(v3_state), V3_ENTRIES);
    return 0;
}
