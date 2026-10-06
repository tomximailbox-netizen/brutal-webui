# Brutal 流量控制 WebUI 用户手册

---

## 目录
1. [系统概述与核心特性](#1-系统概述与核心特性)
2. [环境准备与要求](#2-环境准备与要求)
3. [安装、更新与服务管理](#3-安装更新与服务管理)
   - [3.1 极简远程一行命令安装（推荐）](#31-极简远程一行命令安装推荐)
   - [3.2 可重复执行的平滑无损热更新](#32-可重复执行的平滑无损热更新)
   - [3.3 离线/手动上传部署方式](#33-离线手动上传部署方式)
   - [3.4 系统服务运维指令](#34-系统服务运维指令)
   - [3.5 一键彻底卸载（附带自动安全备份）](#35-一键彻底卸载附带自动安全备份)
4. [网络与安全配置 (HTTPS / Nginx / Xray)](#4-网络与安全配置)
5. [功能使用详解](#5-功能使用详解)
   - [5.1 管理员登录与服务端物理隔离安全防护](#51-管理员登录与服务端物理隔离安全防护)
   - [5.2 规则列表与实时监控](#52-规则列表与实时监控)
   - [5.3 手动添加规则与客户端 IP 自动带入](#53-手动添加规则与客户端-ip-自动带入)
   - [5.4 临时 IP 一键固化到清单](#54-临时-ip-一键固化到清单)
   - [5.5 域名清单配置与 DNS 双栈解析](#55-域名清单配置与-dns-双栈解析)
   - [5.6 静态 IP 清单配置与持久化管理](#56-静态-ip-清单配置与持久化管理)
   - [5.7 单行自定义限速速率规范](#57-单行自定义限速速率规范)
   - [5.8 终端式同步日志控制台](#58-终端式同步日志控制台)
   - [5.9 系统设置与定时调度](#59-系统设置与定时调度)
   - [5.10 多语言切换与国际化](#510-多语言切换与国际化)
6. [配置文件说明 (`config.json`)](#6-配置文件说明)
7. [常见问题与故障排查 (FAQ)](#7-常见问题与故障排查)

---

## 1. 系统概述与核心特性

**Brutal Traffic Control WebUI** 是专为 Linux 内核拥塞控制与 `brutalctl` 命令行工具打造的现代化、轻量级、高安全的图形化流量控制管理系统。

### ✨ 核心亮点
- **零外部 pip 依赖**：100% 基于 Python 3 标准库构建，无需安装任何第三方 Python 轮子或复杂环境，开箱即用。
- **全栈 IPv4 与 IPv6 双栈支持**：
  - IPv4 未填掩码默认自动补齐 `/32`（如 `1.2.3.4` → `1.2.3.4/32`）；
  - IPv6 未填掩码默认自动补齐 `/128`（如 `2001:db8::1` → `2001:db8::1/128`）；
  - 亦支持自定义子网掩码（如 `10.0.0.0/24`、`2408:8207::/64`）。
- **规则来源清晰三态管理**：
  - `[静态IP清单]`（蓝色）：存储于 `brut_ip.txt`，重启后永久保留，定时同步受绝对保护不被清理；
  - `[手动添加(临时)]`（黄色）：纯内存维护，重启自动失效，页面支持**一键转存固化**到清单；
  - `[域名同步]`（青色）：由 `brut_domain.txt` 域名 DNS 动态解析生成，随 A/AAAA 记录变更自动增删。
- **单行自定义速率**：支持在域名或 IP 后面直接以空格指定独享速率（如 `example.com 200`、`1.2.3.4 300`），未定义时默认应用全局 100 Mbps。
- **严格纯净过滤机制**：
  - 若域名无原生 IPv6（无 AAAA 记录），仅添加 IPv4，**绝不添加多余的 IPv6 规则**；
  - 自动添加时**坚决排除 `::ffff:x.x.x.x` 形式的 IPv4 映射兼容地址**；
  - 删除操作与失效清理则完全放行，可自动识别并彻底清理遗留的 `::ffff:...` 规则。
- **开机自愈快速恢复**：服务器开机重启后，系统默认延迟 5 秒立即执行首次域名与静态 IP 规则同步，保证网络服务迅速就绪。
- **灵活可扩展多语言 (i18n)**：支持简体中文、繁體中文与英文，初次访问自动感知浏览器语言（未定义语种默认使用英文），支持主页手动随心切换。

---

## 2. 环境准备与要求

| 项目 | 要求 | 说明 |
| :--- | :--- | :--- |
| **操作系统** | Linux (Ubuntu 20.04+, Debian 10+, CentOS 7+, Rocky Linux 等) | 需已加载 TCP Brutal 内核模块并安装有 `brutalctl` 工具 |
| **Python 版本** | Python 3.6 及以上 | 系统自带即可，**无需执行 `pip install`** |
| **系统特权** | `root` 或具备 `sudo` 免密执行权限 | 用于操作内核网络限速命令 (`brutalctl`) |
| **网络端口** | 默认端口 `8080` (HTTP) 或 `8443` (HTTPS) | 可在 `config.json` 中自由修改 |

---

## 3. 安装、更新与服务管理

### 3.1 极简远程一行命令安装（推荐）

在 Linux 服务器（Ubuntu / Debian / CentOS / Rocky 等）终端直接以 root 权限运行：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/tomximailbox-netizen/brutal-webui/main/install.sh)
```

脚本会自动完成：
- 检查并自动安装缺失的系统基础依赖（`curl`、`tar`、`python3`）；
- 从 GitHub 拉取最新源码归档；
- 部署至标准目录 `/opt/brutal-webui/` 并赋予必要权限；
- 自动生成高强度随机初始管理密码并显示在屏幕上；
- 注册并启动 `brutal-web.service` 系统服务，并设置为开机自启。

### 3.2 可重复执行的平滑无损热更新

当后续发布新功能或修复补丁时，**您只需要再次执行同一条安装命令**：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/tomximailbox-netizen/brutal-webui/main/install.sh)
```

> **安全无损保护机制**：
> 脚本检测到已有安装时会自动触发【无损热更新】流程，会自动备份并还原服务器上的：
> - `config.json`（管理员登录密码、端口与网络设置保持不变）
> - `brut_domain.txt`（原有域名清单 100% 保留）
> - `brut_ip.txt`（原有静态 IP 清单 100% 保留）
> - `cert.pem` / `key.pem`（若配置了 SSL 证书一并无损保留）
> 并在几秒钟内平滑重启服务，绝不会丢失任何现有数据与配置。

### 3.3 离线/手动上传部署方式

若服务器无法直接连接外网 GitHub，也可手动上传代码部署：
1. 将本项目所有文件上传到服务器的临时目录（如 `/root/brutal/`）；
2. 执行部署脚本：
   ```bash
   cd /root/brutal
   chmod +x deploy.sh
   sudo ./deploy.sh
   ```

### 3.4 系统服务运维指令

服务通过 Linux 标准 `systemd` 守护进程管理：
- **查看服务运行状态**：
  ```bash
  systemctl status brutal-web
  ```
- **重启服务**：
  ```bash
  systemctl restart brutal-web
  ```
- **停止服务**：
  ```bash
  systemctl stop brutal-web
  ```
- **查看实时输出日志**：
  ```bash
  journalctl -u brutal-web -f
  ```

### 3.5 一键彻底卸载（附带自动安全备份）

若不再需要使用本工具，可通过以下方式之一彻底清理：

- **方式 A：远程一行命令卸载**
  ```bash
  bash <(curl -fsSL https://raw.githubusercontent.com/tomximailbox-netizen/brutal-webui/main/uninstall.sh)
  ```
- **方式 B：本地已安装目录下直接卸载**
  ```bash
  cd /opt/brutal-webui
  sudo ./uninstall.sh
  ```

> 🛡️ **防后悔自动备份**：
> 脚本在停止服务与清空目录之前，会自动将您服务器上的 `config.json`（密码与端口）、`brut_domain.txt`（域名清单）、`brut_ip.txt`（静态 IP 清单）及证书打包为 `/root/brutal_backup_YYYYMMDD_HHMMSS.tar.gz`，即使误卸载也可以随时找回您的宝贵数据。

---

## 4. 网络与安全配置

公网传输流量控制管理密码存在被嗅探风险，强烈建议启用 HTTPS。

### 4.1 方案 A：Python 内置原生 HTTPS（推荐，免安装任何额外 Web 服务）

Python 内置的 `ssl` 模块支持开箱即用直接开启 HTTPS：

1. **生成证书**（若使用 IP 直连访问，执行一条命令生成有效期 10 年的自签名证书）：
   ```bash
   cd /opt/brutal-webui
   openssl req -x509 -newkey rsa:2048 -nodes -keyout key.pem -out cert.pem -days 3650 -subj "/CN=brutal-webui"
   ```
   *(若有自己的域名证书，直接将公钥证书命名为 `cert.pem`，私钥命名为 `key.pem` 放置于该目录)*
2. **修改 `/opt/brutal-webui/config.json` 开启 SSL**：
   ```json
   {
     "server": {
       "host": "0.0.0.0",
       "port": 8443
     },
     "ssl": {
       "enabled": true,
       "cert_file": "./cert.pem",
       "key_file": "./key.pem"
     }
   }
   ```
3. **重启生效**：`systemctl restart brutal-web`。访问：`https://<你的服务器IP>:8443`。

---

### 4.2 方案 B：Nginx HTTPS 反向代理（推荐结合域名）

让 WebUI 仅监听本地内网 `127.0.0.1:8080`，所有外部访问通过 Nginx 的 443 端口加密接入：

1. **修改 `/opt/brutal-webui/config.json`**：
   ```json
   {
     "server": {
       "host": "127.0.0.1",
       "port": 8080
     },
     "ssl": {
       "enabled": false
     }
   }
   ```
   重启服务：`systemctl restart brutal-web`。

2. **Nginx 配置示例 (`/etc/nginx/conf.d/brutal.conf`)**：

   - **场景 1：根路径访问 (`https://your-domain.com/`)**
     ```nginx
     server {
         listen 443 ssl http2;
         server_name your-domain.com;

         ssl_certificate     /etc/nginx/ssl/cert.pem;
         ssl_certificate_key /etc/nginx/ssl/key.pem;

         location / {
             proxy_pass http://127.0.0.1:8080;
             proxy_set_header Host $host;
             proxy_set_header X-Real-IP $remote_addr;
             proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
             proxy_set_header X-Forwarded-Proto $scheme;
             proxy_buffering off;
             proxy_read_timeout 300s;
         }
     }
     ```

   - **场景 2：子目录/二级路径访问 (`https://your-domain.com/brutal/`)**
     ```nginx
     location ^~ /brutal/ {
         # 【关键】末尾必须带斜杠 "/"，Nginx 才会将前缀剥离后转给后端
         proxy_pass http://127.0.0.1:8080/;

         proxy_set_header Host $host;
         proxy_set_header X-Real-IP $remote_addr;
         proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
         proxy_set_header X-Forwarded-Proto $scheme;
         proxy_buffering off;
         proxy_read_timeout 300s;
     }
     ```

---

### 4.3 方案 C：Xray Reality 回落到 Nginx 并透传客户端真实 IP

若架构为 `Xray Reality (443) -> 回落 Nginx -> 反代本地 WebUI`：
1. **Xray 配置**：在 `fallbacks` 中为回落目标增加 `"xver": 1`；
2. **Nginx 配置**：
   ```nginx
   server {
       listen 80 proxy_protocol;  # 开启 PROXY Protocol
       server_name your-domain.com;

       set_real_ip_from 127.0.0.1;
       set_real_ip_from unix:;
       real_ip_header proxy_protocol;  # 还原真实公网客户端 IP

       location ^~ /brutal/ {
           proxy_pass http://127.0.0.1:8080/;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_buffering off;
       }
   }
   ```
这样在添加规则时，系统就能准确识别到访客真实的公网客户端 IP，而不会显示 `unix:` 或 `127.0.0.1`。

---

## 5. 功能使用详解

### 5.1 管理员登录与服务端物理隔离安全防护
- **服务端强制物理隔离 (Server-Side Guard)**：未登录访客访问面板时，后端服务器**绝对只下发独立的极简登录页面 (`login.html`)**，完全不发送任何管理控制台的 HTML 结构、不加载管理逻辑代码，从根源上杜绝 F12 审查元素泄露界面结构与任何后台数据。
- **登录流程**：输入配置文件中的管理密码，回车或点击确认解锁；认证成功后发放随机高强度会话 Token 并写入 HttpOnly Cookie。
- **安全登出与 Cookie 销毁**：点击退出登录时，服务端立即废除该 Token 并下发清除指令彻底销毁浏览器 Cookie，页面自动刷新重置回独立登录页。

### 5.2 规则列表与实时监控
- **概览看板**：
  - **当前受控 IP 数量**：统计当前系统中正在生效的规则总条数；
  - **托管解析域名**：当前 `brut_domain.txt` 中配置的有效域名数；
  - **累计发包数据量**：汇总展示各规则已发出的流量总量；
  - **最近同步状态**：显示上次定时或手动同步的执行结果与具体时间。
- **规则表格与来源标签**：
  - 表格清晰展示：目标网段 (`DESTINATION`)、限速速率 (`RATE`)、增益 (`GAIN`)、状态 (`STATUS`)、成员连接数 (`MEMBERS`) 以及已发流量 (`SENT`)；
  - **来源徽章**：
    - 🔵 `[静态IP清单]`：永久持久化规则，重启不失效，定时同步不误删；
    - 🟡 `[手动添加(临时)]`：临时测试规则，重启后自动失效；
    - 🟢 `[域名同步]`：随域名动态解析维护。
- **实时搜索过滤**：顶部搜索框输入任意 IP 字符，表格即时按关键字无刷新过滤。

### 5.3 手动添加规则与客户端 IP 自动带入
1. 点击右上角绿色按钮 **“添加 IP 规则”**；
2. **自动带入功能**：输入框**默认已经自动识别并填入您当前的客户端公网 IP**，并高亮选中文本；右上角显示 `客户端 IP: x.x.x.x (点击填入)`，方便清空后随时一键复原；
3. **掩码智能补齐**：
   - 输入 IPv4（如 `1.2.3.4`）→ 自动补齐为 `/32`；
   - 输入 IPv6（如 `2001:db8::1`）→ 自动补齐为 `/128`；
   - 显式输入自定义掩码（如 `10.0.0.0/24` 或 `2001:db8::/64`）→ 保留用户指定的网段；
4. **快捷速率选择**：提供 `50M`、`100M`、`200M`、`500M`、`1000M` 快捷标签芯片，一键点击设定速率；
5. 点击 **“确认添加”**，规则立即下发到内核生效。

### 5.4 临时 IP 一键固化到清单
- **单条固化**：对于规则列表中带有黄色 `[手动添加(临时)]` 标签的行，操作列提供专属按键 **“存入清单”**。点击并确认后，系统将该 IP 及其当前设定的实际速率自动写入 `brut_ip.txt`，其标签立即转为蓝色的 `[静态IP清单]`，在服务器重启后依然永久生效！
- **批量全部固化**：当列表中存在临时 IP 时，顶部会自动浮现黄色按钮 **“一键保存临时IP到清单 (N)”**，点击一次即可将所有临时 IP 及其速率全部一次性固化写入静态清单。

### 5.5 域名清单配置与 DNS 双栈解析
- 切换至 **“域名清单配置”** 选项卡；
- **在线编辑**：在文本框中编辑 `brut_domain.txt`（每行一个域名，支持 `#` 注释）；
- **操作按钮**：
  - **仅保存修改**：仅更新文件，等待下一次定时刷新周期自动应用；
  - **保存并立即同步到 brutalctl**：保存文件并立即在后台异步触发同步，同时自动切换到“同步控制台”查看实时执行过程；
- **单域名 DNS 解析测试工具**：
  - 侧边输入框输入测试域名（如 `google.com`），点击“测试”；
  - 界面会分类输出当前服务器解析到的所有有效 `[IPv4]` 与原生 `[IPv6]` 地址列表。

### 5.6 静态 IP 清单配置与持久化管理
- 切换至 **“静态IP清单配置”** 选项卡；
- **在线编辑**：文本框直接查看与修改 `brut_ip.txt`；
- **操作按钮**：点击“保存并立即应用到 brutalctl”，系统在 1 毫秒内：
  1. 立即将新增或保留的静态规则以其对应速率下发给内核；
  2. 自动从内核中清理删除您在文本框中删减掉的废弃静态规则；
- **侧边 IP 格式检测工具**：输入待验证的 IP，检测其 IPv4/IPv6 语法及补齐后的标准形式。

### 5.7 单行自定义限速速率规范
在 **`brut_domain.txt`** 和 **`brut_ip.txt`** 中，每行均支持在目标后以空格指定该行专享的速率（单位为 Mbps）：

```text
# 1. 域名清单自定义速率示例：
example.com                    # 未指定：应用默认速率 100 Mbps
speed.example.org 200          # 自定义：该域名解析出的所有 IPv4/IPv6 均限速 200 Mbps
fast.example.net 500           # 自定义：该域名解析出的所有 IPv4/IPv6 均限速 500 Mbps

# 2. 静态 IP 清单自定义速率示例：
1.2.3.4                        # 未指定：应用默认速率 100 Mbps
192.168.1.100 300              # 自定义：限速 300 Mbps
10.0.0.0/24 50                 # 自定义：网段限速 50 Mbps
2001:db8::1 800                # 自定义：IPv6 地址限速 800 Mbps
```

### 5.8 终端式同步日志控制台
- 切换至 **“同步控制台”** 选项卡；
- 仿 Linux 终端黑色窗口，带彩色彩色语法高亮：
  - `[DNS]`（青色）：域名解析日志与解析结果；
  - `[ADD ]`（绿色粗体）：新增的下发规则；
  - `[KEEP]`（常规）：已存在或白名单保护保留的规则；
  - `[DEL ]`（红色粗体）：已失效被自动删除清理的废弃规则；
- 终端自带自动滚动到底部，方便直观监控。

### 5.9 系统设置与定时调度
- 切换至 **“系统设置”** 选项卡：
  - **修改管理员登录密码**：输入新密码保存后，下次登录时生效；
  - **启用后台定时自动同步开关**：控制后台是否周期自动运行 DNS 探测；
  - **同步执行周期 (秒)**：自定义自动同步间隔（建议 300 秒或 600 秒）；
  - **服务启动/重启后首次同步延迟 (秒)**：默认为 5 秒。系统开机或服务重启 5 秒后，自动触发一次完整的首次同步，快速恢复控速规则。

### 5.10 多语言切换与国际化
- **自动感应**：系统根据您的浏览器语种自动展示对应语言（繁体、简体、英文）；
- **手动选择**：顶部导航栏右上角设有语言选择下拉菜单，可随时在 `🇨🇳 简体中文`、`🇭🇰 繁體中文`、`🇺🇸 English` 之间无缝切换；
- **扩展性**：未来若需添加新语言（如日文、韩文等），只需在 `static/i18n.js` 中增加一个语言字典对象即可全站自动生效。

---

## 6. 配置文件说明 (`config.json`)

配置文件位于 `/opt/brutal-webui/config.json`（首次安装时由 `deploy.sh` 根据模板自动创建并生成随机初始强密码）：

```json
{
  "server": {
    "host": "0.0.0.0",                 // 监听地址 (Nginx 反代场景建议改为 127.0.0.1)
    "port": 8080                       // 监听端口 (默认 8080)
  },
  "auth": {
    "admin_password": "ChangeThisPassword123!", // 管理员登录密码 (首次部署自动生成高强度随机密码)
    "session_timeout_hours": 24        // 会话 Token 有效期 (小时)
  },
  "brutal": {
    "brutalctl_bin": "brutalctl",      // 底层 brutalctl 可执行程序名称或绝对路径
    "default_rate_mbps": 100,          // 全局默认限速速率 (Mbps)
    "domain_file_path": "./brut_domain.txt", // 域名清单持久化文件路径 (支持自定义速率)
    "ip_file_path": "./brut_ip.txt",   // 静态 IP 清单持久化文件路径 (支持 IPv4/IPv6 与自定义速率)
    "sync_script_path": "./brutal_sync.sh"   // 原生同步核心脚本路径
  },
  "sync_scheduler": {
    "enabled": true,                   // 是否开启后台定时自动同步
    "interval_seconds": 300,           // 周期同步时间间隔 (秒，推荐 300 或 600)
    "startup_sync_delay": 5            // 服务启动/重启后首次同步延迟 (秒)，开机快速恢复控速
  },
  "ssl": {
    "enabled": false,                  // 是否启用 Python 原生 HTTPS
    "cert_file": "./cert.pem",         // SSL 公钥证书路径
    "key_file": "./key.pem"            // SSL 私钥文件路径
  }
}
```

---

## 7. 常见问题与故障排查 (FAQ)

### Q1: 页面获取 IP 时显示 `unix:` 是什么原因？
**原因**：Nginx 或上游前置代理（如 Xray / 宝塔 / 容器套接字）通过 Unix Socket 转发时，`$remote_addr` 变量的值即为 `"unix:"`。  
**解决**：
1. 后端代码已内建过滤机制，会自动忽略 `unix:` 并穿透寻找合法 IP；
2. 若使用了 Xray Reality 回落，请参照手册第 4.3 节开启 `proxy_protocol` 即可完整还原真实客户端 IP。

### Q2: 规则列表里的三种标签有什么区别？
- **`[静态IP清单]`**：持久保存在 `brut_ip.txt` 中，服务器重启后依然永久存在，定时同步时受绝对保护不被误删。
- **`[手动添加(临时)]`**：仅在当前运行内存中维护，适合临时测试，服务器重启后自动失效；支持随时点击“存入清单”一键转为永久。
- **`[域名同步]`**：由 `brut_domain.txt` 中的域名解析生成，DNS 解析变化时自动同步增删。

### Q3: 为什么有的域名只添加了 IPv4，没有添加 IPv6？
这是系统的**纯净防护特性**：系统只会在域名拥有真实的 AAAA 记录时添加 IPv6。如果域名本身没有 IPv6 地址，系统坚决不会添加虚假的 IPv6 规则，也不会添加 `::ffff:x.x.x.x` 形式的兼容映射地址，保持规则列表纯洁干净。

### Q4: 如何手动修改管理密码？
- **方式 1（图形化）**：登录 WebUI 面板，进入“系统设置”选项卡，输入新密码并点击“保存全部设置”；
- **方式 2（命令行）**：编辑 `/opt/brutal-webui/config.json`，修改 `"admin_password"` 的值，然后执行 `systemctl restart brutal-web` 重启服务即可生效。
