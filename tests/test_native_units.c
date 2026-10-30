#define main collector_main
#include "../collector.c"
#undef main
#include <assert.h>
int main(void) {
    char out[64];
    const unsigned char degree_c[16] = {0xb0, 'C', 0};
    const unsigned char volts[16] = {'V', 0};
    unitfield(out, sizeof out, degree_c);
    assert(!strcmp(out, "\xc2\xb0"
                        "C"));
    unitfield(out, sizeof out, volts);
    assert(!strcmp(out, "V"));
    puts("native unit decoding: OK");
    return 0;
}
