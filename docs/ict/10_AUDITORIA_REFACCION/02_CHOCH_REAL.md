# Tema 02 — CHOCH REAL VS COPIA DE BOS (#2, Crítico)

## Qué dice la teoría (y el docstring de market_structure.py)
- BOS (Break of Structure): continuación de tendencia. El close rompe el
  ÚLTIMO swing high (alcista) o swing low (bajista).
- CHOCH (Change of Character): aviso de REVERSIÓN. ROMPE el swing que DEFINE
  la tendencia OPUESTA.
- REGLA CLAVE (dailypriceaction, citada en el docstring líneas 18-19):
  "un CHOCH válido debe romper el swing que produjo el ÚLTIMO BOS. Si rompe
  un swing equivocado, no cuenta."

## Evidencia empírica (verificada 2026-07-11, EURUSD H4, 10136 velas)
```python
ms = detect_market_structure(fr["H4"])
(ms["bos_dir"] == ms["choch_dir"]).all()     # => True
(ms["bos_dir"] != ms["choch_dir"]).sum()     # => 0
```
`choch_dir` y `bos_dir` son el MISMO array, bar por bar. El `or` en
`sequence.py::_has_bos` es cosmético:
```python
return (bos_dir == want) or (choch_dir == want)   # choch nunca difiere
```

## Código original (market_structure.py:93-95)
```python
up_choch = bear_break   # misma condición que BOS bajista
dn_choch = bull_break   # misma condición que BOS alcista
d["choch_dir"] = np.select([dn_choch, up_choch], [1, -1], default=0)
```
CHOCH era una copia literal de BOS con otro nombre.

## Fix aplicado — CHOCH real (rompe el swing que produjo el último BOS)
Se implementa con MEMORIA DE ESTADO (como `_track_bos`): se guarda el nivel y
la dirección del último BOS; un CHOCH válido es un break en dirección OPUESTA
a ese último BOS, rompiendo el swing que lo definió.

```python
def _track_choch(d, max_age, last_bos_dir, last_bos_level):
    # CHOCH = break en dirección OPUESTA al último BOS, sobre el swing que
    # produjo ese BOS (last_bos_level). No es igual a BOS.
    ...
```
Y en `detect_market_structure`:
```python
bos_dir = np.select([bull_break, bear_break], [1, -1], default=0)
# CHOCH: cruza el swing OPUESTO al último BOS (reversión, no continuación)
last_bos_dir = ...   # del estado secuencial
last_bos_level = ...
up_choch = (d["close"] > last_bos_level) & (last_bos_dir == -1)
dn_choch = (d["close"] < last_bos_level) & (last_bos_dir == 1)
choch_dir = np.select([up_choch, dn_choch], [1, -1], default=0)
```
Ahora `choch_dir` difiere de `bos_dir` cuando hay reversión real.

## Impacto
- Conceptual: el modelo contra-tendencia (Turtle Soup de `06_TURTLE_SOUP.md`)
  ahora tiene un detector distinto, no un alias.
- Numérico: puede reducir señales falsas de "reversión" y cambiar el PF.
  Se mide al re-correr.

## Fuentes
- dailypriceaction — SMC Market Structure (BOS & CHoCH):
  https://dailypriceaction.com/blog/smc-market-structure/
- Inner Circle Trader — BOS vs CHOCH:
  https://innercircletrader.net/tutorials/break-of-structure-vs-change-of-character/
- Flux Charts — BOS Explained: https://www.fluxcharts.com/articles/break-of-structure-bos-explained
- Alchemy Markets — CHoCH Guide: https://alchemymarkets.com/education/strategies/change-of-character-guide/
