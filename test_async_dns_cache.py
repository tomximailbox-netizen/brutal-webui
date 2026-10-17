import os
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.domain_manager import DomainManager


class TestAsyncDnsCache(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.domain_file = os.path.join(self.temp_dir.name, "brut_domain.txt")
        with open(self.domain_file, "w", encoding="utf-8") as f:
            f.write("node1.example.com\nnode2.example.org\n")
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

    def test_non_blocking_returns_immediately(self):
        # 模拟 resolve_ips 需要很长的耗时 (例如 2 秒网络延迟)
        def slow_resolve(domain):
            time.sleep(0.5)
            if "node1" in domain:
                return (["1.2.3.4"], [])
            return (["5.6.7.8"], [])

        self.domain_mgr.dns_resolver.resolve_ips = slow_resolve

        # 首次无缓存调用，blocking=False 必须瞬间返回 (耗时必须远小于 0.2 秒)
        start = time.time()
        res = self.domain_mgr.get_cached_ip_to_domain_map(blocking=False)
        duration = time.time() - start

        self.assertLess(duration, 0.2, "get_cached_ip_to_domain_map 未能做到非阻塞瞬间返回！")
        self.assertIsInstance(res, dict)

        # 等待后台刷新线程完成
        time.sleep(1.2)
        # 再次获取，此时后台解析已完成，缓存已注入
        cached_res = self.domain_mgr.get_cached_ip_to_domain_map(blocking=False)
        self.assertIn("1.2.3.4", cached_res)
        self.assertEqual(cached_res["1.2.3.4"], "node1.example.com")
        self.assertEqual(cached_res["5.6.7.8"], "node2.example.org")


if __name__ == "__main__":
    unittest.main()
