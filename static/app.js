// Brutal WebUI 前端核心逻辑

const state = {
  token: localStorage.getItem("brutal_token") || "",
  clientIp: "",
  rules: [],
  domainsContent: "",
  activeTab: "rules",
  isSyncing: false,
  logInterval: null
};

// --- Toast 弹窗 ---
function showToast(msg, type = "info") {
  const container = document.getElementById("toast-container");
  const el = document.createElement("div");
  const colors = {
    success: "bg-emerald-600 border-emerald-500",
    error: "bg-rose-600 border-rose-500",
    info: "bg-indigo-600 border-indigo-500"
  };
  el.className = `flex items-center px-4 py-3 rounded-xl border text-white text-sm shadow-xl transition-all transform duration-300 translate-y-2 opacity-0 ${colors[type] || colors.info}`;
  el.innerHTML = `
    <span>${msg}</span>
  `;
  container.appendChild(el);

  // 动画进入
  requestAnimationFrame(() => {
    el.classList.remove("translate-y-2", "opacity-0");
  });

  setTimeout(() => {
    el.classList.add("translate-y-2", "opacity-0");
    setTimeout(() => el.remove(), 300);
  }, 3000);
}

// 自动推断当前页面的基础路径（支持根目录 / 访问，以及反向代理子路径如 /brutal/ 访问）
function resolveUrl(path) {
  let base = window.location.pathname;
  if (!base.endsWith('/')) {
    base = base.substring(0, base.lastIndexOf('/') + 1);
  }
  const cleanPath = path.startsWith('/') ? path.slice(1) : path;
  return base + cleanPath;
}

// --- 通用 API 请求 ---
async function apiCall(endpoint, method = "GET", data = null) {
  const headers = {
    "Content-Type": "application/json"
  };
  if (state.token) {
    headers["Authorization"] = `Bearer ${state.token}`;
  }

  const options = { method, headers };
  if (data && (method === "POST" || method === "PUT" || method === "DELETE")) {
    options.body = JSON.stringify(data);
  }

  try {
    const res = await fetch(resolveUrl(endpoint), options);
    if (res.status === 401) {
      localStorage.removeItem("brutal_token");
      window.location.reload();
      return { need_login: true };
    }
    const json = await res.json();
    if (!res.ok) {
      throw new Error(json.error || `请求失败 (${res.status})`);
    }
    return json;
  } catch (err) {
    showToast(err.message, "error");
    throw err;
  }
}

async function handleLogout() {
  try {
    await apiCall("/api/logout", "POST");
  } catch (e) {}
  state.token = "";
  localStorage.removeItem("brutal_token");
  window.location.reload();
}

// --- Tab 切换 ---
function switchTab(tab) {
  state.activeTab = tab;
  document.querySelectorAll(".tab-content").forEach(el => el.classList.add("hidden"));
  document.querySelectorAll(".tab-btn").forEach(el => {
    el.classList.remove("border-indigo-500", "text-indigo-400", "bg-slate-800/60");
    el.classList.add("border-transparent", "text-slate-400");
  });

  const targetTab = document.getElementById(`tab-${tab}`);
  const targetBtn = document.getElementById(`btn-tab-${tab}`);
  if (targetTab) targetTab.classList.remove("hidden");
  if (targetBtn) {
    targetBtn.classList.remove("border-transparent", "text-slate-400");
    targetBtn.classList.add("border-indigo-500", "text-indigo-400", "bg-slate-800/60");
  }

  if (tab === "rules") loadRules();
  if (tab === "domains") loadDomains();
  if (tab === "static-ips") loadStaticIps();
  if (tab === "logs") loadLogs();
  if (tab === "settings") loadSettings();
}

