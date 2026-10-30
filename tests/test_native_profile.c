#define main collector_main
#include "../collector.c"
#undef main
#include <assert.h>
int main(void) {
    FILE *f = fopen("ddr5.filter", "r");
    char p[256];
    assert(f);
    while (fgets(p, sizeof p, f)) {
        p[strcspn(p, "\r\n")] = 0;
        if (*p && *p != '#') {
            assert(npat < MAXPAT);
            assert(strlen(p) < sizeof patterns[0]);
            strcpy(patterns[npat++], p);
        }
    }
    fclose(f);
    const char *cpu = "CPU [#0]: Example CPU: Enhanced";
    const char *names[] = {"CPU (Tctl/Tdie)",
                           "CPU Die (average)",
                           "CPU CCD1 (Tdie)",
                           "CPU CCD2 (Tdie)",
                           "Core0 (CCD1)",
                           "Core15 (CCD2)",
                           "L3 Cache (CCD1)",
                           "L3 Cache (CCD2)",
                           "CPU IOD Hotspot",
                           "CPU VDDCR_VDD VRM (SVI3 TFN)",
                           "CPU VDDCR_SOC VRM (SVI3 TFN)",
                           "CPU VDD_MISC VRM (SVI3 TFN)",
                           "DRAM Read Bandwidth",
                           "DRAM Write Bandwidth",
                           "Infinity Fabric Clock (FCLK)",
                           "Memory Controller Clock (UCLK)"};
    for (unsigned i = 0; i < sizeof names / sizeof names[0]; i++)
        assert(selected(cpu, names[i]));
    const char *dimm = "DDR5 DIMM [#0]: Example";
    const char *rails[] = {"SPD Hub Temperature", "VDD (SWA) Voltage", "VDDQ (SWB) Voltage",
                           "VPP (SWC) Voltage",   "VIN Voltage",       "1.8V VOUT Voltage",
                           "1.0V VOUT Voltage",   "Total Power",       "PMIC High Temperature",
                           "PMIC Over Voltage",   "PMIC Under Voltage"};
    for (unsigned i = 0; i < sizeof rails / sizeof rails[0]; i++)
        assert(selected(dimm, rails[i]));
    assert(selected("Memory Timings", "Tcas"));
    assert(selected("Memory Timings", "Trfc"));
    assert(selected("Memory Timings", "Memory Clock"));
    assert(!selected("GPU [#0]", "GPU Temperature"));
    assert(!selected("Drive", "Drive Temperature"));
    assert(!selected("PSU", "Total Power"));
    puts("expanded profile selection: OK");
    return 0;
}
