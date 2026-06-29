from backtest.bos_backtest import BacktestConfig as BosBacktestConfig
from backtest.bos_backtest import run_backtest as run_bos_backtest
from backtest.trend_backtest import BacktestConfig as TrendBacktestConfig
from backtest.trend_backtest import run_backtest as run_trend_backtest

__all__ = [
	"BosBacktestConfig",
	"TrendBacktestConfig",
	"run_bos_backtest",
	"run_trend_backtest",
]
