import pandas as pd

from ict_backtest.data_feed import build_features, build_objects


def _mini_df():
    return pd.DataFrame({
        "open": [1.0, 1.0], "high": [1.1, 1.1], "low": [0.9, 0.9],
        "close": [1.0, 1.0], "time": [0, 1], "atr": [0.01, 0.01],
    })


def test_build_features_preserva_columnas_clave():
    feats = build_features(_mini_df())
    for col in ("bos_direction", "fvg_bullish", "ob_bullish", "choch_dir",
                "bsl_price", "sweep_low"):
        assert col in feats.columns


def test_build_objects_preserva_columnas_y_sella_capa():
    df = _mini_df()
    feats = build_features(df.copy())
    # Simular salida de detectores (sin tocar build_features): un BOS y un FVG.
    feats = feats.copy()
    feats["bos_direction"] = [1, 0]
    feats["fvg_bullish"] = [True, False]
    # build_objects NO debe romper las columnas (las necesita para df_to_objects)
    objs = build_objects({"H4": feats}, symbol="X")
    assert isinstance(objs, list)
    assert any(o.origin_tf == "H4" for o in objs)
    # y la vista legacy sigue reconstruyendose
    from ict_backtest.translation import objects_to_legacy_df
    lg = objects_to_legacy_df(objs)
    assert "bos_direction" in lg.columns
