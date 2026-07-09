"""
Reporte de noticias economicas para EURUSD (fase FundedNext).

Fuente: RSS oficial de ForexFactory (sin restricciones, sin API key, sin
Cloudflare). Probado y funcional:
    https://nfs.faireconomy.media/ff_calendar_thisweek.xml

El modulo descarga el RSS, filtra los eventos que correlacionan con EURUSD
(EUR / USD de alto impacto) y los presenta como contexto fundamental. El
resultado se cachea por dia en data/news_cache.json para no descargar varias
veces. Si no hay internet, cae al cache local (o avisa).

Uso:
  python scripts/news_report.py            # imprime eventos del dia
  python scripts/news_report.py --json     # solo JSON filtrado
  python scripts/news_report.py --no-fetch # usa solo el cache local
"""
from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

CACHE = Path("data/news_cache.json")
RSS_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.xml"

# Ventana de operacion Ecuador 8-11 AM = 13-16 UTC (mas 1h de margen cada lado).
TRADE_START_UTC = 12
TRADE_END_UTC = 17

# Divisas que correlacionan con EURUSD.
RELEVANT_CURRENCIES = {"EUR", "USD"}

# Zona horaria del RSS de ForexFactory (US Eastern, con DST).
try:
    import pytz
    ET_TZ = pytz.timezone("America/New_York")
except Exception:
    ET_TZ = None


def _download_rss() -> str | None:
    """Descarga el RSS oficial. None si no hay conexion."""
    try:
        req = Request(RSS_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=10) as resp:
            return resp.read().decode("windows-1252", errors="ignore")
    except (URLError, HTTPError, OSError) as e:
        print(f"[news] RSS no disponible ({e}); uso cache local si existe.")
        return None


def _parse_dt(date_str: str, time_str: str):
    """ForexFactory: date='07-06-2026' time='1:00am' (ET). Devuelve datetime UTC."""
    date_str = date_str.strip()
    time_str = time_str.strip().lower()
    try:
        dt_naive = datetime.strptime(f"{date_str} {time_str}", "%m-%d-%Y %I:%M%p")
    except ValueError:
        try:
            dt_naive = datetime.strptime(date_str, "%m-%d-%Y")
        except ValueError:
            return None
    if ET_TZ is not None:
        dt_et = ET_TZ.localize(dt_naive)
        return dt_et.astimezone(timezone.utc).replace(tzinfo=None)
    # fallback sin DST (aprox)
    return dt_naive + timedelta(hours=0)


def _parse_rss(xml: str) -> list[dict]:
    events: list[dict] = []
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return events
    today = datetime.now(timezone.utc).date()
    for ev in root.iter("event"):
        def g(tag: str) -> str:
            node = ev.find(tag)
            return (node.text or "").strip() if node is not None else ""
        country = g("country").upper()
        impact = g("impact")
        date_str = g("date")
        time_str = g("time")
        title = g("title")
        if not country or not impact or not date_str:
            continue
        dt_utc = _parse_dt(date_str, time_str)
        if dt_utc is None:
            continue
        events.append({
            "currency": country,
            "impact": impact,
            "time_utc": dt_utc.strftime("%H:%M"),
            "date_utc": dt_utc.strftime("%Y-%m-%d"),
            "event": title,
            "actual": g("actual"),
            "forecast": g("forecast"),
            "previous": g("previous"),
            "is_today": dt_utc.date() == today,
        })
    return events


def _is_relevant(ev: dict) -> bool:
    cur = (ev.get("currency") or "").upper()
    if cur not in RELEVANT_CURRENCIES:
        return False
    imp = (ev.get("impact") or "").lower()
    # solo High (rojo) es relevante para bloqueo/FundedNext
    return imp == "high"


def _in_window(ev: dict) -> bool:
    try:
        hh = int(ev["time_utc"].split(":")[0])
    except (ValueError, KeyError):
        return True
    return TRADE_START_UTC <= hh <= TRADE_END_UTC


def load_events(no_fetch: bool = False) -> tuple[list[dict], str]:
    """Devuelve (eventos_filtrados_hoy, fuente). Cachea por dia."""
    if not no_fetch:
        xml = _download_rss()
        if xml:
            all_ev = _parse_rss(xml)
            today = datetime.now(timezone.utc).date()
            todays = [e for e in all_ev if e.get("is_today")]
            relevant = [e for e in todays if _is_relevant(e)]
            # cachear
            try:
                CACHE.parent.mkdir(parents=True, exist_ok=True)
                CACHE.write_text(json.dumps(
                    {"date": today.isoformat(), "events": relevant}, indent=2
                ), encoding="utf-8")
            except Exception:
                pass
            return relevant, "RSS ForexFactory (en vivo)"

    # fallback cache local
    if CACHE.exists():
        try:
            data = json.loads(CACHE.read_text(encoding="utf-8"))
            return data.get("events", []), "cache local"
        except Exception:
            pass
    return [], "sin datos"


def filter_relevant(events: list[dict]) -> list[dict]:
    return [e for e in events if _is_relevant(e) and _in_window(e)]


def render(events: list[dict], source: str) -> str:
    L = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    L.append("=" * 64)
    L.append(f"  NOTICIAS EURUSD (contexto fundamental)   generado {now}")
    L.append("=" * 64)
    L.append(f"  Fuente: {source}")
    if not events:
        L.append("  (sin noticias rojas USD/EUR hoy en ventana 8-11 AM Ecuador)")
        L.append("=" * 64)
        return "\n".join(L)

    red = False
    for e in events:
        cur = e.get("currency", "")
        time = e.get("time_utc", "")
        name = e.get("event", "")
        actual = e.get("actual", "")
        forecast = e.get("forecast", "")
        prev = e.get("previous", "")
        L.append(f"  [ROJO {cur}] {time} UTC")
        L.append(f"     {name}")
        L.append(f"     actual={actual or '-'}  forecast={forecast or '-'}  prev={prev or '-'}")
        red = True
    L.append("-" * 64)
    if red:
        L.append("  >>> NOTICIA ROJA EN VENTANA: en fase CHALLENGE podes operar,")
        L.append("      pero ojo al slippage. En cuenta FUNDEADA solo cuentas 40%")
        L.append("      del profit en la ventana 5min antes/despues (News Reward Share).")
    L.append("=" * 64)
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description="Reporte noticias EURUSD")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-fetch", action="store_true", help="usar solo cache local")
    args = ap.parse_args()

    events, source = load_events(no_fetch=args.no_fetch)
    relevant = filter_relevant(events)

    if args.json:
        print(json.dumps({"source": source, "events": relevant}, indent=2,
                         ensure_ascii=False))
        return 0

    print(render(relevant, source))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
