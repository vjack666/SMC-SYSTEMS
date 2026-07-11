# Tema 05 — WALK-FORWARD REAL (MULTI-FOLD) (#5, Alto)

## Hallazgo
`--n-windows 2` produce exactamente 1 ventana in-sample + 1 out-of-sample.
El "PF out-of-sample 2.429 / sin overfit claro" descansa en UN solo fold de 32
trades. No distingue "edge real" de "esta ventana tuvo suerte".

Además, la dirección temporal estaba INVERTIDA: se optimizó en el ÚLTIMO
tercio (más reciente) y se validó hacia atrás (datos viejos). En producción el
sistema optimiza sobre el pasado y opera hacia el futuro — lo opuesto.

## Fix aplicado — walk-forward rolling multi-fold
1. `--n-windows N` (N>=3) genera N ventanas rolling: cada una optimiza en su
   tramo train y valida en su tramo test contiguo, avanzando en el tiempo.
2. Se reporta PF/WR/trades PROMEDIO de TODOS los folds out-of-sample, y la
   DESVIACIÓN (si un fold da PF<1, el edge es frágil).
3. Dirección temporal CORRECTA: in-sample = pasado, out-of-sample = futuro
   (no se invierte). La optimización de Optuna corre sobre el PRIMER tramo
   train; los folds siguientes validan hacia adelante.
4. Para no triplicar el tiempo de cómputo (ya ~129 min con 12 trials), se
   reduce `trials` por defecto y se documenta que correr 30-60 trials requiere
   vectorizar primero (#6).

```python
def _split_windows(n, n_windows, min_train):
    # rolling: cada fold usa train[prev_test:i] + test[i:j], avanzando.
    step = (n - min_train) // n_windows
    out = []
    for k in range(n_windows):
        te_e = min_train + step*(k+1)
        te_s = min_train + step*k
        tr_s = 0
        tr_e = te_s
        out.append((tr_s, tr_e, te_s, te_e))
    return out
```

## Fuentes
- Susan Potter — Walk-Forward Optimization (anchored vs rolling):
  https://www.susanpotter.net/quant/walk-forward-optimization/
- QuantInsti — Walk-Forward Optimization intro/limitations:
  https://blog.quantinsti.com/walk-forward-optimization-introduction/
- QuantBeckman — Walk-Forward CVCL (code):
  https://www.quantbeckman.com/p/with-code-walk-forward-cvcl-optimization
- Reddit r/algotrading — A real professional backtest is walk-forward:
  https://www.reddit.com/r/algotrading/comments/1t5e9q6/
