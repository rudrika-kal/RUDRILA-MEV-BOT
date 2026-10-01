import tempfile
import unittest

from rudrila_mev.canary import effective_trade_amount
from rudrila_mev.impact import calculate_price_impact_bps, impact_guard
from rudrila_mev.ledger import daily_kill_switch
from rudrila_mev.policy import candidate_policy
from rudrila_mev.preflight import live_preflight
from rudrila_mev.registry import CandidateRegistry
from rudrila_mev.simulation import TokenSimulation, simulation_guard


class PretestSafetyTests(unittest.TestCase):
    def test_stale_candidate_rejected(self):
        d = candidate_policy(
            token="0xabc", factory="0xfac", current_block=200, discovered_block=100,
            confirmations=10, required_confirmations=1, max_age_blocks=25,
            denylist=[], approved_factories=["0xfac"]
        )
        self.assertFalse(d.accepted)

    def test_unapproved_factory_rejected(self):
        d = candidate_policy(
            token="0xabc", factory="0xbad", current_block=101, discovered_block=100,
            confirmations=1, required_confirmations=1, max_age_blocks=25,
            denylist=[], approved_factories=["0xgood"]
        )
        self.assertFalse(d.accepted)

    def test_registry_duplicate_and_cooldown(self):
        r = CandidateRegistry(cooldown_blocks=20, max_failed_attempts_per_token=2)
        r.mark_pool_seen("0xPool")
        self.assertTrue(r.is_duplicate_pool("0xpool"))
        r.record_attempt("0xToken", 100, False)
        ok, _ = r.can_attempt("0xtoken", 110)
        self.assertFalse(ok)
        ok, _ = r.can_attempt("0xtoken", 121)
        self.assertTrue(ok)

    def test_failed_attempt_limit(self):
        r = CandidateRegistry(cooldown_blocks=0, max_failed_attempts_per_token=2)
        r.record_attempt("0xT", 1, False)
        r.record_attempt("0xT", 2, False)
        ok, _ = r.can_attempt("0xT", 3)
        self.assertFalse(ok)

    def test_price_impact(self):
        bps = calculate_price_impact_bps(
            actual_amount_in=1000, actual_amount_out=900,
            probe_amount_in=100, probe_amount_out=100
        )
        self.assertEqual(bps, 1000)
        self.assertFalse(impact_guard(impact_bps=bps, min_impact_bps=0, max_impact_bps=250).accepted)

    def test_gas_loss_kill_switch(self):
        d = daily_kill_switch(
            failed_gas_wei=100, failed_transactions=1,
            max_daily_gas_loss_wei=100, max_daily_failed_transactions=3
        )
        self.assertTrue(d.blocked)

    def test_canary_amount(self):
        self.assertEqual(effective_trade_amount(
            normal_amount_wei=1000, canary_mode=True, canary_amount_wei=50
        ), 50)

    def test_honeypot_like_sell_failure_rejected(self):
        sim = TokenSimulation(
            buy_success=True, sell_success=False, amount_in_wei=1000,
            buy_received_raw=100, base_received_back_wei=0, expected_base_back_wei=900
        )
        self.assertFalse(simulation_guard(sim).accepted)

    def test_dynamic_tax_rejected(self):
        sim = TokenSimulation(
            buy_success=True, sell_success=True, amount_in_wei=1000,
            buy_received_raw=100, base_received_back_wei=950, expected_base_back_wei=980,
            dynamic_tax_suspected=True
        )
        self.assertFalse(simulation_guard(sim).accepted)

    def test_live_preflight_blocks_early_live(self):
        d = live_preflight(
            chain_verified=False, dex_addresses_verified=False, executor_deployed=False,
            executor_source_verified=False, private_relay_verified=False,
            fork_simulation_passed=False, dry_run_count=0
        )
        self.assertFalse(d.ready)
        self.assertGreaterEqual(len(d.missing), 6)


if __name__ == "__main__":
    unittest.main()
