[CmdletBinding()]
param([string]$Compiler, [switch]$UseWsl, [switch]$Tests)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot
Push-Location $root
try {
    New-Item -ItemType Directory -Force build | Out-Null
    if (-not $Compiler) { $Compiler = if ($UseWsl) { 'x86_64-w64-mingw32-gcc' } else { 'gcc' } }
    if ($UseWsl) {
        $linuxRoot = (& wsl.exe --exec wslpath -a $root).Trim()
        if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve repository path in WSL.' }
    } else {
        $Compiler = (Get-Command $Compiler -ErrorAction Stop).Source
    }
    $sources = @(@{ Source = 'collector.c'; Output = 'build/hwtrace.exe' })
    if ($Tests) {
        foreach ($name in @('units', 'profile', 'snapshot', 'start_gate', 'process')) {
            $sources += @{ Source = "tests/test_native_$name.c"; Output = "build/test_native_$name.exe" }
        }
    }
    foreach ($item in $sources) {
        $arguments = @('-std=c11', '-Wall', '-Wextra', '-Werror', '-O2', $item.Source, '-o', $item.Output)
        if ($UseWsl) { & wsl.exe --cd $linuxRoot --exec $Compiler @arguments }
        else { & $Compiler @arguments }
        if ($LASTEXITCODE -ne 0) { throw "Compilation failed: $($item.Source)" }
        Write-Host "Built $($item.Output)"
    }
} finally { Pop-Location }
