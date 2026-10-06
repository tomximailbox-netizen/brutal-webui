#!/bin/bash
# ============================================================
# Brutal Traffic Control WebUI - 一键在线安装 / 无损热更新脚本
# ============================================================
# 支持初次安装与重复执行无损升级（自动保留配置、密码、证书与IP清单）
# GitHub 仓库: https://github.com/tomximailbox-netizen/brutal-webui
# ============================================================

set -euo pipefail

# 仓库信息与默认分支（可通过环境变量自定义覆盖）
REPO_OWNER="${BRUTAL_REPO_OWNER:-tomximailbox-netizen}"
REPO_NAME="${BRUTAL_REPO_NAME:-brutal-webui}"
BRANCH="${BRUTAL_BRANCH:-main}"

echo "=================================================="
echo "      🚀 Brutal WebUI 自动化安装与更新引导       "
echo "=================================================="

# 1. 检查 root 权限
if [ "$(id -u)" -ne 0 ]; then
    echo "❌ 错误：请使用 root 权限或 sudo 运行本安装脚本！"
    echo "示例: sudo bash <(curl -fsSL https://raw.githubusercontent.com/${REPO_OWNER}/${REPO_NAME}/${BRANCH}/install.sh)"
    exit 1
fi

# 2. 检测系统包管理器并自动安装必要依赖
install_dependencies() {
    local missing=()
    command -v curl >/dev/null 2>&1 || missing+=("curl")
    command -v tar >/dev/null 2>&1 || missing+=("tar")
    command -v python3 >/dev/null 2>&1 || missing+=("python3")

    if [ ${#missing[@]} -gt 0 ]; then
        echo "正在自动安装缺失的系统依赖: ${missing[*]} ..."
        if command -v apt-get >/dev/null 2>&1; then
            apt-get update -y && apt-get install -y "${missing[@]}"
        elif command -v dnf >/dev/null 2>&1; then
            dnf install -y "${missing[@]}"
        elif command -v yum >/dev/null 2>&1; then
            yum install -y "${missing[@]}"
        elif command -v apk >/dev/null 2>&1; then
            apk add --no-cache "${missing[@]}"
        elif command -v pacman >/dev/null 2>&1; then
            pacman -Sy --noconfirm "${missing[@]}"
        elif command -v zypper >/dev/null 2>&1; then
            zypper install -y "${missing[@]}"
        else
            echo "⚠️ 无法识别系统包管理器，请确保系统中已安装: ${missing[*]}"
        fi
    fi
}

install_dependencies

# 3. 创建安全临时下载工作区并在脚本退出时自动清理
TMP_DIR=$(mktemp -d /tmp/brutal-install.XXXXXX)
cleanup() {
    rm -rf "$TMP_DIR"
}
trap cleanup EXIT INT TERM

echo "正在从 GitHub 获取最新项目归档源码包 (${REPO_OWNER}/${REPO_NAME}@${BRANCH}) ..."

TAR_URL_OFFICIAL="https://github.com/${REPO_OWNER}/${REPO_NAME}/archive/refs/heads/${BRANCH}.tar.gz"
TAR_URL_MIRROR1="https://ghfast.top/https://github.com/${REPO_OWNER}/${REPO_NAME}/archive/refs/heads/${BRANCH}.tar.gz"
TAR_URL_MIRROR2="https://ghproxy.net/https://github.com/${REPO_OWNER}/${REPO_NAME}/archive/refs/heads/${BRANCH}.tar.gz"

ARCHIVE_FILE="$TMP_DIR/source.tar.gz"
DOWNLOAD_SUCCESS=0

# 多源轮询容错下载（支持海外直连与国内加速代理自动切换）
for URL in "$TAR_URL_OFFICIAL" "$TAR_URL_MIRROR1" "$TAR_URL_MIRROR2"; do
    echo "尝试下载通道: $URL ..."
    if curl -fsSL --connect-timeout 10 --max-time 120 "$URL" -o "$ARCHIVE_FILE" 2>/dev/null; then
        if [ -s "$ARCHIVE_FILE" ] && tar -tzf "$ARCHIVE_FILE" >/dev/null 2>&1; then
            DOWNLOAD_SUCCESS=1
            echo "✅ 源码包下载成功！"
            break
        fi
    fi
    echo "当前通道连接超时或受阻，自动切换下一个备选通道..."
done

if [ "$DOWNLOAD_SUCCESS" -ne 1 ]; then
    echo "❌ 错误：下载源码归档包失败，请检查服务器网络连接或稍后重试。"
    exit 1
fi

# 4. 解压并定位源码目录
echo "正在解压项目文件 ..."
tar -xzf "$ARCHIVE_FILE" -C "$TMP_DIR"

SRC_DIR=$(find "$TMP_DIR" -maxdepth 2 -type f -name "deploy.sh" -exec dirname {} \; | head -n 1)

if [ -z "$SRC_DIR" ] || [ ! -d "$SRC_DIR" ]; then
    echo "❌ 错误：归档包解压内容异常，未找到部署核心文件 deploy.sh"
    exit 1
fi

# 5. 执行无损部署/热更新逻辑
cd "$SRC_DIR"
chmod +x deploy.sh

echo "正在启动部署进程 ..."
./deploy.sh

exit 0
