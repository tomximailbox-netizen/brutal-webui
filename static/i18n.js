// ============================================================
// Brutal WebUI 国际化多语言引擎 (可插拔与高扩展架构)
// 默认语言: en (英文)
// 支持: en (English), zh-CN (简体中文), zh-TW (繁體中文)
// 扩展方式: 只需在 I18N_RESOURCES 注册表中增加一个新对象即可自动生效
// ============================================================

const DEFAULT_LANG = "en";

const I18N_RESOURCES = {
  "en": {
    name: "English",
    flag: "🇺🇸",
    matches: ["en"],
    dict: {
      // 导航与品牌
      app_title: "Brutal Traffic Control Panel",
      app_subtitle: "Linux TCP Congestion Control / brutalctl IP Rule Manager",
      status_detecting: "Detecting...",
      status_mock: "Mock Virtual Mode",
      status_normal: "brutalctl Normal",
      sync_scheduled: "Auto Sync: every %s",
      sync_paused: "Auto Sync: Paused",
      btn_sync_now: "Sync Now",
      btn_logout: "Logout",
      tooltip_logout: "Sign Out Safely",

      // 概览指标卡片
      metric_rules_title: "Active Controlled IPs",
      metric_rules_unit: "rules",
      metric_domains_title: "Managed Domains",
      metric_domains_unit: "targets",
      metric_sent_title: "Total Sent Traffic",
      metric_sync_title: "Last Sync Status",
      sync_never: "Never Run",

      // 选项卡 Tabs
      tab_rules: "Rules List",
      tab_domains: "Domain List Config",
      tab_static_ips: "Static IP Config",
      tab_logs: "Sync Console",
      tab_settings: "Settings",

      // Tab 1: 规则列表
      search_placeholder: "Filter by IP / CIDR...",
      btn_refresh: "Refresh",
      btn_add_rule: "Add IP Rule",
      btn_save_all_manual: "Save All Temp IPs to List",
      th_destination: "DESTINATION",
      th_rate: "RATE (Speed)",
      th_gain: "GAIN",
      th_status: "STATUS",
      th_members: "MEMBERS",
      th_sent: "SENT (Traffic)",
      th_actions: "ACTIONS",
      badge_static: "Static List",
      badge_manual: "Manual (Temp)",
      badge_domain: "Domain Sync",
      btn_save_to_list: "Save to List",
      btn_delete: "Delete",
      no_rules_matched: "No rules matched",
      loading_rules: "Loading rules...",

      // Tab 2: 域名配置
      domains_editor_title: "brut_domain.txt Domain List Editor",
      domains_editor_desc: "One domain per line, supports # comment lines and custom speed (e.g. domain.com 200)",
      domains_effective_count: "Active Domains: %s",
      domains_placeholder: "google.com\ncloudflare.com 200\ngithub.com 50\n# One domain per line, trailing number sets rate (default 100Mbps)",
      btn_save_only: "Save Only",
      btn_save_and_sync: "Save & Sync to brutalctl",
      dns_test_title: "Single Domain DNS Resolve Test",
      dns_test_desc: "Check if the server can resolve IPv4 and IPv6 for this domain",
      dns_test_placeholder: "e.g. google.com",
      btn_test: "Test",
      testing: "Resolving...",
      resolve_success: "Resolved successfully (%s addresses):",
      resolve_failed: "Resolution failed: %s",
      sync_logic_title: "💡 Sync Logic Notes:",
      sync_logic_1: "1. Resolves all IPv4 and IPv6 addresses for all domains in the list.",
      sync_logic_2: "2. Automatically sets speed: IPv4 defaults to /32, IPv6 defaults to /128.",
      sync_logic_3: "3. Obsolete IPs are automatically deleted (manual temp & static IPs are protected).",
      sync_logic_4: "4. If all domains fail to resolve, deletion is aborted to prevent accidental clearing.",

      // Tab 3: 静态 IP 清单配置
      static_editor_title: "brut_ip.txt Static IP List Editor",
      static_editor_desc: "One IPv4/IPv6 address or CIDR per line, supports # comments and custom speed (e.g. 1.2.3.4 200)",
      static_effective_count: "Active IPs: %s (IPv4: %s, IPv6: %s)",
      static_placeholder: "# Static IP list example (supports custom speed, defaults to 100Mbps)\n1.2.3.4 200\n10.0.0.0/24 50\n2001:db8::1 500\n2408:8207::/64",
      static_test_title: "IP / CIDR Format Validator",
      static_test_desc: "Verify whether the entered IP syntax is valid and view the auto-completed mask",
      static_test_placeholder: "e.g. 1.2.3.4 or 2001:db8::1",
      btn_validate: "Validate",
      validating: "Validating...",
      valid_format: "Valid format [IPv%s]",
      applied_target: "Applied target: %s",
      invalid_format: "Validation failed: %s",
      static_logic_title: "💡 Static IP List Notes:",
      static_logic_1: "1. Stored in brut_ip.txt, permanently retained across server reboots.",
      static_logic_2: "2. Supports IPv4 (/32 by default) and IPv6 (/128 by default), plus custom CIDRs.",
      static_logic_3: "3. All rules here are in the whitelist and will never be cleared during auto sync.",
      static_logic_4: "4. Temporary manual IPs in the dashboard can be converted into this list with one click.",

      // Tab 4: 同步控制台
      console_title: "Terminal Live Output",
      console_desc: "Shows brutal_sync.sh execution output, DNS resolving, and rule changes",
      btn_refresh_logs: "Refresh Output",
      console_empty: "// No sync logs yet, click 'Sync Now' to start",

      // Tab 5: 系统设置
      settings_security_title: "Security & Credentials",
      settings_pwd_label: "Change Admin Password",
      settings_pwd_placeholder: "Enter new admin password (leave empty to keep current)",
      settings_pwd_desc: "Takes effect on next sign in",
      settings_sched_title: "Auto Sync Schedule",
      settings_sched_toggle: "Enable Background Auto Sync",
      settings_sched_desc: "Automatically run DNS check and rule synchronization in the background",
      settings_interval_label: "Sync Interval (seconds)",
      settings_interval_desc: "Recommended 300 seconds (5 min) or higher to avoid excessive DNS requests",
      settings_startup_label: "Initial Sync Delay after Startup/Reboot (seconds)",
      settings_startup_desc: "Delay in seconds after server startup before immediate first sync",
      btn_save_settings: "Save All Settings",

      // 添加规则弹窗
      modal_add_title: "Add brutalctl Speed Rule",
      modal_add_ip_label: "Target IP / CIDR",
      modal_add_client_label: "Client IP:",
      modal_add_client_detecting: "Detecting...",
      modal_add_ip_placeholder: "e.g. 1.2.3.4 or 2001:db8::1 (supports /64)",
      modal_add_ip_desc: "Auto-fills your client IP. Defaults: IPv4 to /32, IPv6 to /128",
      modal_add_rate_label: "Speed Rate (Mbps)",
      btn_cancel: "Cancel",
      btn_confirm_add: "Confirm Add",

      // 登录弹窗
      modal_login_title: "Admin Authentication",
      modal_login_desc: "Please enter your admin password to unlock the dashboard",
      modal_login_placeholder: "Enter password...",
      btn_unlock: "Unlock Dashboard",

      // 提示与通知 Toast
      toast_login_success: "Login successful",
      toast_login_error: "Incorrect password",
      toast_input_pwd: "Please enter admin password",
      toast_logout: "Signed out safely",
      toast_input_valid_ip: "Please enter a valid IP or CIDR",
      toast_confirm_del: "Are you sure you want to delete rule [%s]?",
      toast_confirm_save_manual: "Save temporary rule [%s] (%s Mbps) to static list?\nIt will persist across server reboots.",
      toast_confirm_save_all: "Save all current temporary manual IPs to static list?\nThey will become permanent.",
      toast_saved_to_list: "Saved to static list",
      toast_domains_saved: "Domain list saved (%s active domains)",
      toast_static_saved: "Static IP list saved (%s active rules)",
      toast_sync_triggered: "Sync task started",
      toast_config_updated: "Configuration updated successfully",
      toast_net_error: "Network connection error",
      toast_empty_ip: "Please enter an IP or CIDR"
    }
  },

  "zh-CN": {
    name: "简体中文",
    flag: "🇨🇳",
    matches: ["zh", "zh-cn", "zh-sg", "zh-hans"],
    dict: {
      app_title: "Brutal 流量控制面板",
      app_subtitle: "Linux TCP 拥塞控制 / brutalctl IP 规则实时管理器",
      status_detecting: "检测中...",
      status_mock: "Mock 虚拟模式",
      status_normal: "brutalctl 正常",
      sync_scheduled: "定时同步: 每 %s",
      sync_paused: "定时同步: 已暂停",
      btn_sync_now: "立即同步",
      btn_logout: "退出登录",
      tooltip_logout: "安全退出",

      metric_rules_title: "当前受控 IP 数量",
      metric_rules_unit: "条规则",
      metric_domains_title: "托管解析域名",
      metric_domains_unit: "个目标",
      metric_sent_title: "累计发包数据量",
      metric_sync_title: "最近同步状态",
      sync_never: "从未运行",

      tab_rules: "规则列表",
      tab_domains: "域名清单配置",
      tab_static_ips: "静态IP清单配置",
      tab_logs: "同步控制台",
      tab_settings: "系统设置",

      search_placeholder: "按 IP / CIDR 搜索过滤...",
      btn_refresh: "刷新列表",
      btn_add_rule: "添加 IP 规则",
      btn_save_all_manual: "一键保存临时IP到清单",
      th_destination: "DESTINATION (目标)",
      th_rate: "RATE (速率)",
      th_gain: "GAIN",
      th_status: "STATUS",
      th_members: "MEMBERS",
      th_sent: "SENT (流量)",
      th_actions: "操作",
      badge_static: "静态IP清单",
      badge_manual: "手动添加(临时)",
      badge_domain: "域名同步",
      btn_save_to_list: "存入清单",
      btn_delete: "删除",
      no_rules_matched: "无匹配的规则",
      loading_rules: "正在加载规则...",

      domains_editor_title: "brut_domain.txt 文件编辑",
      domains_editor_desc: "每行一个域名，支持以 # 开头的注释行与自定义速度 (如 domain.com 200)",
      domains_effective_count: "当前有效域名: %s 个",
      domains_placeholder: "google.com\ncloudflare.com 200\ngithub.com 50\n# 每行一个，支持在域名后空格指定速率 (未指定默认 100Mbps)",
      btn_save_only: "仅保存修改",
      btn_save_and_sync: "保存并立即同步到 brutalctl",
      dns_test_title: "单域名 DNS 解析测试",
      dns_test_desc: "测试服务器能否通过 DNS 解析该域名的 IPv4 与 IPv6",
      dns_test_placeholder: "例如: google.com",
      btn_test: "测试",
      testing: "正在解析...",
      resolve_success: "✓ 解析成功 (%s 个地址):",
      resolve_failed: "✗ 解析失败: %s",
      sync_logic_title: "💡 同步逻辑说明：",
      sync_logic_1: "1. 系统自动解析文件中所有域名的 IPv4 与 IPv6 地址。",
      sync_logic_2: "2. 解析出的新 IP 自动执行限速：IPv4 默认 /32，IPv6 默认 /128。",
      sync_logic_3: "3. 已不在域名解析结果中的旧 IP 会自动执行 del 清理（手动临时与静态 IP 保护不删）。",
      sync_logic_4: "4. 若 DNS 全部解析失败，为防止误删将自动放弃执行。",

      static_editor_title: "brut_ip.txt 静态 IP 清单编辑",
      static_editor_desc: "每行一个 IPv4 或 IPv6 地址/网段，支持以 # 开头的注释行与自定义速度 (如 1.2.3.4 200)",
      static_effective_count: "有效 IP: %s (IPv4: %s, IPv6: %s)",
      static_placeholder: "# 静态 IP 清单示例 (支持自定义速率，未指定默认 100Mbps)\n1.2.3.4 200\n10.0.0.0/24 50\n2001:db8::1 500\n2408:8207::/64",
      static_test_title: "IP/CIDR 格式快速校验",
      static_test_desc: "检测输入的 IP 语法是否有效及自动补齐的掩码",
      static_test_placeholder: "例如: 1.2.3.4 或 2001:db8::1",
      btn_validate: "检测",
      validating: "正在校验...",
      valid_format: "✓ 语法合法 [IPv%s]",
      applied_target: "应用目标: %s",
      invalid_format: "✗ 校验失败: %s",
      static_logic_title: "💡 静态 IP 清单说明：",
      static_logic_1: "1. 本清单存储于 brut_ip.txt 文件中，服务器重启后永久持久化保留。",
      static_logic_2: "2. 支持 IPv4（未加掩码默认 /32）与 IPv6（未加掩码默认 /128），支持自定义掩码如 /24 或 /64。",
      static_logic_3: "3. 此文件中的所有规则自动纳入免清理白名单，在后台定时同步刷新时绝不被误删。",
      static_logic_4: "4. 页面查看的临时手动 IP 支持一键转存到此清单中。",

      console_title: "终端实时输出",
      console_desc: "展示 brutal_sync.sh 运行过程与 DNS 解析/规则添加日志",
      btn_refresh_logs: "刷新输出",
      console_empty: "// 暂无同步日志，点击“立即执行同步”开始",

      settings_security_title: "安全与访问凭据",
      settings_pwd_label: "修改管理员登录密码",
      settings_pwd_placeholder: "输入新的管理密码 (留空则不修改)",
      settings_pwd_desc: "修改后下次登录时生效",
      settings_sched_title: "自动同步定时调度",
      settings_sched_toggle: "启用后台定时自动同步",
      settings_sched_desc: "按固定周期自动在后台运行 DNS 探测与规则更新",
      settings_interval_label: "同步执行周期 (秒)",
      settings_interval_desc: "建议设置为 300 秒 (5分钟) 或更高，避免过度频繁请求 DNS 解析",
      settings_startup_label: "服务启动/重启后首次同步延迟 (秒)",
      settings_startup_desc: "服务器启动或服务重启后延迟此秒数立即执行首次同步，迅速拉取域名生效规则",
      btn_save_settings: "保存全部设置",

      modal_add_title: "添加 brutalctl 限速规则",
      modal_add_ip_label: "目标 IP / CIDR",
      modal_add_client_label: "客户端 IP:",
      modal_add_client_detecting: "检测中...",
      modal_add_ip_placeholder: "例如: 1.2.3.4 或 2001:db8::1 (支持 /64)",
      modal_add_ip_desc: "默认已自动带入客户端 IP。若未填掩码：IPv4 默认补齐 /32，IPv6 默认补齐 /128",
      modal_add_rate_label: "限速速率 (Mbps)",
      btn_cancel: "取消",
      btn_confirm_add: "确认添加",

      modal_login_title: "管理员身份验证",
      modal_login_desc: "请输入配置的管理密码以解锁控制面板",
      modal_login_placeholder: "输入管理密码...",
      btn_unlock: "确认解锁",

      toast_login_success: "登录成功",
      toast_login_error: "密码错误",
      toast_input_pwd: "请输入管理密码",
      toast_logout: "已安全退出",
      toast_input_valid_ip: "请输入有效的 IP 或 CIDR",
      toast_confirm_del: "确定要从 brutalctl 中删除规则 [%s] 吗？",
      toast_confirm_save_manual: "确定要将临时规则 [%s] (速率: %s Mbps) 保存到静态清单吗？\n保存后服务器重启将永久保留生效。",
      toast_confirm_save_all: "确定要将当前所有临时手动 IP 一键保存到静态清单吗？\n保存后将永久生效，重启不失效。",
      toast_saved_to_list: "已存入静态清单",
      toast_domains_saved: "域名清单已保存 (有效域名 %s 个)",
      toast_static_saved: "静态 IP 清单已保存 (有效规则 %s 个)",
      toast_sync_triggered: "同步任务已触发",
      toast_config_updated: "配置已更新",
      toast_net_error: "网络连接异常",
      toast_empty_ip: "请输入待检测的 IP 或 CIDR"
    }
  },

  "zh-TW": {
    name: "繁體中文",
    flag: "🇭🇰",
    matches: ["zh-tw", "zh-hk", "zh-mo", "zh-hant"],
    dict: {
      app_title: "Brutal 流量控制面板",
      app_subtitle: "Linux TCP 擁塞控制 / brutalctl IP 規則實時管理器",
      status_detecting: "檢測中...",
      status_mock: "Mock 虛擬模式",
      status_normal: "brutalctl 正常",
      sync_scheduled: "定時同步: 每 %s",
      sync_paused: "定時同步: 已暫停",
      btn_sync_now: "立即同步",
      btn_logout: "登出",
      tooltip_logout: "安全登出",

      metric_rules_title: "當前受控 IP 數量",
      metric_rules_unit: "條規則",
      metric_domains_title: "託管解析網域名稱",
      metric_domains_unit: "個目標",
      metric_sent_title: "累計發包數據量",
      metric_sync_title: "最近同步狀態",
      sync_never: "從未運行",

      tab_rules: "規則列表",
      tab_domains: "網域名單配置",
      tab_static_ips: "靜態IP名單配置",
      tab_logs: "同步主控台",
      tab_settings: "系統設定",

      search_placeholder: "按 IP / CIDR 搜尋篩選...",
      btn_refresh: "重新整理",
      btn_add_rule: "新增 IP 規則",
      btn_save_all_manual: "一鍵儲存暫存IP至名單",
      th_destination: "DESTINATION (目標)",
      th_rate: "RATE (速率)",
      th_gain: "GAIN",
      th_status: "STATUS",
      th_members: "MEMBERS",
      th_sent: "SENT (流量)",
      th_actions: "操作",
      badge_static: "靜態IP名單",
      badge_manual: "手動新增(暫存)",
      badge_domain: "網域同步",
      btn_save_to_list: "存入名單",
      btn_delete: "刪除",
      no_rules_matched: "無相符的規則",
      loading_rules: "正在載入規則...",

      domains_editor_title: "brut_domain.txt 網域名單編輯",
      domains_editor_desc: "每行一個網域，支援以 # 開頭的註解行與自訂速度 (如 domain.com 200)",
      domains_effective_count: "當前有效網域: %s 個",
      domains_placeholder: "google.com\ncloudflare.com 200\ngithub.com 50\n# 每行一個，支援在網域後空格指定速率 (未指定預設 100Mbps)",
      btn_save_only: "僅儲存修改",
      btn_save_and_sync: "儲存並立即同步至 brutalctl",
      dns_test_title: "單一網域 DNS 解析測試",
      dns_test_desc: "測試伺服器能否透過 DNS 解析該網域的 IPv4 與 IPv6",
      dns_test_placeholder: "例如: google.com",
      btn_test: "測試",
      testing: "正在解析...",
      resolve_success: "✓ 解析成功 (%s 個位址):",
      resolve_failed: "✗ 解析失敗: %s",
      sync_logic_title: "💡 同步邏輯說明：",
      sync_logic_1: "1. 系統自動解析清單中所有網域的 IPv4 與 IPv6 位址。",
      sync_logic_2: "2. 解析出的新 IP 自動套用限速：IPv4 預設 /32，IPv6 預設 /128。",
      sync_logic_3: "3. 已不在網域解析結果中的舊 IP 會自動執行 del 清理（手動暫存與靜態 IP 受保護不刪除）。",
      sync_logic_4: "4. 若 DNS 全部解析失敗，為防誤刪將自動放棄執行。",

      static_editor_title: "brut_ip.txt 靜態 IP 名單編輯",
      static_editor_desc: "每行一個 IPv4 或 IPv6 位址/網段，支援以 # 開頭的註解行與自訂速度 (如 1.2.3.4 200)",
      static_effective_count: "有效 IP: %s (IPv4: %s, IPv6: %s)",
      static_placeholder: "# 靜態 IP 名單範例 (支援自訂速率，未指定預設 100Mbps)\n1.2.3.4 200\n10.0.0.0/24 50\n2001:db8::1 500\n2408:8207::/64",
      static_test_title: "IP/CIDR 格式快速校驗",
      static_test_desc: "檢測輸入的 IP 語法是否有效及自動補全的遮罩",
      static_test_placeholder: "例如: 1.2.3.4 或 2001:db8::1",
      btn_validate: "檢測",
      validating: "正在檢驗...",
      valid_format: "✓ 語法合法 [IPv%s]",
      applied_target: "套用目標: %s",
      invalid_format: "✗ 檢驗失敗: %s",
      static_logic_title: "💡 靜態 IP 名單說明：",
      static_logic_1: "1. 本名單儲存於 brut_ip.txt 檔案中，伺服器重啟後永久持久化保留。",
      static_logic_2: "2. 支援 IPv4（未加遮罩預設 /32）與 IPv6（未加遮罩預設 /128），支援自訂遮罩如 /24 或 /64。",
      static_logic_3: "3. 此檔案中的所有規則自動納入免清理白名單，在後台定時同步重新整理時絕不被誤刪。",
      static_logic_4: "4. 頁面查看的暫存手動 IP 支援一鍵轉存至此名單中。",

      console_title: "終端實時輸出",
      console_desc: "展示 brutal_sync.sh 執行過程與 DNS 解析/規則變更記錄",
      btn_refresh_logs: "重新整理輸出",
      console_empty: "// 暫無同步日誌，點擊「立即同步」開始",

      settings_security_title: "安全與存取憑據",
      settings_pwd_label: "修改管理員登入密碼",
      settings_pwd_placeholder: "輸入新的管理密碼 (留空則不修改)",
      settings_pwd_desc: "修改後下次登入時生效",
      settings_sched_title: "自動同步排程設定",
      settings_sched_toggle: "啟用後台定時自動同步",
      settings_sched_desc: "按固定週期自動在背景運行 DNS 探測與規則更新",
      settings_interval_label: "同步執行週期 (秒)",
      settings_interval_desc: "建議設定為 300 秒 (5分鐘) 或更高，避免過度頻繁請求 DNS 解析",
      settings_startup_label: "伺服器開機/重啟後首次同步延遲 (秒)",
      settings_startup_desc: "伺服器啟動或服務重啟後延遲此秒數立即執行首次同步，迅速拉取網域生效規則",
      btn_save_settings: "儲存全部設定",

      modal_add_title: "新增 brutalctl 限速規則",
      modal_add_ip_label: "目標 IP / CIDR",
      modal_add_client_label: "客戶端 IP:",
      modal_add_client_detecting: "檢測中...",
      modal_add_ip_placeholder: "例如: 1.2.3.4 或 2001:db8::1 (支援 /64)",
      modal_add_ip_desc: "預設已自動帶入客戶端 IP。若未填遮罩：IPv4 預設補齊 /32，IPv6 預設補齊 /128",
      modal_add_rate_label: "限速速率 (Mbps)",
      btn_cancel: "取消",
      btn_confirm_add: "確認新增",

      modal_login_title: "管理員身分驗證",
      modal_login_desc: "請輸入設定的管理密碼以解鎖控制面板",
      modal_login_placeholder: "輸入管理密碼...",
      btn_unlock: "確認解鎖",

      toast_login_success: "登入成功",
      toast_login_error: "密碼錯誤",
      toast_input_pwd: "請輸入管理密碼",
      toast_logout: "已安全登出",
      toast_input_valid_ip: "請輸入有效的 IP 或 CIDR",
      toast_confirm_del: "確定要從 brutalctl 中刪除規則 [%s] 嗎？",
      toast_confirm_save_manual: "確定要將暫存規則 [%s] (速率: %s Mbps) 儲存至靜態名單嗎？\n儲存後伺服器重啟將永久保留生效。",
      toast_confirm_save_all: "確定要將當前所有暫存手動 IP 一鍵儲存至靜態名單嗎？\n儲存後將永久生效，重啟不失效。",
      toast_saved_to_list: "已存入靜態名單",
      toast_domains_saved: "網域名單已儲存 (有效網域 %s 個)",
      toast_static_saved: "靜態 IP 名單已儲存 (有效規則 %s 個)",
      toast_sync_triggered: "同步任務已觸發",
      toast_config_updated: "設定已更新",
      toast_net_error: "網路連線異常",
      toast_empty_ip: "請輸入待檢測的 IP 或 CIDR"
    }
  }
};

