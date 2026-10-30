#define main collector_main
#include "../collector.c"
#undef main
#include <assert.h>
static void set32(unsigned char *b, size_t off, uint32_t v) {
    memcpy(b + off, &v, 4);
}
int main(void) {
    unsigned char b[48 + 264 + 316] = {0};
    set32(b, 0, 0x53695748);
    set32(b, 4, 2);
    set32(b, 20, 48);
    set32(b, 24, 264);
    set32(b, 28, 1);
    set32(b, 32, 312);
    set32(b, 36, 316);
    set32(b, 40, 1);
    set32(b, 48, 1);
    set32(b, 52, 2);
    memcpy(b + 56, "DIMM #0", 8);
    set32(b, 312, 1);
    set32(b, 316, 0);
    set32(b, 320, 3);
    memcpy(b + 324, "SPD Hub Temperature", 20);
    b[580] = 0xb0;
    b[581] = 'C';
    double value = NAN;
    memcpy(b + 596, &value, 8);
    InitializeCriticalSection(&lock);
    strcpy(session, "native-fixture");
    assert(serialize_sensor(1, b, sizeof b) == 1);
    assert(serialize_sensor(0, b, sizeof b) == 0);
    value = 42.5;
    memcpy(b + 596, &value, 8);
    assert(serialize_sensor(0, b, sizeof b) == 1);
    for (unsigned i = 0; i < count; i++)
        fputs(queue[(head + i) % QSIZE], stdout);
    DeleteCriticalSection(&lock);
    return 0;
}
