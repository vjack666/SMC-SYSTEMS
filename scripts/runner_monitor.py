#!/usr/bin/env python3
"""Hermes Runner Monitor — event-wait launcher for heavy jobs.

Runs pytest, backtests, Optuna, ML training, walk-forward, etc. with:
  - OS wait on the child process (no chat polling)
  - optional secondary console window (--window)
  - live resource panel (CPU / RAM / elapsed)
  - real progress only if the job writes HERMES_PROGRESS_FILE
  - conservative defaults: ~75% CPU workers, Above Normal priority, RAM guard

Usage:
  python scripts/runner_monitor.py --title "pytest r10c" -- pytest tests/test_r10c_state_machine.py -q
  python scripts/runner_monitor.py --window --title "backtest" -- python ict_backtest/run_backtest.py --symbol XAUUSD
  python scripts/runner_monitor.py --workers 10 -- python -m pytest -n 10 tests/

Agent rule: one blocking call; do not spam "still running" in chat.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

# ---------------------------------------------------------------------------
# Constants (resource policy for 16 GB / multi-core laptops)
# ---------------------------------------------------------------------------

DEFAULT_CPU_FRACTION = 0.75
DEFAULT_RAM_SOFT_RATIO = 0.80  # warn / note throttle when system RAM load > 80%
DEFAULT_RAM_TARGET_GB = 12.0
SHORT_SEC = 20.0
MEDIUM_SEC = 120.0
UI_REFRESH_SEC = 0.5
SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
PROGRESS_ENV = "HERMES_PROGRESS_FILE"
WORKERS_ENV = "HERMES_WORKERS"
CHILD_ENV = "HERMES_MONITOR_CHILD"
SUMMARY_ENV = "HERMES_MONITOR_SUMMARY"

# Windows priority classes
_ABOVE_NORMAL_PRIORITY_CLASS = 0x00008000
_PROCESS_SET_INFORMATION = 0x0200
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


# ---------------------------------------------------------------------------
# Resource helpers (stdlib only — no psutil dependency)
# ---------------------------------------------------------------------------


def recommended_workers(
    cpu_count: int | None = None,
    fraction: float = DEFAULT_CPU_FRACTION,
) -> int:
    """Return ~70–80% of logical CPUs, always at least 1."""
    n = cpu_count if cpu_count is not None else (os.cpu_count() or 4)
    n = max(1, int(n))
    return max(1, min(n, int(round(n * fraction))))


def format_elapsed(seconds: float) -> str:
    s = max(0, int(seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h:02d}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"


def format_bar(done: int, total: int, width: int = 24) -> str:
    if total <= 0:
        return "░" * width
    ratio = max(0.0, min(1.0, done / total))
    filled = int(round(width * ratio))
    return "█" * filled + "░" * (width - filled)


def format_resource_bar(ratio: float, width: int = 12) -> str:
    ratio = max(0.0, min(1.0, ratio))
    filled = int(round(width * ratio))
    return "█" * filled + "░" * (width - filled)


@dataclass
class SystemSnapshot:
    """Resource sample for the monitor panel.

    When *pid* is tracked (job mode), cpu_pct / ram_used_gb are the **job
    process tree** (root + children), not the whole machine.
    System RAM soft-cap still uses system_ram_load_pct.
    """

    cpu_pct: float | None
    ram_used_gb: float | None
    ram_total_gb: float | None
    ram_load_pct: float | None
    threads: int | None = None
    # Optional context
    scope: str = "system"  # "job" | "system"
    process_count: int | None = None
    system_ram_used_gb: float | None = None
    system_ram_load_pct: float | None = None


class SystemSampler:
    """Sample CPU% and RAM for a job process tree (preferred) or the system.

    Job mode (pass root_pid):
      - CPU: GetProcessTimes over root+children, as % of all logical CPUs (0–100)
      - RAM: sum of Working Set of root+children (GB)
    System mode (root_pid=None): legacy whole-machine sample.
    """

    def __init__(self, root_pid: int | None = None) -> None:
        self.root_pid = root_pid
        self._prev_proc_time: int | None = None  # 100ns units
        self._prev_wall: float | None = None
        self._prev_idle: int | None = None
        self._prev_kernel: int | None = None
        self._prev_user: int | None = None
        self._is_windows = sys.platform == "win32"
        self._ncpu = max(1, os.cpu_count() or 1)

    def set_root_pid(self, pid: int | None) -> None:
        self.root_pid = pid
        self._prev_proc_time = None
        self._prev_wall = None

    def snapshot(self) -> SystemSnapshot:
        if self._is_windows:
            if self.root_pid and self.root_pid > 0:
                return self._windows_job_snapshot(self.root_pid)
            return self._windows_system_snapshot()
        return self._fallback_snapshot()

    def _fallback_snapshot(self) -> SystemSnapshot:
        # No portable process CPU without /proc; leave None rather than invent %.
        return SystemSnapshot(None, None, None, None, None, scope="system")

    def _system_ram(self) -> tuple[float | None, float | None, float | None]:
        """Return (used_gb, total_gb, load_pct) system-wide."""
        if not self._is_windows:
            return None, None, None
        import ctypes
        from ctypes import wintypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", wintypes.DWORD),
                ("dwMemoryLoad", wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_uint64),
                ("ullAvailPhys", ctypes.c_uint64),
                ("ullTotalPageFile", ctypes.c_uint64),
                ("ullAvailPageFile", ctypes.c_uint64),
                ("ullTotalVirtual", ctypes.c_uint64),
                ("ullAvailVirtual", ctypes.c_uint64),
                ("ullAvailExtendedVirtual", ctypes.c_uint64),
            ]

        mem = MEMORYSTATUSEX()
        mem.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem)):
            return None, None, None
        total = float(mem.ullTotalPhys)
        avail = float(mem.ullAvailPhys)
        return (
            (total - avail) / (1024**3),
            total / (1024**3),
            float(mem.dwMemoryLoad),
        )

    def _windows_system_snapshot(self) -> SystemSnapshot:
        import ctypes
        from ctypes import wintypes

        class FILETIME(ctypes.Structure):
            _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]

        def _ft_to_int(ft: FILETIME) -> int:
            return (int(ft.dwHighDateTime) << 32) + int(ft.dwLowDateTime)

        ram_used, ram_total, ram_load = self._system_ram()

        idle = FILETIME()
        kernel = FILETIME()
        user = FILETIME()
        cpu_pct = None
        if ctypes.windll.kernel32.GetSystemTimes(
            ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)
        ):
            i = _ft_to_int(idle)
            k = _ft_to_int(kernel)
            u = _ft_to_int(user)
            if self._prev_idle is not None:
                di = i - self._prev_idle
                dk = k - self._prev_kernel  # type: ignore[operator]
                du = u - self._prev_user  # type: ignore[operator]
                total_d = dk + du
                if total_d > 0:
                    busy = total_d - di
                    cpu_pct = max(0.0, min(100.0, 100.0 * busy / total_d))
            self._prev_idle, self._prev_kernel, self._prev_user = i, k, u

        return SystemSnapshot(
            cpu_pct,
            ram_used,
            ram_total,
            ram_load,
            None,
            scope="system",
            system_ram_used_gb=ram_used,
            system_ram_load_pct=ram_load,
        )

    def _process_tree_pids(self, root_pid: int) -> list[int]:
        """Return root + all descendants (Windows Toolhelp)."""
        import ctypes
        from ctypes import wintypes

        TH32CS_SNAPPROCESS = 0x00000002
        INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD),
                ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
                ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", wintypes.DWORD),
                ("szExeFile", wintypes.WCHAR * 260),
            ]

        kernel32 = ctypes.windll.kernel32
        snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if snap == INVALID_HANDLE_VALUE or snap is None:
            return [root_pid]

        children: dict[int, list[int]] = {}
        try:
            pe = PROCESSENTRY32W()
            pe.dwSize = ctypes.sizeof(PROCESSENTRY32W)
            ok = kernel32.Process32FirstW(snap, ctypes.byref(pe))
            while ok:
                pid = int(pe.th32ProcessID)
                ppid = int(pe.th32ParentProcessID)
                children.setdefault(ppid, []).append(pid)
                ok = kernel32.Process32NextW(snap, ctypes.byref(pe))
        finally:
            kernel32.CloseHandle(snap)

        out: list[int] = []
        stack = [root_pid]
        seen: set[int] = set()
        while stack:
            p = stack.pop()
            if p in seen or p <= 0:
                continue
            seen.add(p)
            out.append(p)
            stack.extend(children.get(p, []))
        return out or [root_pid]

    def _proc_times_and_ws(self, pid: int) -> tuple[int, int] | None:
        """Return (cpu_time_100ns, working_set_bytes) for one PID, or None."""
        import ctypes
        from ctypes import wintypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        PROCESS_VM_READ = 0x0010
        # PROCESS_QUERY_INFORMATION needed on some builds for GetProcessMemoryInfo
        PROCESS_QUERY_INFORMATION = 0x0400

        class FILETIME(ctypes.Structure):
            _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]

        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        def _ft_to_int(ft: FILETIME) -> int:
            return (int(ft.dwHighDateTime) << 32) + int(ft.dwLowDateTime)

        kernel32 = ctypes.windll.kernel32
        access = (
            PROCESS_QUERY_LIMITED_INFORMATION
            | PROCESS_QUERY_INFORMATION
            | PROCESS_VM_READ
        )
        handle = kernel32.OpenProcess(access, False, pid)
        if not handle:
            # Retry with limited rights only (still enough for GetProcessTimes)
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not handle:
                return None
        try:
            ctime = FILETIME()
            etime = FILETIME()
            ktime = FILETIME()
            utime = FILETIME()
            cpu_ok = kernel32.GetProcessTimes(
                handle,
                ctypes.byref(ctime),
                ctypes.byref(etime),
                ctypes.byref(ktime),
                ctypes.byref(utime),
            )
            if not cpu_ok:
                return None
            cpu_100ns = _ft_to_int(ktime) + _ft_to_int(utime)

            ws = 0
            try:
                psapi = ctypes.windll.psapi
                pmc = PROCESS_MEMORY_COUNTERS()
                pmc.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
                if psapi.GetProcessMemoryInfo(handle, ctypes.byref(pmc), pmc.cb):
                    ws = int(pmc.WorkingSetSize)
            except Exception:
                ws = 0
            return cpu_100ns, ws
        finally:
            kernel32.CloseHandle(handle)

    def _windows_job_snapshot(self, root_pid: int) -> SystemSnapshot:
        sys_used, sys_total, sys_load = self._system_ram()
        pids = self._process_tree_pids(root_pid)
        total_cpu_100ns = 0
        total_ws = 0
        alive = 0
        for pid in pids:
            sample = self._proc_times_and_ws(pid)
            if sample is None:
                continue
            c, ws = sample
            total_cpu_100ns += c
            total_ws += ws
            alive += 1

        wall = time.monotonic()
        cpu_pct = None
        if self._prev_proc_time is not None and self._prev_wall is not None:
            d_cpu = total_cpu_100ns - self._prev_proc_time  # 100ns units
            d_wall = wall - self._prev_wall  # seconds
            if d_wall > 0 and d_cpu >= 0:
                # FILETIME is 100ns; convert to seconds then % of all CPUs
                cpu_sec = d_cpu / 10_000_000.0
                # 100% = all logical CPUs busy for the interval
                cpu_pct = max(0.0, min(100.0, 100.0 * cpu_sec / (d_wall * self._ncpu)))
        self._prev_proc_time = total_cpu_100ns
        self._prev_wall = wall

        ram_job_gb = total_ws / (1024**3) if alive else None
        # For the bar: job RAM vs system total (context), not "job thinks it has 16GB"
        return SystemSnapshot(
            cpu_pct=cpu_pct,
            ram_used_gb=ram_job_gb,
            ram_total_gb=sys_total,
            ram_load_pct=sys_load,  # keep system load for soft-cap note
            threads=None,
            scope="job",
            process_count=alive,
            system_ram_used_gb=sys_used,
            system_ram_load_pct=sys_load,
        )


def set_above_normal_priority(pid: int) -> bool:
    """Set Windows process priority to Above Normal. No-op / False elsewhere."""
    if sys.platform != "win32" or pid <= 0:
        return False
    import ctypes

    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(
        _PROCESS_SET_INFORMATION | _PROCESS_QUERY_LIMITED_INFORMATION,
        False,
        pid,
    )
    if not handle:
        return False
    try:
        ok = bool(kernel32.SetPriorityClass(handle, _ABOVE_NORMAL_PRIORITY_CLASS))
        return ok
    finally:
        kernel32.CloseHandle(handle)


def read_progress(path: Path | None) -> dict[str, Any] | None:
    """Read optional progress JSON written by the job. Never invents %.

    Expected keys (all optional except meaningful ones):
      current: str
      done: int
      total: int
      unit: str  (candles, trades, folds, ...)
    """
    if path is None or not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    # Empty {} means "no real progress yet" — do not treat as progress.
    if not any(k in data for k in ("current", "done", "total", "message", "unit")):
        return None
    return data


@dataclass
class RunStats:
    title: str
    command: list[str]
    started_at: float
    ended_at: float | None = None
    exit_code: int | None = None
    workers: int = 1
    cpu_samples: list[float] = field(default_factory=list)
    ram_peak_gb: float | None = None
    ram_warned: bool = False
    priority_set: bool = False
    progress_last: dict[str, Any] | None = None

    @property
    def elapsed(self) -> float:
        end = self.ended_at if self.ended_at is not None else time.monotonic()
        return end - self.started_at

    def avg_cpu(self) -> float | None:
        if not self.cpu_samples:
            return None
        return sum(self.cpu_samples) / len(self.cpu_samples)


def render_panel(stats: RunStats, snap: SystemSnapshot, spin_i: int, done: bool) -> str:
    lines: list[str] = []
    border = "═" * 52
    lines.append("╔" + border + "╗")
    lines.append("║" + "HERMES RUNNER MONITOR".center(52) + "║")
    lines.append("╠" + border + "╣")
    lines.append(f" Task      {stats.title}")
    if done:
        status = "COMPLETED" if stats.exit_code == 0 else f"FAILED (exit {stats.exit_code})"
    else:
        status = f"{SPINNER[spin_i % len(SPINNER)]} Running..."
    lines.append(f" Status    {status}")
    lines.append(f" Elapsed   {format_elapsed(stats.elapsed)}")
    lines.append(f" Workers   {stats.workers}  (target ~{int(DEFAULT_CPU_FRACTION * 100)}% CPUs)")

    scope = getattr(snap, "scope", "system") or "system"
    scope_lbl = "job" if scope == "job" else "sys"

    if snap.cpu_pct is not None:
        bar = format_resource_bar(snap.cpu_pct / 100.0)
        nproc = getattr(snap, "process_count", None)
        extra = f"  ({nproc} proc)" if scope == "job" and nproc else ""
        lines.append(f" CPU({scope_lbl}) {bar} {snap.cpu_pct:5.1f}%{extra}")
    else:
        lines.append(f" CPU({scope_lbl}) (sampling...)")

    if snap.ram_used_gb is not None:
        if scope == "job":
            # Job working-set vs machine total (for scale bar only)
            total = snap.ram_total_gb or 1.0
            ratio = min(1.0, snap.ram_used_gb / total) if total else 0.0
            bar = format_resource_bar(ratio)
            lines.append(f" RAM(job)  {bar} {snap.ram_used_gb:4.1f} GB WS")
            sys_u = getattr(snap, "system_ram_used_gb", None)
            sys_t = snap.ram_total_gb
            sys_l = getattr(snap, "system_ram_load_pct", None) or snap.ram_load_pct
            if sys_u is not None and sys_t is not None:
                warn = (
                    "  ⚠ soft cap"
                    if (sys_l or 0) >= DEFAULT_RAM_SOFT_RATIO * 100
                    else ""
                )
                lines.append(
                    f" RAM(sys)  {sys_u:4.1f} / {sys_t:4.1f} GB used{warn}"
                )
        elif snap.ram_total_gb is not None:
            ratio = snap.ram_used_gb / snap.ram_total_gb if snap.ram_total_gb else 0.0
            bar = format_resource_bar(ratio)
            warn = (
                "  ⚠ soft cap"
                if (snap.ram_load_pct or 0) >= DEFAULT_RAM_SOFT_RATIO * 100
                else ""
            )
            lines.append(
                f" RAM(sys)  {bar} {snap.ram_used_gb:4.1f} / {snap.ram_total_gb:4.1f} GB{warn}"
            )
    else:
        lines.append(f" RAM({scope_lbl}) (n/a)")

    prog = stats.progress_last
    if prog:
        current = str(prog.get("current") or prog.get("message") or "")
        if current:
            lines.append(f" Current   {current}")
        done_n = prog.get("done")
        total_n = prog.get("total")
        unit = str(prog.get("unit") or "items")
        if isinstance(done_n, (int, float)) and isinstance(total_n, (int, float)) and total_n > 0:
            d, t = int(done_n), int(total_n)
            lines.append(f" Progress  {format_bar(d, t)}")
            lines.append(f"           {d:,} / {t:,} {unit}")
        elif isinstance(done_n, (int, float)):
            lines.append(f" Progress  {int(done_n):,} {unit} (no total — not inventing %)")
    else:
        lines.append(" Current   (no progress file — spinner only, no fake %)")

    lines.append("╚" + border + "╝")
    if not done:
        lines.append(" Wait mode: OS event (process exit). No chat polling.")
    return "\n".join(lines)


def render_summary(stats: RunStats) -> str:
    lines = [
        "",
        "═" * 40,
        " RUN COMPLETED" if stats.exit_code == 0 else " RUN FAILED",
        "═" * 40,
        f" Task       {stats.title}",
        f" Elapsed    {format_elapsed(stats.elapsed)}",
        f" Exit code  {stats.exit_code}",
        f" Workers    {stats.workers}",
    ]
    avg = stats.avg_cpu()
    if avg is not None:
        lines.append(f" CPU avg    {avg:.1f}%")
    if stats.ram_peak_gb is not None:
        lines.append(f" RAM peak   {stats.ram_peak_gb:.1f} GB (job WS)")
    if stats.priority_set:
        lines.append(" Priority   Above Normal")
    if stats.progress_last:
        d = stats.progress_last.get("done")
        t = stats.progress_last.get("total")
        u = stats.progress_last.get("unit", "items")
        if d is not None:
            if t:
                lines.append(f" Progress   {int(d):,} / {int(t):,} {u}")
            else:
                lines.append(f" Progress   {int(d):,} {u}")
    lines.append("═" * 40)
    lines.append("Next: agent reads stdout/stderr + exit code, then analyzes.")
    return "\n".join(lines)


def _clear_screen() -> None:
    if sys.platform == "win32":
        os.system("cls")
    else:
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()


def run_monitored(
    command: Sequence[str],
    *,
    title: str,
    workers: int,
    progress_path: Path | None,
    cwd: Path | None,
    log_path: Path | None,
    quiet_ui: bool = False,
) -> int:
    env = os.environ.copy()
    env[WORKERS_ENV] = str(workers)
    if progress_path is not None:
        progress_path.parent.mkdir(parents=True, exist_ok=True)
        env[PROGRESS_ENV] = str(progress_path.resolve())
        # Seed empty progress so the path exists.
        if not progress_path.is_file():
            progress_path.write_text("{}", encoding="utf-8")

    # Prefer joblib / optuna / xdist consumers that honor HERMES_WORKERS.
    env.setdefault("JOBLIB_NUM_THREADS", str(workers))
    env.setdefault("OMP_NUM_THREADS", str(max(1, workers // 2)))
    env.setdefault("MKL_NUM_THREADS", str(max(1, workers // 2)))
    env.setdefault("OPENBLAS_NUM_THREADS", str(max(1, workers // 2)))

    stats = RunStats(
        title=title,
        command=list(command),
        started_at=time.monotonic(),
        workers=workers,
    )
    # Job-scoped sampler (root PID set after Popen).
    sampler = SystemSampler(root_pid=None)

    creationflags = 0
    if sys.platform == "win32":
        # Keep child in same console group for monitor mode (UI in this process).
        creationflags = 0

    proc = subprocess.Popen(
        list(command),
        cwd=str(cwd) if cwd else None,
        env=env,
        stdout=None,  # inherit — user/agent sees live job output below panel if redirected differently
        stderr=None,
        creationflags=creationflags,
    )
    stats.priority_set = set_above_normal_priority(proc.pid)
    # Track the job process tree (backtest + any workers it spawns).
    sampler.set_root_pid(proc.pid)
    # Warm up CPU sampler (needs two samples).
    sampler.snapshot()
    time.sleep(0.05)

    spin_i = 0
    try:
        while True:
            rc = proc.poll()
            snap = sampler.snapshot()
            if snap.cpu_pct is not None:
                stats.cpu_samples.append(snap.cpu_pct)
            # Peak = job working set, not system used
            if snap.scope == "job" and snap.ram_used_gb is not None:
                if stats.ram_peak_gb is None or snap.ram_used_gb > stats.ram_peak_gb:
                    stats.ram_peak_gb = snap.ram_used_gb
            elif snap.scope != "job" and snap.ram_used_gb is not None:
                if stats.ram_peak_gb is None or snap.ram_used_gb > stats.ram_peak_gb:
                    stats.ram_peak_gb = snap.ram_used_gb
            sys_load = getattr(snap, "system_ram_load_pct", None)
            if sys_load is None:
                sys_load = snap.ram_load_pct
            if (sys_load or 0) >= DEFAULT_RAM_SOFT_RATIO * 100:
                stats.ram_warned = True
            stats.progress_last = read_progress(progress_path)

            if not quiet_ui:
                _clear_screen()
                print(render_panel(stats, snap, spin_i, done=(rc is not None)))
                if rc is None:
                    print()
                    print("Command:", " ".join(command))
                    print(
                        f"PID {proc.pid}  |  priority="
                        f"{'AboveNormal' if stats.priority_set else 'default'}  |  "
                        f"metrics=job tree"
                    )
                    if stats.ram_warned:
                        print(
                            f"NOTE: system RAM load ≥ {int(DEFAULT_RAM_SOFT_RATIO * 100)}% "
                            f"— prefer fewer workers next run."
                        )

            if rc is not None:
                stats.exit_code = rc
                stats.ended_at = time.monotonic()
                break

            spin_i += 1
            # UI refresh only — agent is blocked on this whole process (event wait).
            time.sleep(UI_REFRESH_SEC)
    except KeyboardInterrupt:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        stats.exit_code = 130
        stats.ended_at = time.monotonic()

    summary = render_summary(stats)
    print(summary)

    payload = {
        "title": stats.title,
        "command": stats.command,
        "exit_code": stats.exit_code,
        "elapsed_sec": round(stats.elapsed, 3),
        "workers": stats.workers,
        "cpu_avg": stats.avg_cpu(),
        "cpu_scope": "job_tree",
        "ram_peak_gb": stats.ram_peak_gb,
        "ram_scope": "job_working_set",
        "ram_warned": stats.ram_warned,
        "priority_above_normal": stats.priority_set,
        "progress": stats.progress_last,
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Summary JSON: {log_path}")

    # Machine-readable one-liner for agents
    print("HERMES_MONITOR_RESULT " + json.dumps(payload, separators=(",", ":")))
    return int(stats.exit_code if stats.exit_code is not None else 1)


def launch_in_new_window(argv: list[str], cwd: Path) -> int:
    """Re-exec this script in a new Windows console and WAIT for it (event)."""
    if sys.platform != "win32":
        print("NOTE: --window is best on Windows; falling back to same terminal.", file=sys.stderr)
        return -1

    env = os.environ.copy()
    env[CHILD_ENV] = "1"
    # Strip --window from child args to avoid recursion.
    child_args = [a for a in argv if a != "--window"]
    cmd = [sys.executable, str(Path(__file__).resolve()), *child_args]

    # CREATE_NEW_CONSOLE = 0x00000010
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=env,
        creationflags=0x00000010,
    )
    # Parent agent waits here — no polling loop in chat.
    return int(proc.wait())


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Hermes Runner Monitor — wait-on-process launcher for heavy jobs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--title", default="heavy-job", help="Label shown in the monitor")
    p.add_argument(
        "--workers",
        type=int,
        default=None,
        help=f"Worker hint (default: {int(DEFAULT_CPU_FRACTION * 100)}%% of CPUs)",
    )
    p.add_argument(
        "--window",
        action="store_true",
        help="Open a secondary console (Windows) and wait on it",
    )
    p.add_argument(
        "--progress-file",
        type=Path,
        default=None,
        help="JSON progress file path (or set via job writing HERMES_PROGRESS_FILE)",
    )
    p.add_argument(
        "--log",
        type=Path,
        default=Path("results/runner_monitor_last.json"),
        help="Write final summary JSON here",
    )
    p.add_argument(
        "--quiet-ui",
        action="store_true",
        help="Do not redraw panel (still waits; useful for CI)",
    )
    p.add_argument(
        "--cwd",
        type=Path,
        default=None,
        help="Working directory for the job (default: repo root)",
    )
    p.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Command after --  e.g. -- pytest -q",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    # If --window and we are the parent, spawn secondary console and wait.
    if "--window" in argv and os.environ.get(CHILD_ENV) != "1":
        # Resolve repo root (parent of scripts/)
        repo = Path(__file__).resolve().parent.parent
        return launch_in_new_window(argv, repo)

    parser = build_parser()
    args = parser.parse_args(argv)

    cmd = list(args.command)
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]
    if not cmd:
        parser.error("Missing command after --  Example: -- pytest -q")

    repo = Path(__file__).resolve().parent.parent
    cwd = args.cwd.resolve() if args.cwd else repo
    workers = args.workers if args.workers is not None else recommended_workers()

    progress = args.progress_file
    if progress is None:
        # Default progress path under results/ so jobs can write without inventing UI %
        safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", args.title)[:40]
        progress = repo / "results" / f"runner_progress_{safe}.json"

    return run_monitored(
        cmd,
        title=args.title,
        workers=workers,
        progress_path=progress,
        cwd=cwd,
        log_path=args.log,
        quiet_ui=args.quiet_ui,
    )


if __name__ == "__main__":
    raise SystemExit(main())
