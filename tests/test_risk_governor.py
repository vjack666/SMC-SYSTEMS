from __future__ import annotations

import pytest

from smc_successor.risk import GovernorConfig, GovernorPool, GovernorState, mode_risk_multiplier, mode_threshold_add, next_state


class TestGovernorPool:
    def test_get_state_returns_default_for_unknown_symbol(self):
        pool = GovernorPool()
        state = pool.get_state("EURUSD")
        assert state.mode == "NORMAL"
        assert state.consecutive_losses == 0

    def test_next_transitions_and_stores_state(self):
        pool = GovernorPool()
        current = GovernorState(consecutive_losses=3)
        new_state = pool.next("EURUSD", current)
        assert new_state.mode == "DEFENSIVE"
        stored = pool.get_state("EURUSD")
        assert stored.mode == "DEFENSIVE"
        assert stored.consecutive_losses == 3

    def test_per_symbol_isolation(self):
        pool = GovernorPool()
        eur_state = pool.next("EURUSD", GovernorState(consecutive_losses=5))
        assert eur_state.mode == "LOCKDOWN"
        gbp_state = pool.get_state("GBPUSD")
        assert gbp_state.mode == "NORMAL"

    def test_update_from_trade_updates_consecutive_losses(self):
        pool = GovernorPool()
        result = pool.update_from_trade("EURUSD", -0.5)
        assert result.consecutive_losses == 1
        assert result.mode == "NORMAL"

    def test_update_from_trade_multiple_losses(self):
        pool = GovernorPool()
        pool.update_from_trade("EURUSD", -1.0)
        pool.update_from_trade("EURUSD", -1.0)
        result = pool.update_from_trade("EURUSD", -1.0)
        assert result.consecutive_losses == 3
        assert result.mode == "DEFENSIVE"

    def test_update_from_trade_win_resets_losses(self):
        pool = GovernorPool()
        pool.update_from_trade("EURUSD", -1.0)
        pool.update_from_trade("EURUSD", -1.0)
        result = pool.update_from_trade("EURUSD", 2.0)
        assert result.consecutive_losses == 0

    def test_reset_clears_symbol(self):
        pool = GovernorPool()
        pool.next("EURUSD", GovernorState(consecutive_losses=5))
        pool.reset("EURUSD")
        assert pool.get_state("EURUSD").consecutive_losses == 0

    def test_reset_all_clears_all(self):
        pool = GovernorPool()
        pool.next("EURUSD", GovernorState(consecutive_losses=5))
        pool.next("GBPUSD", GovernorState(consecutive_losses=3))
        pool.reset_all()
        assert pool.get_state("EURUSD").mode == "NORMAL"
        assert pool.get_state("GBPUSD").mode == "NORMAL"

    def test_custom_config(self):
        cfg = GovernorConfig(caution_after_losses=1, defensive_after_losses=2, lockdown_after_losses=3)
        pool = GovernorPool(cfg)
        pool.update_from_trade("EURUSD", -1.0)
        assert pool.get_state("EURUSD").mode == "CAUTION"
        pool.update_from_trade("EURUSD", -1.0)
        assert pool.get_state("EURUSD").mode == "DEFENSIVE"
        pool.update_from_trade("EURUSD", -1.0)
        assert pool.get_state("EURUSD").mode == "LOCKDOWN"

    def test_update_from_trade_total_drawdown(self):
        pool = GovernorPool()
        pool.update_from_trade("EURUSD", -5.0)
        pool.update_from_trade("EURUSD", -5.0)
        result = pool.update_from_trade("EURUSD", -5.0)
        assert result.mode == "LOCKDOWN"

    def test_multiple_symbols_independent_states(self):
        pool = GovernorPool()
        pool.update_from_trade("EURUSD", -1.0)
        pool.update_from_trade("EURUSD", -1.0)
        pool.update_from_trade("GBPUSD", 1.0)
        assert pool.get_state("EURUSD").consecutive_losses == 2
        assert pool.get_state("GBPUSD").consecutive_losses == 0

    def test_update_from_trade_with_running_pnl_all_symbols(self):
        pool = GovernorPool()
        result = pool.update_from_trade("EURUSD", -1.0)
        pool.update_from_trade("EURUSD", -2.0)
        result = pool.update_from_trade("EURUSD", -3.0)
        assert result.total_drawdown_pct > 0
