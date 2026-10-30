#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
int main(int argc, char **argv) {
    MEMORYSTATUSEX m = {0};
    m.dwLength = sizeof m;
    if (GlobalMemoryStatusEx(&m))
        printf("Available RAM MiB=%llu; available commit MiB=%llu; memory load=%lu%%\n",
               (unsigned long long)(m.ullAvailPhys / 1048576),
               (unsigned long long)(m.ullAvailPageFile / 1048576), m.dwMemoryLoad);
    if (argc != 2)
        return 2;
    HANDLE p = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE,
                           (DWORD)strtoul(argv[1], 0, 10)),
           t = NULL;
    if (!p) {
        printf("OpenProcess Win32=%lu\n", GetLastError());
        return 1;
    }
    if (!OpenProcessToken(p, TOKEN_QUERY, &t)) {
        printf("OpenProcessToken Win32=%lu\n", GetLastError());
        CloseHandle(p);
        return 1;
    }
    TOKEN_ELEVATION e;
    DWORD needed;
    if (GetTokenInformation(t, TokenElevation, &e, sizeof e, &needed))
        printf("HWiNFO token elevated=%lu\n", e.TokenIsElevated);
    GetTokenInformation(t, TokenPrivileges, NULL, 0, &needed);
    TOKEN_PRIVILEGES *priv = malloc(needed);
    if (priv && GetTokenInformation(t, TokenPrivileges, priv, needed, &needed)) {
        int found = 0;
        for (DWORD i = 0; i < priv->PrivilegeCount; i++) {
            char n[128];
            DWORD size = sizeof n;
            if (LookupPrivilegeNameA(NULL, &priv->Privileges[i].Luid, n, &size) &&
                !strcmp(n, "SeCreateGlobalPrivilege")) {
                printf("SeCreateGlobalPrivilege present; enabled=%d\n",
                       !!(priv->Privileges[i].Attributes & SE_PRIVILEGE_ENABLED));
                found = 1;
            }
        }
        if (!found)
            puts("SeCreateGlobalPrivilege absent");
    }
    free(priv);
    CloseHandle(t);
    CloseHandle(p);
    return 0;
}
