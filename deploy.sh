#!/bin/bash
# ============================================================
# Brutal WebUI 一键安装与部署脚本
# ============================================================

set -euo pipefail

INSTALL_DIR="/opt/brutal-webui"
SERVICE_NAME="brutal-web"

echo "=================================================="
echo "          🚀 安装 Brutal 流量控制 WebUI          "
echo "=================================================="

# 1. 检查 root 权限
if [ "$(id -u)" -ne 0 ]; then
    echo "错误：请使用 root 或 sudo 执行本脚本。"
    exit 1
fi

# 2. 检查 Python 3 环境
if ! command -v python3 >/dev/null 2>&1; then
    echo "错误：未检测到 Python 3，请先安装 (例如: apt update && apt install -y python3 或 yum install -y python3)"
    exit 1
fi

PY_VER=$(python3 --version)
echo "检测到环境: $PY_VER"

# 3. 部署或增量更新文件
if [ -d "$INSTALL_DIR" ] && [ -f "$INSTALL_DIR/config.json" ]; then
    echo "检测到已有安装，正在执行【无损热更新】（将保留现有密码、域名清单与静态IP清单）..."
    cp "$INSTALL_DIR/config.json" /tmp/brutal_config.json.bak
    [ -f "$INSTALL_DIR/brut_domain.txt" ] && cp "$INSTALL_DIR/brut_domain.txt" /tmp/brutal_domain.txt.bak
    [ -f "$INSTALL_DIR/brut_ip.txt" ] && cp "$INSTALL_DIR/brut_ip.txt" /tmp/brutal_ip.txt.bak
    HAS_EXISTING=1
else
    echo "正在全新安装文件到: $INSTALL_DIR ..."
    mkdir -p "$INSTALL_DIR"
    HAS_EXISTING=0
fi

cp -r ./* "$INSTALL_DIR/"
cd "$INSTALL_DIR"

# 如果是更新，自动恢复原有的配置和域名文件，防止被本地测试文件覆盖
if [ "$HAS_EXISTING" -eq 1 ]; then
    echo "已成功恢复您的原配置文件与清单数据..."
    cp /tmp/brutal_config.json.bak "$INSTALL_DIR/config.json"
    [ -f /tmp/brutal_domain.txt.bak ] && cp /tmp/brutal_domain.txt.bak "$INSTALL_DIR/brut_domain.txt"
    [ -f /tmp/brutal_ip.txt.bak ] && cp /tmp/brutal_ip.txt.bak "$INSTALL_DIR/brut_ip.txt"
    rm -f /tmp/brutal_config.json.bak /tmp/brutal_domain.txt.bak /tmp/brutal_ip.txt.bak
fi

# 4. 给予脚本执行权限
chmod +x brutal_sync.sh deploy.sh app.py

# 5. 生成配置文件
if [ ! -f config.json ]; then
    echo "正在初始化 config.json ..."
    RANDOM_PASS=$(tr -dc A-Za-z0-9 </dev/urandom 2>/dev/null | head -c 16 || echo "Admin$RANDOM")
    sed "s/ChangeThisPassword123!/$RANDOM_PASS/g" config.example.json > config.json
    echo "--------------------------------------------------"
    echo "【初始管理员密码】: $RANDOM_PASS"
    echo "--------------------------------------------------"
fi

# 6. 配置 systemd 服务
echo "正在配置 systemd 系统服务 ..."
cp brutal-web.service "/etc/systemd/system/${SERVICE_NAME}.service"
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}.service"
systemctl restart "${SERVICE_NAME}.service"

echo
echo "=================================================="
if [ "$HAS_EXISTING" -eq 1 ]; then
    echo "          🎉 Brutal WebUI 更新并重启成功！       "
else
    echo "          🎉 Brutal WebUI 首次部署成功！         "
fi
echo "=================================================="
echo "服务状态: systemctl status $SERVICE_NAME"
echo "查看日志: journalctl -u $SERVICE_NAME -f"
echo "WebUI 地址: 查看 $INSTALL_DIR/config.json 中的端口配置"
echo "若要启用 HTTPS，可在 $INSTALL_DIR/config.json 开启 ssl.enabled"
echo "=================================================="
