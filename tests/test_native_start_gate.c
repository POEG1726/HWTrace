#define main collector_main
#include "../collector.c"
#undef main
#include <assert.h>
int main(void) {
    const char *id = "0123456789abcdef0123456789abcdef";
    HANDLE gate = CreateEventW(NULL, TRUE, FALSE,
                               L"Local\\HWTraceCaptureStart-0123456789abcdef0123456789abcdef");
    assert(gate);
    assert(WaitForSingleObject(gate, 0) == WAIT_TIMEOUT);
    signal_capture_start(id);
    assert(WaitForSingleObject(gate, 0) == WAIT_OBJECT_0);
    CloseHandle(gate);
    puts("collector -> screenshot startup signal: OK");
    return 0;
}