// 状态管理
let currentLang = DEFAULT_LANG;

/**
 * 语言嗅探与判定
 * 优先级: localStorage > navigator.language 前缀智能匹配 > DEFAULT_LANG ("en")
 */
function detectLanguage() {
  const saved = localStorage.getItem("brutal_lang");
  if (saved && I18N_RESOURCES[saved]) {
    return saved;
  }

  const browserLang = (navigator.language || navigator.userLanguage || "").toLowerCase().trim();
  if (!browserLang) return DEFAULT_LANG;

  // 1. 优先完全或精确匹配前缀
  for (const [langKey, langObj] of Object.entries(I18N_RESOURCES)) {
    if (langObj.matches) {
      for (const m of langObj.matches) {
        if (browserLang === m || browserLang.startsWith(m + "-") || browserLang.startsWith(m + "_")) {
          return langKey;
        }
      }
    }
  }

  // 2. 繁体中文关键词特定识别
  if (browserLang.includes("tw") || browserLang.includes("hk") || browserLang.includes("mo") || browserLang.includes("hant")) {
    return "zh-TW";
  }

  // 3. 中文通用 fallback 到简体中文
  if (browserLang.startsWith("zh")) {
    return "zh-CN";
  }

  // 4. 未识别语种一律回退到英文 DEFAULT_LANG
  return DEFAULT_LANG;
}

