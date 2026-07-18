"""Smoke test de regresión Fase B1 (Ruben rule: prueba empírica de cableo).

Cuenta las señales de run_sequence sobre EURUSD M15 REAL (datos locales,
no MT5) CON los metadatos B1 (HEAD) y SIN ellos (padre HEAD~1). Para el
baseline usa `git checkout HEAD~1 -- <5 archivos>` en el propio proceso
antes de lanzar el subprocess que cuenta; luego restaura con `git checkout
HEAD -- <5 archivos>`. Stash es poco fiable aqui (archivos ya commiteados),
por eso se usa checkout explicito. Si el conteo difiere, B1 alteró la
decisión del motor (fuente única R7 rota). Debe ser idéntico.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CODE_FILES = [
    "detectors/fvg.py", "detectors/ob.py",
    "ict_backtest/data_feed.py", "ict_backtest/translation.py",
    "ict_backtest/sequence.py",
]
COUNT_SNIPPET = """
import sys
sys.path.insert(0, r'%s')
from ict_backtest.data_feed import load_frames
from ict_backtest.sequence import SequenceConfig, run_sequence, _candle_objects

frames = load_frames('EURUSD', ('M15',))
dfm = frames['M15'].tail(8000).reset_index(drop=True)

def est_htf_fn(i):
    r = dfm.iloc[i]
    return {'trend': str(r.get('trend', 'RANGING')),
            'sweep_up': bool(r.get('liquidity_sweep_up', False)),
            'sweep_down': bool(r.get('liquidity_sweep_down', False))}

objs = _candle_objects(dfm, 'M15')
sigs, _ = run_sequence(objs, est_htf_fn, SequenceConfig(),
                       htf_poi_fn=None, ltf_tf='M15', bos_table=None)
print('N_SIGNALS', len(sigs))
""" % ROOT


def _run_count(baseline: bool) -> int:
    if baseline:
        subprocess.run(["git", "checkout", "HEAD~1", "--", *CODE_FILES],
                       cwd=ROOT, check=True, capture_output=True)
    try:
        out = subprocess.run([sys.executable, "-c", COUNT_SNIPPET],
                             cwd=ROOT, capture_output=True, text=True, timeout=200)
    finally:
        # siempre restaura al HEAD (B1) para no dejar el arbol sucio
        subprocess.run(["git", "checkout", "HEAD", "--", *CODE_FILES],
                       cwd=ROOT, check=True, capture_output=True)
    for line in out.stdout.splitlines():
        if line.startswith("N_SIGNALS"):
            return int(line.split()[1])
    raise RuntimeError("no N_SIGNALS en salida:\n" + out.stdout + out.stderr)


def main():
    n_with = _run_count(baseline=False)
    n_base = _run_count(baseline=True)
    print(f"B1 señales = {n_with} | baseline = {n_base}")
    if n_with != n_base:
        print("FALLO: B1 alteró la decisión del motor (fuente única R7)")
        sys.exit(1)
    print("OK: B1 no altera la decisión de run_sequence (metadatos solo informativos)")


if __name__ == "__main__":
    main()