// --- 状态与概览数据 ---
async function loadStatus() {
  try {
    const data = await apiCall("/api/status");
    if (data.need_login) return;

    // 更新状态徽章
    const modeBadge = document.getElementById("mode-badge");
    if (data.is_mock) {
      modeBadge.className = "px-2.5 py-1 text-xs font-semibold rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30 flex items-center gap-1.5";
      modeBadge.innerHTML = `<span class="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse"></span>${t("status_mock")}`;
    } else {
      modeBadge.className = "px-2.5 py-1 text-xs font-semibold rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 flex items-center gap-1.5";
      modeBadge.innerHTML = `<span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>${t("status_normal")}`;
    }

    // 记录并更新客户端 IP
    if (data.client_ip) {
      state.clientIp = data.client_ip;
      const clientIpDisplay = document.getElementById("client-ip-display");
      if (clientIpDisplay) {
        clientIpDisplay.textContent = state.clientIp;
      }
    }

    // 统计指标
    document.getElementById("metric-rules-count").textContent = data.rule_count || 0;
    document.getElementById("metric-domains-count").textContent = data.domain_count || 0;
    document.getElementById("metric-sent-mb").textContent = (data.total_sent_mb || 0) + " MB";
    document.getElementById("metric-sync-status").textContent = data.sync?.last_status || t("sync_never");
    document.getElementById("metric-sync-time").textContent = data.sync?.last_run_time || "-";

    const syncBadge = document.getElementById("sync-sched-badge");
    if (data.sync?.scheduler_enabled) {
      syncBadge.textContent = t("sync_scheduled", data.sync.scheduler_interval + "s");
      syncBadge.className = "text-xs px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30";
    } else {
      syncBadge.textContent = t("sync_paused");
      syncBadge.className = "text-xs px-2 py-0.5 rounded bg-slate-700 text-slate-400";
    }
  } catch (e) {}
}

// --- 规则列表 (Rules) ---
async function loadRules() {
  const tbody = document.getElementById("rules-table-body");
  tbody.innerHTML = `<tr><td colspan="7" class="text-center py-8 text-slate-400"><div class="inline-block animate-spin mr-2">⏳</div> ${t("loading_rules")}</td></tr>`;

  try {
    const data = await apiCall("/api/rules");
    if (data.need_login) return;

    state.rules = data.rules || [];
    renderRules();
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="7" class="text-center py-8 text-rose-400">加载失败</td></tr>`;
  }
}

function renderRules() {
  const tbody = document.getElementById("rules-table-body");
  const filter = (document.getElementById("rule-search-input")?.value || "").toLowerCase().trim();

  const filtered = state.rules.filter(r => r.destination.toLowerCase().includes(filter));

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="text-center py-10 text-slate-500">${t("no_rules_matched")}</td></tr>`;
    return;
  }

  const manualRules = state.rules.filter(r => r.is_manual || r.source === 'manual');
  const btnSaveAll = document.getElementById("btn-save-all-manual");
  const badgeSaveAll = document.getElementById("manual-ips-badge");
  if (btnSaveAll && badgeSaveAll) {
    if (manualRules.length > 0) {
      btnSaveAll.classList.remove("hidden");
      badgeSaveAll.textContent = manualRules.length;
    } else {
      btnSaveAll.classList.add("hidden");
    }
  }

  tbody.innerHTML = filtered.map(r => {
    let sourceBadge = `<span class="px-2 py-0.5 rounded-full font-sans text-[11px] font-normal bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">${t("badge_domain")}</span>`;
    let dotColor = "bg-emerald-400";
    let isManual = r.is_manual || r.source === 'manual';

    if (r.source === 'static') {
      sourceBadge = `<span class="px-2 py-0.5 rounded-full font-sans text-[11px] font-normal bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">${t("badge_static")}</span>`;
      dotColor = "bg-indigo-400";
    } else if (isManual) {
      sourceBadge = `<span class="px-2 py-0.5 rounded-full font-sans text-[11px] font-normal bg-amber-500/20 text-amber-300 border border-amber-500/30">${t("badge_manual")}</span>`;
      dotColor = "bg-amber-400";
    }

    return `
    <tr class="hover:bg-slate-800/40 transition border-b border-slate-800/60 text-sm">
      <td class="py-3 px-4 font-mono font-medium text-indigo-300 flex items-center gap-2 flex-wrap">
        <span class="w-2 h-2 rounded-full ${dotColor}"></span>
        <span>${r.destination}</span>
        ${sourceBadge}
      </td>
      <td class="py-3 px-4">
        <span class="px-2 py-0.5 rounded-full font-mono text-xs font-semibold bg-blue-500/20 text-blue-300 border border-blue-500/30">
          ${r.rate_mbps} Mbps
        </span>
      </td>
      <td class="py-3 px-4 text-slate-300">${r.gain}</td>
      <td class="py-3 px-4 text-xs font-mono text-slate-400">Lock: ${r.lock} / Route: ${r.route}</td>
      <td class="py-3 px-4 text-slate-300">${r.members}</td>
      <td class="py-3 px-4 text-slate-200 font-mono">${r.sent_mb} MB</td>
      <td class="py-3 px-4 text-right whitespace-nowrap">
        ${isManual ? `
          <button onclick="handleAppendStaticIp('${r.destination}', ${r.rate_mbps})" class="px-2 py-1 text-xs text-amber-300 hover:text-white hover:bg-amber-600 rounded-lg transition border border-amber-500/40 mr-1.5" title="${t('btn_save_to_list')}">
            ${t("btn_save_to_list")}
          </button>
        ` : ''}
        <button onclick="confirmDelRule('${r.destination}')" class="px-2.5 py-1 text-xs text-rose-400 hover:text-white hover:bg-rose-600 rounded-lg transition border border-rose-500/30">
          ${t("btn_delete")}
        </button>
      </td>
    </tr>
  `}).join("");
}

