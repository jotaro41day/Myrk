/* Independent scalar C oracle/baseline. REAL and R(x) selected by driver.
 * Keep the specified Euler operation order; no calls to Myrk code.
 * Compiler is allowed to vectorize this reference with the SAME flags.
 */
static int32_t reference_step(int32_t count, REAL * restrict voltage,
    REAL * restrict recovery, REAL a, REAL b, REAL c, REAL d, REAL dt, REAL input) {
    int32_t total = 0;
    for (int32_t j = 0; j < count; ++j) {
        REAL x = voltage[j];
        REAL y = recovery[j];
        REAL dv = R(0.04) * x;
        dv = dv * x;
        dv = dv + R(5.0) * x;
        dv = dv + R(140.0);
        dv = dv - y;
        dv = dv + input;
        REAL du = b * x;
        du = du - y;
        du = a * du;
        x = x + dt * dv;
        y = y + dt * du;
        if (x >= R(30.0)) {
            x = c;
            y = y + d;
            ++total;
        }
        voltage[j] = x;
        recovery[j] = y;
    }
    return total;
}
