param(
    [string]$ShortcutDirectory = ""
)

# Create a per-user shortcut; no administrator privileges are required.
$ErrorActionPreference = "Stop"
$scriptDir = [IO.Path]::GetFullPath((Split-Path -Parent $MyInvocation.MyCommand.Path))

if (-not [string]::IsNullOrWhiteSpace($ShortcutDirectory)) {
    $desktopPath = [IO.Path]::GetFullPath($ShortcutDirectory)
} else {
    if (-not [string]::IsNullOrWhiteSpace($env:NASHEED_STUDIO_SHORTCUT_DIR)) {
        $ShortcutDirectory = $env:NASHEED_STUDIO_SHORTCUT_DIR
    }
}

if (-not [string]::IsNullOrWhiteSpace($ShortcutDirectory)) {
    $desktopPath = [IO.Path]::GetFullPath($ShortcutDirectory)
} else {
    $desktopPath = [Environment]::GetFolderPath("Desktop")
    if ([string]::IsNullOrWhiteSpace($desktopPath) -or -not (Test-Path -LiteralPath $desktopPath -PathType Container)) {
        $desktopPath = Join-Path $env:USERPROFILE "Desktop"
    }
}

if (-not (Test-Path -LiteralPath $desktopPath -PathType Container)) {
    try {
        New-Item -ItemType Directory -Path $desktopPath -Force | Out-Null
    } catch {
        Write-Host "[ERROR] Could not access or create the shortcut destination '$desktopPath': $($_.Exception.Message)" -ForegroundColor Red
        exit 1
    }
}
$desktopPath = [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $desktopPath).Path)

# Support the script beside the executable, at the delivery root, or in Installation/.
$candidates = @(
    $scriptDir,
    (Join-Path $scriptDir "Application\NCN Studio"),
    (Join-Path $scriptDir "..\Application\NCN Studio"),
    (Join-Path $scriptDir "..\NCN Studio"),
    (Join-Path $scriptDir "..\..\Application\NCN Studio")
)

$targetExe = $null
$targetDir = $null
foreach ($candidate in $candidates) {
    $candidateExe = Join-Path $candidate "NCN Studio.exe"
    if (Test-Path -LiteralPath $candidateExe -PathType Leaf) {
        $targetDir = [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $candidate).Path)
        $targetExe = [IO.Path]::GetFullPath((Join-Path $targetDir "NCN Studio.exe"))
        break
    }
}

if (-not $targetExe) {
    Write-Host "[ERROR] Could not locate 'NCN Studio.exe' next to this script or in the adjacent Application folder." -ForegroundColor Red
    Write-Host "Keep the executable, its _internal folder, and this helper in the delivered application layout." -ForegroundColor Yellow
    exit 1
}

$shortcutPath = Join-Path $desktopPath "NCN Studio.lnk"
$iconCandidates = @(
    (Join-Path $targetDir "assets\app_icon.ico"),
    (Join-Path $targetDir "_internal\assets\app_icon.ico")
)
$iconPath = $iconCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
if (-not $iconPath) {
    # The executable carries the app icon; this fallback also works in older bundles.
    $iconPath = $targetExe
}

$wsh = $null
try {
    $wsh = New-Object -ComObject WScript.Shell
    $shortcut = $wsh.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $targetExe
    $shortcut.WorkingDirectory = $targetDir
    $shortcut.IconLocation = "$iconPath,0"
    $shortcut.Description = "NCN Studio - Video Playlist Generator"
    $shortcut.Save()

    Write-Host "==========================================================" -ForegroundColor Green
    Write-Host " SUCCESS: Desktop shortcut created successfully!" -ForegroundColor Green
    Write-Host " Shortcut: $shortcutPath" -ForegroundColor Cyan
    Write-Host " Target:   $targetExe" -ForegroundColor Gray
    Write-Host " WorkDir:  $targetDir" -ForegroundColor Gray
    Write-Host " Icon:     $iconPath" -ForegroundColor Gray
    Write-Host "==========================================================" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Failed to create the shortcut at '$shortcutPath': $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Check that the destination is writable and that Windows Script Host is available." -ForegroundColor Yellow
    exit 1
} finally {
    if ($wsh) {
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($wsh)
    }
}