function showAddRuleModal(show = true) {
  const modal = document.getElementById("add-rule-modal");
  const ipInput = document.getElementById("add-rule-ip");
  if (show) {
    modal.classList.remove("hidden");
    // 如果输入框为空，默认带入客户端 IP
    if (!ipInput.value.trim() && state.clientIp) {
      ipInput.value = state.clientIp;
    }
    ipInput.focus();
    if (ipInput.value) {
      ipInput.select();
    }
    const clientIpDisplay = document.getElementById("client-ip-display");
    if (clientIpDisplay && state.clientIp) {
      clientIpDisplay.textContent = state.clientIp;
    }
  } else {
    modal.classList.add("hidden");
  }
}

function fillClientIp() {
  if (state.clientIp) {
    const ipInput = document.getElementById("add-rule-ip");
    ipInput.value = state.clientIp;
    ipInput.focus();
    ipInput.select();
  }
}

function setPresetRate(rate) {
  document.getElementById("add-rule-rate").value = rate;
}

async function handleAddRule() {
  const ip = document.getElementById("add-rule-ip").value.trim();
  const rate = document.getElementById("add-rule-rate").value.trim();

  if (!ip) {
    showToast(t("toast_input_valid_ip"), "error");
    return;
  }

  try {
    const res = await apiCall("/api/rules", "POST", { ip, rate: Number(rate) || 100 });
    showToast(res.msg || t("toast_config_updated"), "success");
    showAddRuleModal(false);
    document.getElementById("add-rule-ip").value = "";
    loadRules();
    loadStatus();
  } catch (e) {}
}

async function confirmDelRule(ip) {
  if (!confirm(t("toast_confirm_del", ip))) return;

  try {
    const res = await apiCall("/api/rules", "DELETE", { ip });
    showToast(res.msg || t("btn_delete"), "success");
    loadRules();
    loadStatus();
  } catch (e) {}
}

// --- 域名管理 (Domains) ---
async function loadDomains() {
  try {
    const data = await apiCall("/api/domains");
    if (data.need_login) return;

    document.getElementById("domains-editor").value = data.raw_content || "";
    document.getElementById("domains-effective-count").textContent = t("domains_effective_count", data.count || 0);
  } catch (e) {}
}

