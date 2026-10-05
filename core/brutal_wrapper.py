import ipaddress
import os
import re
import shutil
import subprocess
from typing import List, Dict, Any, Tuple


def validate_ip_cidr(ip_str: str, for_delete: bool = False) -> str:
    """
    严格校验 IP 或 CIDR 格式，杜绝命令注入与非法字符。
    若输入纯 IPv4 则默认补齐 /32；若输入纯 IPv6 则默认补齐 /128。
    增加/添加时严格拦截 ::ffff: 兼容映射地址，删除时允许识别并处理遗留的 ::ffff: 规则。
    """
    if not ip_str or not isinstance(ip_str, str):
        raise ValueError("IP 地址不能为空")

    clean_ip = ip_str.strip()
    # 严格白名单字符集：数字、十六进制字母、冒号、点、斜杠
    if not re.match(r'^[0-9a-fA-F:\./]+$', clean_ip):
        raise ValueError(f"IP 格式包含非法字符: {clean_ip}")

    # 自动补齐默认掩码
    if '/' not in clean_ip:
        if ':' in clean_ip:
            clean_ip = f"{clean_ip}/128"
        else:
            clean_ip = f"{clean_ip}/32"

    # 添加时不增加 ::ffff: 兼容地址；删除时允许通过以便清理遗留规则
    if not for_delete and "::ffff:" in clean_ip.lower():
        raise ValueError(f"不支持添加 IPv4 映射兼容地址 ({clean_ip})，请使用原生 IPv4 或原生 IPv6")

    try:
        network = ipaddress.ip_network(clean_ip, strict=False)
        return clean_ip
    except ValueError as e:
        raise ValueError(f"无效的 IPv4/IPv6 或 CIDR 地址: {clean_ip} ({e})")


