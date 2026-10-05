import os
import sys
import unittest
import tempfile
import time

# 将当前目录加入路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.auth import AuthManager
from core.brutal_wrapper import BrutalWrapper, validate_ip_cidr
from core.domain_manager import DomainManager
from core.ip_manager import IpManager
from core.sync_runner import SyncRunner


class TestAuth(unittest.TestCase):
    def setUp(self):
        self.auth = AuthManager(admin_password="MySecretPassword123", token_expire_hours=1)

    def test_verify_password(self):
        self.assertTrue(self.auth.verify_password("MySecretPassword123"))
        self.assertFalse(self.auth.verify_password("WrongPassword"))
        self.assertFalse(self.auth.verify_password(""))

    def test_token_issue_and_validate(self):
        token = self.auth.create_token()
        self.assertTrue(self.auth.validate_token(token))
        self.assertFalse(self.auth.validate_token("invalid-fake-token"))

    def test_revoke_token(self):
        token = self.auth.create_token()
        self.assertTrue(self.auth.validate_token(token))
        self.auth.revoke_token(token)
        self.assertFalse(self.auth.validate_token(token))


class TestBrutalWrapper(unittest.TestCase):
    def setUp(self):
        # 强制使用 mock 模式进行测试
        self.wrapper = BrutalWrapper(mock_mode=True)

    def test_validate_ip_cidr(self):
        # 合法 IPv4 输入
        self.assertEqual(validate_ip_cidr("192.168.1.1"), "192.168.1.1/32")
        self.assertEqual(validate_ip_cidr("1.2.3.4/32"), "1.2.3.4/32")
        self.assertEqual(validate_ip_cidr("10.0.0.0/24"), "10.0.0.0/24")

        # 合法 IPv6 输入（默认补齐 /128）
        self.assertEqual(validate_ip_cidr("2001:db8::1"), "2001:db8::1/128")
        self.assertEqual(validate_ip_cidr("::1"), "::1/128")
        self.assertEqual(validate_ip_cidr("2408:8207:7888::1/128"), "2408:8207:7888::1/128")
        self.assertEqual(validate_ip_cidr("2001:db8::/64"), "2001:db8::/64")

        # 恶意注入输入拦截
        with self.assertRaises(ValueError):
            validate_ip_cidr("1.2.3.4; rm -rf /")
        with self.assertRaises(ValueError):
            validate_ip_cidr("2001:db8::1; rm -rf /")
        with self.assertRaises(ValueError):
            validate_ip_cidr("1.2.3.4 && cat /etc/passwd")
        with self.assertRaises(ValueError):
            validate_ip_cidr("abc.def.ghi.jkl")
        with self.assertRaises(ValueError):
            validate_ip_cidr("999.999.999.999")
        with self.assertRaises(ValueError):
            validate_ip_cidr("2001:gggg::1")

        # 添加时拦截 ::ffff: IPv4 映射兼容地址
        with self.assertRaises(ValueError):
            validate_ip_cidr("::ffff:125.81.232.217", for_delete=False)
        with self.assertRaises(ValueError):
            validate_ip_cidr("::ffff:125.81.232.217/128", for_delete=False)

        # 删除时允许识别并处理 ::ffff: 兼容地址
        self.assertEqual(validate_ip_cidr("::ffff:125.81.232.217", for_delete=True), "::ffff:125.81.232.217/128")
        self.assertEqual(validate_ip_cidr("::ffff:125.81.232.217/128", for_delete=True), "::ffff:125.81.232.217/128")

    def test_mock_rules_crud(self):
        # 列出初始规则
        rules = self.wrapper.list_rules()
        self.assertIsInstance(rules, list)

        # 添加 IPv4 规则
        success, msg = self.wrapper.add_rule("1.2.3.4", 150)
        self.assertTrue(success)

        # 添加 IPv6 规则（未带掩码，应默认补齐 /128）
        success, msg = self.wrapper.add_rule("2001:db8::88", 200)
        self.assertTrue(success)

        # 查询应存在
        rules = self.wrapper.list_rules()
        dests = [r["destination"] for r in rules]
        self.assertIn("1.2.3.4/32", dests)
        self.assertIn("2001:db8::88/128", dests)

        # 查找对应项并验证 rate
        target = next(r for r in rules if r["destination"] == "1.2.3.4/32")
        self.assertEqual(target["rate_mbps"], 150.0)
        target_v6 = next(r for r in rules if r["destination"] == "2001:db8::88/128")
        self.assertEqual(target_v6["rate_mbps"], 200.0)

        # 删除规则
        success, msg = self.wrapper.del_rule("1.2.3.4/32")
        self.assertTrue(success)
        success, msg = self.wrapper.del_rule("2001:db8::88/128")
        self.assertTrue(success)

        # 模拟系统原本存在 ::ffff: 遗留规则，测试删除时应允许并成功删除
        self.wrapper._mock_rules.append({
            "destination": "::ffff:125.81.232.217/128",
            "rate_mbps": 100.0,
            "gain": 20, "lock": "yes", "route": "yes", "id": 99, "members": 0, "sent_mb": 0.0
        })
        success, msg = self.wrapper.del_rule("::ffff:125.81.232.217/128")
        self.assertTrue(success)

        # 查询不应存在
        rules = self.wrapper.list_rules()
        dests = [r["destination"] for r in rules]
        self.assertNotIn("1.2.3.4/32", dests)
        self.assertNotIn("2001:db8::88/128", dests)
        self.assertNotIn("::ffff:125.81.232.217/128", dests)


