#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv) {
    if (argc != 3) {
        fputs("usage: lif_reference NEURONS STEPS\n", stderr);
        return 2;
    }
    long neurons = strtol(argv[1], NULL, 10);
    long steps = strtol(argv[2], NULL, 10);
    if (neurons < 1 || steps < 1 || neurons > 1000000 || steps > 1000000) {
        fputs("invalid dimensions\n", stderr);
        return 2;
    }
    double *voltage = calloc((size_t)neurons, sizeof(double));
    if (!voltage) {
        fputs("allocation failed\n", stderr);
        return 2;
    }
    uint64_t spikes = 0;
    for (long t = 0; t < steps; ++t) {
        for (long i = 0; i < neurons; ++i) {
            double input = 1.2 + (double)(i % 7) * 0.1;
            double v = voltage[i] + (input - voltage[i]) * 0.05;
            if (v >= 1.0) {
                ++spikes;
                v = 0.0;
            }
            voltage[i] = v;
        }
    }
    double sum = 0.0;
    for (long i = 0; i < neurons; ++i) {
        sum += voltage[i];
    }
    printf("%llu %.12f\n", (unsigned long long)spikes, sum);
    free(voltage);
    return 0;
}
