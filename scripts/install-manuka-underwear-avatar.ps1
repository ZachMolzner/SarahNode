param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Source
)

$ErrorActionPreference = "Stop"

$sourcePath = (Resolve-Path -LiteralPath $Source).Path
if (-not $sourcePath.ToLowerInvariant().EndsWith(".vrm")) {
    throw "Source must be a .vrm file."
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$targetDir = Join-Path $repoRoot "frontend\public\models"
$targetPath = Join-Path $targetDir "sarah-underwear.vrm"

New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
Copy-Item -LiteralPath $sourcePath -Destination $targetPath -Force

$sizeMb = [Math]::Round((Get-Item -LiteralPath $targetPath).Length / 1MB, 1)
Write-Host "Installed Sarah underwear profile:" -ForegroundColor Green
Write-Host "  $targetPath"
Write-Host "  Size: $sizeMb MB"
Write-Host ""
Write-Host "The model is ignored by Git and stays local to this SarahNode installation."
