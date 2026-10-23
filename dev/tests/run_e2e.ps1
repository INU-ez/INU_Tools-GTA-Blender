# Runs the e2e test suite by launching Blender headless and pointing it
# at dev/tests/_e2e_entry.py, which boots pytest inside Blender's Python.
#
# Usage:
#   .\dev\tests\run_e2e.ps1                    # auto-detect Blender
#   .\dev\tests\run_e2e.ps1 -Blender "C:\..."  # explicit path
#   $env:BLENDER = "C:\..."; .\dev\tests\run_e2e.ps1
#
# Exit code: pytest exit code (0 = all pass, 1 = test failures, etc.)
#
# NOTE: keep this file ASCII-only. PowerShell 5.1 reads .ps1 without a
# BOM as Windows-1251 on RU locale, which breaks any non-ASCII char.

param(
    [string]$Blender = ""
)

$ErrorActionPreference = "Stop"

# --- Resolve Blender executable ----------------------------------
if (-not $Blender -and $env:BLENDER) { $Blender = $env:BLENDER }

if (-not $Blender) {
    $candidates = @(
        "D:\Program\Steam\steamapps\common\Blender\blender.exe",
        "D:\blender-4.2.23-windows-x64\blender.exe",
        "C:\Program Files\Blender Foundation\Blender 4.5\blender.exe",
        "C:\Program Files\Blender Foundation\Blender 4.4\blender.exe",
        "C:\Program Files\Blender Foundation\Blender 4.3\blender.exe",
        "C:\Program Files\Blender Foundation\Blender 4.2\blender.exe",
        "D:\Program\Blender 5.1\blender.exe",
        "D:\Program\blender-4.2.20-windows-x64\blender.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { $Blender = $c; break }
    }
}

if (-not $Blender -or -not (Test-Path $Blender)) {
    Write-Host "Blender not found. Pass -Blender 'C:\path\to\blender.exe' or set `$env:BLENDER." -ForegroundColor Red
    exit 2
}

Write-Host "Using Blender: $Blender" -ForegroundColor Cyan

# --- Locate entry script -----------------------------------------
$Entry = Join-Path $PSScriptRoot "_e2e_entry.py"
if (-not (Test-Path $Entry)) {
    Write-Host "Missing entry script: $Entry" -ForegroundColor Red
    exit 2
}

# --- Run ---------------------------------------------------------
# --background loads user prefs (so the INU Tools addon is enabled)
# but suppresses the GUI. Don't add --factory-startup -- that would
# disable installed addons and break every test.
$StatusFile = Join-Path $PSScriptRoot ".e2e_last_exit"
if (Test-Path $StatusFile) { Remove-Item $StatusFile -Force }

& $Blender --background --python $Entry

# Blender always exits 0 from --python scripts even on Python errors,
# so we round-trip the real exit code through a status file written
# by _e2e_entry.py. Missing file = entry script crashed before reaching
# the write — treat as failure.
if (Test-Path $StatusFile) {
    $code = [int](Get-Content $StatusFile -Raw).Trim()
} else {
    $code = 99
    Write-Host "Status file missing -- entry script likely crashed before pytest ran" -ForegroundColor Yellow
}
Write-Host "exit code: $code" -ForegroundColor Cyan
exit $code
