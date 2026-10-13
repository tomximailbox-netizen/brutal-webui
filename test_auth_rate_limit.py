import unittest
import time
from core.auth import AuthManager


class TestAuthRateLimit(unittest.TestCase):
    def setUp(self):
        # 使用较短的时间参数便于测试
        self.auth = AuthManager(
            admin_password="test_password_123",
            token_expire_hours=1,
            max_failed_attempts=3,
            lockout_duration_seconds=2,
            failure_delay_seconds=0.1
        )
        self.test_ip = "192.168.1.100"

    def test_initial_state_not_locked(self):
        is_locked, remaining = self.auth.is_ip_locked(self.test_ip)
        self.assertFalse(is_locked)
        self.assertEqual(remaining, 0)

    def test_record_failure_and_delay(self):
        start = time.time()
        self.auth.record_login_failure(self.test_ip)
        elapsed = time.time() - start
        self.assertGreaterEqual(elapsed, 0.08)  # 验证确实发生了延迟惩罚

        is_locked, _ = self.auth.is_ip_locked(self.test_ip)
        self.assertFalse(is_locked)

    def test_trigger_lockout_after_max_attempts(self):
        # 连续失败 3 次
        for _ in range(2):
            self.auth.record_login_failure(self.test_ip)
            is_locked, _ = self.auth.is_ip_locked(self.test_ip)
            self.assertFalse(is_locked)

        # 第 3 次失败触发锁定
        self.auth.record_login_failure(self.test_ip)
        is_locked, remaining = self.auth.is_ip_locked(self.test_ip)
        self.assertTrue(is_locked)
        self.assertGreater(remaining, 0)
        self.assertLessEqual(remaining, 2)

    def test_lockout_auto_expires(self):
        # 触发锁定 (锁定 2 秒)
        for _ in range(3):
            self.auth.record_login_failure(self.test_ip)

        self.assertTrue(self.auth.is_ip_locked(self.test_ip)[0])

        # 等待锁定期结束
        time.sleep(2.1)
        is_locked, remaining = self.auth.is_ip_locked(self.test_ip)
        self.assertFalse(is_locked)
        self.assertEqual(remaining, 0)

    def test_success_clears_failures(self):
        # 失败 2 次（未达阈值 3 次）
        self.auth.record_login_failure(self.test_ip)
        self.auth.record_login_failure(self.test_ip)

        # 登录成功
        self.auth.record_login_success(self.test_ip)

        # 再次失败 1 次不会被锁
        self.auth.record_login_failure(self.test_ip)
        is_locked, _ = self.auth.is_ip_locked(self.test_ip)
        self.assertFalse(is_locked)

    def test_ipv6_64_subnet_lockout(self):
        # 验证 IPv6 地址自动按 /64 子网聚合并锁定
        ipv6_addr1 = "2001:db8:abcd:1234::1"
        ipv6_addr2 = "2001:db8:abcd:1234::2"
        ipv6_addr3 = "2001:db8:abcd:1234::dead:beef"
        ipv6_diff_subnet = "2001:db8:abcd:5678::1"

        # 同一个 /64 子网内变换不同后缀尝试登录
        self.auth.record_login_failure(ipv6_addr1)
        self.auth.record_login_failure(ipv6_addr2)
        is_locked, _ = self.auth.is_ip_locked(ipv6_addr3)
        self.assertFalse(is_locked)

        # 第 3 次失败触发锁定
        self.auth.record_login_failure(ipv6_addr3)

        # 验证同一 /64 子网下的任意全新未出现过的后缀地址一并处于锁定状态
        ipv6_new_suffix = "2001:db8:abcd:1234::8888"
        is_locked, remaining = self.auth.is_ip_locked(ipv6_new_suffix)
        self.assertTrue(is_locked)
        self.assertGreater(remaining, 0)

        # 验证其它 /64 子网完全不受牵连
        is_locked_diff, _ = self.auth.is_ip_locked(ipv6_diff_subnet)
        self.assertFalse(is_locked_diff)

        # 验证该网段下任意 IP 登录成功后解除整个 /64 的锁定
        self.auth.record_login_success("2001:db8:abcd:1234::cafe")
        is_locked_after, _ = self.auth.is_ip_locked(ipv6_new_suffix)
        self.assertFalse(is_locked_after)


if __name__ == "__main__":
    unittest.main()
