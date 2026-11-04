function Get-MonitoredProcessPresent {
    param([Parameter(Mandatory)][string]$ProcessName,
          [string]$CollectorPath = (Join-Path $PSScriptRoot 'build/hwtrace.exe'))
    & $CollectorPath --process-present $ProcessName
    if ($LASTEXITCODE -eq 2) { throw 'Cannot inspect monitored processes or invalid process list.' }
    if ($LASTEXITCODE -notin @(0, 1)) { throw "Process inspection failed: $LASTEXITCODE" }
    return $LASTEXITCODE -eq 0
}

function Import-DesktopCapture {
    if (-not ('HWTraceDesktopCapture' -as [type])) {
        Add-Type -AssemblyName System.Drawing.Common
        $references = @(
            [Drawing.Bitmap].Assembly.Location,
            [Drawing.Rectangle].Assembly.Location,
            [Diagnostics.Process].Assembly.Location,
            [ComponentModel.Component].Assembly.Location
        )
        foreach ($name in @('System.Threading.Thread', 'System.Threading', 'System.Console', 'System.Threading.Tasks')) {
            $references += Join-Path $PSHOME "ref/$name.dll"
        }
        $references += @([Drawing.Bitmap].Assembly.GetReferencedAssemblies() | Where-Object { $_.Name -like 'System.Private.Windows*' } | ForEach-Object { [Reflection.Assembly]::Load($_).Location })
        Add-Type -Path (Join-Path $PSScriptRoot 'capture/DesktopCapture.cs') -ReferencedAssemblies $references -ErrorAction Stop
    }
}

function New-DesktopScreenshot {
    if (-not [Environment]::UserInteractive -or [Diagnostics.Process]::GetCurrentProcess().SessionId -eq 0) { throw 'Screenshots require launching the script from the logged-in Windows desktop.' }
    Import-DesktopCapture
    return ,([HWTraceDesktopCapture]::CaptureFrame().Png)
}

function Send-StartupScreenshot {
    param([string]$SshCommand, [byte[]]$Png, [string]$CaptureId, [string]$CapturedAt, [string]$ProcessName)
    Import-DesktopCapture
    $worker = [HWTraceScreenshotWorker]::StartUpload($SshCommand, $ProcessName, $CaptureId, $Png, [DateTime]::Parse($CapturedAt).ToUniversalTime())
    try {
        if (-not $worker.Wait(45000)) { throw 'Screenshot upload timed out.' }
        if ($worker.Error) { throw $worker.Error }
    } finally { $worker.Dispose() }
}

function Initialize-StartupContext {
    param([Parameter(Mandatory)][string]$ProcessName, [Parameter(Mandatory)][string]$SshCommand,
          [string]$CollectorPath = (Join-Path $PSScriptRoot 'build/hwtrace.exe'))
    $result = [ordered]@{
        Id = [Guid]::NewGuid().ToString('N')
        StartedAt = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ss.fffZ')
        ProcessAlreadyRunning = (Get-MonitoredProcessPresent -ProcessName $ProcessName -CollectorPath $CollectorPath)
        Event = 'startup_waiting_for_process'
    }
    $result.Worker = $null
    if ($result.ProcessAlreadyRunning) {
        try {
            $result.Worker = Start-BackgroundStartupScreenshot -SshCommand $SshCommand -ProcessName $ProcessName -CaptureId $result.Id
            $result.Event = 'startup_screenshot_pending'
        } catch {
            $result.Event = 'startup_screenshot_failed'
            Write-Warning "Cannot start screenshot worker; telemetry will still start. $($_.Exception.Message)"
        }
    }
    return [pscustomobject]$result
}

function Start-BackgroundStartupScreenshot {
    param([string]$SshCommand, [string]$ProcessName, [string]$CaptureId)
    Import-DesktopCapture
    return [HWTraceScreenshotWorker]::Start($SshCommand, $ProcessName, $CaptureId)
}
