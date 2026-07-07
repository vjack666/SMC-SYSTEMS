from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from monitoring.alerter import Alerter
from monitoring.config import MonitoringConfig
from monitoring.dashboard import generate_dashboard
from monitoring.drift_detector import DriftDetector
from monitoring.equity_telemetry import EquityTelemetry
from monitoring.performance_tracker import PerformanceTracker


@pytest.fixture
def tmp_path(tmpdir: Path) -> Path:
    return Path(tmpdir)


@pytest.fixture
def alerter(tmp_path: Path) -> Alerter:
    cfg = MonitoringConfig(alert_persistence_file=str(tmp_path / "alerts.json"))
    return Alerter(max_history=10, config=cfg)


# ══════════════════════════════════════════════════════════════════════════
# Alerter
# ══════════════════════════════════════════════════════════════════════════


class TestAlerter:
    def test_send_creates_alert(self, alerter: Alerter):
        alert_id = alerter.send("INFO", "test message", "test_source")
        assert alert_id is not None
        assert len(alert_id) > 0

    def test_send_increments_history(self, alerter: Alerter):
        alerter.send("WARN", "warn 1", "src")
        alerter.send("WARN", "warn 2", "src")
        recent = alerter.get_recent(5)
        assert len(recent) == 2

    def test_send_populates_fields(self, alerter: Alerter):
        alert_id = alerter.send("INFO", "hello", "mod_a")
        recent = alerter.get_recent(1)
        entry = recent[0]
        assert entry["alert_id"] == alert_id
        assert entry["level"] == "INFO"
        assert entry["message"] == "hello"
        assert entry["source"] == "mod_a"

    def test_get_recent_limits(self, alerter: Alerter):
        for i in range(5):
            alerter.send("INFO", f"msg {i}", "src")
        recent = alerter.get_recent(3)
        assert len(recent) == 3
        assert recent[-1]["message"] == "msg 4"

    def test_max_history_trims(self, alerter: Alerter):
        for i in range(15):
            alerter.send("INFO", f"msg {i}", "src")
        assert len(alerter.get_recent(100)) == 10

    def test_get_summary(self, alerter: Alerter):
        alerter.send("INFO", "info msg", "src")
        alerter.send("WARN", "warn msg", "src")
        alerter.send("CRITICAL", "critical msg", "src")
        alerter.send("CRITICAL", "another critical", "src")
        summary = alerter.get_summary()
        assert summary["total_alerts"] == 4
        assert summary["critical_count"] == 2
        assert summary["warn_count"] == 1
        assert summary["info_count"] == 1
        assert summary["last_alert_timestamp"] is not None

    def test_get_summary_empty(self, alerter: Alerter):
        summary = alerter.get_summary()
        assert summary["total_alerts"] == 0
        assert summary["last_alert_timestamp"] is None

    def test_no_escalation_below_threshold(self, alerter: Alerter):
        alerter.send("CRITICAL", "c1", "src")
        escalation = alerter.escalate()
        assert escalation is None

    def test_escalation_above_threshold(self, alerter: Alerter):
        for _ in range(5):
            alerter.send("CRITICAL", "many criticals", "src")
        escalation = alerter.escalate()
        assert escalation is not None
        assert escalation["level"] == "ESCALATION"

    def test_persist_and_reload(self, tmp_path: Path):
        path = tmp_path / "alerts_persist.json"
        cfg = MonitoringConfig(alert_persistence_file=str(path))
        a1 = Alerter(max_history=10, config=cfg)
        a1.send("WARN", "persisted alert", "test")
        a2 = Alerter(max_history=10, config=cfg)
        assert len(a2.get_recent(10)) == 1
        assert a2.get_recent(10)[0]["message"] == "persisted alert"

    def test_load_corrupted_file_recovers(self, tmp_path: Path):
        path = tmp_path / "bad.json"
        path.write_text("not valid json", encoding="utf-8")
        cfg = MonitoringConfig(alert_persistence_file=str(path))
        a = Alerter(max_history=10, config=cfg)
        assert len(a.get_recent(10)) == 0


# ══════════════════════════════════════════════════════════════════════════
# PerformanceTracker
# ══════════════════════════════════════════════════════════════════════════


