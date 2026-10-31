<#
.SYNOPSIS
    Publishes a new release to GitHub with release notes and the distribution zip archive.

.DESCRIPTION
    Automates extracting the latest release notes from Release_Notes.md, finding the matching
    distribution zip in bloodborne_pc/dist/, computing SHA-256 hashes, creating/pushing the
    git tag, and creating the release on GitHub using the GitHub CLI (`gh`).

.PARAMETER Tag
    Explicit release tag (default: v<version> extracted from Release_Notes.md or version.txt).

.PARAMETER ZipPath
    Path to custom distribution .zip archive.

.PARAMETER Draft
    Creates the GitHub release as a draft for review before publishing.

.PARAMETER PreRelease
    Marks the release as a pre-release.

.PARAMETER DryRun
    Previews extracted release notes, tag, and commands without making any changes.

.PARAMETER AllowDirty
    Allows publishing even if there are uncommitted changes in the repository.

.PARAMETER AllowBranch
    Allows publishing from branches other than 'main'.

.EXAMPLE
    .\scripts\publish_release.ps1 -DryRun
    .\scripts\publish_release.ps1
    .\scripts\publish_release.ps1 -Draft
#>

[CmdletBinding()]
param(
    [string]$Tag,
    [string]$ZipPath,
    [switch]$Draft,
    [switch]$PreRelease,
    [switch]$DryRun,
    [switch]$AllowDirty,
    [switch]$AllowBranch,
    [switch]$AttachSource
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$PythonScript = Join-Path $PSScriptRoot "publish_release.py"

# Find Python: prioritize .venv in repo root, then PATH
$PythonExe = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    $PythonExe = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
}

if (-not $PythonExe -or -not (Test-Path $PythonExe)) {
    Write-Error "Python executable not found. Please activate your virtual environment or install Python."
    exit 1
}

$env:PYTHONIOENCODING = "utf-8"

$ArgsList = @($PythonScript)

if ($Tag) { $ArgsList += @("--tag", $Tag) }
if ($ZipPath) { $ArgsList += @("--zip", $ZipPath) }
if ($Draft) { $ArgsList += "--draft" }
if ($PreRelease) { $ArgsList += "--prerelease" }
if ($DryRun) { $ArgsList += "--dry-run" }
if ($AllowDirty) { $ArgsList += "--allow-dirty" }
if ($AllowBranch) { $ArgsList += "--allow-branch" }
if ($AttachSource) { $ArgsList += "--attach-source" }

Write-Host "Running release publisher: & '$PythonExe' $($ArgsList -join ' ')" -ForegroundColor Cyan
& $PythonExe @ArgsList

if ($LASTEXITCODE -ne 0) {
    Write-Error "publish_release.py failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}
