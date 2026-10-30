function Get-MonitoredProcessPresent {
    param([Parameter(Mandatory)][string]$ProcessName)
    $name = [IO.Path]::GetFileNameWithoutExtension($ProcessName)
    return @(Get-Process -Name $name -ErrorAction SilentlyContinue).Count -gt 0
}

function Import-DesktopCapture {
    if (-not ('HWTraceDesktopCapture' -as [type])) {
        Add-Type -AssemblyName System.Drawing.Common
        $references = @([Drawing.Bitmap].Assembly.Location, [Drawing.Rectangle].Assembly.Location, [Diagnostics.Process].Assembly.Location, (Join-Path $PSHOME 'ref/System.Threading.Thread.dll'), (Join-Path $PSHOME 'ref/System.Threading.dll'), (Join-Path $PSHOME 'ref/System.Console.dll'), (Join-Path $PSHOME 'ref/System.Threading.Tasks.dll'), [ComponentModel.Component].Assembly.Location)
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
    param([Parameter(Mandatory)][string]$ProcessName, [Parameter(Mandatory)][string]$SshCommand)
    $result = [ordered]@{
        Id = [Guid]::NewGuid().ToString('N')
        StartedAt = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ss.fffZ')
        ProcessAlreadyRunning = (Get-MonitoredProcessPresent -ProcessName $ProcessName)
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
