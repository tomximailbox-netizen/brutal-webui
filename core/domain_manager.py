import os
import socket
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple, Dict, Any, Optional
from core.dns_resolver import SimpleDnsResolver


class DomainManager:
    """管理 brut_domain.txt 的原子化读取、写入与解析验证"""

    def __init__(
        self,
        file_path: str = "./brut_domain.txt",
        dns_servers: Optional[List[str]] = None,
        dns_timeout: float = 2.0,
    ):
        self.file_path = os.path.abspath(file_path)
        self._cache_lock = threading.Lock()
        self._cached_ip_map: Optional[Dict[str, str]] = None
        self._last_map_time: float = 0.0
        self._mock_ip_mapping: Dict[str, str] = {}
        self.dns_resolver = SimpleDnsResolver(servers=dns_servers, timeout=dns_timeout)
        self._refresh_lock = threading.Lock()
        self._is_refreshing = False

    def set_dns_config(self, servers: Optional[List[str]] = None, timeout: float = 2.0):
        """动态更新 DNS 解析服务器与超时时间"""
        self.dns_resolver.set_servers(servers or ["8.8.8.8", "8.8.4.4"])
        self.dns_resolver.set_timeout(timeout)
        self.clear_cache()

    def set_mock_ip_mapping(self, mapping: Dict[str, str]):
        """测试或 Mock 环境下注入指定的 IP 到域名映射"""
        self._mock_ip_mapping = dict(mapping)
        self.clear_cache()

    def clear_cache(self):
        """清空 IP-域名 解析缓存（保存文件或执行同步时调用）"""
        with self._cache_lock:
            self._cached_ip_map = None
            self._last_map_time = 0.0

    def trigger_async_refresh(self):
        """非阻塞后台异步刷新 DNS IP-域名 映射缓存（避免主 HTTP 线程阻塞）"""
        with self._refresh_lock:
            if self._is_refreshing:
                return
            self._is_refreshing = True

        threading.Thread(target=self._run_async_refresh_worker, daemon=True).start()

    def _run_async_refresh_worker(self):
        try:
            self._refresh_dns_ip_map()
        finally:
            with self._refresh_lock:
                self._is_refreshing = False

    def _refresh_dns_ip_map(self) -> Dict[str, str]:
        """并发解析所有域名并原子化写入缓存"""
        domains = self.get_effective_domains()
        if not domains:
            with self._cache_lock:
                self._cached_ip_map = {}
                self._last_map_time = time.time()
            return {}

        result: Dict[str, str] = {}
        max_workers = min(10, max(1, len(domains)))

        def resolve_single(dom):
            try:
                v4, v6 = self.dns_resolver.resolve_ips(dom)
                return dom, v4 + v6
            except Exception:
                return dom, []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_dom = {executor.submit(resolve_single, d): d for d in domains}
            for future in as_completed(future_to_dom):
                dom, ips = future.result()
                for clean_ip in ips:
                    result[clean_ip] = dom
                    if "/" not in clean_ip:
                        mask = "/128" if ":" in clean_ip else "/32"
                        result[f"{clean_ip}{mask}"] = dom

        now = time.time()
        with self._cache_lock:
            self._cached_ip_map = result
            self._last_map_time = now

        return result

    def get_cached_ip_to_domain_map(self, ttl_seconds: float = 120.0, blocking: bool = False) -> Dict[str, str]:
        """
        获取当前 brut_domain.txt 中所有域名解析出的 IP 到域名的映射字典。
        包含纯 IP 与带掩码 CIDR 键（如 '1.2.3.4' 和 '1.2.3.4/32'）。
        - blocking=False (默认): 非阻塞模式，若无缓存立即在后台异步解析，主线程 0ms 瞬间响应；
        - blocking=True: 阻塞等待所有域名并发解析完成。
        """
        now = time.time()
        with self._cache_lock:
            if self._cached_ip_map is not None and (now - self._last_map_time) < ttl_seconds:
                return dict(self._cached_ip_map)
            stale_cache = dict(self._cached_ip_map) if self._cached_ip_map is not None else None

        # 1. 若配置了 mock/自定义映射（单元测试或离线模拟环境），直接使用并返回，避免阻塞网络探测
        if self._mock_ip_mapping:
            result = {}
            for ip, dom in self._mock_ip_mapping.items():
                clean_ip = ip.strip()
                result[clean_ip] = dom
                if "/" not in clean_ip:
                    mask = "/128" if ":" in clean_ip else "/32"
                    result[f"{clean_ip}{mask}"] = dom
            with self._cache_lock:
                self._cached_ip_map = result
                self._last_map_time = now
            return dict(result)

        # 2. 阻塞与非阻塞模式处理
        if blocking:
            return self._refresh_dns_ip_map()
        else:
            self.trigger_async_refresh()
            # Stale-While-Revalidate: 有旧数据立即返回旧数据，无缓存返回空字典，绝不阻塞用户请求
            return stale_cache if stale_cache is not None else {}

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
            self.clear_cache()
            return True, "域名清单保存成功", effective_count
        except Exception as e:
            return False, f"保存失败: {str(e)}", 0

    def set_domain_rate(self, domain: str, rate: float) -> Tuple[bool, str]:
        """
        修改指定域名的限速速率，并原子化持久化到 brut_domain.txt 文件中。
        保留文件中原有的注释、空行与格式。
        """
        clean_domain = domain.strip().lower()
        if not clean_domain:
            return False, "域名不能为空"
        try:
            parsed_rate = float(rate)
            if parsed_rate <= 0:
                return False, "速率必须大于 0 Mbps"
        except (ValueError, TypeError):
            return False, "无效的速率数值"

        rate_str = str(int(parsed_rate)) if parsed_rate.is_integer() else str(parsed_rate)

        raw = self.get_raw_content()
        lines = raw.splitlines()
        found = False
        new_lines = []

        for line in lines:
            stripped = line.strip()
            # 空行或纯注释行直接保留
            if not stripped or stripped.startswith("#"):
                new_lines.append(line)
                continue

            # 分离配置代码与行尾注释
            code_part, *comment_parts = line.split("#", 1)
            comment_part = comment_parts[0] if comment_parts else None

            tokens = code_part.strip().split()
            if tokens and tokens[0].lower() == clean_domain:
                found = True
                new_line = f"{tokens[0]} {rate_str}"
                if comment_part is not None:
                    new_line += f" #{comment_part}"
                new_lines.append(new_line)
            else:
                new_lines.append(line)

        if not found:
            return False, f"域名 [{domain}] 不存在于域名清单中"

        new_content = "\n".join(new_lines)
        if raw.endswith("\n") or not raw:
            new_content += "\n"

        success, msg, _ = self.save_content(new_content)
        if success:
            return True, f"域名 [{domain}] 速率已成功更新为 {rate_str} Mbps"
        return False, msg

    @staticmethod
    def test_resolve(
        domain: str,
        dns_servers: Optional[List[str]] = None,
        dns_timeout: float = 2.5,
    ) -> Dict[str, Any]:
        """测试指定域名的 IPv4 与 IPv6 解析结果 (默认通过 Google DNS 等外部服务器)"""
        domain = domain.strip()
        if not domain:
            return {"domain": domain, "success": False, "ips": [], "error": "域名不能为空"}

        try:
            resolver = SimpleDnsResolver(servers=dns_servers, timeout=dns_timeout)
            v4, v6 = resolver.resolve_ips(domain)
            ips = v4 + v6
            server_display = ", ".join(resolver.servers)
            return {
                "domain": domain,
                "success": True,
                "ips": ips,
                "ips_v4": v4,
                "ips_v6": v6,
                "dns_servers": server_display,
                "error": None,
            }
        except Exception as e:
            return {"domain": domain, "success": False, "ips": [], "error": str(e)}