class TestDomainManager(unittest.TestCase):
    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, mode='w', encoding='utf-8')
        self.temp_file.write("# 初始测试\nexample.com\n\ntest.org\n# 注释\n")
        self.temp_file.close()
        self.dm = DomainManager(self.temp_file.name)

    def tearDown(self):
        if os.path.exists(self.temp_file.name):
            os.remove(self.temp_file.name)

    def test_get_raw_and_domains(self):
        raw = self.dm.get_raw_content()
        self.assertIn("example.com", raw)
        self.assertIn("# 初始测试", raw)

        domains = self.dm.get_effective_domains()
        self.assertEqual(domains, ["example.com", "test.org"])

    def test_update_content(self):
        new_content = "google.com\n# 新增\ncloudflare.com"
        success, msg, count = self.dm.save_content(new_content)
        self.assertTrue(success)
        self.assertEqual(count, 2)

        domains = self.dm.get_effective_domains()
        self.assertEqual(domains, ["google.com", "cloudflare.com"])

    def test_custom_rates_parsing(self):
        content = "fast.com 500\nslow.com 50\ndefault.com\n# 注释 999\n"
        self.dm.save_content(content)
        rate_map = self.dm.get_effective_domains_with_rates(default_rate=100.0)
        self.assertEqual(rate_map.get("fast.com"), 500.0)
        self.assertEqual(rate_map.get("slow.com"), 50.0)
        self.assertEqual(rate_map.get("default.com"), 100.0)


class TestIpManager(unittest.TestCase):
    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, mode='w', encoding='utf-8')
        self.temp_file.write("# 静态 IP 清单\n1.2.3.4\n2001:db8::1\n\n# 备用\n10.0.0.0/24\n")
        self.temp_file.close()
        self.im = IpManager(self.temp_file.name)

    def tearDown(self):
        if os.path.exists(self.temp_file.name):
            os.remove(self.temp_file.name)

    def test_get_raw_and_effective_ips(self):
        raw = self.im.get_raw_content()
        self.assertIn("1.2.3.4", raw)
        self.assertIn("2001:db8::1", raw)

        # 有效 IP 自动补齐掩码并标准化
        ips = self.im.get_effective_ips()
        self.assertIn("1.2.3.4/32", ips)
        self.assertIn("2001:db8::1/128", ips)
        self.assertIn("10.0.0.0/24", ips)
        self.assertEqual(len(ips), 3)

    def test_save_content(self):
        new_content = "192.168.1.1\n# 新增\n2408:8207:7888::1\n"
        success, msg, count = self.im.save_content(new_content)
        self.assertTrue(success)
        self.assertEqual(count, 2)

        ips = self.im.get_effective_ips()
        self.assertEqual(ips, ["192.168.1.1/32", "2408:8207:7888::1/128"])

    def test_append_ip(self):
        # 追加单个临时 IPv4 (带自定义速率 250M)
        success, msg = self.im.append_ip("172.16.0.1", rate=250)
        self.assertTrue(success)
        self.assertIn("172.16.0.1/32", self.im.get_effective_ips())
        rates = self.im.get_effective_ips_with_rates()
        self.assertEqual(rates.get("172.16.0.1/32"), 250.0)

        # 追加单个临时 IPv6 (不带速率，默认 100M)
        success, msg = self.im.append_ip("2001:db8:8888::5")
        self.assertTrue(success)
        self.assertIn("2001:db8:8888::5/128", self.im.get_effective_ips())
        rates = self.im.get_effective_ips_with_rates()
        self.assertEqual(rates.get("2001:db8:8888::5/128"), 100.0)

        # 重复追加应提示已存在
        success, msg = self.im.append_ip("172.16.0.1/32")
        self.assertFalse(success)
        self.assertIn("已存在", msg)

    def test_custom_rates_parsing(self):
        content = "1.2.3.4 300\n2001:db8::1 600\n10.0.0.1\n# 注释 999\n"
        self.im.save_content(content)
        rates = self.im.get_effective_ips_with_rates(default_rate=100.0)
        self.assertEqual(rates.get("1.2.3.4/32"), 300.0)
        self.assertEqual(rates.get("2001:db8::1/128"), 600.0)
        self.assertEqual(rates.get("10.0.0.1/32"), 100.0)

    def test_static_source_accurate_recognition(self):
        # 验证静态 IP（如 173.245.48.0 300）在 list_rules 中 100% 识别为 static 来源，绝不误判为 domain
        self.im.save_content("173.245.48.0 300\n")
        wrapper = BrutalWrapper(mock_mode=True)
        # 模拟系统内存在一条 destination 为 173.245.48.0/32 的规则
        wrapper._mock_rules.append({
            "destination": "173.245.48.0/32",
            "rate_mbps": 300.0,
            "gain": 20, "lock": "yes", "route": "yes", "id": 10, "members": 0, "sent_mb": 0.0
        })

        rules = wrapper.list_rules(static_ips=self.im.get_effective_ips())
        target = next(r for r in rules if "173.245.48.0" in r["destination"])
        self.assertEqual(target["source"], "static", "静态 IP 不应被标记为 domain (域名同步)")
        self.assertFalse(target["is_manual"])


