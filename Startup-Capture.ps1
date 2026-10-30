function Get-MonitoredProcessPresent {
    param([Parameter(Mandatory)][string]$ProcessName)
    $name = [IO.Path]::GetFileNameWithoutExtension($ProcessName)
    return @(Get-Process -Name $name -ErrorAction SilentlyContinue).Count -gt 0
}

function New-DesktopScreenshot {
    # A single virtual-desktop PNG, held only in RAM. No desktop controls are invoked.
    if (-not [Environment]::UserInteractive -or [Diagnostics.Process]::GetCurrentProcess().SessionId -eq 0) { throw 'Screenshots require launching the script from the logged-in Windows desktop.' }
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    $bounds = [Windows.Forms.SystemInformation]::VirtualScreen
    if ($bounds.Width -le 0 -or $bounds.Height -le 0) { throw 'No interactive desktop is available.' }
    $bitmap = [Drawing.Bitmap]::new($bounds.Width, $bounds.Height)
    $graphics = $null
    $stream = [IO.MemoryStream]::new()
    try {
        $graphics = [Drawing.Graphics]::FromImage($bitmap)
        $graphics.CopyFromScreen($bounds.Location, [Drawing.Point]::Empty, $bounds.Size)
        $bitmap.Save($stream, [Drawing.Imaging.ImageFormat]::Png)
        if ($stream.Length -gt 32MB) { throw 'Startup screenshot exceeds the 32 MiB upload limit.' }
        return ,$stream.ToArray()
    } finally {
        if ($graphics) { $graphics.Dispose() }
        $bitmap.Dispose()
        $stream.Dispose()
    }
}

function Send-StartupScreenshot {
    param(
        [Parameter(Mandatory)][string]$SshCommand,
        [Parameter(Mandatory)][byte[]]$Png,
        [Parameter(Mandatory)][string]$CaptureId,
        [Parameter(Mandatory)][string]$CapturedAt,
        [Parameter(Mandatory)][string]$ProcessName
    )
    if ($SshCommand -notmatch '^\s*(?:"(?<exe>[^"]+)"|(?<exe>\S+))\s+(?<arguments>.+)$') {
        throw 'Cannot parse ssh_command executable and arguments.'
    }
    $exe = $Matches.exe
    $arguments = $Matches.arguments
    $hostName = [Environment]::MachineName
    if ($CaptureId -notmatch '^[a-f0-9]{32}$' -or $hostName -notmatch '^[A-Za-z0-9_.-]+$' -or $CapturedAt -notmatch '^[0-9T:.Z+-]+$') {
        throw 'Invalid screenshot upload metadata.'
    }
    $encodedName = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($ProcessName))
    $process = [Diagnostics.Process]::new()
    $started = $false
    try {
        $process.StartInfo.FileName = $exe
        $process.StartInfo.Arguments = "$arguments --startup-screenshot $CaptureId --captured-at $CapturedAt --source-host $hostName --process-name-b64 $encodedName"
        $process.StartInfo.UseShellExecute = $false
        $process.StartInfo.CreateNoWindow = $true
        $process.StartInfo.RedirectStandardInput = $true
        $process.StartInfo.RedirectStandardOutput = $true
        $process.StartInfo.RedirectStandardError = $true
        $null = $process.Start()
        $started = $true
        $stdout = $process.StandardOutput.ReadToEndAsync()
        $stderr = $process.StandardError.ReadToEndAsync()
        $write = $process.StandardInput.BaseStream.WriteAsync($Png, 0, $Png.Length)
        if (-not $write.Wait(20000)) { throw 'Screenshot transfer timed out.' }
        $process.StandardInput.Close()
        if (-not $process.WaitForExit(20000)) { throw 'Screenshot receiver acknowledgement timed out.' }
        $output = $stdout.GetAwaiter().GetResult().Trim()
        $errorOutput = $stderr.GetAwaiter().GetResult()
        if ($process.ExitCode -ne 0 -or $output -ne "STORED $CaptureId") {
            throw "Screenshot was not acknowledged: $errorOutput $output"
        }
    } finally {
        if ($started -and -not $process.HasExited) { $process.Kill($true) }
        $process.Dispose()
    }
}

function Initialize-StartupContext {
    param([Parameter(Mandatory)][string]$ProcessName, [Parameter(Mandatory)][string]$SshCommand)
    $result = [ordered]@{
        Id = [Guid]::NewGuid().ToString('N')
        StartedAt = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ss.fffZ')
        ProcessAlreadyRunning = (Get-MonitoredProcessPresent -ProcessName $ProcessName)
        Event = 'startup_waiting_for_process'
    }
    if ($result.ProcessAlreadyRunning) {
        try {
            $png = New-DesktopScreenshot
            Send-StartupScreenshot -SshCommand $SshCommand -Png $png -CaptureId $result.Id -CapturedAt $result.StartedAt -ProcessName $ProcessName
            $result.Event = 'startup_screenshot_uploaded'
            Write-Host "Startup screenshot received: $($result.Id).png"
        } catch {
            $result.Event = 'startup_screenshot_failed'
            Write-Warning "Startup screenshot failed; telemetry will still start. $($_.Exception.Message)"
        }
    }
    return [pscustomobject]$result
}
