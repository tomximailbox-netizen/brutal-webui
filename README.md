# Brutal 流量控制 WebUI

基于 Linux 内核拥塞控制与 `brutalctl` 命令行工具的现代化轻量级可视化流量控制管理系统。

---

## ✨ 核心特性

1. **直接管理 IP 流量控制规则（全面支持 IPv4 与 IPv6）**：
   - 实时读取并展示 `brutalctl list` 规则清单（包含 DESTINATION、RATE、GAIN、LOCK、ROUTE、MEMBERS、SENT 等字段）。
   - 规则来源清晰区分：直观标记 `[域名同步]` 与 `[手动添加(临时)]` 来源标签。
   - **手动规则内存隔离（重启自动失效）**：WebUI 手动添加的 IP 规则仅在内存中维护、绝不落盘持久化，服务器重启后自动失效。
   - **定时刷新白名单保护**：后台域名定时同步刷新时，只针对域名自身的 IP 变化做增删比对，**自动保护手动添加的 IP 不会被误删**。
   - **智能掩码补齐**：支持手动添加 IPv4 与 IPv6。若未填掩码：**IPv4 默认补齐 `/32`，IPv6 默认补齐 `/128`**；若手动输入自定义掩码（如 `/64` 或 `/24`）则予以保留。
   - 默认自动识别并带入客户端当前真实 IP（支持 IPv4/IPv6），内置预设速率快捷键（50M, 100M, 200M, 500M, 1000M）。
   - 实时搜索与单条删除规则（带确认防误触）。
2. **域名清单持久化与自动同步（双栈解析 & 纯净过滤 & 支持单行自定义速率）**：
   - 在线可视化编辑 `brut_domain.txt`（每行一个域名，支持 `#` 注释）。
   - **支持单域名自定义限速速率**：可在域名后以空格指定速率（如 `example.com 200` 或 `fast.org 500`），未定义时默认应用全局速率（**100 Mbps**）。
   - 自动与原生 `brutal_sync.sh` 脚本联动，同时自动解析域名的 **IPv4 (A记录)** 与 **IPv6 (AAAA记录)** 并分别继承该域名指定的速率应用 `/32` 与 `/128` 限速规则。
   - **严格纯净过滤（增加时不增加，删除时允许并自动清理）**：
     - 若域名无原生 IPv6（无 AAAA 记录），则**只添加 IPv4，绝不添加多余的 IPv6 规则**；
     - **自动增加时绝不添加 `::ffff:x.x.x.x` 形式的 IPv4 兼容/映射地址**；
     - **删除操作（WebUI 手动删除 & 定时同步自动清理）完全允许并支持识别 `::ffff:` 规则**，确保之前已经误添加在服务器上的 `::ffff:.../128` 遗留规则能在下次同步时被自动清理，或在 Web 界面被正常删除。
   - 内置单域名 DNS 解析测试工具，即时排查并分类展示域名的 IPv4 与原生 IPv6 解析结果。
3. **静态 IP 清单配置 (`brut_ip.txt`) & 临时 IP 一键固化（支持自定义速率）**：
   - 模仿域名清单，全新提供独立的 **“静态IP清单配置”** 选项卡。
   - 在线编辑与维护 `brut_ip.txt`（每行一个 IP/CIDR，支持 IPv4 与 IPv6，支持以 `#` 开头的注释行）。
   - **支持单个 IP 自定义限速速率**：支持 `1.2.3.4 200`、`2001:db8::1 500` 等格式，未定义默认应用 100 Mbps。
   - **一键固化保存（速率不丢失）**：在规则列表查看页面中，对于手动添加的临时规则，支持**单条点击“存入清单”**或**顶部“一键保存所有临时IP到清单”**，一键写入 `brut_ip.txt`（自动连同当前运行的实际速率如 200M 一并保存写入），重启后永久保留生效。
   - 此清单中的规则自动纳入同步免清理白名单，开机与定时同步时受绝对保护不被误删。
4. **灵活可插拔的多语言国际化支持 (i18n)**：
   - 完整支持 **简体中文 (zh-CN)**、**繁體中文 (zh-TW)** 与 **English (en)**。
   - **智能浏览器语言嗅探**：初次访问自动根据用户的浏览器语言偏好展示（包含香港/台湾地区自动切换繁体，中文地区切换简体，**其他任何语种默认优雅回退为英文**）。
   - **主页自由切换**：顶部导航栏自带语言切换器，随选即生效且记忆存储。
   - **高扩展性架构 (`static/i18n.js`)**：后续增加新语言（如日文、韩文等）**无需改动任何 HTML**，仅需在注册表中增加一个对象即可自动全站生效！
5. **终端式同步控制台**：
   - 模拟 Linux 终端样式的日志窗口，实时滚动查看 `brutal_sync.sh` 同步执行的输出细节。
6. **后台自动定时调度 & 开机自启快速同步**：
   - **服务启动延迟即时同步**：服务器启动或服务重启后，默认延迟 5 秒立即执行首次域名解析与规则同步，快速恢复控速规则。
   - 支持在 Web 设置界面开启/关闭后台定时调度，并可自由配置执行周期（如 300 秒/600 秒）与启动首次同步延迟时间。
7. **安全凭据认证**：
   - 内置管理员密码防护，生成高强度随机 Token 会话认证（Header 与 HttpOnly Cookie 双重支持），防暴力破解与时序攻击。
