import io
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import BrutalWebApp


class TestUpgradeCompatibility(unittest.TestCase):
    """验证从早期极简旧版本 config.json 平滑无损升级时的兼容性"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_config_path = os.path.join(self.temp_dir.name, "config.json")

        # 模拟早期无 webui 节点、无防爆破参数、无 startup_sync_delay 的极简旧配置
        self.old_config_data = {
            "server": {
                "host": "127.0.0.1",
                "port": 9090
            },
            "auth": {
                "admin_password": "MyCustomOldPassword999",
                "session_timeout_hours": 12
            },
            "brutal": {
                "brutalctl_bin": "brutalctl",
                "default_rate_mbps": 200,
                "domain_file_path": "./brut_domain.txt"
            },
            "sync_scheduler": {
                "enabled": True,
                "interval_seconds": 600
            }
        }
        with open(self.old_config_path, "w", encoding="utf-8") as f:
            json.dump(self.old_config_data, f, indent=2)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_seamless_boot_with_old_config(self):
        # 1. 在完全缺乏 webui 配置的环境下初始化服务
        app = BrutalWebApp(config_path=self.old_config_path)

        # 2. 验证原有的关键配置 100% 得到保留
        self.assertEqual(app.config["server"]["port"], 9090)
        self.assertEqual(app.config["server"]["host"], "127.0.0.1")
        self.assertEqual(app.config["auth"]["session_timeout_hours"], 12)
        self.assertEqual(app.config["brutal"]["default_rate_mbps"], 200)

        # 3. 验证原密码依然可以成功校验登录
        self.assertTrue(app.auth.verify_password("MyCustomOldPassword999"))
        self.assertFalse(app.auth.verify_password("WrongPassword"))

        # 4. 验证新增的 webui 轮询和缓存配置自动应用默认值，程序不抛异常
        self.assertEqual(app.poll_interval_seconds, 5)
        self.assertEqual(app.brutal.cache_ttl_seconds, 3.0)

        # 5. 验证新增的 webui 结构被安全补齐
        self.assertIn("webui", app.config)
        self.assertEqual(app.config["webui"]["poll_interval_seconds"], 5)
        self.assertEqual(app.config["webui"]["status_cache_ttl_seconds"], 3)

        # 6. 验证 disk 文件中已经平滑补全，且原有密码绝对未被篡改
        with open(self.old_config_path, "r", encoding="utf-8") as f:
            disk_conf = json.load(f)
        self.assertEqual(disk_conf["auth"]["admin_password"], "MyCustomOldPassword999")
        self.assertEqual(disk_conf["server"]["port"], 9090)
        self.assertIn("webui", disk_conf)

        # 7. 模拟 HTTP 请求 /api/status 与 /api/config 验证 API 响应完全正常
        token = app.auth.create_token()

        status_box = []
        def start_response(status, resp_headers):
            status_box.append(status)

        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/api/status",
            "wsgi.input": io.BytesIO(),
            "SERVER_NAME": "localhost",
            "SERVER_PORT": "9090",
            "wsgi.version": (1, 0),
            "wsgi.url_scheme": "http",
            "REMOTE_ADDR": "127.0.0.1",
            "HTTP_AUTHORIZATION": f"Bearer {token}"
        }
        resp = app(environ, start_response)
        body = json.loads(b"".join(resp).decode("utf-8"))

        self.assertIn("200 OK", status_box[0])
        self.assertEqual(body.get("poll_interval_seconds"), 5)
        self.assertIn("rule_count", body)


if __name__ == "__main__":
    unittest.main()
