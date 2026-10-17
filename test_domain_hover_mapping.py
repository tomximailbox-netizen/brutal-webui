import io
import json
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import BrutalWebApp
from core.brutal_wrapper import BrutalWrapper
from core.domain_manager import DomainManager


class TestDomainHoverMapping(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.domain_file = os.path.join(self.temp_dir.name, "brut_domain.txt")
        with open(self.domain_file, "w", encoding="utf-8") as f:
            f.write("node1.example.com 200\nnode2.example.org\n")
        self.domain_mgr = DomainManager(file_path=self.domain_file)

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            time.sleep(0.1)
            try:
                self.temp_dir.cleanup()
            except Exception:
                pass

    def test_domain_manager_ip_to_domain_map(self):
        # 测试自定义注入映射与缓存验证
        self.domain_mgr.set_mock_ip_mapping({"123.145.97.17": "node1.example.com", "2001:db8::1": "node2.example.org"})
        cached_map = self.domain_mgr.get_cached_ip_to_domain_map()
        self.assertIsInstance(cached_map, dict)
        self.assertEqual(cached_map.get("123.145.97.17"), "node1.example.com")
        self.assertEqual(cached_map.get("123.145.97.17/32"), "node1.example.com")
        self.assertEqual(cached_map.get("2001:db8::1/128"), "node2.example.org")

    def test_wrapper_list_rules_with_domain_mapping(self):
        wrapper = BrutalWrapper(mock_mode=True)
        domain_ip_map = {
            "123.145.97.17/32": "node1.example.com",
            "123.145.97.17": "node1.example.com",
            "2001:db8::1/128": "node2.example.org"
        }

        # 列出规则并传入域名映射
        rules = wrapper.list_rules(static_ips={"1.1.1.1/32"}, domain_ip_map=domain_ip_map)
        rule_map = {r["destination"]: r for r in rules}

        # 123.145.97.17/32 不是 static，也不是 manual，属于 domain
        self.assertEqual(rule_map["123.145.97.17/32"]["source"], "domain")
        self.assertEqual(rule_map["123.145.97.17/32"].get("domain"), "node1.example.com")

        # 2001:db8::1/128 属于 domain
        self.assertEqual(rule_map["2001:db8::1/128"]["source"], "domain")
        self.assertEqual(rule_map["2001:db8::1/128"].get("domain"), "node2.example.org")

        # 1.1.1.1/32 属于 static，不应有 domain
        self.assertEqual(rule_map["1.1.1.1/32"]["source"], "static")
        self.assertIsNone(rule_map["1.1.1.1/32"].get("domain"))

    def test_api_rules_returns_domain_field(self):
        config_path = os.path.join(self.temp_dir.name, "config.json")
        conf = {
            "server": {"host": "0.0.0.0", "port": 8080},
            "auth": {"admin_password": "test_password_123"},
            "brutal": {
                "brutalctl_bin": "brutalctl",
                "domain_file_path": self.domain_file
            }
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(conf, f)

        app = BrutalWebApp(config_path=config_path)
        # 注入 mock 域名解析映射
        app.domain_mgr.set_mock_ip_mapping({"123.145.97.17": "node1.example.com"})

        token = app.auth.create_token()
        status_box = []
        def start_response(status, resp_headers):
            status_box.append(status)

        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/api/rules",
            "wsgi.input": io.BytesIO(),
            "SERVER_NAME": "localhost",
            "SERVER_PORT": "8080",
            "wsgi.version": (1, 0),
            "wsgi.url_scheme": "http",
            "REMOTE_ADDR": "127.0.0.1",
            "HTTP_AUTHORIZATION": f"Bearer {token}"
        }
        resp = app(environ, start_response)
        data = json.loads(b"".join(resp).decode("utf-8"))

        self.assertIn("200 OK", status_box[0])
        rules = data.get("rules", [])
        matched = [r for r in rules if r["destination"] == "123.145.97.17/32"]
        self.assertTrue(len(matched) > 0)
        self.assertEqual(matched[0].get("domain"), "node1.example.com")


if __name__ == "__main__":
    unittest.main()
