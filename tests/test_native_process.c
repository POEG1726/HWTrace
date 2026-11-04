#define main collector_main
#include "../collector.c"
#undef main
#include <assert.h>

int main(int argc, char **argv) {
    ProcessState state = {0};
    if (argc > 1 && !strcmp(argv[1], "--hold")) {
        Sleep(30000);
        return 0;
    }
    assert(configure_processes(DEFAULT_PROCESS_SPEC));
    assert(process_count == 2);
    assert(configure_processes(" tm5.EXE , y-cruncher.exe "));
    assert(!configure_processes("TM5.exe,"));
    assert(!configure_processes("TM5.exe,tm5.EXE"));
    assert(!configure_processes("TM5.exe,,other.exe"));
    assert(!configure_processes("*.exe"));
    assert(!configure_processes("C:\\TM5.exe"));
    assert(!configure_processes(""));
    assert(configure_processes(DEFAULT_PROCESS_SPEC));
    InitializeCriticalSection(&lock);
    grace_ms = 600;
    assert(!update_process_state(&state, 0, 1000));
    assert(!state.deadline && !state.seen && count == 0);
    assert(!update_process_state(&state, 3, 2000));
    assert(count == 2 && strstr(queue[0], "TM5.exe") && strstr(queue[1], "y-cruncher.exe"));
    assert(!update_process_state(&state, 2, 2500));
    assert(!state.deadline && count == 3);
    assert(!update_process_state(&state, -1, 3000));
    assert(state.previous == 2 && count == 3);
    assert(!update_process_state(&state, 0, 3500));
    assert(state.deadline == 4100 && count == 4);
    assert(!update_process_state(&state, 1, 4000));
    assert(!state.deadline && count == 5);
    assert(!update_process_state(&state, 0, 4500));
    assert(!update_process_state(&state, 0, 5099));
    assert(update_process_state(&state, 0, 5100));
    assert(count == 7 && strstr(queue[6], "auto_stop"));
    state = (ProcessState){0};
    grace_ms = 0;
    assert(!update_process_state(&state, 1, 6000));
    assert(update_process_state(&state, 0, 6500));
    DeleteCriticalSection(&lock);
    puts("process list and multi-tool grace state: OK");
    return 0;
}
