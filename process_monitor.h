#ifndef HWTRACE_PROCESS_MONITOR_H
#define HWTRACE_PROCESS_MONITOR_H

#define DEFAULT_PROCESS_SPEC "TM5.exe,y-cruncher.exe"
#define MAX_PROCESSES 16
static char process_names[MAX_PROCESSES][128];
static unsigned process_count;

/* Exact executable names separated by commas; preserve single-name callers. */
static int configure_processes(const char *spec) {
    const char *start = spec;
    process_count = 0;
    if (!spec || !*spec || strlen(spec) >= 1024)
        return 0;
    while (*start) {
        const char *end = strchr(start, ',');
        size_t length;
        if (!end)
            end = start + strlen(start);
        while (start < end && (*start == ' ' || *start == '\t'))
            start++;
        while (end > start && (end[-1] == ' ' || end[-1] == '\t'))
            end--;
        length = (size_t)(end - start);
        if (!length || length >= sizeof process_names[0] || process_count == MAX_PROCESSES)
            return 0;
        memcpy(process_names[process_count], start, length);
        process_names[process_count][length] = 0;
        if (strpbrk(process_names[process_count], "\\/:*?\"<>|\r\n\t") ||
            length <= 4 || _stricmp(process_names[process_count] + length - 4, ".exe"))
            return 0;
        for (unsigned i = 0; i < process_count; i++)
            if (!_stricmp(process_names[i], process_names[process_count]))
                return 0;
        process_count++;
        start = strchr(start, ',');
        if (!start)
            break;
        start++;
        if (!*start)
            return 0;
    }
    return process_count != 0;
}

/* Optimized executables belong to a y-cruncher installation, not any process
 * whose name happens to look like a CPU architecture. The launcher need not run. */
static int is_y_cruncher_binary(const wchar_t *path) {
    wchar_t launcher[32768];
    const wchar_t *file = wcsrchr(path, L'\\');
    const wchar_t *directory;
    size_t prefix;
    DWORD attributes;
    if (!file || wcslen(file) < 5 || _wcsicmp(file + wcslen(file) - 4, L".exe"))
        return 0;
    prefix = (size_t)(file - path);
    if (prefix >= sizeof launcher / sizeof launcher[0])
        return 0;
    wmemcpy(launcher, path, prefix);
    launcher[prefix] = 0;
    directory = wcsrchr(launcher, L'\\');
    if (!directory || _wcsicmp(directory + 1, L"Binaries"))
        return 0;
    prefix = (size_t)(directory - launcher) + 1;
    if (prefix + wcslen(L"y-cruncher.exe") >= sizeof launcher / sizeof launcher[0])
        return 0;
    wcscpy(launcher + prefix, L"y-cruncher.exe");
    attributes = GetFileAttributesW(launcher);
    return attributes != INVALID_FILE_ATTRIBUTES && !(attributes & FILE_ATTRIBUTE_DIRECTORY);
}

#endif
