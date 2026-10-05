import os
import ssl
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class TestSslSupport(unittest.TestCase):
    def test_ssl_context_loading(self):
        # 验证 Python 内置 ssl 是否支持 TLS_SERVER
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.assertIsNotNone(ctx)


if __name__ == "__main__":
    unittest.main()
