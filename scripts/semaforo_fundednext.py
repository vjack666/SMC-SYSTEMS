"""
Semáforo FundedNext — regla de oro para el challenge.

Toma el veredicto técnico de la rutina (scripts/rutina_eurusd.py) + la
presencia de noticia roja (scripts/news_report.py) y las reglas exactas del
Stellar Lite $5K (tools/fundednext_compliance.py) y emite un veredicto simple:

  VERDE   : estructura clara, sin noticia roja en ventana -> operá con tu plan.
  AMARILLO: estructura presente PERO hay noticia roja, o sesgo NEUTRAL ->
            solo confirmación clara y reducí size (0.5% en vez de 1%).
  ROJO    : sesgo NEUTRAL sin confirmación, o noticia roja + sesgo opuesto ->
            NO operes hoy.

NO es consejo de inversión: es una capa de disciplina que te recuerda los
límites del challenge (DLL 4%, MLL 8%, riesgo <=3% por trade).

Uso:
  python scripts/semaforo_fundednext.py
  python scripts/semaforo_fundednext.py --save
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import rutina_eurusd as rut
import news_report

# Límites Stellar Lite $5K (fuente: tools/fundednext_compliance.py)
DLL_PCT = 4.0       # Daily Loss Limit
MLL_PCT = 8.0       # Max Loss Limit (drawdown estático)
MAX_RISK_PCT = 3.0  # riesgo máx por trade


def _red_flags(relevant: list[dict]) -> list[str]:
    out = []
    for e in relevant:
        out.append(f"{e.get('currency')} {e.get('event', '')} {e.get('time_utc')} UTC")
    return out


def evaluate(bias: str, relevant: list[dict]) -> tuple[str, list[str]]:
    """Devuelve (color, razones)."""
    reasons: list[str] = []
    has_red = len(relevant) > 0
    red_list = _red_flags(relevant)

    if has_red:
        reasons.append("NOTICIA ROJA hoy en ventana (USD/EUR High):")
        for r in red_list:
            reasons.append(f"   - {r}")
        reasons.append("Challenge: podés operar; cuenta fondeada solo 40% profit en ventana 10min.")

    if bias.startswith("NEUTRAL"):
        # Sin sesgo claro
        if has_red:
            color = "ROJO"
            reasons.append("Sesgo NEUTRAL + noticia roja -> mejor no operar hoy.")
        else:
            color = "AMARILLO"
            reasons.append("Sesgo NEUTRAL sin confirmación -> si operás, solo con setup claro y size reducido (0.5%).")
        return color, reasons

    # Sesgo definido (LONG/SHORT)
    if has_red:
        color = "AMARILLO"
        reasons.append("Estructura clara PERO hay noticia roja -> reducí size y poné SL justo (cuidado slippage).")
    else:
        color = "VERDE"
        reasons.append("Estructura clara y sin noticia roja en ventana -> operá con tu plan habitual.")

    # Recordatorio de límites SIEMPRE (regla de oro del challenge)
    reasons.append(f"Límites challenge: DLL {DLL_PCT}% | MLL {MLL_PCT}% | riesgo <= {MAX_RISK_PCT}% por trade.")
    return color, reasons


def render(color: str, reasons: list[str], bias: str) -> str:
    icon = {"VERDE": "VERDE ✅", "AMARILLO": "AMARILLO ⚠️", "ROJO": "ROJO ⛔"}.get(color, color)
    L = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    L.append("=" * 64)
    L.append(f"  SEMÁFORO FUNDEDNEXT (Stellar Lite $5K)   {now}")
    L.append("=" * 64)
    L.append(f"  Sesgo técnico : {bias}")
    L.append(f"  Veredicto     : {icon}")
    L.append("-" * 64)
    for r in reasons:
        L.append(f"   {r}")
    L.append("=" * 64)
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description="Semáforo FundedNext")
    ap.add_argument("--save", action="store_true")
    args = ap.parse_args()

    # técnico
    d1 = rut.analyze_timeframe(rut._load("EURUSD", "D1"), "D1")
    h4 = rut.analyze_timeframe(rut._load("EURUSD", "H4"), "H4")
    m15 = rut.analyze_timeframe(rut._load("EURUSD", "M15"), "M15")
    verdict = rut.build_verdict(d1, h4, m15)
    bias = verdict["bias"]

    # noticias
    events, _ = news_report.load_events()
    relevant = news_report.filter_relevant(events)

    color, reasons = evaluate(bias, relevant)
    txt = render(color, reasons, bias)
    print(txt)

    if args.save:
        out_dir = Path("docs/diario")
        out_dir.mkdir(parents=True, exist_ok=True)
        fecha = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        p = out_dir / f"SEMAFORO_{fecha}.md"
        p.write_text("```\n" + txt + "\n```\n", encoding="utf-8")
        print(f"\n[*] Semáforo guardado en {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
