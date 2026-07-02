from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class MT5BridgeConfig:
    """Configuration for the MT5 bridge module."""

    # --- Communication protocol ---
    protocol: str = "file"
    host: str = "127.0.0.1"
    pull_port: int = 5555
    push_port: int = 5556
    pub_port: int = 5557

    # --- Timeouts & retries ---
    heartbeat_interval_sec: int = 5
    command_timeout_ms: int = 10_000
    max_retries: int = 3
    retry_delay_sec: float = 1.0

    # --- Signal persistence ---
    signal_log_dir: str = "signals"
    archive_after_days: int = 30

    # --- MT5 account ---
    mt5_account: int | None = None
    mt5_password_env_var: str = "MT5_PASSWORD"
    mt5_server_env_var: str = "MT5_SERVER"

    # --- Paths ---
    base_dir: Path = field(default_factory=lambda: Path.cwd())
    data_dir: Path = field(default_factory=lambda: Path.cwd() / "data" / "mt5")
    log_dir: Path = field(default_factory=lambda: Path.cwd() / "logs" / "mt5_bridge")

    @property
    def signal_log_path(self) -> Path:
        return self.base_dir / self.signal_log_dir

    @property
    def pull_address(self) -> str:
        return f"tcp://{self.host}:{self.pull_port}"

    @property
    def push_address(self) -> str:
        return f"tcp://{self.host}:{self.push_port}"

    @property
    def pub_address(self) -> str:
        return f"tcp://{self.host}:{self.pub_port}"
