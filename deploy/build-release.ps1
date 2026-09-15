# build-release.ps1 - 本地构建发版 wheel 产物
#
# 构建 akm-shared 与 akm-node 两个 wheel 到 src/dist/,并做存在性校验。
# 发版主流程在 GitHub Actions(release.yml)中执行,本脚本用于本地验证
# 与安装脚本联调(AKM_WHEEL_DIR 指向 src/dist 干跑 deploy/install-akm-node.ps1)。
#
# 用法:
#   powershell -ExecutionPolicy Bypass -File scripts/build-release.ps1
#   powershell -ExecutionPolicy Bypass -File scripts/build-release.ps1 -OutDir D:\tmp\wheels

param(
    [string]$OutDir = ""
)

$ErrorActionPreference = "Stop"

# 定位仓库与 src/
$repoRoot = Split-Path -Parent $PSScriptRoot
$srcRoot = Join-Path $repoRoot "src"

if (-not $OutDir) {
    $OutDir = Join-Path $srcRoot "dist"
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Error "未找到 uv,请先安装:https://docs.astral.sh/uv/getting-started/installation/"
}

# 清理并重建输出目录
if (Test-Path $OutDir) {
    Remove-Item $OutDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

# 逐包构建
foreach ($pkg in @("shared", "node")) {
    $pkgDir = Join-Path $srcRoot $pkg
    Write-Host "==> uv build $pkg"
    Push-Location $pkgDir
    try {
        uv build --out-dir $OutDir
    }
    finally {
        Pop-Location
    }
}

# 校验产物
$expected = @(
    "akm_shared-*-py3-none-any.whl",
    "akm_node-*-py3-none-any.whl"
)
foreach ($pattern in $expected) {
    $found = Get-ChildItem $OutDir -Filter $pattern -ErrorAction SilentlyContinue
    if (-not $found) {
        Write-Error "缺少预期产物:$pattern(输出目录 $OutDir)"
    }
}

Write-Host ""
Write-Host "✅ 构建完成,产物位于 ${OutDir}:"
Get-ChildItem $OutDir -Filter *.whl | ForEach-Object { Write-Host ("   " + $_.Name) }
Write-Host ""
Write-Host "联调安装脚本(本地 wheel 干跑):"
Write-Host ('  $env:AKM_VERSION = "0.2.0"; $env:AKM_WHEEL_DIR = "' + $OutDir + '"; powershell -File deploy\install-akm-node.ps1')
