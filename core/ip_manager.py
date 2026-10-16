import os
import tempfile
from typing import List, Tuple, Dict, Any

from core.brutal_wrapper import validate_ip_cidr


class IpManager:
    """管理 brut_ip.txt 的原子化读取、写入与单条/批量固化追加"""

    def __init__(self, file_path: str = "./brut_ip.txt"):
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

    def get_effective_ips(self) -> List[str]:
        """获取有效静态 IP 清单（自动规范化补齐 /32 或 /128 掩码）"""
        raw = self.get_raw_content()
        ips = []
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if not parts:
                continue
            try:
                valid = validate_ip_cidr(parts[0], for_delete=False)
                if valid not in ips:
                    ips.append(valid)
            except ValueError:
                continue
        return ips

    def get_effective_ips_with_rates(self, default_rate: float = 100.0) -> Dict[str, float]:
        """获取有效静态 IP 及其自定义限速速率（若未指定则使用 default_rate）"""
        raw = self.get_raw_content()
        rate_map: Dict[str, float] = {}
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if not parts:
                continue
            try:
                valid = validate_ip_cidr(parts[0], for_delete=False)
            except ValueError:
                continue

            rate = default_rate
            if len(parts) >= 2:
                try:
                    parsed_rate = float(parts[1])
                    if parsed_rate > 0:
                        rate = parsed_rate
                except ValueError:
                    pass
            rate_map[valid] = rate
        return rate_map

    def save_content(self, new_content: str) -> Tuple[bool, str, int]:
        """保存新的文件内容，采用原子写入方式"""
        try:
            dir_name = os.path.dirname(self.file_path) or "."
            os.makedirs(dir_name, exist_ok=True)

            # 统计有效 IP 数量
            effective_count = 0
            for line in new_content.splitlines():
                clean = line.strip()
                if clean and not clean.startswith("#"):
                    parts = clean.split()
                    if parts:
                        try:
                            validate_ip_cidr(parts[0], for_delete=False)
                            effective_count += 1
                        except ValueError:
                            pass

            with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, encoding="utf-8") as tf:
                tf.write(new_content)
                temp_name = tf.name

            os.replace(temp_name, self.file_path)
            return True, "IP 清单保存成功", effective_count
        except Exception as e:
            return False, f"保存失败: {str(e)}", 0

    def append_ip(self, ip_or_cidr: str, rate: float = None) -> Tuple[bool, str]:
        """将临时 IP 单条固化追加写入 brut_ip.txt 文件中，支持持久化自定义速率"""
        try:
            valid_ip = validate_ip_cidr(ip_or_cidr, for_delete=False)
        except ValueError as e:
            return False, str(e)

        current_ips = self.get_effective_ips()
        if valid_ip in current_ips:
            return False, f"IP 规则 [{valid_ip}] 已存在于静态清单中"

        raw = self.get_raw_content()
        if raw and not raw.endswith("\n"):
            raw += "\n"

        if rate is not None and float(rate) > 0:
            rate_str = str(int(rate)) if float(rate).is_integer() else str(rate)
            line_to_add = f"{valid_ip} {rate_str}\n"
        else:
            line_to_add = f"{valid_ip}\n"

        new_raw = raw + line_to_add
        success, msg, _ = self.save_content(new_raw)
        if success:
            return True, f"规则 [{valid_ip}] 已成功存入静态 IP 清单"
        return False, msg

    def set_ip_rate(self, ip_or_cidr: str, rate: float) -> Tuple[bool, str]:
        """
        修改已存在于 brut_ip.txt 中的静态 IP/CIDR 速率，并原子化持久化保存。
        完整保留原有行内注释，规范化匹配目标 IP。
        """
        try:
            valid_target = validate_ip_cidr(ip_or_cidr, for_delete=False)
            parsed_rate = float(rate)
            if parsed_rate <= 0:
                return False, "速率必须大于 0 Mbps"
        except ValueError as e:
            return False, str(e)
        except (TypeError, Exception):
            return False, "无效的速率数值"

        rate_str = str(int(parsed_rate)) if parsed_rate.is_integer() else str(parsed_rate)

        raw = self.get_raw_content()
        lines = raw.splitlines()
        found = False
        new_lines = []

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                new_lines.append(line)
                continue

            code_part, *comment_parts = line.split("#", 1)
            comment_part = comment_parts[0] if comment_parts else None

            tokens = code_part.strip().split()
            if not tokens:
                new_lines.append(line)
                continue

            try:
                line_valid_ip = validate_ip_cidr(tokens[0], for_delete=False)
            except ValueError:
                new_lines.append(line)
                continue

            if line_valid_ip == valid_target:
                found = True
                new_line = f"{tokens[0]} {rate_str}"
                if comment_part is not None:
                    new_line += f" #{comment_part}"
                new_lines.append(new_line)
            else:
                new_lines.append(line)

        if not found:
            return False, f"IP 规则 [{valid_target}] 不存在于静态清单中"

        new_content = "\n".join(new_lines)
        if raw.endswith("\n") or not raw:
            new_content += "\n"

        success, msg, _ = self.save_content(new_content)
        if success:
            return True, f"静态规则 [{valid_target}] 速率已成功更新为 {rate_str} Mbps"
        return False, msg

    @staticmethod
    def test_ip_format(ip_str: str) -> Dict[str, Any]:
        """测试指定 IP/CIDR 格式是否有效及版本归属"""
        ip_str = ip_str.strip()
        if not ip_str:
            return {"valid": False, "formatted": "", "version": 0, "error": "IP 地址不能为空"}
        try:
            formatted = validate_ip_cidr(ip_str, for_delete=False)
            is_v6 = ":" in formatted
            return {
                "valid": True,
                "formatted": formatted,
                "version": 6 if is_v6 else 4,
                "error": None
            }
        except ValueError as e:
            return {"valid": False, "formatted": "", "version": 0, "error": str(e)}
