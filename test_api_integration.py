import io
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import BrutalWebApp


class TestApiIntegration(unittest.TestCase):
    def setUp(self):
        self.app = BrutalWebApp()
        self.admin_password = self.app.config.get("auth", {}).get("admin_password", "admin123")
        self.token = None

    def make_request(self, method, path, body=None, token=None, extra_headers=None):
        headers = {}
        input_stream = io.BytesIO()
        content_length = "0"

        if body is not None:
            raw_body = json.dumps(body).encode('utf-8')
            input_stream = io.BytesIO(raw_body)
            content_length = str(len(raw_body))
            headers["CONTENT_TYPE"] = "application/json"

        headers["CONTENT_LENGTH"] = content_length

        if token:
            headers["HTTP_AUTHORIZATION"] = f"Bearer {token}"

        if extra_headers:
            headers.update(extra_headers)

        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path,
            "wsgi.input": input_stream,
            "SERVER_NAME": "localhost",
            "SERVER_PORT": "8080",
            "wsgi.version": (1, 0),
            "wsgi.url_scheme": "http",
            "REMOTE_ADDR": "127.0.0.1"
        }
        environ.update(headers)

        status_box = []
        response_headers_box = []

        def start_response(status, resp_headers):
            status_box.append(status)
            response_headers_box.extend(resp_headers)

        response_iter = self.app(environ, start_response)
        response_data = b"".join(response_iter)

        parsed_json = None
        try:
            parsed_json = json.loads(response_data.decode('utf-8'))
        except Exception:
            pass

        return {
            "status": status_box[0] if status_box else "500",
            "headers": response_headers_box,
            "data": response_data,
            "json": parsed_json
        }

    def test_full_workflow(self):
        # 1. 验证未登录时，服务端强制物理隔离：只返回独立登录页，绝不发送任何管理后台 DOM 与结构
        res = self.make_request("GET", "/")
        self.assertIn("200 OK", res["status"])
        self.assertIn(b"login-password", res["data"])
        self.assertNotIn(b"rules-table-body", res["data"])
        self.assertNotIn(b"domains-editor", res["data"])
        self.assertNotIn(b"static-ips-editor", res["data"])
        self.assertNotIn(b"terminal-output", res["data"])

        # 2. 未登录访问 /api/status 应返回 401
        res = self.make_request("GET", "/api/status")
        self.assertIn("401", res["status"])

        # 3. 错误密码登录失败
        res = self.make_request("POST", "/api/login", body={"password": "WrongPassword"})
        self.assertIn("403", res["status"])

        # 4. 正确密码登录成功
        res = self.make_request("POST", "/api/login", body={"password": self.admin_password})
        self.assertIn("200 OK", res["status"])
        self.assertIsNotNone(res["json"].get("token"))
        token = res["json"]["token"]

        # 4.1 登录后访问主页，服务端校验通过，正式返回管理控制面板完整结构
        res_auth_index = self.make_request("GET", "/", token=token)
        self.assertIn("200 OK", res_auth_index["status"])
        self.assertIn(b"rules-table-body", res_auth_index["data"])
        self.assertIn(b"domains-editor", res_auth_index["data"])
        self.assertIn(b"static-ips-editor", res_auth_index["data"])

        # 5. 带 Token 访问 /api/status，验证 client_ip 与 version 返回
        res = self.make_request("GET", "/api/status", token=token, extra_headers={"REMOTE_ADDR": "203.0.113.19"})
        self.assertIn("200 OK", res["status"])
        self.assertIn("rule_count", res["json"])
        self.assertIn("version", res["json"])
        self.assertTrue(res["json"]["version"].startswith("v"))
        self.assertEqual(res["json"].get("client_ip"), "203.0.113.19")

        # 5.1 验证 X-Forwarded-For 代理下提取最左侧客户端真实 IP
        res_proxy = self.make_request(
            "GET", "/api/status", token=token,
            extra_headers={"HTTP_X_FORWARDED_FOR": "198.51.100.88, 10.0.0.1", "REMOTE_ADDR": "127.0.0.1"}
        )
        self.assertEqual(res_proxy["json"].get("client_ip"), "198.51.100.88")

        # 5.2 验证当代理传过来 unix: 伪 IP 时，自动过滤并寻找真实客户端 IP
        res_unix = self.make_request(
            "GET", "/api/status", token=token,
            extra_headers={"HTTP_X_REAL_IP": "unix:", "HTTP_X_FORWARDED_FOR": "unix:, 203.0.113.55, 10.0.0.1", "REMOTE_ADDR": "unix:"}
        )
        self.assertEqual(res_unix["json"].get("client_ip"), "203.0.113.55")

        # 5.3 验证所有来源都是 unix: 时，不返回 unix: 伪地址
        res_all_unix = self.make_request(
            "GET", "/api/status", token=token,
            extra_headers={"HTTP_X_REAL_IP": "unix:", "REMOTE_ADDR": "unix:"}
        )
        self.assertEqual(res_all_unix["json"].get("client_ip"), "")

        # 6. 规则 CRUD (IPv4 与 IPv6)
        # 添加 IPv4 规则
        res = self.make_request("POST", "/api/rules", body={"ip": "198.51.100.1", "rate": 200}, token=token)
        self.assertIn("200 OK", res["status"])

        # 添加 IPv6 规则 (未带掩码，默认补齐 /128)
        res = self.make_request("POST", "/api/rules", body={"ip": "2001:db8:beef::1", "rate": 500}, token=token)
        self.assertIn("200 OK", res["status"])

        # 查询规则
        res = self.make_request("GET", "/api/rules", token=token)
        self.assertIn("200 OK", res["status"])
        dests = [r["destination"] for r in res["json"]["rules"]]
        self.assertIn("198.51.100.1/32", dests)
        self.assertIn("2001:db8:beef::1/128", dests)

        # 删除规则
        res = self.make_request("DELETE", "/api/rules", body={"ip": "198.51.100.1/32"}, token=token)
        self.assertIn("200 OK", res["status"])
        res = self.make_request("DELETE", "/api/rules", body={"ip": "2001:db8:beef::1/128"}, token=token)
        self.assertIn("200 OK", res["status"])

        # 尝试添加 ::ffff: 兼容地址应被拦截拒绝 (自动增加时不增加)
        res_reject = self.make_request("POST", "/api/rules", body={"ip": "::ffff:125.81.232.217", "rate": 100}, token=token)
        self.assertIn("400", res_reject["status"])

        # 删除操作应允许删除 ::ffff: 遗留兼容规则
        res_del_compat = self.make_request("DELETE", "/api/rules", body={"ip": "::ffff:125.81.232.217/128"}, token=token)
        self.assertIn("200 OK", res_del_compat["status"])

        # 7. 静态 IP 清单 API 与一键固化测试
        res = self.make_request("GET", "/api/static-ips", token=token)
        self.assertIn("200 OK", res["status"])
        self.assertIn("ips", res["json"])

        # 保存更新静态 IP 清单
        res = self.make_request("PUT", "/api/static-ips", body={"content": "10.0.0.1\n2001:db8::1\n"}, token=token)
        self.assertIn("200 OK", res["status"])
        self.assertEqual(res["json"]["count"], 2)

        # 添加一条临时手动规则
        self.make_request("POST", "/api/rules", body={"ip": "172.16.55.1", "rate": 100}, token=token)
        # 单条固化存入静态清单
        res = self.make_request("POST", "/api/static-ips/append", body={"ip": "172.16.55.1/32"}, token=token)
        self.assertIn("200 OK", res["status"])

        # 再添加两条临时规则，测试一键批量固化
        self.make_request("POST", "/api/rules", body={"ip": "172.16.55.2", "rate": 100}, token=token)
        self.make_request("POST", "/api/rules", body={"ip": "2001:db8:77::1", "rate": 200}, token=token)
        res = self.make_request("POST", "/api/static-ips/save-all-manual", token=token)
        self.assertIn("200 OK", res["status"])
        self.assertGreaterEqual(res["json"]["saved_count"], 2)

        # 测试 IP 格式检测
        res = self.make_request("POST", "/api/static-ips/test-format", body={"ip": "2408:8207::1"}, token=token)
        self.assertIn("200 OK", res["status"])
        self.assertTrue(res["json"]["valid"])
        self.assertEqual(res["json"]["formatted"], "2408:8207::1/128")

        # 8. 域名配置
        res = self.make_request("GET", "/api/domains", token=token)
        self.assertIn("200 OK", res["status"])
        self.assertIn("raw_content", res["json"])

        # 9. 测试单域名解析
        res = self.make_request("POST", "/api/domains/test-resolve", body={"domain": "127.0.0.1"}, token=token)
        self.assertIn("200 OK", res["status"])

        # 10. 触发同步
        res = self.make_request("POST", "/api/sync/run", token=token)
        self.assertIn("200 OK", res["status"])

        # 11. 获取同步日志
        res = self.make_request("GET", "/api/sync/logs", token=token)
        self.assertIn("200 OK", res["status"])
        self.assertIn("logs", res["json"])

        # 11. 登出
        res = self.make_request("POST", "/api/logout", token=token)
        self.assertIn("200 OK", res["status"])

        # 登出后再用原 Token 应被拒绝
        res = self.make_request("GET", "/api/status", token=token)
        self.assertIn("401", res["status"])

    def test_login_brute_force_lockout(self):
        # 针对特定 IP 进行防暴力破解测试
        attack_ip = "198.51.100.99"
        # 调整测试 app 的防爆破参数
        self.app.auth.max_failed_attempts = 3
        self.app.auth.lockout_duration_seconds = 2
        self.app.auth.failure_delay_seconds = 0.05

        # 连续尝试错误密码 2 次
        for attempt in (1, 2):
            res = self.make_request(
                "POST", "/api/login",
                body={"password": "WrongPwd"},
                extra_headers={"REMOTE_ADDR": attack_ip}
            )
            self.assertIn("403", res["status"])
            self.assertIn("还可尝试", res["json"].get("error", ""))

        # 第 3 次失败触发锁定，返回 429
        res_locked = self.make_request(
            "POST", "/api/login",
            body={"password": "WrongPwd"},
            extra_headers={"REMOTE_ADDR": attack_ip}
        )
        self.assertIn("429", res_locked["status"])
        self.assertTrue(res_locked["json"].get("locked"))

        # 锁定期间即使输入正确密码也被拒绝
        res_correct_blocked = self.make_request(
            "POST", "/api/login",
            body={"password": self.admin_password},
            extra_headers={"REMOTE_ADDR": attack_ip}
        )
        self.assertIn("429", res_correct_blocked["status"])

    def test_ipv6_subnet_lockout_via_api(self):
        # 验证通过 HTTP API 访问时 IPv6 /64 子网防爆破锁定生效
        self.app.auth.max_failed_attempts = 2
        self.app.auth.lockout_duration_seconds = 2
        self.app.auth.failure_delay_seconds = 0.05

        v6_1 = "2408:8207:1111:2222::1"
        v6_2 = "2408:8207:1111:2222::cafe"
        v6_new = "2408:8207:1111:2222::9999"

        # 尝试 2 次失败
        self.make_request("POST", "/api/login", body={"password": "bad"}, extra_headers={"REMOTE_ADDR": v6_1})
        res = self.make_request("POST", "/api/login", body={"password": "bad"}, extra_headers={"REMOTE_ADDR": v6_2})
        self.assertIn("429", res["status"])

        # 同一 /64 子网的全新地址访问即被 429 锁定拦截
        res_blocked = self.make_request("POST", "/api/login", body={"password": "any"}, extra_headers={"REMOTE_ADDR": v6_new})
        self.assertIn("429", res_blocked["status"])

    def test_update_rule_rate_api(self):
        # 1. 未登录拦截
        res_unauth = self.make_request("PUT", "/api/rules", body={"ip": "1.1.1.1", "rate": 200})
        self.assertIn("401", res_unauth["status"])

        token = self.app.auth.create_token()

        # 2. 非法入参拦截
        res_bad_rate = self.make_request("PUT", "/api/rules", body={"ip": "1.1.1.1", "rate": -10}, token=token)
        self.assertIn("400", res_bad_rate["status"])
        res_bad_ip = self.make_request("PUT", "/api/rules", body={"ip": "999.999.999.999", "rate": 100}, token=token)
        self.assertIn("400", res_bad_ip["status"])

        # 3. 修改静态 IP 规则速率
        orig_ip_content = self.app.ip_mgr.get_raw_content()
        self.app.ip_mgr.save_content("10.0.0.1 50\n172.16.55.1/32 100\n")
        try:
            res_static = self.make_request(
                "PUT", "/api/rules",
                body={"ip": "10.0.0.1", "rate": 250, "source": "static"},
                token=token
            )
            self.assertIn("200 OK", res_static["status"])
            self.assertEqual(res_static["json"]["source"], "static")
            # 验证持久化清单更新
            updated_ips = self.app.ip_mgr.get_effective_ips_with_rates()
            self.assertEqual(updated_ips.get("10.0.0.1/32"), 250.0)
        finally:
            self.app.ip_mgr.save_content(orig_ip_content)

        # 4. 修改域名解析 IP 规则速率
        orig_dom_content = self.app.domain_mgr.get_raw_content()
        self.app.domain_mgr.save_content("mytest.com 80\n")
        try:
            # 建立 domain_ip 映射
            self.app.domain_mgr.set_mock_ip_mapping({"192.0.2.1": "mytest.com", "2001:db8::1": "mytest.com"})
            self.app.brutal.add_rule("192.0.2.1", 80, is_manual=False)
            self.app.brutal.add_rule("2001:db8::1", 80, is_manual=False)

            res_domain = self.make_request(
                "PUT", "/api/rules",
                body={"ip": "192.0.2.1", "rate": 350, "source": "domain", "domain": "mytest.com"},
                token=token
            )
            self.assertIn("200 OK", res_domain["status"])
            self.assertEqual(res_domain["json"]["domain"], "mytest.com")

            # 验证清单文件持久化更新
            rates = self.app.domain_mgr.get_effective_domains_with_rates()
            self.assertEqual(rates.get("mytest.com"), 350.0)

            # 验证关联 IP 的内核规则速率均已更新
            rules = self.app.brutal.list_rules()
            rule_map = {r["destination"]: r["rate_mbps"] for r in rules}
            self.assertEqual(rule_map.get("192.0.2.1/32"), 350.0)
            self.assertEqual(rule_map.get("2001:db8::1/128"), 350.0)
        finally:
            self.app.domain_mgr.save_content(orig_dom_content)

        # 5. 修改临时规则速率
        self.app.brutal.add_rule("198.51.100.1", 100, is_manual=True)
        res_manual = self.make_request(
            "PUT", "/api/rules",
            body={"ip": "198.51.100.1", "rate": 450, "source": "manual"},
            token=token
        )
        self.assertIn("200 OK", res_manual["status"])
        self.assertEqual(res_manual["json"]["source"], "manual")
        rules = self.app.brutal.list_rules()
        rule_map = {r["destination"]: r["rate_mbps"] for r in rules}
        self.assertEqual(rule_map.get("198.51.100.1/32"), 450.0)


if __name__ == "__main__":
    unittest.main()