class TestSyncRunner(unittest.TestCase):
    def test_lock_and_logs(self):
        runner = SyncRunner(script_path="mock", domain_file="mock", mock_mode=True)
        self.assertFalse(runner.is_running())

        success, msg = runner.trigger_sync()
        self.assertTrue(success)

        # 等待模拟线程执行完毕
        time.sleep(0.5)
        self.assertFalse(runner.is_running())

        logs = runner.get_logs()
        self.assertTrue(len(logs) > 0)
        self.assertIn("同步", "".join(logs))

    def test_static_ips_applied_on_sync(self):
        # 验证同步执行时，静态 IP 清单中的规则能真正下发并生效
        temp_ip_file = tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8")
        temp_ip_file.write("192.168.99.1 250\n2001:db8:ffff::1 400\n")
        temp_ip_file.close()

        wrapper = BrutalWrapper(mock_mode=True)
        im = IpManager(temp_ip_file.name)
        runner = SyncRunner(script_path="mock", domain_file="mock", mock_mode=True, wrapper=wrapper, ip_mgr=im)

        try:
            success, msg = runner.trigger_sync()
            self.assertTrue(success)
            time.sleep(0.6)

            # 验证规则已成功添加并在 list_rules 中生效且速率匹配
            static_ips = set(im.get_effective_ips())
            rules = wrapper.list_rules(static_ips=static_ips)
            rule_map = {r["destination"]: r for r in rules}

            self.assertIn("192.168.99.1/32", rule_map)
            self.assertEqual(rule_map["192.168.99.1/32"]["rate_mbps"], 250.0)
            self.assertEqual(rule_map["192.168.99.1/32"]["source"], "static")

            self.assertIn("2001:db8:ffff::1/128", rule_map)
            self.assertEqual(rule_map["2001:db8:ffff::1/128"]["rate_mbps"], 400.0)
            self.assertEqual(rule_map["2001:db8:ffff::1/128"]["source"], "static")
        finally:
            if os.path.exists(temp_ip_file.name):
                os.remove(temp_ip_file.name)

    def test_startup_initial_delay_sync(self):
        # 测试启动后延迟执行首次同步
        runner = SyncRunner(script_path="mock", domain_file="mock", mock_mode=True)
        runner.start_scheduler(interval_seconds=300, initial_delay=0.1)
        try:
            # 轮询等待首次同步完成
            start_time = time.time()
            finished = False
            while time.time() - start_time < 2.0:
                if runner.get_status()["last_status"] != "未运行" and not runner.is_running():
                    finished = True
                    break
                time.sleep(0.05)
            self.assertTrue(finished, "首次延迟同步未能按期完成")
            logs = "".join(runner.get_logs())
            self.assertIn("首次", logs)
        finally:
            runner.stop_scheduler()


class TestServerStartup(unittest.TestCase):
    def test_server_creation(self):
        from app import BrutalWebApp, ThreadedWSGIServer, SilentWSGIRequestHandler
        from wsgiref.simple_server import make_server
        app = BrutalWebApp()
        # 端口 0 表示操作系统动态分配可用端口
        server = make_server("127.0.0.1", 0, app, server_class=ThreadedWSGIServer, handler_class=SilentWSGIRequestHandler)
        self.assertIsNotNone(server)
        server.server_close()



if __name__ == '__main__':
    unittest.main()
