param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot
. (Join-Path $root 'Startup-Capture.ps1')
$fixture = [Convert]::FromBase64String('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jhuQAAAAASUVORK5CYII=')
$temp = Join-Path ([IO.Path]::GetTempPath()) ('HWTrace startup test ' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $temp | Out-Null
try {
    $pythonExe = (Get-Command $Python).Source
    $receiver = Join-Path $root 'receiver.py'
    $db = Join-Path $temp 'test.sqlite3'
    $command = '"' + $pythonExe + '" "' + $receiver + '" --db "' + $db + '" --ack'
    $id = [Guid]::NewGuid().ToString('N')
    Send-StartupScreenshot -SshCommand $command -Png $fixture -CaptureId $id -CapturedAt '2026-10-30T04:00:00Z' -ProcessName 'TM5.exe'
    $actual = [IO.File]::ReadAllBytes((Join-Path $temp "screenshots/$id.png"))
    if ([Convert]::ToBase64String($actual) -ne [Convert]::ToBase64String($fixture)) { throw 'Binary upload changed PNG bytes.' }
    # Exercise the exact GDI copying path against a selected offscreen bitmap.
    Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class HWTraceTestGdi {
 [DllImport("gdi32.dll")] public static extern IntPtr CreateCompatibleDC(IntPtr dc);
 [DllImport("gdi32.dll")] public static extern IntPtr SelectObject(IntPtr dc,IntPtr obj);
 [DllImport("gdi32.dll")] public static extern bool DeleteObject(IntPtr obj);
 [DllImport("gdi32.dll")] public static extern bool DeleteDC(IntPtr dc);
}
"@
    $sourceImage = [Drawing.Bitmap]::new(257,131,[Drawing.Imaging.PixelFormat]::Format24bppRgb)
    $targetImage = [Drawing.Bitmap]::new(257,131,[Drawing.Imaging.PixelFormat]::Format24bppRgb)
    $sg = [Drawing.Graphics]::FromImage($sourceImage)
    $sg.Clear([Drawing.Color]::Navy);$sg.Dispose()
    $sourceImage.SetPixel(256,130,[Drawing.Color]::Lime)
    $tg = [Drawing.Graphics]::FromImage($targetImage)
    $sourceDC = [HWTraceTestGdi]::CreateCompatibleDC([IntPtr]::Zero)
    $bitmapHandle = $sourceImage.GetHbitmap()
    $oldBitmap = [HWTraceTestGdi]::SelectObject($sourceDC,$bitmapHandle)
    try {
        [HWTraceDesktopCapture]::CopyPixels($tg,$sourceDC,[Drawing.Rectangle]::new(0,0,257,131))
        if ($targetImage.GetPixel(0,0).ToArgb() -ne [Drawing.Color]::Navy.ToArgb() -or $targetImage.GetPixel(256,130).ToArgb() -ne [Drawing.Color]::Lime.ToArgb()) { throw 'Pixel copy did not cover full physical image.' }
    } finally {
        $null=[HWTraceTestGdi]::SelectObject($sourceDC,$oldBitmap)
        $null=[HWTraceTestGdi]::DeleteObject($bitmapHandle)
        $null=[HWTraceTestGdi]::DeleteDC($sourceDC)
        $tg.Dispose();$sourceImage.Dispose();$targetImage.Dispose()
    }
    $startGate = [Threading.EventWaitHandle]::new($false, [Threading.EventResetMode]::ManualReset, 'Local\HWTraceCaptureStart-0123456789abcdef0123456789abcdef')
    try {
        & (Join-Path $root 'build/test_native_start_gate.exe') | Out-Null
        if ($LASTEXITCODE -ne 0 -or -not $startGate.WaitOne(0)) { throw 'Native collector did not signal the managed screenshot gate.' }
    } finally { $startGate.Dispose() }
    # A desktop worker must wait for collector startup; cancelling here takes no screenshot.
    $waiting = [HWTraceScreenshotWorker]::Start('not-used', 'TM5.exe', [Guid]::NewGuid().ToString('N'))
    try {
        if ($waiting.Wait(100)) { throw 'Screenshot worker did not wait for the collector startup signal.' }
        $waiting.Cancel()
        if (-not $waiting.Wait(2000) -or $waiting.Error) { throw 'Waiting screenshot worker failed to cancel cleanly.' }
    } finally { $waiting.Dispose() }
    # Slow upload must not hold up the caller or a concurrently started collector.
    $slow = Join-Path $temp 'slow_receiver.py'
    $receiverLiteral = "r'" + $receiver.Replace("'", "\'") + "'"
    "import time,runpy; time.sleep(2); runpy.run_path($receiverLiteral,run_name='__main__')" | Set-Content -LiteralPath $slow -Encoding utf8
    $slowCommand = '"' + $pythonExe + '" "' + $slow + '" --db "' + $db + '" --ack'
    $asyncId = [Guid]::NewGuid().ToString('N')
    $watch = [Diagnostics.Stopwatch]::StartNew()
    $worker = [HWTraceScreenshotWorker]::StartUpload($slowCommand, 'TM5.exe', $asyncId, $fixture, [DateTime]::UtcNow)
    try {
        if ($watch.ElapsedMilliseconds -gt 500) { throw 'Worker start blocked on upload.' }
        & (Join-Path $root 'build/test_native_snapshot.exe') | Out-Null
        if ($LASTEXITCODE -ne 0 -or $worker.IsCompleted) { throw 'Native collection did not run while upload was pending.' }
        if (-not $worker.Wait(10000) -or $worker.Error) { throw "Async upload failed: $($worker.Error)" }
        if (-not (Test-Path (Join-Path $temp "screenshots/$asyncId.png"))) { throw 'Async PNG missing.' }
        $flags = [Reflection.BindingFlags]'NonPublic,Instance'
        if ([HWTraceScreenshotWorker].GetField('capture',$flags).GetValue($worker) -or [HWTraceScreenshotWorker].GetField('upload',$flags).GetValue($worker)) { throw 'Worker retained image factory or upload process.' }
    } finally { $worker.Dispose() }
    $cancelWorker = [HWTraceScreenshotWorker]::StartUpload($slowCommand, 'TM5.exe', [Guid]::NewGuid().ToString('N'), $fixture, [DateTime]::UtcNow)
    try {
        Start-Sleep -Milliseconds 100
        $cancelWorker.Cancel()
        if (-not $cancelWorker.Wait(10000)) { throw 'Cancelled worker did not release its thread.' }
    } finally { $cancelWorker.Dispose() }
    if ([Environment]::UserInteractive -and [Diagnostics.Process]::GetCurrentProcess().SessionId -ne 0) {
        # DPI regression: physical bounds must be independent of an unaware calling thread.
        $physical = [HWTraceDesktopCapture]::GetPhysicalBounds()
        $before = [HWTraceDesktopCapture]::GetThreadDpiAwarenessContext()
        $setter = [HWTraceDesktopCapture].GetMethod('SetThreadDpiAwarenessContext', [Reflection.BindingFlags]'NonPublic,Static')
        try {
            $null = $setter.Invoke($null, @([IntPtr]::new(-1)))
            $underScaling = [HWTraceDesktopCapture]::GetPhysicalBounds()
            if ($physical -ne $underScaling) { throw 'Physical monitor bounds changed under DPI virtualization.' }
            if (-not [HWTraceDesktopCapture]::AreDpiAwarenessContextsEqual([HWTraceDesktopCapture]::GetThreadDpiAwarenessContext(),[IntPtr]::new(-1))) { throw 'Capture did not restore calling-thread DPI context.' }
        } finally { $null = $setter.Invoke($null, @($before)) }
    } else {
        Write-Host 'SKIP physical monitor geometry: noninteractive/headless session.'
    }
    $script:already = $false; $script:workers = 0
    function Get-MonitoredProcessPresent { param($ProcessName); return $script:already }
    function Start-BackgroundStartupScreenshot { param($SshCommand,$ProcessName,$CaptureId); $script:workers++; return [object]::new() }
    $a = Initialize-StartupContext -ProcessName 'TM5.exe' -SshCommand 'test'
    if ($a.Event -ne 'startup_waiting_for_process' -or $a.Worker -or $script:workers -ne 0) { throw 'Absent process started a screenshot thread.' }
    $script:already = $true
    $b = Initialize-StartupContext -ProcessName 'TM5.exe' -SshCommand 'test'
    if ($b.Event -ne 'startup_screenshot_pending' -or -not $b.Worker -or $script:workers -ne 1) { throw 'Existing process must start one background screenshot thread.' }
    function Start-BackgroundStartupScreenshot { param($SshCommand,$ProcessName,$CaptureId); throw 'simulated thread startup failure' }
    $c = Initialize-StartupContext -ProcessName 'TM5.exe' -SshCommand 'test' -WarningAction SilentlyContinue
    if ($c.Event -ne 'startup_screenshot_failed') { throw 'Worker startup failure must allow collection to continue.' }
    Write-Host 'Async startup/upload, cancellation, resource release, physical DPI bounds and presence branches: OK (synthetic PNG; no desktop capture).'
} finally {
    $resolved = [IO.Path]::GetFullPath($temp)
    $expectedParent = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\','/') + [IO.Path]::DirectorySeparatorChar
    if (-not $resolved.StartsWith($expectedParent,[StringComparison]::OrdinalIgnoreCase) -or -not ([IO.Path]::GetFileName($resolved)).StartsWith('HWTrace startup test ')) { throw 'Unexpected test cleanup path.' }
    Remove-Item -LiteralPath $resolved -Recurse -Force
}
