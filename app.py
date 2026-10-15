import json
import os
import re
import ssl
import ipaddress
import mimetypes
import socketserver
from wsgiref.simple_server import make_server, WSGIServer, WSGIRequestHandler
from urllib.parse import parse_qs, urlparse

from core.auth import AuthManager
from core.brutal_wrapper import BrutalWrapper
from core.domain_manager import DomainManager
from core.ip_manager import IpManager
from core.sync_runner import SyncRunner

# 基础目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")


class ThreadedWSGIServer(socketserver.ThreadingMixIn, WSGIServer):
    """支持多线程并发处理的 WSGI 服务器"""
    daemon_threads = True


class SilentWSGIRequestHandler(WSGIRequestHandler):
    """精简请求日志输出"""
    def log_message(self, format, *args):
        # 仅打印 API 请求与页面访问
        if len(args) >= 1 and isinstance(args[0], str) and ("GET /api/sync/logs" in args[0]):
            return  # 避免频繁轮询日志刷屏
        super().log_message(format, *args)


class BrutalWebApp:
    def __init__(self, config_path: str = CONFIG_PATH):
        self.config_path = config_path
        self.config = self.load_config()

        # 初始化模块
        auth_conf = self.config.get("auth", {})
        self.auth = AuthManager(
            admin_password=auth_conf.get("admin_password", "admin123"),
            token_expire_hours=auth_conf.get("session_timeout_hours", 24),
            max_failed_attempts=int(auth_conf.get("max_failed_attempts", 5)),
            lockout_duration_seconds=int(auth_conf.get("lockout_duration_seconds", 900)),
            failure_delay_seconds=float(auth_conf.get("failure_delay_seconds", 1.5))
        )

        brutal_conf = self.config.get("brutal", {})
        webui_conf = self.config.get("webui", {})
        self.poll_interval_seconds = int(webui_conf.get("poll_interval_seconds", 5))
        status_cache_ttl = float(webui_conf.get("status_cache_ttl_seconds", 3))

        self.brutal = BrutalWrapper(
            brutalctl_bin=brutal_conf.get("brutalctl_bin", "brutalctl"),
            cache_ttl_seconds=status_cache_ttl
        )

        domain_file = os.path.join(BASE_DIR, brutal_conf.get("domain_file_path", "brut_domain.txt"))
        self.domain_mgr = DomainManager(file_path=domain_file)

        ip_file = os.path.join(BASE_DIR, brutal_conf.get("ip_file_path", "brut_ip.txt"))
        self.ip_mgr = IpManager(file_path=ip_file)

        sync_script = os.path.join(BASE_DIR, brutal_conf.get("sync_script_path", "brutal_sync.sh"))
        self.sync_runner = SyncRunner(
            script_path=sync_script,
            domain_file=domain_file,
            mock_mode=self.brutal.is_mock(),
            wrapper=self.brutal,
            ip_mgr=self.ip_mgr
        )

        # 启动后台定时同步调度（如果启用）
        scheduler_conf = self.config.get("sync_scheduler", {})
        if scheduler_conf.get("enabled", False):
            interval = scheduler_conf.get("interval_seconds", 600)
            startup_delay = float(scheduler_conf.get("startup_sync_delay", 5))
            self.sync_runner.start_scheduler(interval, initial_delay=startup_delay)

    @staticmethod
    def _merge_defaults(user_conf: dict, default_conf: dict) -> tuple:
        """平滑递归合并默认配置：新版本增加的配置项自动补齐，但绝对保留用户原有的所有自定义值"""
        changed = False
        merged = dict(user_conf)
        for key, default_val in default_conf.items():
            if key not in merged:
                merged[key] = json.loads(json.dumps(default_val))
                changed = True
            elif isinstance(default_val, dict) and isinstance(merged[key], dict):
                sub_merged, sub_changed = BrutalWebApp._merge_defaults(merged[key], default_val)
                merged[key] = sub_merged
                if sub_changed:
                    changed = True
        return merged, changed

    def get_default_config(self) -> dict:
        return {
            "server": {"host": "0.0.0.0", "port": 8080},
            "auth": {
                "admin_password": "admin123",
                "session_timeout_hours": 24,
                "max_failed_attempts": 5,
                "lockout_duration_seconds": 900,
                "failure_delay_seconds": 1.5
            },
            "brutal": {
                "brutalctl_bin": "brutalctl",
                "default_rate_mbps": 100,
                "domain_file_path": "./brut_domain.txt",
                "ip_file_path": "./brut_ip.txt",
                "sync_script_path": "./brutal_sync.sh"
            },
            "sync_scheduler": {"enabled": True, "interval_seconds": 600, "startup_sync_delay": 5},
            "webui": {"poll_interval_seconds": 5, "status_cache_ttl_seconds": 3},
            "ssl": {"enabled": False, "cert_file": "./cert.pem", "key_file": "./key.pem"}
        }

    def load_config(self) -> dict:
        default_conf = self.get_default_config()
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    user_conf = json.load(f)
                merged, changed = self._merge_defaults(user_conf, default_conf)
                if changed:
                    self.save_config(merged)
                return merged
            except Exception as e:
                print(f"[Warn] 加载配置失败，使用默认配置: {e}")
        return default_conf

    def save_config(self, new_config: dict):
        self.config = new_config
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(new_config, f, indent=2, ensure_ascii=False)

    def __call__(self, environ, start_response):
        """WSGI 处理主入口"""
        method = environ.get("REQUEST_METHOD", "GET").upper()
        path = environ.get("PATH_INFO", "/")

        # 静态文件处理
        if path.startswith("/static/"):
            return self.serve_static(path, start_response)

        # 主页面 HTML (根据服务端登录状态物理隔离)
        if path == "/" or path == "/index.html":
            return self.serve_index(environ, start_response)

        # API 路由
        if path.startswith("/api/"):
            return self.dispatch_api(method, path, environ, start_response)

        # 404
        start_response("404 Not Found", [("Content-Type", "text/plain; charset=utf-8")])
        return [b"404 Not Found"]

    def serve_index(self, environ, start_response):
        token = self._extract_token(environ)
        # 1. 服务端强制鉴权：未登录访客绝对只下发独立 login.html，物理杜绝管理后台结构与数据泄露
        if not self.auth.validate_token(token):
            login_file = os.path.join(BASE_DIR, "templates", "login.html")
            if os.path.exists(login_file):
                with open(login_file, "rb") as f:
                    content = f.read()
                start_response("200 OK", [
                    ("Content-Type", "text/html; charset=utf-8"),
                    ("Cache-Control", "no-cache, no-store, must-revalidate")
                ])
                return [content]
            start_response("500 Internal Server Error", [("Content-Type", "text/plain")])
            return [b"Template login.html not found"]

        # 2. 鉴权通过后才正式下发完整管理控制台模板 index.html
        index_file = os.path.join(BASE_DIR, "templates", "index.html")
        if os.path.exists(index_file):
            with open(index_file, "rb") as f:
                content = f.read()
            start_response("200 OK", [
                ("Content-Type", "text/html; charset=utf-8"),
                ("Cache-Control", "no-cache, no-store, must-revalidate")
            ])
            return [content]
        start_response("500 Internal Server Error", [("Content-Type", "text/plain")])
        return [b"Template index.html not found"]

    def serve_static(self, path, start_response):
        rel_path = path[len("/static/"):]
        file_path = os.path.normpath(os.path.join(BASE_DIR, "static", rel_path))
        static_dir = os.path.join(BASE_DIR, "static")

        # 防止路径穿越
        if not file_path.startswith(static_dir) or not os.path.exists(file_path):
            start_response("404 Not Found", [("Content-Type", "text/plain")])
            return [b"File not found"]

        mime_type, _ = mimetypes.guess_type(file_path)
        content_type = mime_type or "application/octet-stream"

        with open(file_path, "rb") as f:
            content = f.read()
        start_response("200 OK", [("Content-Type", content_type)])
        return [content]

    def _extract_token(self, environ) -> str:
        # 1. 尝试从 Authorization Header 中读取
        auth_header = environ.get("HTTP_AUTHORIZATION", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:].strip()

        # 2. 尝试从 Cookie 中读取 session_token
        cookie_header = environ.get("HTTP_COOKIE", "")
        if cookie_header:
            cookies = [c.strip() for c in cookie_header.split(";")]
            for c in cookies:
                if c.startswith("session_token="):
                    return c[len("session_token="):].strip()
        return ""

    def _extract_client_ip(self, environ) -> str:
        """从 WSGI 请求环境中识别客户端的真实合法 IPv4/IPv6 地址（过滤 unix: 等伪地址）"""
        def is_valid_ip(candidate: str) -> bool:
            if not candidate or not isinstance(candidate, str):
                return False
            clean = candidate.strip()
            if clean.startswith("unix:") or clean.lower() in ("unknown", "none"):
                return False
            # 去除可能携带的端口号（如 1.2.3.4:5678）
            if ":" in clean and not clean.startswith("[") and clean.count(":") == 1:
                clean = clean.split(":")[0]
            try:
                ipaddress.ip_address(clean)
                return True
            except ValueError:
                return False

        def clean_ip_str(candidate: str) -> str:
            clean = candidate.strip()
            if ":" in clean and not clean.startswith("[") and clean.count(":") == 1:
                clean = clean.split(":")[0]
            return clean

        # 1. 尝试 Cloudflare 特有的 Header (CF-Connecting-IP)
        cf_ip = environ.get("HTTP_CF_CONNECTING_IP", "").strip()
        if is_valid_ip(cf_ip):
            return clean_ip_str(cf_ip)

        # 2. 遍历 X-Forwarded-For 寻找第一个有效合法的 IP
        xff = environ.get("HTTP_X_FORWARDED_FOR", "")
        if xff:
            parts = [p.strip() for p in xff.split(",")]
            for p in parts:
                if is_valid_ip(p):
                    return clean_ip_str(p)

        # 3. 尝试获取 X-Real-IP
        x_real_ip = environ.get("HTTP_X_REAL_IP", "").strip()
        if is_valid_ip(x_real_ip):
            return clean_ip_str(x_real_ip)

        # 4. 回退到底层连接地址 REMOTE_ADDR
        remote_addr = environ.get("REMOTE_ADDR", "").strip()
        if is_valid_ip(remote_addr):
            return clean_ip_str(remote_addr)

        return ""

    def dispatch_api(self, method, path, environ, start_response):
        # 登录接口无需鉴权
        if path == "/api/login" and method == "POST":
            return self.api_login(environ, start_response)

        # 其它 API 接口必须验证 Token
        token = self._extract_token(environ)
        if not self.auth.validate_token(token):
            return self.json_response({"error": "未授权，请先登录", "need_login": True}, start_response, status="401 Unauthorized")

        # 登出 (同时彻底注销客户端 Cookie)
        if path == "/api/logout" and method == "POST":
            self.auth.revoke_token(token)
            headers = [
                ("Set-Cookie", "session_token=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT; HttpOnly; SameSite=Lax")
            ]
            return self.json_response({"status": "ok", "msg": "已登出"}, start_response, headers=headers)

        # 系统状态
        if path == "/api/status" and method == "GET":
            return self.api_status(environ, start_response)

        # 规则管理
        if path == "/api/rules":
            if method == "GET":
                return self.api_list_rules(start_response)
            elif method == "POST":
                return self.api_add_rule(environ, start_response)
            elif method == "DELETE":
                return self.api_del_rule(environ, start_response)

        # 域名管理
        if path == "/api/domains":
            if method == "GET":
                return self.api_get_domains(start_response)
            elif method == "PUT":
                return self.api_save_domains(environ, start_response)

        # 静态 IP 清单管理
        if path == "/api/static-ips":
            if method == "GET":
                return self.api_get_static_ips(start_response)
            elif method == "PUT":
                return self.api_save_static_ips(environ, start_response)

        # 单条临时 IP 存入静态清单
        if path == "/api/static-ips/append" and method == "POST":
            return self.api_append_static_ip(environ, start_response)

        # 一键将所有临时 IP 存入静态清单
        if path == "/api/static-ips/save-all-manual" and method == "POST":
            return self.api_save_all_manual_ips(start_response)

        # IP 格式快速校验
        if path == "/api/static-ips/test-format" and method == "POST":
            return self.api_test_ip_format(environ, start_response)

        # 单域名测试解析
        if path == "/api/domains/test-resolve" and method == "POST":
            return self.api_test_resolve(environ, start_response)

        # 同步操作
        if path == "/api/sync/run" and method == "POST":
            return self.api_sync_run(start_response)

        if path == "/api/sync/logs" and method == "GET":
            return self.api_sync_logs(start_response)

        # 配置管理
        if path == "/api/config":
            if method == "GET":
                return self.api_get_config(start_response)
            elif method == "PUT":
                return self.api_update_config(environ, start_response)

        return self.json_response({"error": "API 接口不存在"}, start_response, status="404 Not Found")

    def _parse_json_body(self, environ) -> dict:
        try:
            length = int(environ.get('CONTENT_LENGTH', '0'))
            if length > 0:
                body = environ['wsgi.input'].read(length)
                return json.loads(body.decode('utf-8'))
        except Exception:
            pass
        return {}

    def json_response(self, data, start_response, status="200 OK", headers=None):
        if headers is None:
            headers = []
        headers.append(("Content-Type", "application/json; charset=utf-8"))
        headers.append(("Cache-Control", "no-cache"))
        start_response(status, headers)
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        return [body]

    # --- 具体 API 实现 ---

    def api_login(self, environ, start_response):
        client_ip = self._extract_client_ip(environ)
        # 1. 检查客户端 IP 是否处于锁定状态
        is_locked, remaining_seconds = self.auth.is_ip_locked(client_ip)
        if is_locked:
            return self.json_response(
                {
                    "error": f"登录失败次数过多，该 IP 已被临时锁定，请在 {remaining_seconds} 秒后再试",
                    "locked": True,
                    "remaining_seconds": remaining_seconds
                },
                start_response,
                status="429 Too Many Requests"
            )

        body = self._parse_json_body(environ)
        password = body.get("password", "")

        # 2. 密码验证成功
        if self.auth.verify_password(password):
            self.auth.record_login_success(client_ip)
            token = self.auth.create_token()
            headers = [
                ("Set-Cookie", f"session_token={token}; Path=/; HttpOnly; SameSite=Lax")
            ]
            return self.json_response({"status": "ok", "token": token, "msg": "登录成功"}, start_response, headers=headers)

        # 3. 密码错误：记录失败并施加延迟惩罚
        count, is_now_locked = self.auth.record_login_failure(client_ip)
        if is_now_locked:
            _, remaining_seconds = self.auth.is_ip_locked(client_ip)
            return self.json_response(
                {
                    "error": f"密码连续错误超过限制，该 IP 已被临时锁定 {remaining_seconds} 秒",
                    "locked": True,
                    "remaining_seconds": remaining_seconds
                },
                start_response,
                status="429 Too Many Requests"
            )

        remaining_attempts = max(0, self.auth.max_failed_attempts - count)
        return self.json_response(
            {
                "error": f"密码错误，还可尝试 {remaining_attempts} 次",
                "remaining_attempts": remaining_attempts
            },
            start_response,
            status="403 Forbidden"
        )

    def api_status(self, environ, start_response):
        static_ips = set(self.ip_mgr.get_effective_ips())
        domain_ip_map = self.domain_mgr.get_cached_ip_to_domain_map()
        rules = self.brutal.list_rules(static_ips=static_ips, domain_ip_map=domain_ip_map)
        effective_domains = self.domain_mgr.get_effective_domains()
        sync_status = self.sync_runner.get_status()
        client_ip = self._extract_client_ip(environ)

        total_sent_mb = sum([r.get("sent_mb", 0.0) for r in rules])
        manual_count = sum(1 for r in rules if r.get("source") == "manual")

        return self.json_response({
            "is_mock": self.brutal.is_mock(),
            "client_ip": client_ip,
            "rule_count": len(rules),
            "domain_count": len(effective_domains),
            "static_ip_count": len(static_ips),
            "manual_count": manual_count,
            "total_sent_mb": round(total_sent_mb, 2),
            "poll_interval_seconds": self.poll_interval_seconds,
            "sync": sync_status
        }, start_response)

    def api_list_rules(self, start_response):
        static_ips = set(self.ip_mgr.get_effective_ips())
        domain_ip_map = self.domain_mgr.get_cached_ip_to_domain_map()
        rules = self.brutal.list_rules(static_ips=static_ips, domain_ip_map=domain_ip_map)
        return self.json_response({"rules": rules}, start_response)

    def api_add_rule(self, environ, start_response):
        body = self._parse_json_body(environ)
        ip = body.get("ip", "")
        rate = body.get("rate", self.config.get("brutal", {}).get("default_rate_mbps", 100))
        success, msg = self.brutal.add_rule(ip, rate, is_manual=True)
        if success:
            return self.json_response({"status": "ok", "msg": msg}, start_response)
        return self.json_response({"error": msg}, start_response, status="400 Bad Request")

    def api_del_rule(self, environ, start_response):
        body = self._parse_json_body(environ)
        ip = body.get("ip", "")
        success, msg = self.brutal.del_rule(ip)
        if success:
            return self.json_response({"status": "ok", "msg": msg}, start_response)
        return self.json_response({"error": msg}, start_response, status="400 Bad Request")

    def api_get_domains(self, start_response):
        raw = self.domain_mgr.get_raw_content()
        domains = self.domain_mgr.get_effective_domains()
        return self.json_response({"raw_content": raw, "domains": domains, "count": len(domains)}, start_response)

    def api_save_domains(self, environ, start_response):
        body = self._parse_json_body(environ)
        new_content = body.get("content", "")
        success, msg, count = self.domain_mgr.save_content(new_content)
        if success:
            return self.json_response({"status": "ok", "msg": msg, "count": count}, start_response)
        return self.json_response({"error": msg}, start_response, status="500 Internal Server Error")

    def api_get_static_ips(self, start_response):
        raw = self.im_raw = self.ip_mgr.get_raw_content()
        ips = self.ip_mgr.get_effective_ips()
        v4_count = sum(1 for ip in ips if ":" not in ip)
        v6_count = sum(1 for ip in ips if ":" in ip)
        return self.json_response({
            "raw_content": raw,
            "ips": ips,
            "count": len(ips),
            "v4_count": v4_count,
            "v6_count": v6_count
        }, start_response)

    def api_save_static_ips(self, environ, start_response):
        body = self._parse_json_body(environ)
        new_content = body.get("content", "")

        # 记录保存前的旧静态 IP 集合
        old_ips = set(self.ip_mgr.get_effective_ips())

        success, msg, count = self.ip_mgr.save_content(new_content)
        if success:
            new_rules = self.ip_mgr.get_effective_ips_with_rates(default_rate=100.0)
            new_ips = set(new_rules.keys())

            # 1. 清理从清单中被移除的废弃静态规则
            removed_ips = old_ips - new_ips
            for r_ip in removed_ips:
                self.brutal.del_rule(r_ip)

            # 2. 立即将清单中的所有有效静态规则下发生效到 brutalctl
            for s_ip, s_rate in new_rules.items():
                self.brutal.add_rule(s_ip, s_rate, is_manual=False)

            return self.json_response({
                "status": "ok",
                "msg": f"静态 IP 清单已保存并已立即应用生效 ({count} 条规则)",
                "count": count
            }, start_response)

        return self.json_response({"error": msg}, start_response, status="500 Internal Server Error")

    def api_append_static_ip(self, environ, start_response):
        body = self._parse_json_body(environ)
        ip = body.get("ip", "")
        rate = body.get("rate")
        success, msg = self.ip_mgr.append_ip(ip, rate=rate)
        if success:
            # 存入静态清单后，从临时内存集合中注销并作为静态规则立即确保下发生效
            self.brutal.unmark_manual_ip(ip)
            apply_rate = float(rate) if rate and float(rate) > 0 else 100.0
            self.brutal.add_rule(ip, apply_rate, is_manual=False)
            return self.json_response({"status": "ok", "msg": msg}, start_response)
        return self.json_response({"error": msg}, start_response, status="400 Bad Request")

    def api_save_all_manual_ips(self, start_response):
        manual_ips = set(self.brutal.get_manual_ips())
        if not manual_ips:
            return self.json_response({"status": "ok", "msg": "当前没有临时手动 IP 需要保存", "saved_count": 0}, start_response)

        # 获取当前运行规则中记录的自定义速率
        rules = self.brutal.list_rules()
        rule_rate_map = {r.get("destination"): r.get("rate_mbps") for r in rules}

        saved = 0
        for mip in manual_ips:
            rule_rate = rule_rate_map.get(mip)
            ok, _ = self.ip_mgr.append_ip(mip, rate=rule_rate)
            if ok:
                saved += 1
            self.brutal.unmark_manual_ip(mip)

        return self.json_response({
            "status": "ok",
            "msg": f"已成功将 {saved} 个临时 IP 及其速率配置保存到静态清单中",
            "saved_count": saved
        }, start_response)

    def api_test_ip_format(self, environ, start_response):
        body = self._parse_json_body(environ)
        ip = body.get("ip", "")
        result = self.ip_mgr.test_ip_format(ip)
        return self.json_response(result, start_response)

    def api_test_resolve(self, environ, start_response):
        body = self._parse_json_body(environ)
        domain = body.get("domain", "")
        result = self.domain_mgr.test_resolve(domain)
        return self.json_response(result, start_response)

    def api_sync_run(self, start_response):
        success, msg = self.sync_runner.trigger_sync()
        if success:
            self.brutal.invalidate_cache()
            return self.json_response({"status": "ok", "msg": msg}, start_response)
        return self.json_response({"error": msg}, start_response, status="409 Conflict")

    def api_sync_logs(self, start_response):
        logs = self.sync_runner.get_logs()
        status = self.sync_runner.get_status()
        return self.json_response({"logs": logs, "status": status}, start_response)

    def api_get_config(self, start_response):
        # 屏蔽明文密码
        safe_conf = json.loads(json.dumps(self.config))
        if "auth" in safe_conf and "admin_password" in safe_conf["auth"]:
            safe_conf["auth"]["has_password"] = True
            safe_conf["auth"]["admin_password"] = "******"
        if "webui" not in safe_conf:
            safe_conf["webui"] = {
                "poll_interval_seconds": 5,
                "status_cache_ttl_seconds": 3
            }
        return self.json_response(safe_conf, start_response)

    def api_update_config(self, environ, start_response):
        body = self._parse_json_body(environ)
        # 支持修改密码与自动同步设置
        auth_conf = body.get("auth", {})
        new_pwd = auth_conf.get("new_password")
        if new_pwd:
            if len(new_pwd) < 5:
                return self.json_response({"error": "密码长度不能少于 5 位"}, start_response, status="400 Bad Request")
            self.config["auth"]["admin_password"] = new_pwd
            self.auth.update_password(new_pwd)

        scheduler_conf = body.get("sync_scheduler", {})
        if scheduler_conf:
            enabled = scheduler_conf.get("enabled", self.config.get("sync_scheduler", {}).get("enabled", True))
            interval = int(scheduler_conf.get("interval_seconds", self.config.get("sync_scheduler", {}).get("interval_seconds", 600)))
            startup_delay = float(scheduler_conf.get("startup_sync_delay", self.config.get("sync_scheduler", {}).get("startup_sync_delay", 5)))
            if "sync_scheduler" not in self.config:
                self.config["sync_scheduler"] = {}
            self.config["sync_scheduler"]["enabled"] = enabled
            self.config["sync_scheduler"]["interval_seconds"] = interval
            self.config["sync_scheduler"]["startup_sync_delay"] = startup_delay

            if enabled:
                self.sync_runner.start_scheduler(interval, initial_delay=0)
            else:
                self.sync_runner.stop_scheduler()

        webui_conf = body.get("webui", {})
        if webui_conf:
            if "webui" not in self.config:
                self.config["webui"] = {}
            if "poll_interval_seconds" in webui_conf:
                poll_interval = max(1, int(webui_conf["poll_interval_seconds"]))
                self.config["webui"]["poll_interval_seconds"] = poll_interval
                self.poll_interval_seconds = poll_interval
            if "status_cache_ttl_seconds" in webui_conf:
                cache_ttl = max(0.0, float(webui_conf["status_cache_ttl_seconds"]))
                self.config["webui"]["status_cache_ttl_seconds"] = cache_ttl
                self.brutal.set_cache_ttl(cache_ttl)

        self.save_config(self.config)
        return self.json_response({"status": "ok", "msg": "配置更新成功"}, start_response)


