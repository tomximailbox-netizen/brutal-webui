#!/bin/bash
# ============================================================
# Brutal Traffic Control WebUI - 一键彻底卸载脚本
# ============================================================
# GitHub: https://github.com/tomximailbox-netizen/brutal-webui
# ============================================================

set -euo pipefail

INSTALL_DIR="/opt/brutal-webui"
SERVICE_NAME="brutal-web"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

echo "=================================================="
echo "          🗑️  Brutal WebUI 一键卸载向导          "
echo "=================================================="

# 1. 检查 root 权限
if [ "$(id -u)" -ne 0 ]; then
    echo "❌ 错误：请使用 root 权限或 sudo 运行本卸载脚本！"
    exit 1
fi

# 2. 检查系统是否安装过
if [ ! -d "$INSTALL_DIR" ] && [ ! -f "$SERVICE_FILE" ]; then
    echo "ℹ️  未在系统中检测到 Brutal WebUI 的安装痕迹，无需卸载。"
    exit 0
fi

# 3. 二次确认（支持 -y 或 --yes 跳过交互）
FORCE=0
for arg in "$@"; do
    if [ "$arg" = "-y" ] || [ "$arg" = "--yes" ]; then
        FORCE=1
    fi
done

if [ "$FORCE" -ne 1 ]; then
    read -rp "⚠️  确认要彻底卸载 Brutal WebUI 吗？此操作将停止服务并删除安装目录。(y/N): " confirm
    case "$confirm" in
        [yY][eE][sS]|[yY])
            ;;
        *)
            echo "已取消卸载操作。"
            exit 0
            ;;
    esac
fi

# 4. 安全防护：自动备份关键配置与清单（防止误删丢失）
BACKUP_TAR=""
if [ -d "$INSTALL_DIR" ]; then
    BACKUP_TIME=$(date +"%Y%m%d_%H%M%S")
    BACKUP_TAR="/root/brutal_backup_${BACKUP_TIME}.tar.gz"

    FILES_TO_BACKUP=()
    [ -f "$INSTALL_DIR/config.json" ] && FILES_TO_BACKUP+=("config.json")
    [ -f "$INSTALL_DIR/brut_domain.txt" ] && FILES_TO_BACKUP+=("brut_domain.txt")
    [ -f "$INSTALL_DIR/brut_ip.txt" ] && FILES_TO_BACKUP+=("brut_ip.txt")
    [ -f "$INSTALL_DIR/cert.pem" ] && FILES_TO_BACKUP+=("cert.pem")
    [ -f "$INSTALL_DIR/key.pem" ] && FILES_TO_BACKUP+=("key.pem")

    if [ ${#FILES_TO_BACKUP[@]} -gt 0 ]; then
        echo "正在自动备份关键配置与数据清单至: $BACKUP_TAR ..."
        tar -czf "$BACKUP_TAR" -C "$INSTALL_DIR" "${FILES_TO_BACKUP[@]}" 2>/dev/null || true
        echo "✅ 备份完成！若将来重新安装，可从该压缩包中恢复数据。"
    fi
fi

# 5. 停止并注销 systemd 服务
echo "正在停止并注销系统服务 ..."
if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
    systemctl stop "$SERVICE_NAME" 2>/dev/null || true
fi

if systemctl is-enabled --quiet "$SERVICE_NAME" 2>/dev/null; then
    systemctl disable "$SERVICE_NAME" 2>/dev/null || true
fi

if [ -f "$SERVICE_FILE" ]; then
    rm -f "$SERVICE_FILE"
    systemctl daemon-reload 2>/dev/null || true
fi

# 6. 删除安装目录与相关临时文件
echo "正在清理安装目录 ($INSTALL_DIR) ..."
if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
fi

rm -f /tmp/brutal_config.json.bak /tmp/brutal_domain.txt.bak /tmp/brutal_ip.txt.bak /tmp/brutal_cert.pem.bak /tmp/brutal_key.pem.bak 2>/dev/null || true

echo
echo "=================================================="
echo "          🎉 Brutal WebUI 已彻底卸载完成！       "
echo "=================================================="
if [ -n "$BACKUP_TAR" ] && [ -f "$BACKUP_TAR" ]; then
    echo "您的历史配置备份保留在: $BACKUP_TAR"
fi
echo "感谢您的使用！"
echo "=================================================="

exit 0
