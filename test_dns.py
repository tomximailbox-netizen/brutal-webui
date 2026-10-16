import unittest
import socket
import struct
from unittest.mock import patch, MagicMock
from core.dns_resolver import (
    encode_dns_query,
    parse_dns_response,
    query_dns_server,
    resolve_domain_ips,
    SimpleDnsResolver,
)


class TestDnsResolver(unittest.TestCase):
    """测试纯 Python 标准库实现的轻量级 DNS 查询器"""

    def test_encode_dns_query(self):
        # 编码 example.com A 记录 (qtype=1)
        pkt, qid = encode_dns_query("example.com", 1)
        self.assertEqual(len(pkt), 12 + len(b"\x07example\x03com\x00") + 4)
        # Header ID
        parsed_id = struct.unpack("!H", pkt[:2])[0]
        self.assertEqual(parsed_id, qid)
        # Flags = 0x0100 (RD=1)
        flags = struct.unpack("!H", pkt[2:4])[0]
        self.assertEqual(flags, 0x0100)
        # QDCOUNT = 1
        self.assertEqual(struct.unpack("!H", pkt[4:6])[0], 1)

    def test_parse_dns_response_a_record(self):
        # 构造一个模拟的 A 记录 DNS 响应包: 93.184.216.34
        qid = 0x1234
        # Header: ID, Flags=0x8180 (Response, NoError), QD=1, AN=1, NS=0, AR=0
        header = struct.pack("!HHHHHH", qid, 0x8180, 1, 1, 0, 0)
        # Question: \x07example\x03com\x00, Type=1, Class=1
        question = b"\x07example\x03com\x00" + struct.pack("!HH", 1, 1)
        # Answer: Pointer to question name (0xc00c), Type=1, Class=1, TTL=300, RDLENGTH=4, RDATA=93.184.216.34
        ip_bytes = socket.inet_aton("93.184.216.34")
        answer = struct.pack("!HHHIH", 0xC00C, 1, 1, 300, 4) + ip_bytes
        response = header + question + answer

        ips = parse_dns_response(response, qid, 1)
        self.assertEqual(ips, ["93.184.216.34"])

    def test_parse_dns_response_aaaa_record(self):
        # 构造模拟的 AAAA 记录 DNS 响应包: 2606:2800:220:1:248:1893:25c8:1946
        qid = 0xABCD
        header = struct.pack("!HHHHHH", qid, 0x8180, 1, 1, 0, 0)
        question = b"\x07example\x03com\x00" + struct.pack("!HH", 28, 1)
        ipv6_str = "2606:2800:220:1:248:1893:25c8:1946"
        ip_bytes = socket.inet_pton(socket.AF_INET6, ipv6_str)
        answer = struct.pack("!HHHIH", 0xC00C, 28, 1, 300, 16) + ip_bytes
        response = header + question + answer

        ips = parse_dns_response(response, qid, 28)
        self.assertEqual(ips, [ipv6_str])

    def test_parse_dns_response_cname_and_a(self):
        # 构造包含 CNAME 和最终 A 记录的组合响应包
        qid = 0x5678
        header = struct.pack("!HHHHHH", qid, 0x8180, 1, 2, 0, 0)
        question = b"\x03foo\x07example\x03com\x00" + struct.pack("!HH", 1, 1)
        # Answer 1: CNAME -> \x03bar\x07example\x03com\x00
        cname_data = b"\x03bar\xc0\x10"  # bar.example.com
        ans1 = struct.pack("!HHHIH", 0xC00C, 5, 1, 300, len(cname_data)) + cname_data
        # Answer 2: A 记录 -> 1.2.3.4
        ans2 = struct.pack("!HHHIH", 0xC00C, 1, 1, 300, 4) + socket.inet_aton("1.2.3.4")
        response = header + question + ans1 + ans2

        ips = parse_dns_response(response, qid, 1)
        self.assertEqual(ips, ["1.2.3.4"])

    @patch("core.dns_resolver.socket.socket")
    def test_query_dns_server_success(self, mock_socket_cls):
        mock_sock = MagicMock()
        mock_socket_cls.return_value.__enter__.return_value = mock_sock

        # 准备返回数据
        qid = 0x1111
        header = struct.pack("!HHHHHH", qid, 0x8180, 1, 1, 0, 0)
        question = b"\x03foo\x03com\x00" + struct.pack("!HH", 1, 1)
        answer = struct.pack("!HHHIH", 0xC00C, 1, 1, 300, 4) + socket.inet_aton("8.8.8.8")
        mock_sock.recvfrom.return_value = (header + question + answer, ("8.8.8.8", 53))

        with patch("core.dns_resolver.random.randint", return_value=qid):
            ips = query_dns_server("foo.com", "8.8.8.8", 1, timeout=1.0)
            self.assertEqual(ips, ["8.8.8.8"])

    @patch("core.dns_resolver.query_dns_server")
    @patch("socket.getaddrinfo")
    def test_fallback_to_system_on_failure(self, mock_getaddrinfo, mock_query):
        # 模拟外部 DNS 查询全部超时/异常
        mock_query.side_effect = Exception("DNS network timeout")
        # 模拟系统 getaddrinfo 成功
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("1.1.1.1", 0)),
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2606:4700::1111", 0)),
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("::ffff:1.1.1.1", 0)),  # 兼容地址应被过滤
        ]

        resolver = SimpleDnsResolver(servers=["8.8.8.8", "8.8.4.4"])
        v4, v6 = resolver.resolve_ips("cloudflare.com")
        self.assertEqual(v4, ["1.1.1.1"])
        self.assertEqual(v6, ["2606:4700::1111"])

    @patch("core.dns_resolver.SimpleDnsResolver.resolve_ips")
    def test_domain_manager_test_resolve_returns_dns_info(self, mock_resolve):
        from core.domain_manager import DomainManager
        mock_resolve.return_value = (["93.184.216.34"], ["2606:2800:220:1:248:1893:25c8:1946"])
        res = DomainManager.test_resolve("example.com", dns_servers=["8.8.8.8", "8.8.4.4"])
        self.assertTrue(res["success"])
        self.assertEqual(res["ips_v4"], ["93.184.216.34"])
        self.assertEqual(res["dns_servers"], "8.8.8.8, 8.8.4.4")

    def test_app_dns_config_roundtrip(self):
        import tempfile
        import json
        import os
        from app import BrutalWebApp
        from io import BytesIO

        with tempfile.TemporaryDirectory() as td:
            conf_path = os.path.join(td, "config.json")
            with open(conf_path, "w", encoding="utf-8") as f:
                json.dump({
                    "auth": {"admin_password": "testpassword"},
                    "dns": {"servers": ["8.8.8.8", "8.8.4.4"], "timeout_seconds": 2.5}
                }, f)
            app = BrutalWebApp(config_path=conf_path)
            self.assertEqual(app.domain_mgr.dns_resolver.servers, ["8.8.8.8", "8.8.4.4"])

            # 模拟 PUT /api/config 更新 DNS 配置
            update_body = json.dumps({"dns": {"servers": "1.1.1.1, 8.8.8.8", "timeout_seconds": 3.0}}).encode("utf-8")
            environ = {
                "REQUEST_METHOD": "PUT",
                "PATH_INFO": "/api/config",
                "CONTENT_LENGTH": str(len(update_body)),
                "wsgi.input": BytesIO(update_body),
            }
            start_resp = MagicMock()
            app.api_update_config(environ, start_resp)

            # 验证内存与持久化更新
            self.assertEqual(app.config["dns"]["servers"], ["1.1.1.1", "8.8.8.8"])
            self.assertEqual(app.domain_mgr.dns_resolver.servers, ["1.1.1.1", "8.8.8.8"])
            self.assertEqual(app.sync_runner.dns_servers, ["1.1.1.1", "8.8.8.8"])


if __name__ == "__main__":
    unittest.main()