async function handleSaveDomains(andSync = false) {
  const content = document.getElementById("domains-editor").value;
  try {
    const res = await apiCall("/api/domains", "PUT", { content });
    showToast(t("toast_domains_saved", res.count), "success");
    loadDomains();
    loadStatus();

    if (andSync) {
      handleTriggerSync();
      switchTab("logs");
    }
  } catch (e) {}
}

async function handleTestResolve() {
  const domain = document.getElementById("test-domain-input").value.trim();
  const resultEl = document.getElementById("test-resolve-result");
  if (!domain) {
    showToast(t("dns_test_placeholder"), "error");
    return;
  }

  resultEl.innerHTML = `<span class="text-slate-400">${t("testing")} ${domain} ...</span>`;
  try {
    const res = await apiCall("/api/domains/test-resolve", "POST", { domain });
    if (res.success && res.ips && res.ips.length > 0) {
      let outputHtml = `<div class="text-emerald-400 font-mono text-xs mt-1 space-y-1"><div>${t("resolve_success", res.ips.length)}</div>`;
      if (res.ips_v4 && res.ips_v4.length > 0) {
        outputHtml += `<div><span class="text-slate-400">[IPv4]:</span> <strong>${res.ips_v4.join(", ")}</strong></div>`;
      }
      if (res.ips_v6 && res.ips_v6.length > 0) {
        outputHtml += `<div><span class="text-slate-400">[IPv6]:</span> <strong>${res.ips_v6.join(", ")}</strong></div>`;
      }
      outputHtml += `</div>`;
      resultEl.innerHTML = outputHtml;
    } else {
      resultEl.innerHTML = `
        <div class="text-rose-400 font-mono text-xs mt-1">
          ${t("resolve_failed", res.error || "No valid IP")}
        </div>
      `;
    }
  } catch (e) {
    resultEl.innerHTML = `<div class="text-rose-400 font-mono text-xs mt-1">${t("toast_net_error")}</div>`;
  }
}

// --- 静态 IP 清单管理 (Static IPs) ---
async function loadStaticIps() {
  try {
    const data = await apiCall("/api/static-ips");
    if (data.need_login) return;

    document.getElementById("static-ips-editor").value = data.raw_content || "";
    document.getElementById("static-ips-count-badge").textContent = t("static_effective_count", data.count || 0, data.v4_count || 0, data.v6_count || 0);
  } catch (e) {}
}

async function handleSaveStaticIps(andApply = false) {
  const content = document.getElementById("static-ips-editor").value;
  try {
    const res = await apiCall("/api/static-ips", "PUT", { content });
    showToast(t("toast_static_saved", res.count), "success");
    loadStaticIps();
    loadStatus();
    loadRules();

    if (andApply) {
      handleTriggerSync();
      switchTab("logs");
    }
  } catch (e) {}
}

// 单条临时 IP 存入清单
async function handleAppendStaticIp(ip, rate = 100) {
  if (!confirm(t("toast_confirm_save_manual", ip, rate))) return;

  try {
    const res = await apiCall("/api/static-ips/append", "POST", { ip, rate });
    showToast(res.msg || t("toast_saved_to_list"), "success");
    loadRules();
    loadStatus();
  } catch (e) {}
}

// 一键将所有临时手动 IP 全部存入清单
async function handleSaveAllManualIps() {
  if (!confirm(t("toast_confirm_save_all"))) return;

  try {
    const res = await apiCall("/api/static-ips/save-all-manual", "POST");
    showToast(res.msg || t("toast_saved_to_list"), "success");
    loadRules();
    loadStatus();
  } catch (e) {}
}

