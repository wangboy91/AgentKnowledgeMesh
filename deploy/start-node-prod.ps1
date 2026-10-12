# start-node-prod.ps1 - 启动「正式环境」隔离节点实例(Windows PowerShell)
#
# 作用:把正式实例的隔离参数固化在「进程环境」里,再调用全局 akm-node。
#       交互登录同样走本脚本:`start-node-prod.ps1 login`
#
# 为什么必须在「进程环境」里设,而不是写进 .env:
#   app/config.py 在模块 import 时用 os.environ 读取 AKM_NODE_ENV_FILE /
#   AKM_NODE_STATE_DIR,早于 pydantic-settings 加载 env 文件——写进 .env 不生效。
#   详见 openspec 变更 2026-09-30-fix-node-state-isolation。
#
# 与开发实例的关系:
#   开发: cd src\node; uv run akm-node        (凭证 ~/.akm-node,快照随包内 data/ 或 ~/.akm-node)
#   正式: 本脚本                              (凭证与快照均隔离在 ~/.akm-node-prod)
#
# 用法(本机执行策略默认是 Restricted,必须带 -ExecutionPolicy Bypass):
#   powershell -ExecutionPolicy Bypass -File deploy\start-node-prod.ps1
#   powershell -ExecutionPolicy Bypass -File deploy\start-node-prod.ps1 login
# 等价替代(Git Bash / Linux / macOS): ./deploy/start-node-prod.sh [login]
#
# 环境变量:
#   $env:AKM_PROD_HOME  正式实例的数据目录(默认 $HOME\.akm-node-prod)

$ErrorActionPreference = "Stop"

if ($env:AKM_PROD_HOME) { $ProdHome = $env:AKM_PROD_HOME } else { $ProdHome = Join-Path $HOME ".akm-node-prod" }

# 仅作用于本进程及其子进程,不改动系统级环境变量
$env:AKM_NODE_ENV_FILE = Join-Path $ProdHome ".env"
$env:AKM_NODE_STATE_DIR = $ProdHome

if (-not (Test-Path -LiteralPath $env:AKM_NODE_ENV_FILE)) {
    Write-Error "找不到正式环境配置: $($env:AKM_NODE_ENV_FILE)`n请先创建该文件(参考 docs/deployment.md 的『正式 / 开发双环境隔离』)。"
}

$cmd = Get-Command akm-node -ErrorAction SilentlyContinue
if ($cmd) {
    $AkmNode = $cmd.Source
}
elseif (Test-Path -LiteralPath (Join-Path $HOME ".local\bin\akm-node.exe")) {
    $AkmNode = Join-Path $HOME ".local\bin\akm-node.exe"
}
else {
    Write-Error "找不到 akm-node 命令。请先执行: cd src\node; uv tool install . --reinstall"
}

Write-Host "==> 正式环境隔离参数"
Write-Host "    AKM_NODE_ENV_FILE  = $env:AKM_NODE_ENV_FILE"
Write-Host "    AKM_NODE_STATE_DIR = $env:AKM_NODE_STATE_DIR"
Write-Host "    可执行文件         = $AkmNode"
Write-Host ""

# 恢复默认错误偏好:原生命令往 stderr 写日志(节点运行中常见)不应被当作终止性错误
$ErrorActionPreference = "Continue"

& $AkmNode @args
exit $LASTEXITCODE
