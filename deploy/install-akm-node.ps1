# install-akm-node.ps1 - akm-node 一键安装脚本(Windows PowerShell)
#
# 从 GitHub Release 下载 akm_shared 与 akm_node 两个 wheel,
# 以 uv tool install 安装出全局 akm-node 命令。
#
# 用法(远程一条命令):
#   powershell -ExecutionPolicy Bypass -c "irm https://github.com/wangboy91/AgentKnowledgeMesh/releases/latest/download/install-akm-node.ps1 | iex"
#
# 或下载后本地执行:
#   powershell -ExecutionPolicy Bypass -File scripts\install-akm-node.ps1
#
# 环境变量:
#   $env:AKM_VERSION    指定版本号(如 0.2.0);缺省取最新 release
#   $env:AKM_WHEEL_DIR  本地 wheel 目录,跳过下载(联调/离线安装用)

$ErrorActionPreference = "Stop"

$Repo = "wangboy91/AgentKnowledgeMesh"

# ---------- 1. uv 检测 / 安装 ----------
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "==> 未检测到 uv,开始安装..."
    powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"
    # 刷新当前会话 PATH(安装脚本写入用户级 PATH)
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "User") + ";" + $env:Path
}
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Error "uv 安装后仍不可用,请重开终端后重新执行本脚本"
}

# ---------- 2. 解析版本 ----------
$Version = $env:AKM_VERSION
if (-not $Version) {
    $latest = Invoke-RestMethod "https://api.github.com/repos/$Repo/releases/latest"
    $Version = $latest.tag_name.TrimStart("v")
}
if (-not $Version) {
    Write-Error "无法确定安装版本(未设置 AKM_VERSION 且获取最新 release 失败)"
}
$Tag = "v$Version"
Write-Host "==> 安装 akm-node $Version"

# ---------- 3. 获取 wheel ----------
$TmpDir = Join-Path $env:TEMP "akm-node-install-$Version"
New-Item -ItemType Directory -Force -Path $TmpDir | Out-Null

if ($env:AKM_WHEEL_DIR) {
    $Wheels = $env:AKM_WHEEL_DIR
}
else {
    $BaseUrl = "https://github.com/$Repo/releases/download/$Tag"
    foreach ($name in @("akm_shared-$Version-py3-none-any.whl", "akm_node-$Version-py3-none-any.whl")) {
        Write-Host "==> 下载 $name"
        $dest = Join-Path $TmpDir $name
        try {
            Invoke-WebRequest "$BaseUrl/$name" -OutFile $dest
        }
        catch {
            Write-Error "下载失败,请确认 Release $Tag 存在该资产: $name"
        }
    }
    $Wheels = $TmpDir
}

# ---------- 4. uv tool install ----------
# --reinstall 保证幂等:重复执行等价于升级/修复到目标版本
uv tool install "akm-node==$Version" --find-links $Wheels --reinstall
if ($LASTEXITCODE -ne 0) {
    Write-Error "uv tool install 失败(退出码 $LASTEXITCODE)"
}

# ---------- 5. 引导 ----------
Write-Host ""
Write-Host "=================================================="
Write-Host "✅ akm-node $Version 安装完成"
Write-Host "=================================================="
Write-Host "下一步:"
Write-Host "  1. akm-node login        # 输入 Hub 地址与管理员账号,接入知识库"
Write-Host "  2. akm-node              # 常驻运行,同步本地知识目录"
Write-Host "  3. akm-node --mcp        # 供本机智能体(MCP)调用的检索工具"
Write-Host ""
Write-Host "凭证保存在 $HOME\.akm-node\.env,可用 AKM_NODE_ENV_FILE 自定义路径"
Write-Host "如当前终端找不到 akm-node 命令,请重开终端(PATH 刷新)"
