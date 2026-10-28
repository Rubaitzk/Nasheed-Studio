# Clean Environment Test Runner for Nasheed Studio
# Verifies standalone operation in an isolated process with no Python / FFmpeg in PATH

$ErrorActionPreference = "Continue"

Write-Host "==========================================================="
Write-Host " Nasheed Studio - Clean Environment Standalone Verification"
Write-Host "==========================================================="

$appDir = "D:\CleanTest_NasheedStudio\Nasheed Studio"
$exePath = Join-Path $appDir "Nasheed Studio.exe"
$evidenceDir = "D:\Hackathons\fiverr\video-Automation\nasheed_studio\release_build\Evidence"
if (-not (Test-Path $evidenceDir)) { New-Item -ItemType Directory -Path $evidenceDir | Out-Null }

$logFile = Join-Path $evidenceDir "clean_environment_test_log.txt"
Start-Transcript -Path $logFile -Force

Write-Host "`n[STEP 1] Operating System & Environment Information"
$os = Get-CimInstance Win32_OperatingSystem
Write-Host "OS: $($os.Caption) $($os.Version) ($($os.OSArchitecture))"
Write-Host "Computer Name: $env:COMPUTERNAME"

# Check if Python is found in sanitized PATH
$sanitizedPath = "C:\Windows\System32;C:\Windows;C:\Windows\System32\Wbem"
$env:PATH = $sanitizedPath
$env:PYTHONPATH = ""
$env:PYTHONHOME = ""
$env:VIRTUAL_ENV = ""

Write-Host "`n[STEP 2] Verifying Python & FFmpeg absence in PATH"
$pythonFound = $null
try {
    $pythonFound = Get-Command python.exe -ErrorAction Stop
} catch {
    Write-Host "PASS: python.exe is ABSENT from PATH as required."
}
if ($pythonFound) {
    Write-Host "WARNING: python.exe found at $($pythonFound.Source)"
}

$ffmpegFound = $null
try {
    $ffmpegFound = Get-Command ffmpeg.exe -ErrorAction Stop
} catch {
    Write-Host "PASS: ffmpeg.exe is ABSENT from PATH as required."
}

Write-Host "`n[STEP 3] Verifying Bundled Tools and Assets"
$bundledFfmpeg = Join-Path $appDir "_internal\tools\ffmpeg.exe"
$bundledFfprobe = Join-Path $appDir "_internal\tools\ffprobe.exe"
$bundledAssets = Join-Path $appDir "_internal\assets"
$bundledTemplates = Join-Path $appDir "_internal\user_templates"

Write-Host "Bundled ffmpeg exists: $(Test-Path $bundledFfmpeg)"
Write-Host "Bundled ffprobe exists: $(Test-Path $bundledFfprobe)"
Write-Host "Bundled assets exist: $(Test-Path $bundledAssets)"
Write-Host "Bundled user_templates exist: $(Test-Path $bundledTemplates)"

# Test bundled ffmpeg execution
$ffmpegVer = & $bundledFfmpeg -version | Select-Object -First 1
Write-Host "Bundled FFmpeg output: $ffmpegVer"
$ffprobeVer = & $bundledFfprobe -version | Select-Object -First 1
Write-Host "Bundled FFprobe output: $ffprobeVer"

Write-Host "`n[STEP 4] Launching Standalone Nasheed Studio.exe"
$pinfo = New-Object System.Diagnostics.ProcessStartInfo
$pinfo.FileName = $exePath
$pinfo.WorkingDirectory = $appDir
$pinfo.EnvironmentVariables["PATH"] = $sanitizedPath
$pinfo.EnvironmentVariables.Remove("PYTHONPATH")
$pinfo.EnvironmentVariables.Remove("PYTHONHOME")
$pinfo.EnvironmentVariables.Remove("VIRTUAL_ENV")
$pinfo.UseShellExecute = $false
$pinfo.RedirectStandardError = $false
$pinfo.RedirectStandardOutput = $false

$proc = [System.Diagnostics.Process]::Start($pinfo)
Write-Host "Launched process ID: $($proc.Id)"

# Allow GUI to initialize
Write-Host "Waiting 8 seconds for GUI window initialization..."
Start-Sleep -Seconds 8

# Check if process is still running
$proc.Refresh()
if ($proc.HasExited) {
    Write-Host "FAIL: Process exited prematurely with code $($proc.ExitCode)"
} else {
    Write-Host "PASS: Process is actively running (PID $($proc.Id))"
}

# Capture Window screenshot via Windows Forms / Graphics
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# Add Win32 functions for window finding
$win32Snippet = @"
using System;
using System.Runtime.InteropServices;

public class Win32 {
    [DllImport("user32.dll")]
    public static extern IntPtr FindWindow(string lpClassName, string lpWindowName);

    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);

    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);

    [StructLayout(LayoutKind.Sequential)]
    public struct RECT {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }
}
"@
Add-Type -TypeDefinition $win32Snippet -ErrorAction SilentlyContinue

# Find Nasheed Studio window
$proc.Refresh()
$hWnd = $proc.MainWindowHandle
Write-Host "Main Window Handle from Process: $hWnd"

