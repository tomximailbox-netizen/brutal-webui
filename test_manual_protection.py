import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.brutal_wrapper import BrutalWrapper
from core.sync_runner import SyncRunner


class TestManualIpProtection(unittest.TestCase):
    def setUp(self):
        self.wrapper = BrutalWrapper(mock_mode=True)
        self.temp_domain_file = tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8")
        self.temp_domain_file.write("example.com\n")
        self.temp_domain_file.close()

    def tearDown(self):
        if os.path.exists(self.temp_domain_file.name):
            os.remove(self.temp_domain_file.name)

    def test_manual_ip_kept_in_memory_and_protected_during_sync(self):
        # 1. 用户手动添加一个 IPv4 IP 和一个 IPv6 IP
        manual_ip_v4 = "198.51.100.77"
        manual_ip_v6 = "2001:db8:9999::1"
        success, msg = self.wrapper.add_rule(manual_ip_v4, 120, is_manual=True)
        self.assertTrue(success)
        success, msg = self.wrapper.add_rule(manual_ip_v6, 200, is_manual=True)
        self.assertTrue(success)

        self.assertIn("198.51.100.77/32", self.wrapper.get_manual_ips())
        self.assertIn("2001:db8:9999::1/128", self.wrapper.get_manual_ips())

        # 2. 模拟同步：域名解析得到的 IP 不包含这两个 manual_ip
        # 验证同步器执行时，保护这两个 manual_ip 不被删除
        runner = SyncRunner(
            script_path="mock",
            domain_file=self.temp_domain_file.name,
            mock_mode=True,
            wrapper=self.wrapper
        )
        success, msg = runner.trigger_sync()
        self.assertTrue(success)

        import time
        time.sleep(0.5)

        # 验证两个 manual_ip 依然完好存在于规则中
        rules = self.wrapper.list_rules()
        dests = [r["destination"] for r in rules]
        self.assertIn("198.51.100.77/32", dests)
        self.assertIn("2001:db8:9999::1/128", dests)

    def test_reboot_clears_manual_ips(self):
        # 内存添加 IPv4 和 IPv6
        self.wrapper.add_rule("198.51.100.88", 100, is_manual=True)
        self.wrapper.add_rule("2001:db8::77", 100, is_manual=True)
        self.assertIn("198.51.100.88/32", self.wrapper.get_manual_ips())
        self.assertIn("2001:db8::77/128", self.wrapper.get_manual_ips())

        # 重新创建 wrapper 实例（模拟重启，无持久化磁盘文件）
        new_wrapper = BrutalWrapper(mock_mode=True)
        self.assertEqual(len(new_wrapper.get_manual_ips()), 0)


if __name__ == "__main__":
    unittest.main()