class TestPerformanceTracker:
    @pytest.fixture
    def tracker(self, tmp_path: Path) -> PerformanceTracker:
        cfg = MonitoringConfig(performance_metrics_file=str(tmp_path / "perf.json"))
        return PerformanceTracker(config=cfg)

    def test_empty_metrics(self, tracker: PerformanceTracker):
        m = tracker.get_metrics()
        assert m["total_trades"] == 0

    def test_record_trade_buy(self, tracker: PerformanceTracker):
        tracker.record_trade(100.0, 110.0, 1.0, "BUY")
        m = tracker.get_metrics()
        assert m["total_trades"] == 1

    def test_record_trade_sell(self, tracker: PerformanceTracker):
        tracker.record_trade(110.0, 100.0, 1.0, "SELL")
        m = tracker.get_metrics()
        assert m["total_trades"] == 1

    def test_win_rate(self, tracker: PerformanceTracker):
        tracker.record_trade(100.0, 110.0, 1.0, "BUY")
        tracker.record_trade(100.0, 90.0, 1.0, "BUY")
        m = tracker.get_metrics()
        assert m["win_rate"] == 0.5

    def test_profit_factor(self, tracker: PerformanceTracker):
        tracker.record_trade(100.0, 110.0, 1.0, "BUY")
        tracker.record_trade(100.0, 105.0, 1.0, "BUY")
        m = tracker.get_metrics()
        assert m["profit_factor"] > 0

    def test_equity_curve(self, tracker: PerformanceTracker):
        tracker.record_trade(100.0, 110.0, 1.0, "BUY")
        tracker.record_trade(100.0, 90.0, 1.0, "BUY")
        curve = tracker.get_equity_curve()
        assert len(curve) == 2
        assert curve[-1]["cumulative_pnl"] == pytest.approx(10.0 + (-10.0))

    def test_persist_and_reload(self, tmp_path: Path):
        path = tmp_path / "perf_persist.json"
        cfg = MonitoringConfig(performance_metrics_file=str(path))
        t1 = PerformanceTracker(config=cfg)
        t1.record_trade(100.0, 110.0, 1.0, "BUY")
        t2 = PerformanceTracker(config=cfg)
        assert t2.get_metrics()["total_trades"] == 1
        assert len(t2.get_equity_curve()) == 1


# ══════════════════════════════════════════════════════════════════════════
# Dashboard
# ══════════════════════════════════════════════════════════════════════════


class TestDashboard:
    def test_generate_dashboard_basic(self, tmp_path: Path):
        cfg = MonitoringConfig(
            alert_persistence_file=str(tmp_path / "dash_alerts.json"),
            performance_metrics_file=str(tmp_path / "dash_perf.json"),
        )
        alerter = Alerter(max_history=10, config=cfg)
        equity = EquityTelemetry()
        result = generate_dashboard(alerter=alerter, equity=equity)
        assert "timestamp" in result
        assert "alerts" in result
        assert "drawdown" in result
        assert "performance" in result

    def test_generate_dashboard_with_alert(self, tmp_path: Path):
        cfg = MonitoringConfig(alert_persistence_file=str(tmp_path / "alerts2.json"))
        alerter = Alerter(max_history=10, config=cfg)
        alerter.send("WARN", "test alert", "dash_test")
        equity = EquityTelemetry()
        result = generate_dashboard(alerter=alerter, equity=equity)
        assert result["alerts"]["total_alerts"] == 1
        assert result["alerts"]["warn_count"] == 1


# ══════════════════════════════════════════════════════════════════════════
# Governance
# ══════════════════════════════════════════════════════════════════════════

from governance.auto_report_generator import AutoReportGenerator


class TestAutoReportGenerator:
    def test_generate_returns_string(self):
        gen = AutoReportGenerator(report_dir="data/governance/reports")
        report = gen.generate(
            monitoring_data={"recent_alerts": [], "drift_detected": False, "performance": {}, "drift_psi": {}},
            registry_data={"models": []},
            scheduler_data={"needs_retraining": False, "last_retraining": {}},
        )
        assert isinstance(report, str)
        assert "GOVERNANCE AUTO-REPORT" in report
        assert "No action required" in report

    def test_generate_with_drift_and_alerts(self):
        gen = AutoReportGenerator()
        report = gen.generate(
            monitoring_data={
                "recent_alerts": [
                    {"level": "CRITICAL", "message": "drift on feature_x", "timestamp": "2024-01-01T00:00:00"},
                ],
                "drift_detected": True,
                "performance": {"sharpe": "1.5", "drawdown": "5.0%"},
                "drift_psi": {"feature_x": 0.35},
            },
            registry_data={
                "models": [
                    {"name": "xgboost_v1", "version": "1.0", "metrics": {"sharpe": 1.5}, "created_at": "2024-01-01"},
                ]
            },
            scheduler_data={"needs_retraining": True, "last_retraining": {"timestamp": "2024-01-01", "model_id": "m1"}},
        )
        assert isinstance(report, str)
        assert "DEGRADED" in report
        assert "PSI=0.3500" in report
        assert "trigger model retraining" in report.lower()
        assert "investigate feature drift" in report.lower()

    def test_write_report_creates_file(self, tmp_path: Path):
        path = tmp_path / "reports"
        gen = AutoReportGenerator(report_dir=str(path))
        report = gen.generate(
            monitoring_data={},
            registry_data={},
            scheduler_data={},
        )
        written = gen.write_report(report, filename="test_report.txt")
        assert written.exists()
        assert written.read_text() == report

    def test_write_report_default_filename(self, tmp_path: Path):
        gen = AutoReportGenerator(report_dir=str(tmp_path / "reports2"))
        report = gen.generate(monitoring_data={}, registry_data={}, scheduler_data={})
        written = gen.write_report(report)
        assert written.exists()
        assert "governance_report_" in written.name
