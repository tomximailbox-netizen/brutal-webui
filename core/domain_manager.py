import os
import socket
import tempfile
from typing import List, Tuple, Dict, Any


class DomainManager:
    """管理 brut_domain.txt 的原子化读取、写入与解析验证"""

    def __init__(self, file_path: str = "./brut_domain.txt"):
        self.file_path = os.path.abspath(file_path)

    def get_raw_content(self) -> str:
        """获取原始文件内容（包含注释与换行）"""
        if not os.path.exists(self.file_path):
            return ""
        try:
            with open(self.file_path, "r", encoding="utf-8-sig") as f:
                return f.read()
        except Exception:
            return ""

    def get_effective_domains(self) -> List[str]:
        """获取有效域名清单（过滤注释与空行，提取首列域名）"""
        raw = self.get_raw_content()
        domains = []
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if parts:
                domains.append(parts[0])
        return domains

    def get_effective_domains_with_rates(self, default_rate: float = 100.0) -> Dict[str, float]:
        """获取有效域名及其自定义限速速率（若未指定则使用 default_rate）"""
        raw = self.get_raw_content()
        rate_map: Dict[str, float] = {}
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if not parts:
                continue
            domain = parts[0]
            rate = default_rate
            if len(parts) >= 2:
                try:
                    parsed_rate = float(parts[1])
                    if parsed_rate > 0:
                        rate = parsed_rate
                except ValueError:
                    pass
            rate_map[domain] = rate
        return rate_map

    def save_content(self, new_content: str) -> Tuple[bool, str, int]:
        """
        保存新的文件内容，采用原子写入方式。
        返回 (成功与否, 提示信息, 有效域名数)
        """
        try:
            dir_name = os.path.dirname(self.file_path) or "."
            os.makedirs(dir_name, exist_ok=True)

            # 统计有效域名数量
            effective_count = 0
            for line in new_content.splitlines():
                clean = line.strip()
                if clean and not clean.startswith("#"):
                    effective_count += 1

            # 写入临时文件后原子替换
            with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, encoding="utf-8") as tf:
                tf.write(new_content)
                temp_name = tf.name

            os.replace(temp_name, self.file_path)
            return True, "域名清单保存成功", effective_count
        except Exception as e:
            return False, f"保存失败: {str(e)}", 0

    @staticmethod
    def test_resolve(domain: str) -> Dict[str, Any]:
        """测试指定域名在当前系统的 IPv4 与 IPv6 解析结果"""
        domain = domain.strip()
        if not domain:
            return {"domain": domain, "success": False, "ips": [], "error": "域名不能为空"}

        try:
            # 同时解析 IPv4 与 IPv6
            addrinfo = socket.getaddrinfo(domain, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
            raw_ips = list(set(item[4][0] for item in addrinfo))
            # 严格过滤掉 IPv4 映射/兼容格式的 ::ffff: 伪 IPv6 地址
            raw_ips = [ip for ip in raw_ips if "::ffff:" not in ip.lower()]
            v4 = sorted([ip for ip in raw_ips if ':' not in ip])
            v6 = sorted([ip for ip in raw_ips if ':' in ip])
            ips = v4 + v6
            return {"domain": domain, "success": True, "ips": ips, "ips_v4": v4, "ips_v6": v6, "error": None}
        except Exception as e:
            return {"domain": domain, "success": False, "ips": [], "error": str(e)}
