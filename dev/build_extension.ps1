# Build INU Tools as a Blender extension package.
#
# Single unified build — same .zip works on GitHub release and on
# extensions.blender.org. DXT compression goes through the bundled
# core.dxt numpy encoder (and an optional bpy.gpu compute shader path
# that's WIP) — no external binaries.
#
# Uses Blender's official `extension build` command which:
#   - Validates blender_manifest.toml
#   - Excludes __pycache__/, .pyc, .git/, dev files automatically
#   - Produces a .zip with the correct extension naming (id-version.zip)
#
# Run from repo root.

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

# --- Configure ---------------------------------------------------------
$BlenderExe = "D:\Program\Steam\steamapps\common\Blender\blender.exe"
$SourceDir  = "INU_tools"
$OutputDir  = "."

# --- Pre-build cleanup -------------------------------------------------
Write-Host "Cleaning __pycache__ folders..." -ForegroundColor Cyan
Get-ChildItem -Path $SourceDir -Filter "__pycache__" -Recurse -Directory -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force

# --- Build -------------------------------------------------------------
Write-Host "Building extension via Blender CLI..." -ForegroundColor Cyan
& $BlenderExe --command extension build `
    --source-dir $SourceDir `
    --output-dir $OutputDir 2>&1 |
    Where-Object { $_ -match '^(building|complete|created|error|Error)' }

$builtZip = Get-ChildItem "inu_tools_gta_sa-*.zip" |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1

if (-not $builtZip) {
    Write-Host "Build did not produce a zip -- check output above." -ForegroundColor Red
    exit 1
}

Write-Host "`nDone." -ForegroundColor Green
Get-ChildItem "inu_tools_gta_sa-*.zip" | Format-Table Name, Length, LastWriteTime
