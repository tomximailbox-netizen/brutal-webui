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


if __name__ == "__main__":
    unittest.main()
