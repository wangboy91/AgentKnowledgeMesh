#!/usr/bin/env bash
# install-akm-node.sh - akm-node 一键安装脚本(macOS / Linux)
#
# 从 GitHub Release 下载 akm_shared 与 akm_node 两个 wheel,
# 以 uv tool install 安装出全局 akm-node 命令。
#
# 用法:
#   curl -fsSL https://github.com/wangboy91/AgentKnowledgeMesh/releases/latest/download/install-akm-node.sh | bash
#
# 环境变量:
#   AKM_VERSION    指定版本号(如 0.2.0);缺省取最新 release
#   AKM_WHEEL_DIR  本地 wheel 目录,跳过下载(联调/离线安装用)

set -euo pipefail

REPO="wangboy91/AgentKnowledgeMesh"

# ---------- 1. uv 检测 / 安装 ----------
if ! command -v uv >/dev/null 2>&1; then
    echo "==> 未检测到 uv,开始安装..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi
if ! command -v uv >/dev/null 2>&1; then
    echo "❌ uv 安装后仍不可用,请重开终端后重新执行本脚本" >&2
    exit 1
fi

# ---------- 2. 解析版本 ----------
VERSION="${AKM_VERSION:-}"
if [ -z "$VERSION" ]; then
    VERSION="$(curl -fsSL "https://api.github.com/repos/${REPO}/releases/latest" \
        | sed -n 's/.*"tag_name": *"v\([^"]*\)".*/\1/p')"
fi
if [ -z "$VERSION" ]; then
    echo "❌ 无法确定安装版本(未设置 AKM_VERSION 且获取最新 release 失败)" >&2
    exit 1
fi
TAG="v${VERSION}"
echo "==> 安装 akm-node ${VERSION}"

# ---------- 3. 获取 wheel ----------
TMPDIR_AKM="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_AKM"' EXIT

if [ -n "${AKM_WHEEL_DIR:-}" ]; then
    WHEELS="$AKM_WHEEL_DIR"
else
    BASE_URL="https://github.com/${REPO}/releases/download/${TAG}"
    for name in "akm_shared-${VERSION}-py3-none-any.whl" "akm_node-${VERSION}-py3-none-any.whl"; do
        echo "==> 下载 ${name}"
        curl -fsSL -o "${TMPDIR_AKM}/${name}" "${BASE_URL}/${name}" \
            || { echo "❌ 下载失败,请确认 Release ${TAG} 存在该资产" >&2; exit 1; }
    done
    WHEELS="$TMPDIR_AKM"
fi

# ---------- 4. uv tool install ----------
# --reinstall 保证幂等:重复执行等价于升级/修复到目标版本
uv tool install "akm-node==${VERSION}" --find-links "$WHEELS" --reinstall

# ---------- 5. 引导 ----------
echo ""
echo "=================================================="
echo "✅ akm-node ${VERSION} 安装完成"
echo "=================================================="
echo "下一步:"
echo "  1. akm-node login        # 输入 Hub 地址与管理员账号,接入知识库"
echo "  2. akm-node              # 常驻运行,同步本地知识目录"
echo "  3. akm-node --mcp        # 供本机智能体(MCP)调用的检索工具"
echo ""
echo "凭证保存在 ~/.akm-node/.env,可用 AKM_NODE_ENV_FILE 自定义路径"
