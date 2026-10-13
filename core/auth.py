import hmac
import ipaddress
import secrets
import threading
import time
from typing import Dict, List, Tuple


class AuthManager:
    """管理管理员密码校验、会话 Token 签发与过期验证，以及防暴力破解安全管控"""

    def __init__(
        self,
        admin_password: str,
        token_expire_hours: int = 24,
        max_failed_attempts: int = 5,
        lockout_duration_seconds: int = 900,
        failure_delay_seconds: float = 1.5
    ):
        self.admin_password = admin_password
        self.token_expire_seconds = token_expire_hours * 3600
        # 内存中维护 active tokens: { token: expire_timestamp }
        self._tokens: Dict[str, float] = {}

        # 防暴力破解控制参数
        self.max_failed_attempts = max_failed_attempts
        self.lockout_duration_seconds = lockout_duration_seconds
        self.failure_delay_seconds = failure_delay_seconds

        # 失败计数与锁定状态（线程安全）
        self._lock = threading.Lock()
        self._failed_attempts: Dict[str, List[float]] = {}
        self._lockouts: Dict[str, float] = {}

    def update_password(self, new_password: str):
        self.admin_password = new_password

    @staticmethod
    def get_client_lock_key(ip: str) -> str:
        """
        根据客户端 IP 获取限流与锁定的安全聚合键:
        - IPv4: 按单 IP 精准锁定 (/32)
        - IPv6: 自动聚合为其前 64 位子网 (/64)，防止攻击者通过 SLAAC 隐私地址或多 IP 轮换逃避频次封禁
        """
        if not ip:
            return ""
        clean = ip.strip()
        try:
            addr = ipaddress.ip_address(clean)
            if addr.version == 6:
                network = ipaddress.IPv6Network(f"{clean}/64", strict=False)
                return str(network)
            return str(addr)
        except ValueError:
            return clean

    def is_ip_locked(self, ip: str) -> Tuple[bool, int]:
        """检查指定 IP 是否正处于冻结锁定期，返回 (是否锁定, 剩余锁定秒数)"""
        if not ip:
            return False, 0

        key = self.get_client_lock_key(ip)
        now = time.time()
        with self._lock:
            unlock_time = self._lockouts.get(key)
            if unlock_time:
                if now < unlock_time:
                    remaining = int(unlock_time - now) + 1
                    return True, remaining
                else:
                    # 锁定期已过，自动解除
                    del self._lockouts[key]
                    if key in self._failed_attempts:
                        del self._failed_attempts[key]
            return False, 0

    def record_login_failure(self, ip: str) -> Tuple[int, bool]:
        """记录一次登录失败，执行防爆破延迟惩罚，达到阈值时触发临时封禁"""
        is_locked = False
        count = 1

        if ip:
            key = self.get_client_lock_key(ip)
            now = time.time()
            with self._lock:
                # 保留最近锁定周期内的失败记录
                records = self._failed_attempts.get(key, [])
                cutoff = now - max(self.lockout_duration_seconds, 600)
                records = [t for t in records if t >= cutoff]
                records.append(now)
                self._failed_attempts[key] = records
                count = len(records)

                if count >= self.max_failed_attempts:
                    self._lockouts[key] = now + self.lockout_duration_seconds
                    is_locked = True

        # 渐进式延迟惩罚：输错密码强制休眠，大幅拖慢暴力破解工具的字典穷举效率
        if self.failure_delay_seconds > 0:
            time.sleep(self.failure_delay_seconds)

        return count, is_locked

    def record_login_success(self, ip: str):
        """登录成功时立即清零该 IP（或对应 IPv6 /64 子网）的错误记录与锁定状态"""
        if not ip:
            return
        key = self.get_client_lock_key(ip)
        with self._lock:
            if key in self._failed_attempts:
                del self._failed_attempts[key]
            if key in self._lockouts:
                del self._lockouts[key]

    def verify_password(self, input_password: str) -> bool:
        if not input_password or not self.admin_password:
            return False
        return hmac.compare_digest(input_password.encode('utf-8'), self.admin_password.encode('utf-8'))

    def create_token(self) -> str:
        token = secrets.token_hex(32)
        expire_time = time.time() + self.token_expire_seconds
        self._tokens[token] = expire_time
        self._cleanup_expired()
        return token

    def validate_token(self, token: str) -> bool:
        if not token:
            return False
        self._cleanup_expired()
        expire_time = self._tokens.get(token)
        if not expire_time:
            return False
        return time.time() < expire_time

    def revoke_token(self, token: str):
        if token in self._tokens:
            del self._tokens[token]

    def _cleanup_expired(self):
        now = time.time()
        expired = [t for t, exp in self._tokens.items() if now >= exp]
        for t in expired:
            del self._tokens[t]
