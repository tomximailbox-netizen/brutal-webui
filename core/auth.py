import hmac
import secrets
import time
from typing import Dict


class AuthManager:
    """管理管理员密码校验与会话 Token 签发与过期验证"""

    def __init__(self, admin_password: str, token_expire_hours: int = 24):
        self.admin_password = admin_password
        self.token_expire_seconds = token_expire_hours * 3600
        # 内存中维护 active tokens: { token: expire_timestamp }
        self._tokens: Dict[str, float] = {}

    def update_password(self, new_password: str):
        self.admin_password = new_password

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