class BrutalWrapper:
    """包装系统 brutalctl 命令行工具，支持真实执行与本地 Mock 内存仿真"""

    def __init__(self, brutalctl_bin: str = "brutalctl", mock_mode: bool = False):
        self.brutalctl_bin = brutalctl_bin
        # 判定是否自动启用 mock 模式
        has_bin = shutil.which(self.brutalctl_bin) is not None
        is_posix = os.name == 'posix'
        self.mock_mode = mock_mode or (not is_posix) or (not has_bin)

        # 纯内存维护手动添加的规则（不落盘，重启自动失效）
        self._manual_ips = set()

        # mock 规则存储
        self._mock_rules: List[Dict[str, Any]] = [
            {
                "destination": "123.145.97.17/32",
                "rate_mbps": 100.0,
                "gain": 20,
                "lock": "yes",
                "route": "yes",
                "id": 1,
                "members": 39,
                "sent_mb": 616.5
            },
            {
                "destination": "1.1.1.1/32",
                "rate_mbps": 50.0,
                "gain": 20,
                "lock": "yes",
                "route": "yes",
                "id": 2,
                "members": 12,
                "sent_mb": 102.3
            },
            {
                "destination": "2001:db8::1/128",
                "rate_mbps": 100.0,
                "gain": 20,
                "lock": "yes",
                "route": "yes",
                "id": 3,
                "members": 5,
                "sent_mb": 45.2
            }
        ]

    def is_mock(self) -> bool:
        return self.mock_mode

    def get_manual_ips(self) -> set:
        """获取当前由 WebUI 手动增加且受内存保护的 IP 集合"""
        return set(self._manual_ips)

    def unmark_manual_ip(self, ip_or_cidr: str):
        """将 IP 从临时手动集合中注销（如已被转存入持久化静态清单）"""
        try:
            valid_ip = validate_ip_cidr(ip_or_cidr, for_delete=True)
            self._manual_ips.discard(valid_ip)
        except ValueError:
            pass

    def list_rules(self, static_ips: set = None) -> List[Dict[str, Any]]:
        """列出所有生效的流量控制规则，附带 source 来源标记 (static/manual/domain)"""
        if self.mock_mode:
            rules = [dict(r) for r in self._mock_rules]
        else:
            try:
                res = subprocess.run(
                    [self.brutalctl_bin, "list"],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=10
                )
                rules = self._parse_list_output(res.stdout)
            except Exception:
                rules = []

        static_full = {s.strip() for s in static_ips} if static_ips else set()
        static_raw = {s.strip().split('/')[0] for s in static_ips} if static_ips else set()

        manual_full = {m.strip() for m in self._manual_ips}
        manual_raw = {m.strip().split('/')[0] for m in self._manual_ips}

        # 标记来源：static(持久化清单) > manual(临时手动) > domain(域名同步)
        for r in rules:
            dest = r.get("destination", "").strip()
            dest_raw = dest.split('/')[0] if '/' in dest else dest

            if dest in static_full or dest_raw in static_raw:
                r["source"] = "static"
                r["is_manual"] = False
            elif dest in manual_full or dest_raw in manual_raw:
                r["source"] = "manual"
                r["is_manual"] = True
            else:
                r["source"] = "domain"
                r["is_manual"] = False

        return rules

    def _parse_list_output(self, stdout: str) -> List[Dict[str, Any]]:
        """
        解析 brutalctl list 输出：
        DESTINATION                     RATE(Mbps)  GAIN  LOCK  ROUTE   ID  MEMBERS   SENT(MB)
        123.145.97.17/32                    100.00    20   yes    yes    1       39      616.5
        """
        rules = []
        lines = stdout.strip().splitlines()
        if len(lines) <= 1:
            return rules

        for line in lines[1:]:
            parts = line.split()
            if not parts:
                continue
            try:
                dest = parts[0]
                rate = float(parts[1]) if len(parts) > 1 else 0.0
                gain = int(parts[2]) if len(parts) > 2 else 0
                lock = parts[3] if len(parts) > 3 else "no"
                route = parts[4] if len(parts) > 4 else "no"
                rule_id = int(parts[5]) if len(parts) > 5 else 0
                members = int(parts[6]) if len(parts) > 6 else 0
                sent_mb = float(parts[7]) if len(parts) > 7 else 0.0

                rules.append({
                    "destination": dest,
                    "rate_mbps": rate,
                    "gain": gain,
                    "lock": lock,
                    "route": route,
                    "id": rule_id,
                    "members": members,
                    "sent_mb": sent_mb
                })
            except Exception:
                continue
        return rules

    def add_rule(self, ip_or_cidr: str, rate_mbps: float = 100.0, is_manual: bool = True) -> Tuple[bool, str]:
        """添加规则：brutalctl add IP/32 <rate> 或 IP/128 <rate>"""
        try:
            valid_ip = validate_ip_cidr(ip_or_cidr, for_delete=False)
            rate = float(rate_mbps)
            if rate <= 0:
                return False, "速率必须大于 0 Mbps"
        except ValueError as e:
            return False, str(e)

        if is_manual:
            self._manual_ips.add(valid_ip)

        if self.mock_mode:
            # 查重
            for r in self._mock_rules:
                if r["destination"] == valid_ip:
                    r["rate_mbps"] = rate
                    return True, f"Mock: 规则已更新 {valid_ip} -> {rate} Mbps"
            new_id = max([r.get("id", 0) for r in self._mock_rules] or [0]) + 1
            self._mock_rules.append({
                "destination": valid_ip,
                "rate_mbps": rate,
                "gain": 20,
                "lock": "yes",
                "route": "yes",
                "id": new_id,
                "members": 0,
                "sent_mb": 0.0
            })
            return True, f"Mock: 规则已添加 {valid_ip} {rate} Mbps"

        try:
            res = subprocess.run(
                [self.brutalctl_bin, "add", valid_ip, str(int(rate))],
                capture_output=True,
                text=True,
                timeout=10
            )
            if res.returncode == 0:
                return True, f"规则添加成功: {valid_ip} {rate} Mbps"
            else:
                return False, f"添加失败: {res.stderr.strip() or res.stdout.strip()}"
        except Exception as e:
            return False, f"执行异常: {str(e)}"

    def del_rule(self, ip_or_cidr: str) -> Tuple[bool, str]:
        """删除规则：brutalctl del IP/32 或 IP/128 (允许删除包括 ::ffff: 在内的遗留规则)"""
        try:
            valid_ip = validate_ip_cidr(ip_or_cidr, for_delete=True)
        except ValueError as e:
            return False, str(e)

        # 同步从手动白名单中剔除
        self._manual_ips.discard(valid_ip)

        if self.mock_mode:
            initial_len = len(self._mock_rules)
            # 支持对原始字符串或补全后 destination 的匹配删除
            self._mock_rules = [
                r for r in self._mock_rules
                if r["destination"] != valid_ip and r["destination"] != ip_or_cidr.strip()
            ]
            if len(self._mock_rules) < initial_len:
                return True, f"Mock: 规则已删除 {valid_ip}"
            else:
                return True, f"Mock: 规则不存在或已移除 {valid_ip}"

        try:
            res = subprocess.run(
                [self.brutalctl_bin, "del", valid_ip],
                capture_output=True,
                text=True,
                timeout=10
            )
            if res.returncode == 0:
                return True, f"规则删除成功: {valid_ip}"
            else:
                return False, f"删除失败: {res.stderr.strip() or res.stdout.strip()}"
        except Exception as e:
            return False, f"执行异常: {str(e)}"
