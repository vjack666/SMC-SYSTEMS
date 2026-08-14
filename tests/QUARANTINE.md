# QUARANTINE — tests/_broken

Los tests en `tests/_broken/` estan FUERA del gate oficial de conformidad del motor
(2026-08-14). Causa: exigen modulos eliminados (bar_by_bar_engine.py, _smoke.py) o
datasets ausentes. No se resucitan para forzar PASS. Estado: QUARANTINED con causa
documentada.

Regla (plan de cierre F4): timeout/cancelacion/datos faltantes = INCONCLUSIVE/BLOCKED_DATA,
nunca PASS. APIs eliminadas no se resucitan.
