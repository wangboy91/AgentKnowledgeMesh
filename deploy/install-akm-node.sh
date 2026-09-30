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
echo "  2. akm-node              # 常驻运行,同步本地知识目录(文件改动自动同步)"
echo "  3. akm-node --mcp        # 供本机智能体(MCP)调用的检索工具"
echo ""
echo "凭证保存在 ~/.akm-node/.env,可用 AKM_NODE_ENV_FILE 自定义路径"
echo "无人值守(服务/计划任务)可改配 AKM_HUB_USERNAME / AKM_HUB_PASSWORD,启动时自动登录"
echo ""

# ---------- 6. 后台常驻模板(可选;只打印,不自动注册) ----------
AKM_BIN="$(command -v akm-node 2>/dev/null || echo "$HOME/.local/bin/akm-node")"
OS_NAME="$(uname -s)"

echo "--------------------------------------------------"
echo "可选:让节点后台常驻(文件改动数秒内同步到 Hub)"
echo "--------------------------------------------------"

if [ "$OS_NAME" = "Linux" ]; then
    echo "systemd(user 级)—— 内容保存为 ~/.config/systemd/user/akm-node.service:"
    echo ""
    cat <<EOF
[Unit]
Description=AgentKnowledgeMesh Node
After=network-online.target

[Service]
Type=simple
ExecStart=${AKM_BIN}
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
EOF
    echo ""
    echo "启用:"
    echo "  systemctl --user daemon-reload"
    echo "  systemctl --user enable --now akm-node"
    echo "  systemctl --user status akm-node"
    echo "  # 需要未登录也运行:loginctl enable-linger \$USER"
elif [ "$OS_NAME" = "Darwin" ]; then
    echo "launchd —— 内容保存为 ~/Library/LaunchAgents/com.akm.node.plist:"
    echo ""
    cat <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.akm.node</string>
    <key>ProgramArguments</key>
    <array>
        <string>${AKM_BIN}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
EOF
    echo ""
    echo "启用:"
    echo "  launchctl load ~/Library/LaunchAgents/com.akm.node.plist"
    echo "  launchctl list | grep akm"
else
    echo "当前平台(${OS_NAME})请用 pm2 或系统自带的服务管理方式托管。"
fi

echo ""
echo "任意平台也可用 pm2:  pm2 start akm-node --name akm-node"
echo ""
echo "提示:节点监听知识库目录,文件改动数秒内同步到 Hub。"
echo "      容器 / 网络挂载(bind mount)场景事件监听不可用,"
echo "      请在 ~/.akm-node/.env 设 AKM_WATCH_ENABLED=false 依赖定时对账。"