def main():
    import sys
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

    app = BrutalWebApp()
    host = app.config.get("server", {}).get("host", "0.0.0.0")
    port = app.config.get("server", {}).get("port", 8080)

    # 启动 WSGI 服务器
    server = make_server(host, port, app, server_class=ThreadedWSGIServer, handler_class=SilentWSGIRequestHandler)

    proto = "http"
    ssl_conf = app.config.get("ssl", {})
    if ssl_conf.get("enabled", False):
        cert_file = ssl_conf.get("cert_file", "./cert.pem")
        key_file = ssl_conf.get("key_file", "./key.pem")
        cert_path = os.path.abspath(os.path.join(BASE_DIR, cert_file))
        key_path = os.path.abspath(os.path.join(BASE_DIR, key_file))

        if os.path.exists(cert_path) and os.path.exists(key_path):
            try:
                ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                ssl_ctx.load_cert_chain(certfile=cert_path, keyfile=key_path)
                server.socket = ssl_ctx.wrap_socket(server.socket, server_side=True)
                proto = "https"
            except Exception as e:
                print(f"[警告] SSL 证书加载失败: {e}，回退至 HTTP 模式", flush=True)
        else:
            print(f"[警告] SSL 证书或私钥文件不存在，回退至 HTTP 模式", flush=True)

    print("==================================================", flush=True)
    print("         Brutal Traffic Control WebUI 启动中      ", flush=True)
    print("==================================================", flush=True)
    print(f"监听地址: {proto}://{host}:{port}", flush=True)
    print(f"安全传输: {'[已启用 HTTPS 加密]' if proto == 'https' else '[HTTP 未加密传输]'}", flush=True)
    print(f"运行模式: {'[Mock 模拟模式]' if app.brutal.is_mock() else '[真实系统 brutalctl 模式]'}", flush=True)
    print(f"初始管理密码: {app.config.get('auth', {}).get('admin_password', '')}", flush=True)
    print("==================================================", flush=True)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n正在停止服务...")
    finally:
        app.sync_runner.stop_scheduler()
        server.server_close()


if __name__ == "__main__":
    main()
