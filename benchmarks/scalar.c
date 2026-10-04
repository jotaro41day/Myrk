#include <stdint.h>
#include <stdio.h>

int main(void) {
    int32_t total = 0;
    for (int32_t i = 0; i < 50000000; ++i) {
        total += i % 7;
    }
    printf("%d\n", (int)total);
    return 0;
}
