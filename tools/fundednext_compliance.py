"""
FundedNext Stellar Lite — simulador de cumplimiento de reglas.

NO es producción de trading. Es una capa de evaluación que toma los trades
que YA produce el backtest de SMC-SYSTEMS (mismos SL/TP/hold del engine) y
chequea si cumplen las reglas exactas del modelo Stellar Lite de FundedNext
CFD, fase por fase.

Reglas modeladas (fuente: fundednext.com/cfd-challenge-terms, Jul 2026):
  Stellar Lite:
    Phase 1 : profit target 8%,  DLL 4%, MLL 8%, min 5 trading days
    Phase 2 : profit target 4%,  DLL 4%, MLL 8%
    Funded  : DLL 4%, MLL 8%, max risk 3% at any time
  Transversales CFD: static drawdown (piso sobre balance inicial),
  no consistency rule, news/overnight/weekend permitido, EAs permitidos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class StellarLiteRules:
    """Parámetros del modelo Stellar Lite $5K (editables para otros tamaños)."""
    initial_balance: float = 5000.0
    # Phase 1
    p1_profit_target_pct: float = 8.0
    p1_daily_loss_pct: float = 4.0
    p1_max_loss_pct: float = 8.0
    p1_min_trading_days: int = 5
    # Phase 2
    p2_profit_target_pct: float = 4.0
    p2_daily_loss_pct: float = 4.0
    p2_max_loss_pct: float = 8.0
    p2_min_trading_days: int = 5
    # Funded
    funded_daily_loss_pct: float = 4.0
    funded_max_loss_pct: float = 8.0
    # Riesgo por trade (max 3% at any time). Se usa para validar el sizer.
    max_risk_per_trade_pct: float = 3.0
    # Drawdown estatico: el piso se mide sobre el balance inicial.
    static_drawdown: bool = True


# Resultado de una fase
@dataclass
class PhaseResult:
    name: str
    passed: bool
    profit_pct: float
    profit_target_pct: float
    max_dd_pct: float
    max_daily_loss_pct: float
    max_daily_loss_limit_pct: float
    max_loss_limit_pct: float
    trading_days: int
    min_trading_days: int
    breach_date: str | None = None
    breach_detail: str = ""
    equity_curve: list[float] = field(default_factory=list)


@dataclass
class ComplianceReport:
    rules: StellarLiteRules
    phase1: PhaseResult
    phase2: PhaseResult
    overall_passed: bool
    total_trades: int
    risk_pct: float = 1.0
    notes: list[str] = field(default_factory=list)


def _daily_pnl(trades: pd.DataFrame, risk_pct: float) -> pd.DataFrame:
    """Agrupa trades por dia y acumula pnl en % de balance (riesgo fijo por trade)."""
    df = trades.copy()
    df["date"] = pd.to_datetime(df["entry_time"], utc=True).dt.date
    df["pnl_pct"] = df["pnl_r"].astype(float) * risk_pct
    daily = df.groupby("date")["pnl_pct"].sum()
    return daily


def _evaluate_phase(
    trades: pd.DataFrame,
    name: str,
    profit_target_pct: float,
    daily_loss_pct: float,
    max_loss_pct: float,
    min_trading_days: int,
    initial_balance: float,
    risk_pct: float,
    static_drawdown: bool = True,
) -> PhaseResult:
    if trades.empty:
        return PhaseResult(
            name=name, passed=False, profit_pct=0.0,
            profit_target_pct=profit_target_pct, max_dd_pct=0.0,
            max_daily_loss_pct=0.0, max_daily_loss_limit_pct=daily_loss_pct,
            max_loss_limit_pct=max_loss_pct, trading_days=0,
            min_trading_days=min_trading_days,
            breach_detail="sin trades en el periodo",
        )

    daily = _daily_pnl(trades, risk_pct)
    equity = (daily.cumsum() / 100.0 * initial_balance) + initial_balance
    equity_vals = equity.values
    profit_pct = float(equity_vals[-1] - initial_balance) / initial_balance * 100.0

    # Max drawdown (estatico: piso sobre balance inicial)
    peak = initial_balance
    max_dd = 0.0
    dd_breach_date = None
    for d, eq in zip(equity.index, equity_vals):
        peak = max(peak, eq)
        dd = (peak - eq) / initial_balance * 100.0
        if dd > max_dd:
            max_dd = dd
        if dd > max_loss_pct and dd_breach_date is None:
            dd_breach_date = str(d)

    # Daily loss
    worst_daily = float(daily.min())
    dll_breach_date = None
    if worst_daily < -daily_loss_pct:
        dll_breach_date = str(daily.idxmin())

    trading_days = int(len(daily))

    breaches: list[str] = []
    if profit_pct < profit_target_pct:
        breaches.append(
            f"profit target no alcanzado ({profit_pct:.2f}% < {profit_target_pct:.1f}%)"
        )
    if dd_breach_date is not None:
        breaches.append(
            f"MLL superado el {dd_breach_date} ({max_dd:.2f}% > {max_loss_pct:.1f}%)"
        )
    if dll_breach_date is not None:
        breaches.append(
            f"DLL superado el {dll_breach_date} ({worst_daily:.2f}% < -{daily_loss_pct:.1f}%)"
        )
    if trading_days < min_trading_days:
        breaches.append(
            f"dias de trading insuficientes ({trading_days} < {min_trading_days})"
        )

    passed = len(breaches) == 0
    breach_detail = "; ".join(breaches) if breaches else "cumple todas las reglas"
    breach_date = dll_breach_date or dd_breach_date

    return PhaseResult(
        name=name, passed=passed, profit_pct=round(profit_pct, 4),
        profit_target_pct=profit_target_pct, max_dd_pct=round(max_dd, 4),
        max_daily_loss_pct=round(worst_daily, 4),
        max_daily_loss_limit_pct=daily_loss_pct,
        max_loss_limit_pct=max_loss_pct, trading_days=trading_days,
        min_trading_days=min_trading_days, breach_date=breach_date,
        breach_detail=breach_detail,
        equity_curve=[round(float(x), 2) for x in equity_vals],
    )


def evaluate(
    trades: pd.DataFrame,
    rules: StellarLiteRules | None = None,
    risk_pct: float = 1.0,
) -> ComplianceReport:
    """Evalua las fases del Stellar Lite sobre `trades`.

    trades: DataFrame con columnas ['symbol','entry_time','exit_time',
        'direction','pnl_r','confidence','entry','exit'].
    risk_pct: riesgo fijo por trade en % del balance (debe ser <= max_risk_per_trade_pct).
    """
    if rules is None:
        rules = StellarLiteRules()

    notes: list[str] = []
    if risk_pct > rules.max_risk_per_trade_pct:
        notes.append(
            f"AVISO: risk_pct={risk_pct}% supera el maximo 3% de FundedNext "
            f"(max_risk_per_trade_pct={rules.max_risk_per_trade_pct}%). Ajusta el lote."
        )

    # Orden cronologico
    trades = trades.sort_values("entry_time").reset_index(drop=True)

    # Split por fase: Phase 1 = trades hasta alcanzar el profit target de P1;
    # el resto (si lo hay) es Phase 2. Si no se alcanza P1, P2 queda vacio.
    daily = _daily_pnl(trades, risk_pct)
    equity = (daily.cumsum() / 100.0 * rules.initial_balance) + rules.initial_balance
    target1_balance = rules.initial_balance * (1 + rules.p1_profit_target_pct / 100.0)
    reached = equity[equity >= target1_balance]
    if len(reached) > 0:
        # posicion (en el eje de dias) del primer dia que supera el target
        split_day_pos = daily.index.get_loc(reached.index[0])
        # mapear a posicion de trade: ultimo trade cuyo dia <= ese dia
        trade_dates = pd.to_datetime(trades["entry_time"], utc=True).dt.date
        date_list = list(daily.index)
        split_date = date_list[split_day_pos]
        # inclusivo: P1 lleva hasta el ultimo trade del dia de corte
        p1_mask = [d <= split_date for d in trade_dates]
        p1_trades = trades[p1_mask].copy()
        p2_trades = trades[~pd.Series(p1_mask, index=trades.index)].copy()
        notes.append(
            f"Split auto P1/P2 en el dia {split_date} "
            f"(alcanzo {rules.p1_profit_target_pct}% target)."
        )
    else:
        p1_trades = trades
        p2_trades = trades.iloc[0:0].copy()
        notes.append(
            "No se alcanzo el profit target de Phase 1 en el periodo; "
            "Phase 2 no evaluable (el challenge ya habria fallado en P1)."
        )

    p1 = _evaluate_phase(
        p1_trades, "Phase 1", rules.p1_profit_target_pct, rules.p1_daily_loss_pct,
        rules.p1_max_loss_pct, rules.p1_min_trading_days, rules.initial_balance,
        risk_pct, rules.static_drawdown,
    )
    p2 = _evaluate_phase(
        p2_trades, "Phase 2", rules.p2_profit_target_pct, rules.p2_daily_loss_pct,
        rules.p2_max_loss_pct, rules.p2_min_trading_days, rules.initial_balance,
        risk_pct, rules.static_drawdown,
    )

    overall = p1.passed and (p2.passed if len(p2_trades) > 0 else True)

    return ComplianceReport(
        rules=rules, phase1=p1, phase2=p2,
        overall_passed=overall, total_trades=int(len(trades)),
        risk_pct=risk_pct, notes=notes,
    )


def report_to_text(rep: ComplianceReport) -> str:
    r = rep.rules
    lines = []
    lines.append("=" * 60)
    lines.append("FUNDEDNEXT STELLAR LITE — COMPLIANCE REPORT")
    lines.append("=" * 60)
    lines.append(f"Cuenta inicial      : ${r.initial_balance:,.0f}")
    lines.append(f"Riesgo por trade    : {rep.risk_pct}% (max permitido 3%)")
    lines.append(f"Total trades        : {rep.total_trades}")
    lines.append("")
    for ph in (rep.phase1, rep.phase2):
        lines.append(f"--- {ph.name} ---")
        lines.append(f"  Resultado         : {'PASS ✅' if ph.passed else 'FAIL ❌'}")
        lines.append(f"  Profit            : {ph.profit_pct:.2f}% / target {ph.profit_target_pct:.1f}%")
        lines.append(f"  Max Drawdown      : {ph.max_dd_pct:.2f}% / limite {ph.max_loss_limit_pct:.1f}%")
        lines.append(f"  Peor dia (loss)   : {ph.max_daily_loss_pct:.2f}% / limite -{ph.max_daily_loss_limit_pct:.1f}%")
        lines.append(f"  Dias de trading   : {ph.trading_days} / minimo {ph.min_trading_days}")
        lines.append(f"  Detalle           : {ph.breach_detail}")
        if ph.breach_date:
            lines.append(f"  Fecha de breach   : {ph.breach_date}")
        lines.append("")
    lines.append(f"OVERALL: {'PASA EL CHALLENGE ✅' if rep.overall_passed else 'NO PASA ❌'}")
    for n in rep.notes:
        lines.append(f"  nota: {n}")
    lines.append("=" * 60)
    return "\n".join(lines)
