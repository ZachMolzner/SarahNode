param(
    [string]$SourceBlend = "C:\Users\karvo\MANUKA_ver1.02\MANUKA.blend",
    [string]$BlenderExe = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$builder = Join-Path $repoRoot "scripts\blender\build-manuka-outfit.py"
$outputDir = Join-Path $repoRoot "local\manuka-outfits"
$modelDir = Join-Path $repoRoot "frontend\public\models"

if (-not (Test-Path -LiteralPath $SourceBlend)) {
    throw "MANUKA source blend was not found: $SourceBlend"
}

if (-not $BlenderExe) {
    $command = Get-Command blender -ErrorAction SilentlyContinue
    if ($command) {
        $BlenderExe = $command.Source
    }
}

if (-not $BlenderExe) {
    $candidates = Get-ChildItem "C:\Program Files\Blender Foundation" -Filter blender.exe -Recurse -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending
    if ($candidates) {
        $BlenderExe = $candidates[0].FullName
    }
}

if (-not $BlenderExe -or -not (Test-Path -LiteralPath $BlenderExe)) {
    throw "Blender was not found. Pass -BlenderExe with the full path to blender.exe."
}

if (-not (Test-Path -LiteralPath $builder)) {
    throw "Outfit builder script is missing: $builder"
}

New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
New-Item -ItemType Directory -Force -Path $modelDir | Out-Null

$presets = @(
    "casual-streetwear",
    "cafe-maid",
    "sporty-athleisure",
    "elegant-evening",
    "cozy-sweater",
    "futuristic-idol-techwear"
)

Write-Host "Building MANUKA outfit collection with:" -ForegroundColor Cyan
Write-Host "  Blender: $BlenderExe"
Write-Host "  Source:  $SourceBlend"
Write-Host ""

foreach ($preset in $presets) {
    $blendOutput = Join-Path $outputDir "MANUKA-$preset.blend"
    $vrmOutput = Join-Path $modelDir "sarah-$preset.vrm"

    Write-Host "[$preset]" -ForegroundColor Yellow

    $blenderArgs = @(
        $SourceBlend,
        "--background",
        "--python", $builder,
        "--",
        "--preset", $preset,
        "--output", $blendOutput,
        "--vrm-output", $vrmOutput
    )

    & $BlenderExe @blenderArgs

    if ($LASTEXITCODE -ne 0) {
        throw "Blender failed while building '$preset' (exit code $LASTEXITCODE)."
    }

    if (Test-Path -LiteralPath $vrmOutput) {
        Write-Host "  VRM ready: $vrmOutput" -ForegroundColor Green
    }
    else {
        Write-Host "  Blend ready: $blendOutput" -ForegroundColor Green
        Write-Host "  VRM was not exported. Install/enable the VRM Add-on in Blender, visually tune the outfit, then export it as:" -ForegroundColor DarkYellow
        Write-Host "  $vrmOutput" -ForegroundColor DarkYellow
    }

    Write-Host ""
}

Write-Host "Outfit build pass complete." -ForegroundColor Green
Write-Host "Generated Blender files stay under local\manuka-outfits and are not intended for Git."