async function handleTestIpFormat() {
  const ip = document.getElementById("test-ip-input").value.trim();
  const resultEl = document.getElementById("test-ip-result");
  if (!ip) {
    showToast(t("toast_empty_ip"), "error");
    return;
  }

  resultEl.innerHTML = `<span class="text-slate-400">${t("validating")}</span>`;
  try {
    const res = await apiCall("/api/static-ips/test-format", "POST", { ip });
    if (res.valid) {
      resultEl.innerHTML = `
        <div class="text-emerald-400 font-mono text-xs mt-1 space-y-0.5">
          <div>${t("valid_format", res.version)}</div>
          <div>${t("applied_target", res.formatted)}</div>
        </div>
      `;
    } else {
      resultEl.innerHTML = `
        <div class="text-rose-400 font-mono text-xs mt-1">
          ${t("invalid_format", res.error || "Invalid")}
        </div>
      `;
    }
  } catch (e) {
    resultEl.innerHTML = `<div class="text-rose-400 font-mono text-xs mt-1">${t("toast_net_error")}</div>`;
  }
}

// --- 同步与日志 (Sync & Logs) ---
async function handleTriggerSync() {
  const btn = document.getElementById("btn-sync-trigger");
  if (btn) btn.disabled = true;

  try {
    const res = await apiCall("/api/sync/run", "POST");
    showToast(res.msg || t("toast_sync_triggered"), "info");
    loadLogs();
  } catch (e) {
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function loadLogs() {
  try {
    const data = await apiCall("/api/sync/logs");
    if (data.need_login) return;

    const term = document.getElementById("terminal-output");
    const logs = data.logs || [];

    if (logs.length === 0) {
      term.innerHTML = `<span class="text-slate-600">${t("console_empty")}</span>`;
    } else {
      term.innerHTML = logs.map(line => {
        let colorClass = "text-slate-300";
        if (line.includes("[DNS]")) colorClass = "text-cyan-400";
        if (line.includes("[ADD ]")) colorClass = "text-emerald-400 font-bold";
        if (line.includes("[DEL ]")) colorClass = "text-rose-400 font-bold";
        if (line.includes("[SKIP]")) colorClass = "text-slate-500";
        if (line.includes("错误") || line.includes("error") || line.includes("failed")) colorClass = "text-rose-500 font-bold";
        return `<div class="${colorClass}">${line}</div>`;
      }).join("");

      // 滚动到底部
      term.scrollTop = term.scrollHeight;
    }
  } catch (e) {}
}

// --- 系统设置 (Settings) ---
async function loadSettings() {
  try {
    const data = await apiCall("/api/config");
    if (data.need_login) return;

    document.getElementById("setting-interval").value = data.sync_scheduler?.interval_seconds || 300;
    document.getElementById("setting-startup-delay").value = data.sync_scheduler?.startup_sync_delay ?? 5;
    document.getElementById("setting-scheduler-enabled").checked = data.sync_scheduler?.enabled !== false;
  } catch (e) {}
}

async function handleSaveSettings() {
  const interval = Number(document.getElementById("setting-interval").value) || 300;
  const startupDelay = Number(document.getElementById("setting-startup-delay").value) ?? 5;
  const enabled = document.getElementById("setting-scheduler-enabled").checked;
  const newPwd = document.getElementById("setting-new-password").value.trim();

  const payload = {
    sync_scheduler: {
      enabled: enabled,
      interval_seconds: interval,
      startup_sync_delay: startupDelay
    }
  };

  if (newPwd) {
    payload.auth = { new_password: newPwd };
  }

  try {
    const res = await apiCall("/api/config", "PUT", payload);
    showToast(res.msg || t("toast_config_updated"), "success");
    document.getElementById("setting-new-password").value = "";
    loadStatus();
  } catch (e) {}
}

// --- 初始装载 ---
function loadAllData() {
  loadStatus();
  switchTab(state.activeTab);

  // 定时刷新状态与日志
  if (state.logInterval) clearInterval(state.logInterval);
  state.logInterval = setInterval(() => {
    if (state.token) {
      loadStatus();
      if (state.activeTab === "logs") loadLogs();
    }
  }, 4000);
}

document.addEventListener("DOMContentLoaded", () => {
  // 服务端已在下发 index.html 前校验过认证，此处直接启动数据装载
  loadAllData();

  // 绑定搜索框实时过滤
  document.getElementById("rule-search-input")?.addEventListener("input", () => {
    renderRules();
  });
});