8. **零外部 pip 依赖 & 本地 Mock 支持**：
   - 100% 纯 Python 3 标准库实现，无需在服务器上 `pip install` 任何第三方包。
   - 在未安装 `brutalctl` 或非 Linux 环境（如 Windows/macOS 开发机）下自动启用内置 Mock 虚拟引擎，开箱即用。

---

## 📁 目录结构

```text
.
├── install.sh               # 远程一键安装 / 无损热更新引导入口
├── uninstall.sh             # 一键彻底卸载脚本（自动备份现有数据）
├── deploy.sh                # 本地一键安装、平滑更新与 systemd 部署核心
├── app.py                   # WebUI 服务主程序（WSGI HTTP 服务与 API）
├── config.example.json      # 配置文件模板（包含端口、密码、SSL等配置）
├── brut_domain.txt          # 域名持久化清单（支持单行自定义速率）
├── brut_ip.txt              # 静态 IP 持久化清单（支持单行自定义速率与 CIDR）
├── brutal_sync.sh           # 原生 DNS 解析与 brutalctl 规则同步脚本
├── brutal-web.service       # systemd 服务管理单元
├── nginx.conf.example       # Nginx HTTPS 反向代理与子路径配置范例
├── USER_MANUAL.md           # 详细使用手册（含网络代理、Xray Reality 等高级配置）
├── test_app.py              # 核心逻辑单元测试
├── test_api_integration.py  # 端到端 API 集成测试
├── test_i18n.py             # 多语言国际化自动化测试
├── test_manual_protection.py# 规则保护逻辑验证测试
├── core/
│   ├── auth.py              # 认证鉴权与 Token 管理
│   ├── brutal_wrapper.py    # brutalctl 底层交互封装与本地 Mock 适配
│   ├── domain_manager.py    # brut_domain.txt 读写与 DNS 测试
│   ├── ip_manager.py        # brut_ip.txt 静态规则持久化管理
│   └── sync_runner.py       # 同步脚本调度器、互斥锁与日志捕获
├── static/
│   ├── app.js               # 前端单页面应用交互控制
│   ├── i18n.js              # 注册式多语言国际化引擎 (zh-CN / zh-TW / en)
│   └── style.css            # 终端样式与深色玻璃拟态主题
└── templates/
    ├── login.html           # 独立极简登录页面（服务端物理隔离未授权访问）
    └── index.html           # 授权管理控制台 SPA 页面
```

---

## ⚡ 一行命令快速安装 / 无损热更新

在 Linux 服务器（Ubuntu / Debian / CentOS / Rocky 等）上直接以 root 身份运行：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/tomximailbox-netizen/brutal-webui/main/install.sh)
```

> 💡 **特性说明**：
> 1. **开箱即用**：零外部依赖，免配 Python 虚拟环境，自动配置 `systemd` 开机自启服务；
> 2. **可重复执行（无损热更新）**：后续想要升级到最新版本时，**直接再次运行上述同一行命令即可**！脚本内置数据保护机制，**绝对不会覆盖**您现有的 `config.json`（密码与端口）、`brut_domain.txt`（域名清单）、`brut_ip.txt`（静态 IP 清单）以及自定义的 SSL 证书。

### 🗑️ 一键彻底卸载（防后悔自动备份）
若不再需要本工具，执行一行命令即可彻底移除：
```bash
bash <(curl -fsSL https://raw.githubusercontent.com/tomximailbox-netizen/brutal-webui/main/uninstall.sh)
```
*(卸载脚本会在注销服务并清理安装目录前，自动将您现有的密码配置与 IP/域名清单打包备份至 `/root/brutal_backup_*.tar.gz`)*

---

## 🚀 快速启动与本地测试

### 本地直接运行
在当前电脑上运行：
```bash
python app.py
```
- 服务将监听 `http://0.0.0.0:8080`。
- 浏览器打开 `http://localhost:8080` 即可进入管理面板。
- 默认登录密码：`admin123`（可在 `config.json` 中自定义）。
- 在本地测试时，系统会自动以 `[Mock 虚拟模式]` 运行，可以完整体验添加规则、删除规则、编辑域名与查看模拟同步日志。

---

## 🐧 Linux 离线/手动部署与运维

如果下载了源码包到服务器本地，亦可手动部署：

```bash
chmod +x deploy.sh
sudo ./deploy.sh
```

脚本将自动完成：
1. 校验 Python 3 环境。
2. 安装项目文件到 `/opt/brutal-webui/`。
3. 自动生成并提示初始管理员密码。
4. 注册并启动 `brutal-web.service` 系统服务，并设置开机自启。

### 常用运维命令
- **查看服务状态**：`systemctl status brutal-web`
- **重启服务**：`systemctl restart brutal-web`
- **查看运行日志**：`journalctl -u brutal-web -f`
- **停止服务**：`systemctl stop brutal-web`

---

## ⚙️ 配置文件说明 (`config.json`)

```json
{
  "server": {
    "host": "0.0.0.0",
    "port": 8080
  },
  "auth": {
    "admin_password": "你的强密码",
    "session_timeout_hours": 24
  },
  "brutal": {
    "brutalctl_bin": "brutalctl",
    "default_rate_mbps": 100,
    "domain_file_path": "./brut_domain.txt",
    "sync_script_path": "./brutal_sync.sh"
  },
  "sync_scheduler": {
    "enabled": true,
    "interval_seconds": 300
  }
}
```
可以在 Web 界面的“系统设置”选项卡中在线修改密码与自动同步周期。