/**
 * 翻译字符串获取
 * @param {string} key 翻译键值
 * @param  {...any} args 占位符替换参数 (%s)
 */
function t(key, ...args) {
  const currentDict = I18N_RESOURCES[currentLang]?.dict || {};
  const defaultDict = I18N_RESOURCES[DEFAULT_LANG]?.dict || {};

  let text = currentDict[key] ?? defaultDict[key] ?? key;

  if (args.length > 0) {
    args.forEach(arg => {
      text = text.replace("%s", arg);
    });
  }
  return text;
}

/**
 * 应用全页面 DOM 翻译
 */
function applyTranslations() {
  // 1. 替换普通文本 (data-i18n)
  document.querySelectorAll("[data-i18n]").forEach(el => {
    const key = el.getAttribute("data-i18n");
    el.textContent = t(key);
  });

  // 2. 替换 placeholder (data-i18n-placeholder)
  document.querySelectorAll("[data-i18n-placeholder]").forEach(el => {
    const key = el.getAttribute("data-i18n-placeholder");
    el.setAttribute("placeholder", t(key));
  });

  // 3. 替换 title (data-i18n-title)
  document.querySelectorAll("[data-i18n-title]").forEach(el => {
    const key = el.getAttribute("data-i18n-title");
    el.setAttribute("title", t(key));
  });

  // 4. 更新语言选择下拉框状态
  const select = document.getElementById("lang-select");
  if (select) {
    select.value = currentLang;
  }

  // 5. 更新 html lang 属性
  document.documentElement.lang = currentLang;
}

/**
 * 切换语言
 */
function changeLanguage(newLang) {
  if (I18N_RESOURCES[newLang]) {
    currentLang = newLang;
    localStorage.setItem("brutal_lang", newLang);
    applyTranslations();

    // 重新渲染动态数据以更新徽章与标签
    if (typeof loadAllData === "function") {
      loadStatus();
      if (typeof renderRules === "function") renderRules();
    }
  }
}

/**
 * 动态根据注册表渲染语言选择下拉框（高扩展性，未来增添语言零侵入 HTML）
 */
function initLanguageSelector() {
  const select = document.getElementById("lang-select");
  if (!select) return;

  select.innerHTML = "";
  for (const [key, item] of Object.entries(I18N_RESOURCES)) {
    const opt = document.createElement("option");
    opt.value = key;
    opt.textContent = `${item.flag} ${item.name}`;
    if (key === currentLang) {
      opt.selected = true;
    }
    select.appendChild(opt);
  }

  select.addEventListener("change", (e) => {
    changeLanguage(e.target.value);
  });
}

// 模块初始化
currentLang = detectLanguage();
document.addEventListener("DOMContentLoaded", () => {
  initLanguageSelector();
  applyTranslations();
});
