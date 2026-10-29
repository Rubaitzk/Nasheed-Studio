# Create Desktop Shortcut for Nasheed Studio
$desktopPath = [Environment]::GetFolderPath("Desktop")
if (-not (Test-Path $desktopPath)) {
    # Fallback to user profile desktop if OneDrive or localized path differs
    $desktopPath = Join-Path $env:USERPROFILE "Desktop"
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Check candidates for app directory containing Nasheed Studio.exe
$candidates = @(
    $scriptDir,
    (Join-Path $scriptDir "Application\Nasheed Studio"),
    (Join-Path $scriptDir "..\Application\Nasheed Studio"),
    (Join-Path $scriptDir "..\Nasheed Studio")
)

$targetExe = $null
$targetDir = $null

foreach ($cand in $candidates) {
    if ($cand -and (Test-Path (Join-Path $cand "Nasheed Studio.exe"))) {
        $resolved = (Resolve-Path $cand).Path
        $targetDir = [string]$resolved
        $targetExe = (Join-Path $targetDir "Nasheed Studio.exe")
        break
    }
}

if (-not $targetExe -or -not (Test-Path $targetExe)) {
    Write-Host "[ERROR] Could not locate 'Nasheed Studio.exe'." -ForegroundColor Red
    Write-Host "Please ensure this script is located in the application directory or installation folder." -ForegroundColor Yellow
    exit 1
}

$shortcutPath = Join-Path $desktopPath "Nasheed Studio.lnk"

try {
    $wsh = New-Object -ComObject WScript.Shell
    $shortcut = $wsh.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = [string]$targetExe
    $shortcut.WorkingDirectory = [string]$targetDir
    $shortcut.IconLocation = "$targetExe,0"
    $shortcut.Description = "Nasheed Studio - Video Playlist Generator"
    $shortcut.Save()

    Write-Host "==========================================================" -ForegroundColor Green
    Write-Host " SUCCESS: Desktop shortcut created successfully!" -ForegroundColor Green
    Write-Host " Shortcut: $shortcutPath" -ForegroundColor Cyan
    Write-Host " Target:   $targetExe" -ForegroundColor Gray
    Write-Host " WorkDir:  $targetDir" -ForegroundColor Gray
    Write-Host "==========================================================" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Failed to create shortcut: $_" -ForegroundColor Red
    exit 1
}
