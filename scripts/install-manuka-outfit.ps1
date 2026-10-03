param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet(
        "casual-streetwear",
        "cafe-maid",
        "sporty-athleisure",
        "elegant-evening",
        "cozy-sweater",
        "futuristic-idol-techwear"
    )]
    [string]$Preset,

    [Parameter(Mandatory = $true, Position = 1)]
    [string]$Source
)

$ErrorActionPreference = "Stop"

$sourcePath = (Resolve-Path -LiteralPath $Source).Path
if (-not $sourcePath.ToLowerInvariant().EndsWith(".vrm")) {
    throw "Source must be a .vrm file."
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$targetDir = Join-Path $repoRoot "frontend\public\models"
$targetPath = Join-Path $targetDir "sarah-$Preset.vrm"

New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
Copy-Item -LiteralPath $sourcePath -Destination $targetPath -Force

$sizeMb = [Math]::Round((Get-Item -LiteralPath $targetPath).Length / 1MB, 1)
Write-Host "Installed Sarah outfit '$Preset':" -ForegroundColor Green
Write-Host "  $targetPath"
Write-Host "  Size: $sizeMb MB"
Write-Host ""
Write-Host "The model is ignored by Git and stays local to this SarahNode installation."