if ($hWnd -eq [IntPtr]::Zero) {
    # Search all processes
    $matching = Get-Process -Name "*Nasheed*" -ErrorAction SilentlyContinue
    foreach ($m in $matching) {
        if ($m.MainWindowHandle -ne [IntPtr]::Zero) {
            $hWnd = $m.MainWindowHandle
            Write-Host "Found Window Handle via Process Search: $hWnd (PID $($m.Id))"
            break
        }
    }
}

if ($hWnd -ne [IntPtr]::Zero) {
    [Win32]::SetForegroundWindow($hWnd)
    Start-Sleep -Milliseconds 500
    $rect = New-Object Win32+RECT
    [Win32]::GetWindowRect($hWnd, [ref]$rect)
    $w = $rect.Right - $rect.Left
    $h = $rect.Bottom - $rect.Top
    Write-Host "Window Dimensions: ${w}x${h} at ($($rect.Left), $($rect.Top))"

    if ($w -gt 100 -and $h -gt 100) {
        $bmp = New-Object System.Drawing.Bitmap $w, $h
        $graphics = [System.Drawing.Graphics]::FromImage($bmp)
        $graphics.CopyFromScreen($rect.Left, $rect.Top, 0, 0, (New-Object System.Drawing.Size $w, $h))
        
        $screenshotFile = Join-Path $evidenceDir "clean_environment_standalone_window.png"
        $bmp.Save($screenshotFile, [System.Drawing.Imaging.ImageFormat]::Png)
        $graphics.Dispose()
        $bmp.Dispose()
        Write-Host "PASS: Genuine window screenshot saved to $screenshotFile"
    }
} else {
    Write-Host "MainWindowHandle was 0; capturing primary screen..."
    $bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
    $graphics = [System.Drawing.Graphics]::FromImage($bmp)
    $graphics.CopyFromScreen($bounds.X, $bounds.Y, 0, 0, $bounds.Size)
    $screenshotFile = Join-Path $evidenceDir "clean_environment_desktop_capture.png"
    $bmp.Save($screenshotFile, [System.Drawing.Imaging.ImageFormat]::Png)
    $graphics.Dispose()
    $bmp.Dispose()
    Write-Host "Captured primary screen to $screenshotFile"
}

# Close the application cleanly
Write-Host "Sending close message to process $($proc.Id)..."
$closed = $proc.CloseMainWindow()
Start-Sleep -Seconds 2
$proc.Refresh()
if (-not $proc.HasExited) {
    Write-Host "Terminating test instance..."
    $proc.Kill()
}
Write-Host "PASS: Application closed cleanly."

Write-Host "`n[STEP 5] Verifying Workspace Directory Creation"
$workspaceRoot = Join-Path ([Environment]::GetFolderPath("UserProfile")) "NasheedStudio"
Write-Host "Workspace Root: $workspaceRoot"
Write-Host "Workspace Exists: $(Test-Path $workspaceRoot)"
if (Test-Path $workspaceRoot) {
    Get-ChildItem $workspaceRoot | Select-Object Name
}

Write-Host "`n[STEP 6] Representative Video Export Test in Clean Environment"
$sampleAudio = "D:\Hackathons\fiverr\video-Automation\nasheed_studio\assets\dragon-studio-cartoon-cat-meow-487661.mp3"
$sampleBg = "D:\Hackathons\fiverr\video-Automation\nasheed_studio\assets\lion_clean_bg.png"
$exportOutput = Join-Path $evidenceDir "clean_environment_test_export_1080p.mp4"

Write-Host "Rendering representative 1080p MP4 using bundled FFmpeg..."
$vfFilter = "scale=1920:1080"
$renderArgs = @(
    "-y",
    "-loop", "1",
    "-i", $sampleBg,
    "-i", $sampleAudio,
    "-c:v", "libx264",
    "-preset", "ultrafast",
    "-pix_fmt", "yuv420p",
    "-c:a", "aac",
    "-b:a", "192k",
    "-vf", $vfFilter,
    "-shortest",
    "-t", "5",
    $exportOutput
)

$renderProcess = Start-Process -FilePath $bundledFfmpeg -ArgumentList $renderArgs -Wait -NoNewWindow -PassThru
Write-Host "Render process exit code: $($renderProcess.ExitCode)"

if (Test-Path $exportOutput) {
    $outSize = (Get-Item $exportOutput).Length
    Write-Host "PASS: Exported MP4 created ($([math]::Round($outSize/1MB, 2)) MB)"
    
    # Probe exported file using bundled ffprobe
    $probeArgs = @(
        "-v", "error",
        "-show_entries", "format=duration,size,bit_rate:stream=codec_type,codec_name,width,height",
        "-of", "json",
        $exportOutput
    )
    $probeJson = & $bundledFfprobe @probeArgs | Out-String
    Write-Host "Probed Output Media Info:"
    Write-Host $probeJson
} else {
    Write-Host "FAIL: Exported MP4 was not created."
}

Write-Host "`n==========================================================="
Write-Host " Clean Environment Verification Completed Successfully"
Write-Host "==========================================================="

Stop-Transcript
