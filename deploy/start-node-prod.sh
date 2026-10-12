#!/usr/bin/env bash
# start-node-prod.sh - 启动「正式环境」隔离节点实例(Linux / macOS / Git Bash)
#
# 作用:把正式实例的隔离参数固化在「进程环境」里,再调用全局 akm-node。
#       交互登录同样走本脚本:./deploy/start-node-prod.sh login
#
# 为什么必须在「进程环境」里设,而不是写进 .env:
#   app/config.py 在模块 import 时用 os.environ 读取 AKM_NODE_ENV_FILE /
#   AKM_NODE_STATE_DIR,早于 pydantic-settings 加载 env 文件——写进 .env 不生效。
#   详见 openspec 变更 2026-09-30-fix-node-state-isolation。
#
# 与开发实例的关系:
#   开发: cd src/node && uv run akm-node   (凭证 ~/.akm-node,快照随包内 data/ 或 ~/.akm-node)
#   正式: 本脚本                           (凭证与快照均隔离在 ~/.akm-node-prod)
#
# 用法:
#   ./deploy/start-node-prod.sh
#   ./deploy/start-node-prod.sh login      # 首次交互登录
#
# 环境变量:
#   AKM_PROD_HOME  正式实例的数据目录(默认 $HOME/.akm-node-prod)

set -euo pipefail

PROD_HOME="${AKM_PROD_HOME:-$HOME/.akm-node-prod}"

# 仅作用于本进程及其子进程,不改动 shell 配置文件
export AKM_NODE_ENV_FILE="$PROD_HOME/.env"
export AKM_NODE_STATE_DIR="$PROD_HOME"

if [ ! -f "$AKM_NODE_ENV_FILE" ]; then
  echo "❌ 找不到正式环境配置: $AKM_NODE_ENV_FILE" >&2
  echo "   请先创建该文件(参考 docs/deployment.md 的『正式 / 开发双环境隔离』)。" >&2
  exit 1
fi

if command -v akm-node >/dev/null 2>&1; then
  AKM_NODE_BIN="$(command -v akm-node)"
elif [ -x "$HOME/.local/bin/akm-node" ]; then
  AKM_NODE_BIN="$HOME/.local/bin/akm-node"
elif [ -x "$HOME/.local/bin/akm-node.exe" ]; then
  # Windows(Git Bash):uv tool 装出的可执行文件带 .exe 后缀
  AKM_NODE_BIN="$HOME/.local/bin/akm-node.exe"
else
  echo "❌ 找不到 akm-node 命令。请先执行: (cd src/node && uv tool install . --reinstall)" >&2
  echo "   若已安装仍报此错，请把 ~/.local/bin 加入 PATH: uv tool update-shell" >&2
  exit 1
fi

echo "==> 正式环境隔离参数"
echo "    AKM_NODE_ENV_FILE  = $AKM_NODE_ENV_FILE"
echo "    AKM_NODE_STATE_DIR = $AKM_NODE_STATE_DIR"
echo "    可执行文件         = $AKM_NODE_BIN"
echo ""

exec "$AKM_NODE_BIN" "$@"
