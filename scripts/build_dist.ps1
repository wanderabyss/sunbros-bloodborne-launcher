<#
.SYNOPSIS
    Builds dist and generates release .zip archives for bloodborne_pc.

.DESCRIPTION
    Runs the build pipeline (MSYS2 CLANG64 + build.sh + package.sh) and produces a clean
    .zip file with forward slashes in bloodborne_pc/dist/.

.PARAMETER PackageName
    Name of the package folder and zip file (default: bbport-windows).

.PARAMETER Rebuild
    Forces recompilation with build.sh even if out/ binaries exist.

.PARAMETER SkipBuild
    Skips build.sh and package.sh compilation, directly packaging/zipping.

.PARAMETER OnlyZip
    Fast path: compresses existing dist/<PackageName> folder into .zip without rebuilding.

.PARAMETER BuildCoop
    Also builds the co-op server (shadnet.exe).

.PARAMETER BuildAtlas
    Also builds the Hunter's Atlas map generator.

.EXAMPLE
    .\scripts\build_dist.ps1
    .\scripts\build_dist.ps1 -OnlyZip
    .\scripts\build_dist.ps1 -PackageName "bbport-windows-new" -Rebuild
#>

[CmdletBinding()]
param(
    [string]$PackageName = "bbport-windows",
    [switch]$Rebuild,
    [switch]$SkipBuild,
    [switch]$OnlyZip,
    [switch]$BuildCoop,
    [switch]$BuildAtlas,
    [string]$OutputDir
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$PythonScript = Join-Path $PSScriptRoot "build_dist.py"

# Find Python: prioritize .venv in repo root, then PATH
$PythonExe = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    $PythonExe = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
}

if (-not $PythonExe -or -not (Test-Path $PythonExe)) {
    Write-Error "Python executable not found. Please activate the virtual environment or install Python."
    exit 1
}

# Construct arguments
$ArgsList = @(
    $PythonScript,
    "--pkg-name", $PackageName
)

if ($Rebuild) { $ArgsList += "--rebuild" }
if ($SkipBuild) { $ArgsList += "--skip-build" }
if ($OnlyZip) { $ArgsList += "--only-zip" }
if ($BuildCoop) { $ArgsList += "--build-coop" }
if ($BuildAtlas) { $ArgsList += "--build-atlas" }
if ($OutputDir) { $ArgsList += @("--output-dir", $OutputDir) }

Write-Host "Running: & '$PythonExe' $($ArgsList -join ' ')" -ForegroundColor Cyan
& $PythonExe @ArgsList

if ($LASTEXITCODE -ne 0) {
    Write-Error "build_dist.py exited with error code $LASTEXITCODE"
    exit $LASTEXITCODE
}
