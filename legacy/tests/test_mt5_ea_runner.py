from __future__ import annotations

from adapters.mt5_ea_harness import MQL5EAHarnessAdapter
from backtest.validation.mt5_backtest_runner import MT5BacktestRunner, SlippageConfig
from integration.mt5_bridge.schema import OrderType, SignalAction, SignalMessage


def test_runner_buy_with_tp_hits_take_profit():
    runner = MT5BacktestRunner()
    signal = SignalMessage(
        signal_id="t1",
        symbol="EURUSD",
        action=SignalAction.BUY,
        order_type=OrderType.MARKET,
        volume=0.1,
        price=1.1000,
        stop_loss=1.0950,
        take_profit=1.1100,
    )
    results = runner.run([signal])
    assert len(results) == 1
    assert results[0].exit_reason == "take_profit"
    assert results[0].net_profit > 0


def test_runner_invalid_action_returns_error_via_adapter():
    adapter = MQL5EAHarnessAdapter()
    result = adapter.run([], {"action": "INVALID"})
    assert result["status"] == "error"


def test_slippage_config_affects_entry_price():
    no_slip = MT5BacktestRunner(SlippageConfig(mode="none"))
    with_slip = MT5BacktestRunner(SlippageConfig(mode="fixed", fixed_pips=1.0))
    signal = SignalMessage(
        signal_id="t2",
        symbol="EURUSD",
        action=SignalAction.BUY,
        order_type=OrderType.MARKET,
        volume=0.1,
        price=1.1000,
        stop_loss=1.09,
        take_profit=1.12,
    )
    base_entry = no_slip.run([signal])[0].entry_price
    slip_entry = with_slip.run([signal])[0].entry_price
    assert slip_entry > base_entry