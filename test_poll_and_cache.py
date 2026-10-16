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


class TestBrutalWrapperCache(unittest.TestCase):
    def test_cache_hit_and_expiration(self):
        # 初始化带 1 秒缓存的 wrapper
        wrapper = BrutalWrapper(mock_mode=True, cache_ttl_seconds=1.0)
        rules1 = wrapper.list_rules()
        self.assertGreater(len(rules1), 0)

        # 在底层直接篡改内部 mock 数据，如果缓存命中，list_rules 应依然返回旧数据
        original_mock = wrapper._mock_rules
        wrapper._mock_rules = []

        # 缓存命中：应当依然返回原有规则
        rules2 = wrapper.list_rules()
        self.assertEqual(len(rules2), len(rules1))

        # 等待 1.1 秒让缓存失效
        time.sleep(1.1)

        # 缓存过期后重新获取：应当反映最新数据（0 条）
        rules3 = wrapper.list_rules()
        self.assertEqual(len(rules3), 0)

    def test_cache_invalidation_on_mutation(self):
        # 初始化带 5 秒缓存的 wrapper
        wrapper = BrutalWrapper(mock_mode=True, cache_ttl_seconds=5.0)
        initial_rules = wrapper.list_rules()
        initial_count = len(initial_rules)

        # 添加新规则，应当立即清除缓存
        success, _ = wrapper.add_rule("192.0.2.1", 100)
        self.assertTrue(success)

        # 再次获取，应该立即拿到新规则数量，而不是返回之前的缓存
        new_rules = wrapper.list_rules()
        self.assertEqual(len(new_rules), initial_count + 1)

        # 删除规则，也应当立即清除缓存
        wrapper.del_rule("192.0.2.1/32")
        after_del = wrapper.list_rules()
        self.assertEqual(len(after_del), initial_count)


class TestWebUIPollAndCacheApi(unittest.TestCase):
    def setUp(self):
        # 使用临时配置文件，保证测试隔离且不污染真实 config.json
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_config_path = os.path.join(self.temp_dir.name, "test_config.json")
        default_conf = {
            "server": {"host": "0.0.0.0", "port": 8080},
            "auth": {"admin_password": "test_password_123", "session_timeout_hours": 1},
            "brutal": {
                "brutalctl_bin": "brutalctl",
                "default_rate_mbps": 100,
                "domain_file_path": "./brut_domain.txt",
                "ip_file_path": "./brut_ip.txt",
                "sync_script_path": "./brutal_sync.sh"
            },
            "sync_scheduler": {"enabled": False, "interval_seconds": 600},
            "webui": {
                "poll_interval_seconds": 10,
                "status_cache_ttl_seconds": 8
            }
        }
        with open(self.temp_config_path, "w", encoding="utf-8") as f:
            json.dump(default_conf, f)

        self.app = BrutalWebApp(config_path=self.temp_config_path)
        self.admin_password = "test_password_123"
        # 登录获取 token
        self.token = self.app.auth.create_token()

    def tearDown(self):
        self.temp_dir.cleanup()

    def make_request(self, method, path, body=None):
        headers = {}
        input_stream = io.BytesIO()
        content_length = "0"

        if body is not None:
            raw_body = json.dumps(body).encode('utf-8')
            input_stream = io.BytesIO(raw_body)
            content_length = str(len(raw_body))
            headers["CONTENT_TYPE"] = "application/json"

        headers["CONTENT_LENGTH"] = content_length
        headers["HTTP_AUTHORIZATION"] = f"Bearer {self.token}"

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

    def test_status_returns_poll_interval(self):
        res = self.make_request("GET", "/api/status")
        self.assertIn("200 OK", res["status"])
        self.assertIn("poll_interval_seconds", res["json"])
        self.assertEqual(res["json"]["poll_interval_seconds"], 10)

    def test_config_get_and_update_webui(self):
        # 1. 查询初始配置
        res = self.make_request("GET", "/api/config")
        self.assertIn("200 OK", res["status"])
        self.assertIn("webui", res["json"])
        self.assertEqual(res["json"]["webui"].get("poll_interval_seconds"), 10)
        self.assertEqual(res["json"]["webui"].get("status_cache_ttl_seconds"), 8)

        # 2. 修改配置
        update_payload = {
            "webui": {
                "poll_interval_seconds": 8,
                "status_cache_ttl_seconds": 4
            }
        }
        res_put = self.make_request("PUT", "/api/config", body=update_payload)
        self.assertIn("200 OK", res_put["status"])

        # 3. 再次查询验证生效
        res_get2 = self.make_request("GET", "/api/config")
        self.assertEqual(res_get2["json"]["webui"].get("poll_interval_seconds"), 8)
        self.assertEqual(res_get2["json"]["webui"].get("status_cache_ttl_seconds"), 4)

        # 4. 验证 /api/status 同步返回更新后的 poll_interval_seconds
        res_status = self.make_request("GET", "/api/status")
        self.assertEqual(res_status["json"].get("poll_interval_seconds"), 8)


if __name__ == "__main__":
    unittest.main()
