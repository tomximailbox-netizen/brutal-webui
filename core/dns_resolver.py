import random
import socket
import struct
from typing import List, Tuple, Optional


def encode_dns_query(domain: str, qtype: int) -> Tuple[bytes, int]:
    """
    编码标准 DNS 查询数据包 (RFC 1035)
    qtype: 1 为 A 记录 (IPv4), 28 为 AAAA 记录 (IPv6)
    """
    qid = random.randint(1, 65535)
    # Header: ID, Flags=0x0100 (RD=1 期望递归), QDCOUNT=1, ANCOUNT=0, NSCOUNT=0, ARCOUNT=0
    header = struct.pack("!HHHHHH", qid, 0x0100, 1, 0, 0, 0)

    # Question section: QNAME 格式 (\x03www\x06google\x03com\x00)
    qname_parts = []
    clean_domain = domain.strip().rstrip(".")
    for part in clean_domain.split("."):
        encoded_part = part.encode("idna")
        qname_parts.append(bytes([len(encoded_part)]) + encoded_part)
    qname = b"".join(qname_parts) + b"\x00"

    # QTYPE and QCLASS (1=IN Internet)
    question = qname + struct.pack("!HH", qtype, 1)
    return header + question, qid


def _skip_dns_name(data: bytes, offset: int) -> int:
    """跳过 DNS 报文中的域名（支持指针 0xc0..）"""
    length = len(data)
    while offset < length:
        b = data[offset]
        if b == 0:
            return offset + 1
        elif (b & 0xC0) == 0xC0:
            return offset + 2
        else:
            offset += 1 + b
    return offset


def parse_dns_response(data: bytes, expected_id: int, expected_type: int) -> List[str]:
    """
    解析 DNS 响应数据包，提取指定类型 (A 或 AAAA) 的 IP 地址列表。
    """
    if len(data) < 12:
        return []

    qid, flags, qdcount, ancount, _, _ = struct.unpack("!HHHHHH", data[:12])
    if qid != expected_id:
        return []

    # 检查 RCODE 错误码 (flags & 0x000F)
    rcode = flags & 0x000F
    if rcode != 0:
        return []

    offset = 12

    # 跳过 Question 区域
    for _ in range(qdcount):
        offset = _skip_dns_name(data, offset)
        offset += 4  # 跳过 QTYPE (2) + QCLASS (2)

    ips: List[str] = []

    # 解析 Answer 区域
    for _ in range(ancount):
        if offset >= len(data):
            break
        offset = _skip_dns_name(data, offset)
        if offset + 10 > len(data):
            break

        rtype, rclass, ttl, rdlength = struct.unpack("!HHIH", data[offset : offset + 10])
        offset += 10

        if offset + rdlength > len(data):
            break

        rdata = data[offset : offset + rdlength]
        offset += rdlength

        # A 记录 (IPv4, type=1, length=4)
        if rtype == 1 and expected_type == 1 and rdlength == 4:
            try:
                ip_str = socket.inet_ntoa(rdata)
                if ip_str not in ips:
                    ips.append(ip_str)
            except Exception:
                pass
        # AAAA 记录 (IPv6, type=28, length=16)
        elif rtype == 28 and expected_type == 28 and rdlength == 16:
            try:
                ip_str = socket.inet_ntop(socket.AF_INET6, rdata)
                if "::ffff:" not in ip_str.lower() and ip_str not in ips:
                    ips.append(ip_str)
            except Exception:
                pass

    return ips


def query_dns_server(domain: str, server: str, qtype: int, timeout: float = 2.0) -> List[str]:
    """向指定的 DNS 服务器发送 UDP 查询请求并解析响应"""
    server_clean = server.strip()
    if not server_clean:
        return []

    packet, qid = encode_dns_query(domain, qtype)
    is_ipv6 = ":" in server_clean
    family = socket.AF_INET6 if is_ipv6 else socket.AF_INET

    with socket.socket(family, socket.SOCK_DGRAM) as sock:
        sock.settimeout(max(0.5, timeout))
        target_addr = (server_clean, 53)
        sock.sendto(packet, target_addr)
        response, _ = sock.recvfrom(4096)
        return parse_dns_response(response, qid, qtype)


class SimpleDnsResolver:
    """具备多服务器轮询与原生系统兜底回退机制的轻量级 DNS 解析器"""

    def __init__(self, servers: Optional[List[str]] = None, timeout: float = 2.0):
        # 默认使用 Google IPv4 DNS
        if not servers:
            self.servers = ["8.8.8.8", "8.8.4.4"]
        else:
            self.servers = [s.strip() for s in servers if s and s.strip()]
            if not self.servers:
                self.servers = ["8.8.8.8", "8.8.4.4"]
        self.timeout = float(timeout)

    def set_servers(self, servers: List[str]):
        if servers:
            cleaned = [s.strip() for s in servers if s and s.strip()]
            if cleaned:
                self.servers = cleaned

    def set_timeout(self, timeout: float):
        self.timeout = max(0.5, float(timeout))

    def _query_external(self, domain: str, qtype: int) -> List[str]:
        """按配置的 DNS 服务器顺序尝试查询"""
        for server in self.servers:
            try:
                ips = query_dns_server(domain, server, qtype, timeout=self.timeout)
                if ips:
                    return ips
            except Exception:
                continue
        return []

    def _fallback_getaddrinfo(self, domain: str) -> Tuple[List[str], List[str]]:
        """系统原生 getaddrinfo 兜底解析机制"""
        v4_ips: List[str] = []
        v6_ips: List[str] = []
        try:
            addrinfo = socket.getaddrinfo(domain, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
            for item in addrinfo:
                ip = item[4][0].strip()
                if "::ffff:" in ip.lower():
                    continue
                if ":" in ip:
                    if ip not in v6_ips:
                        v6_ips.append(ip)
                else:
                    if ip not in v4_ips:
                        v4_ips.append(ip)
        except Exception:
            pass
        return sorted(v4_ips), sorted(v6_ips)

    def resolve_ips(self, domain: str) -> Tuple[List[str], List[str]]:
        """
        解析域名的 IPv4 与原生 IPv6 列表。
        优先使用指定的外部 DNS（如 8.8.8.8 / 8.8.4.4）。
        若全部外部 DNS 超时或无响应，自动无缝回退到系统本地解析器。
        返回: (v4_list, v6_list)
        """
        clean_domain = domain.strip()
        if not clean_domain:
            return [], []

        v4_ips: List[str] = []
        v6_ips: List[str] = []

        try:
            # 1. 尝试外部 DNS 查询 A 记录 (type=1)
            v4_ips = self._query_external(clean_domain, 1)
        except Exception:
            v4_ips = []

        try:
            # 2. 尝试外部 DNS 查询 AAAA 记录 (type=28)
            v6_ips = self._query_external(clean_domain, 28)
        except Exception:
            v6_ips = []

        # 3. 若外部 DNS 未能解析到任何记录，使用系统原生 getaddrinfo 兜底
        if not v4_ips and not v6_ips:
            v4_ips, v6_ips = self._fallback_getaddrinfo(clean_domain)

        return sorted(list(set(v4_ips))), sorted(list(set(v6_ips)))


# 全局单例解析器（默认 Google DNS）
default_resolver = SimpleDnsResolver()


def resolve_domain_ips(
    domain: str, servers: Optional[List[str]] = None, timeout: float = 2.0
) -> Tuple[List[str], List[str]]:
    """便捷函数：解析域名 IP"""
    if servers:
        res = SimpleDnsResolver(servers=servers, timeout=timeout)
        return res.resolve_ips(domain)
    return default_resolver.resolve_ips(domain)
