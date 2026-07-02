from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from smc_successor.backtest.validation.trade_comparator import ComparisonResult


class ReportGenerator:
    """Generates human-readable validation reports from ComparisonResult."""

    def __init__(self, output_dir: str | Path = "reports/mt5_validation") -> None:
        self.output_dir = Path(output_dir)

    def generate_text(self, cmp: ComparisonResult, title: str = "MT5 Backtest Validation Report") -> str:
        lines: list[str] = []
        ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        lines.append("=" * 70)
        lines.append(f"  {title}")
        lines.append(f"  Generated: {ts} UTC")
        lines.append("=" * 70)
        lines.append("")

        # --- Summary ---
        lines.append("--- MATCHING SUMMARY ---")
        lines.append(f"  Python trades        : {cmp.total_python_trades}")
        lines.append(f"  EA trades            : {cmp.total_ea_trades}")
        lines.append(f"  Matched              : {cmp.matched_trades}")
        lines.append(f"  Unmatched (Python)   : {cmp.unmatched_python_trades}")
        lines.append(f"  Unmatched (EA)       : {cmp.unmatched_ea_trades}")
        lines.append("")

        # --- Entry quality ---
        lines.append("--- ENTRY PRICE QUALITY ---")
        lines.append(f"  Mean absolute error  : {cmp.entry_price_mae:.5f}")
        lines.append(f"  Max error            : {cmp.entry_price_max_diff:.5f}")
        lines.append("")

        # --- Python metrics ---
        lines.append("--- PYTHON ENGINE ---")
        lines.append(f"  Win rate             : {cmp.python_win_rate:.2%}")
        lines.append(f"  Profit factor        : {cmp.python_profit_factor:.4f}")
        lines.append(f"  Total gross          : ${cmp.python_total_gross:.2f}")
        lines.append(f"  Total net            : ${cmp.python_total_net:.2f}")
        lines.append(f"  Total pips           : {cmp.python_total_pips:.1f}")
        lines.append(f"  Total commission     : ${cmp.python_total_commission:.2f}")
        lines.append(f"  Max drawdown         : ${cmp.python_max_drawdown:.2f}")
        lines.append(f"  Sharpe               : {cmp.python_sharpe:.4f}")
        lines.append("")

        # --- EA metrics ---
        lines.append("--- MT5 EA SIMULATION ---")
        lines.append(f"  Win rate             : {cmp.ea_win_rate:.2%}")
        lines.append(f"  Profit factor        : {cmp.ea_profit_factor:.4f}")
        lines.append(f"  Total gross          : ${cmp.ea_total_gross:.2f}")
        lines.append(f"  Total net            : ${cmp.ea_total_net:.2f}")
        lines.append(f"  Total pips           : {cmp.ea_total_pips:.1f}")
        lines.append(f"  Total commission     : ${cmp.ea_total_commission:.2f}")
        lines.append(f"  Max drawdown         : ${cmp.ea_max_drawdown:.2f}")
        lines.append(f"  Sharpe               : {cmp.ea_sharpe:.4f}")
        lines.append("")

        # --- Deltas ---
        lines.append("--- DELTA (EA - PYTHON) ---")
        lines.append(f"  Win rate             : {cmp.delta_win_rate:+.2%}")
        lines.append(f"  Profit factor        : {cmp.delta_profit_factor:+.4f}")
        lines.append(f"  Total net            : ${cmp.delta_total_net:+.2f}")
        lines.append(f"  Total pips           : {cmp.delta_total_pips:+.1f}")
        lines.append("")

        # --- Slippage ---
        lines.append("--- SLIPPAGE IMPACT ---")
        lines.append(f"  Avg slippage         : {cmp.avg_slippage_pips:.2f} pips")
        lines.append(f"  Slippage cost total  : ${cmp.slippage_cost_total:.2f}")
        lines.append(f"  Slippage cost/trade  : ${cmp.slippage_cost_per_trade:.2f}")
        lines.append("")

        # --- Per-trade details (first 20) ---
        if cmp.details:
            lines.append("--- PER-TRADE DETAIL (first 20) ---")
            lines.append(f"  {'signal_id':<14} {'entry_diff':>10} {'net_diff':>9} {'pips_diff':>9}")
            lines.append("  " + "-" * 46)
            for d in cmp.details[:20]:
                lines.append(
                    f"  {d['signal_id']:<14} {d['entry_diff']:>10.5f} {d['net_diff']:>9.2f} {d['pips_diff']:>9.1f}"
                )
            if len(cmp.details) > 20:
                lines.append(f"  ... and {len(cmp.details) - 20} more trades")
        lines.append("")

        # --- Verdict ---
        lines.append("--- VERDICT ---")
        delta_threshold = 0.10  # 10% tolerance
        if abs(cmp.delta_total_net / max(abs(cmp.python_total_net), 1)) < delta_threshold:
            lines.append("  ✅ PASS — EA simulation matches Python engine within tolerance.")
        else:
            lines.append("  ⚠️  REVIEW — EA simulation deviates from Python engine.")
            lines.append(
                f"     Net P&L delta: ${cmp.delta_total_net:.2f} "
                f"({cmp.delta_total_net / max(abs(cmp.python_total_net), 1) * 100:+.2f}%)"
            )

        lines.append("=" * 70)
        return "\n".join(lines)

    def write_report(self, cmp: ComparisonResult, filename: str | None = None) -> Path:
        if filename is None:
            filename = f"mt5_validation_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.txt"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / filename
        text = self.generate_text(cmp)
        path.write_text(text, encoding="utf-8")
        return path
