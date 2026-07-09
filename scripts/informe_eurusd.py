"""
INFORME combinado EURUSD: analisis tecnico (SMC) + contexto fundamental (noticias).

Une scripts/rutina_eurusd.py (detectores deterministas) con scripts/news_report.py
(contexto fundamental EUR/USD). Entrega UN solo reporte que dice si tecnica y
fundamental empujan la misma direccion o se contradicen.

Uso:
  python scripts/informe_eurusd.py
  python scripts/informe_eurusd.py --save
"""
from __future__ import annotations

import argparse
import io
import sys
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import news_report
import rutina_eurusd as rut


def _capture(fn) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        fn()
    return buf.getvalue()


def _bias_from_direction(d: int) -> str:
    return {1: "LONG", -1: "SHORT", 0: "NEUTRAL"}.get(d, "NEUTRAL")


def fundamental_bias(cache: dict) -> tuple[str, list[str]]:
    """Sesgo grueso del fundamental: si hay evento USD 'fuerte' reciente vs EUR.

    Esto es una guia, NO una verdad: los fundamentales 'en algunos casos'
    guian la direccion, pero el precio los descuenta. Lo tratamos con honestidad.
    """
    reasons = []
    usd = [e for e in cache.get("events", []) if e.get("currency") in ("USD",)]
    # Si hay discurso Fed / dato USD mejor a lo esperado -> USD puede fortalecerse
    has_fed_speak = any("FOMC" in (e.get("event") or "") or "Fed" in (e.get("event") or "") for e in usd)
    better_than_forecast = any(
        e.get("actual") and e.get("forecast") and _num(e["actual"]) < _num(e["forecast"])
        for e in usd if e.get("actual") and e.get("forecast")
    )
    if has_fed_speak:
        reasons.append("Discurso de miembro FOMC (USD) hoy: puede mover al USD.")
    if better_than_forecast:
        reasons.append("Datos USD (jobless claims) salieron MEJOR a lo esperado -> sesgo a USD mas fuerte (EURUSD a la baja).")
    if not reasons:
        reasons.append("Sin evento USD de alto impacto concluyente hoy.")
    # si hay dato USD mejor, sesgo fundamental SHORT en EURUSD
    if better_than_forecast:
        return "SHORT (guia)", reasons
    return "NEUTRAL (guia)", reasons


def _num(s: str):
    try:
        return float(str(s).replace(",", "").replace("K", "000").replace("M", "000000").replace("%", ""))
    except Exception:
        return float("nan")


def main() -> int:
    ap = argparse.ArgumentParser(description="Informe tecnico+fundamental EURUSD")
    ap.add_argument("--save", action="store_true")
    args = ap.parse_args()

    # tecnica
    d1 = rut.analyze_timeframe(rut._load("EURUSD", "D1"), "D1")
    h4 = rut.analyze_timeframe(rut._load("EURUSD", "H4"), "H4")
    m15 = rut.analyze_timeframe(rut._load("EURUSD", "M15"), "M15")
    verdict = rut.build_verdict(d1, h4, m15)
    tech_txt = rut.render("EURUSD", d1, h4, m15, verdict)

    # fundamental (RSS ForexFactory en vivo)
    events, source = news_report.load_events()
    relevant = news_report.filter_relevant(events)
    fund_txt = news_report.render(relevant, source)
    fund_bias, fund_reasons = fundamental_bias({"events": relevant})

    # resumen de cruce
    tech_bias = verdict["bias"].split()[0] if verdict["bias"] else "NEUTRAL"
    L = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    L.append("")
    L.append("#" * 64)
    L.append(f"#  INFORME EURUSD  (tecnico + fundamental)   {now}")
    L.append("#" * 64)
    L.append("")
    L.append("--- TECNICO (SMC, datos MT5 en vivo) ---")
    L.append(tech_txt)
    L.append("")
    L.append("--- FUNDAMENTAL (noticias EUR/USD) ---")
    L.append(fund_txt)
    L.append("")
    L.append("=" * 64)
    L.append("  CRUCE TECNICO vs FUNDAMENTAL")
    L.append("=" * 64)
    L.append(f"  Sesgo tecnico    : {tech_bias}")
    L.append(f"  Sesgo fundamental: {fund_bias}")
    if relevant:
        L.append(f"  >>> NOTICIA ROJA HOY: {len(relevant)} evento(s) USD/EUR High en ventana.")
        L.append("      Challenge: podes operar, ojo al slippage.")
        L.append("      Cuenta fondeada: solo 40% profit en ventana 10min (News Reward Share).")
    if tech_bias != "NEUTRAL" and fund_bias.startswith(tech_bias):
        L.append("  >>> AMBOS EMPUJAN LA MISMA DIRECCION (confluencia).")
    elif tech_bias == "NEUTRAL" or fund_bias.startswith("NEUTRAL"):
        L.append("  >>> EN CONFLICTO O INCONCLUSO: uno de los dos no define. Cuidado.")
    else:
        L.append("  >>> SE CONTRADICEN: tecnica y fundamental van a la opuesta. Esperar o reducir size.")
    L.append("")
    for r in fund_reasons:
        L.append(f"   - fund: {r}")
    L.append("#" * 64)

    out = "\n".join(L)
    print(out)

    if args.save:
        out_dir = Path("docs/diario")
        out_dir.mkdir(parents=True, exist_ok=True)
        fecha = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        p = out_dir / f"INFORME_EURUSD_{fecha}.md"
        p.write_text("```\n" + out + "\n```\n", encoding="utf-8")
        print(f"\n[*] Informe guardado en {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
