"""Start/stop background observer processes (loop + vigilante).

Uses pythonw (no console) when available. Detects running scripts via
Windows process command lines — same idea as EstadoWidget, centralized.

Performance: process probes are TTL-cached and batched (one scan for many
scripts) so the UI never blocks on 2× PowerShell launches per paint.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from app_observador.config import ROOT

_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

LOOP_SCRIPT = "loop_analisis.py"
VIGILANTE_SCRIPT = "vigilante_riesgo.py"
DEMO_GRID_SCRIPT = "run_demo_grid.py"

_SCRIPT_PATHS = {
    LOOP_SCRIPT: ROOT / "scripts" / LOOP_SCRIPT,
    VIGILANTE_SCRIPT: ROOT / "scripts" / VIGILANTE_SCRIPT,
    DEMO_GRID_SCRIPT: ROOT / "scripts" / DEMO_GRID_SCRIPT,
}

# Cache: script_name -> (monotonic_ts, running_bool)
_RUN_CACHE: dict[str, tuple[float, bool]] = {}
_CACHE_TTL_S = 5.0
# PIDs we started ourselves (fast liveness check before full scan)
_OWNED_PIDS: dict[str, set[int]] = {}


def _logs_dir() -> Path:
    d = ROOT / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def resolve_pythonw() -> Path:
    """Prefer project pythonw (Python314), then sibling of current exe."""
    candidates = [
        Path(r"C:\Python314\pythonw.exe"),
        Path(r"C:\Python314\python.exe"),
        Path(sys.executable).with_name("pythonw.exe"),
        Path(sys.executable),
    ]
    env_py = os.environ.get("SMC_PYTHONW") or os.environ.get("SMC_PYTHON")
    if env_py:
        candidates.insert(0, Path(env_py))
    for p in candidates:
        if p and p.exists():
            return p
    return Path(sys.executable)


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        # 0 signal / open process — Windows: tasklist by PID is ok and cheap enough
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True,
            timeout=3,
            creationflags=_NO_WINDOW,
        )
        text = out.stdout.decode("cp1252", errors="replace")
        return str(pid) in text and "No tasks" not in text and "INFO:" not in text
    except Exception:
        return False


def invalidate_run_cache(script_name: str | None = None) -> None:
    if script_name is None:
        _RUN_CACHE.clear()
    else:
        _RUN_CACHE.pop(script_name, None)


def _set_cache(script_name: str, running: bool) -> None:
    _RUN_CACHE[script_name] = (time.monotonic(), running)


def is_script_running(script_name: str, *, force: bool = False) -> bool:
    """True if a python process has script_name in its command line (cached)."""
    now = time.monotonic()
    if not force:
        hit = _RUN_CACHE.get(script_name)
        if hit and (now - hit[0]) < _CACHE_TTL_S:
            return hit[1]
        # Fast path: PIDs we started still alive
        owned = _OWNED_PIDS.get(script_name) or set()
        if owned:
            alive = {p for p in owned if _pid_alive(p)}
            _OWNED_PIDS[script_name] = alive
            if alive:
                _set_cache(script_name, True)
                return True

    status = probe_scripts([script_name], force=True)
    return bool(status.get(script_name))


def probe_scripts(script_names: list[str], *, force: bool = False) -> dict[str, bool]:
    """Batch probe: one process scan for many scripts. Uses TTL cache."""
    now = time.monotonic()
    result: dict[str, bool] = {}
    missing: list[str] = []
    for name in script_names:
        if not force:
            hit = _RUN_CACHE.get(name)
            if hit and (now - hit[0]) < _CACHE_TTL_S:
                result[name] = hit[1]
                continue
            owned = _OWNED_PIDS.get(name) or set()
            if owned:
                alive = {p for p in owned if _pid_alive(p)}
                _OWNED_PIDS[name] = alive
                if alive:
                    _set_cache(name, True)
                    result[name] = True
                    continue
        missing.append(name)

    if not missing:
        return result

    found = _scan_scripts(missing)
    for name in missing:
        running = bool(found.get(name))
        _set_cache(name, running)
        result[name] = running
    return result


def _scan_scripts(script_names: list[str]) -> dict[str, list[int]]:
    """Return {script_name: [pids]} from one PowerShell/CIM pass."""
    out_map: dict[str, list[int]] = {n: [] for n in script_names}
    if sys.platform != "win32" or not script_names:
        return out_map

    # Single CIM query; match in Python (faster than N PowerShell processes)
    try:
        ps = (
            "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | "
            "Where-Object { $_.Name -match '^python' -and $_.CommandLine } | "
            "ForEach-Object { '{0}|{1}' -f $_.ProcessId, $_.CommandLine }"
        )
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=_NO_WINDOW,
        )
        lines = (proc.stdout or "").splitlines()
        for line in lines:
            if "|" not in line:
                continue
            pid_s, cmd = line.split("|", 1)
            if not pid_s.strip().isdigit():
                continue
            pid = int(pid_s.strip())
            cmd_l = cmd.lower()
            for name in script_names:
                if name.lower() in cmd_l:
                    out_map[name].append(pid)
        return out_map
    except Exception:
        pass

    # Fallback: tasklist /V once per image
    try:
        blob = ""
        for image in ("python.exe", "pythonw.exe"):
            out = subprocess.run(
                ["tasklist", "/V", "/FI", f"IMAGENAME eq {image}", "/FO", "CSV"],
                capture_output=True,
                timeout=5,
                creationflags=_NO_WINDOW,
            ).stdout.decode("cp1252", errors="replace")
            blob += out
        for name in script_names:
            if name in blob:
                out_map[name] = [1]  # unknown pid, mark present
    except Exception:
        pass
    return out_map


def _pids_for_script(script_name: str) -> list[int]:
    found = _scan_scripts([script_name])
    pids = found.get(script_name) or []
    # If fallback left a dummy 1 without real pid, re-scan won't kill wrong — empty
    return [p for p in pids if p > 1]


@dataclass
class ProcActionResult:
    ok: bool
    message: str
    running: bool


def start_script(script_name: str) -> ProcActionResult:
    """Start scripts/<script_name> with pythonw if not already running."""
    path = _SCRIPT_PATHS.get(script_name)
    if path is None or not path.exists():
        return ProcActionResult(False, f"Script no encontrado: {script_name}", False)
    if is_script_running(script_name, force=True):
        return ProcActionResult(True, f"Ya estaba ON: {script_name}", True)

    py = resolve_pythonw()
    logs = _logs_dir()
    stem = Path(script_name).stem
    out_log = logs / f"{stem}.out"
    err_log = logs / f"{stem}.err"
    try:
        # DETACHED: window hidden, survives parent UI.
        # Keep log handles open (do not close after Popen) so the child can write.
        flags = 0
        if sys.platform == "win32":
            flags = (
                subprocess.DETACHED_PROCESS
                | subprocess.CREATE_NEW_PROCESS_GROUP
                | subprocess.CREATE_NO_WINDOW
            )
        fo = open(out_log, "a", encoding="utf-8")
        fe = open(err_log, "a", encoding="utf-8")
        child = subprocess.Popen(
            [str(py), str(path)],
            cwd=str(ROOT),
            stdout=fo,
            stderr=fe,
            creationflags=flags,
            close_fds=False,
        )
        # Intentionally do not close fo/fe here — OS reaps when child exits.
        if child.pid:
            _OWNED_PIDS.setdefault(script_name, set()).add(child.pid)
            _set_cache(script_name, True)
    except Exception as e:
        return ProcActionResult(False, f"No se pudo iniciar {script_name}: {e}", False)

    # Brief settle (short — cache already optimistic)
    time.sleep(0.35)
    running = is_script_running(script_name, force=True)
    if running:
        return ProcActionResult(True, f"Encendido: {script_name}", True)
    return ProcActionResult(
        False,
        f"Se lanzó {script_name} pero no aparece en procesos (mirá logs/{stem}.err)",
        False,
    )


def stop_script(script_name: str) -> ProcActionResult:
    """Kill all python processes whose command line includes script_name."""
    invalidate_run_cache(script_name)
    pids = _pids_for_script(script_name)
    # Also kill owned pids
    for p in list(_OWNED_PIDS.get(script_name) or []):
        if p not in pids:
            pids.append(p)
    if not pids:
        _set_cache(script_name, False)
        _OWNED_PIDS[script_name] = set()
        return ProcActionResult(True, f"Ya estaba OFF: {script_name}", False)
    killed = 0
    errors: list[str] = []
    for pid in pids:
        try:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                capture_output=True,
                timeout=8,
                creationflags=_NO_WINDOW,
            )
            killed += 1
        except Exception as e:
            errors.append(f"{pid}:{e}")
    time.sleep(0.35)
    _OWNED_PIDS[script_name] = set()
    still = is_script_running(script_name, force=True)
    if still:
        return ProcActionResult(
            False,
            f"No se apagó del todo {script_name} (killed={killed}, err={errors})",
            True,
        )
    _set_cache(script_name, False)
    return ProcActionResult(True, f"Apagado: {script_name} (PIDs {pids})", False)


def ensure_loop_running() -> ProcActionResult:
    """Loop observador: always try to keep ON."""
    if is_script_running(LOOP_SCRIPT):
        return ProcActionResult(True, "Loop ya ON", True)
    return start_script(LOOP_SCRIPT)


def toggle_vigilante() -> ProcActionResult:
    if is_script_running(VIGILANTE_SCRIPT):
        return stop_script(VIGILANTE_SCRIPT)
    return start_script(VIGILANTE_SCRIPT)
