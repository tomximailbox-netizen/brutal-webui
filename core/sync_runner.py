import collections
import datetime
import os
import subprocess
import tempfile
import threading
import time
from typing import List, Dict, Any, Tuple


class SyncRunner:
    """管理同步脚本的触发、互斥控制、日志捕获与后台定时调度"""

    def __init__(
        self,
        script_path: str = "./brutal_sync.sh",
        domain_file: str = "./brut_domain.txt",
        mock_mode: bool = False,
        wrapper = None,
        ip_mgr = None
    ):
        self.script_path = os.path.abspath(script_path)
        self.domain_file = os.path.abspath(domain_file)
        self.mock_mode = mock_mode or (os.name != 'posix')
        self.wrapper = wrapper
        self.ip_mgr = ip_mgr

        self._lock = threading.Lock()
        self._is_running = False
        self._last_run_time: float = 0.0
        self._last_status: str = "未运行"
        self._last_exit_code: int = 0
        # 保留最近 500 行日志
        self._log_buffer = collections.deque(maxlen=500)

        # 定时器相关
        self._scheduler_thread: threading.Thread = None
        self._scheduler_stop = threading.Event()
        self._scheduler_interval: int = 300
        self._scheduler_enabled: bool = False

    def is_running(self) -> bool:
        return self._is_running

    def get_status(self) -> Dict[str, Any]:
        return {
            "running": self._is_running,
            "last_run_time": datetime.datetime.fromtimestamp(self._last_run_time).strftime("%Y-%m-%d %H:%M:%S") if self._last_run_time else "从未运行",
            "last_status": self._last_status,
            "last_exit_code": self._last_exit_code,
            "scheduler_enabled": self._scheduler_enabled,
            "scheduler_interval": self._scheduler_interval
        }

    def get_logs(self) -> List[str]:
        return list(self._log_buffer)

    def append_log(self, msg: str):
        timestamp = datetime.datetime.now().strftime("[%H:%M:%S] ")
        self._log_buffer.append(f"{timestamp}{msg}")

    def trigger_sync(self) -> Tuple[bool, str]:
        """手动或定时触发同步（异步后台子线程）"""
        if not self._lock.acquire(blocking=False):
            return False, "已有同步任务正在进行中，请稍候"

        self._is_running = True
        self.append_log(">>> 触发同步任务...")

        thread = threading.Thread(target=self._run_sync_worker, daemon=True)
        thread.start()
        return True, "同步任务已启动"

    def _run_sync_worker(self):
        try:
            self._last_run_time = time.time()

            # 1. 优先下发并应用静态 IP 清单规则（确保服务器重启或同步时静态 IP 100% 生效）
            if self.ip_mgr and self.wrapper:
                static_rules = self.ip_mgr.get_effective_ips_with_rates(default_rate=100.0)
                if static_rules:
                    self.append_log(f">>> 正在应用静态 IP 清单规则 (共 {len(static_rules)} 条)...")
                    for s_ip, s_rate in static_rules.items():
                        ok, msg = self.wrapper.add_rule(s_ip, s_rate, is_manual=False)
                        self.append_log(f"[静态IP] {s_ip} ({s_rate} Mbps) -> {'生效' if ok else '失败: ' + msg}")

            # 2. 执行域名 DNS 动态解析同步
            if self.mock_mode:
                self._mock_sync()
                self._last_status = "成功 (Mock)"
                self._last_exit_code = 0
            else:
                self._real_sync()
        except Exception as e:
            self.append_log(f"同步执行发生异常: {str(e)}")
            self._last_status = f"异常: {str(e)}"
            self._last_exit_code = 1
        finally:
            self._is_running = False
            self._lock.release()

    def _mock_sync(self):
        self.append_log("[Mock 模式] 模拟执行 brutal_sync.sh...")
        time.sleep(0.3)
        self.append_log("========================================")
        self.append_log("读取域名文件: " + self.domain_file)
        self.append_log("========================================")
        self.append_log("[DNS] node1.example.com -> 123.145.97.17")
        self.append_log("[DNS] node2.example.com -> 1.1.1.1")
        time.sleep(0.1)
        self.append_log("DNS 解析完成，唯一 IPv4: 2 个")
        self.append_log("[SKIP] 123.145.97.17/32 已存在")
        self.append_log("[KEEP] 1.1.1.1/32 (DNS 解析有效)")

        # 检查受保护的手动规则与静态 IP 清单
        if self.ip_mgr:
            for s_ip in self.ip_mgr.get_effective_ips():
                self.append_log(f"[KEEP] {s_ip} (静态IP清单规则，保留)")

        if self.wrapper:
            manual_ips = self.wrapper.get_manual_ips()
            for m_ip in manual_ips:
                self.append_log(f"[KEEP] {m_ip} (手动添加规则，保留)")

        self.append_log("========================================")
        self.append_log("模拟同步完成: 域名 IP 保持同步，静态与手动规则完好保留")

    def _real_sync(self):
        if not os.path.exists(self.script_path):
            self.append_log(f"错误: 同步脚本不存在: {self.script_path}")
            self._last_status = "脚本不存在"
            self._last_exit_code = 1
            return

        cmd = ["/bin/bash", self.script_path, self.domain_file]

        temp_exclude_file = None
        # 汇总受保护白名单（包含静态 IP 清单和手动临时 IP）
        exclude_set = set()
        if self.ip_mgr:
            exclude_set.update(self.ip_mgr.get_effective_ips())
        if self.wrapper:
            exclude_set.update(self.wrapper.get_manual_ips())

        if exclude_set:
            temp_exclude = tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8")
            for eip in exclude_set:
                clean_ip = eip.split("/")[0]
                temp_exclude.write(clean_ip + "\n")
            temp_exclude.close()
            temp_exclude_file = temp_exclude.name
            cmd.append(temp_exclude_file)

        try:
            self.append_log(f"执行命令: {' '.join(cmd)}")

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            for line in iter(process.stdout.readline, ''):
                clean_line = line.rstrip()
                if clean_line:
                    self.append_log(clean_line)

            process.stdout.close()
            exit_code = process.wait()
            self._last_exit_code = exit_code

            if exit_code == 0:
                self._last_status = "成功"
                self.append_log(">>> 同步脚本执行成功完成。")
            else:
                self._last_status = f"失败 (退出码 {exit_code})"
                self.append_log(f">>> 同步脚本执行失败，退出码: {exit_code}")
        finally:
            if temp_exclude_file and os.path.exists(temp_exclude_file):
                try:
                    os.remove(temp_exclude_file)
                except Exception:
                    pass

    def start_scheduler(self, interval_seconds: int = 300, initial_delay: float = 5.0):
        """启动后台定时同步调度器，支持服务启动后延迟 initial_delay 秒立即执行首次同步"""
        self.stop_scheduler()
        self._scheduler_interval = max(30, interval_seconds)
        self._scheduler_enabled = True
        self._scheduler_stop.clear()

        def _scheduler_loop():
            # 1. 启动初期延迟指定秒数后立即执行首次同步
            if initial_delay > 0:
                if not self._scheduler_stop.wait(initial_delay):
                    if not self._is_running:
                        self.append_log(f"[启动初始化] 服务启动延迟 {initial_delay} 秒已到达，立即执行首次域名同步...")
                        self.trigger_sync()

            # 2. 常规周期定时循环
            while not self._scheduler_stop.wait(self._scheduler_interval):
                if not self._is_running:
                    self.append_log("[定时调度] 触发自动周期同步...")
                    self.trigger_sync()

        self._scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True)
        self._scheduler_thread.start()

    def stop_scheduler(self):
        """停止后台定时同步调度器"""
        self._scheduler_enabled = False
        self._scheduler_stop.set()
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            self._scheduler_thread.join(timeout=1)
