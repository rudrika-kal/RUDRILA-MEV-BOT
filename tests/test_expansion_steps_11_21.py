import unittest

from rudrila_mev.analytics import OpportunityRecord, bounded_tuning_hint, summarize
from rudrila_mev.architecture import Opportunity, RudrilaPipeline, SimulationResult
from rudrila_mev.atomic_planner import OpportunityNode, best_atomic_plan
from rudrila_mev.builder_bid import optimize_builder_bid
from rudrila_mev.dashboard import HealthSnapshot, render_dashboard_html, render_health_json
from rudrila_mev.ethereum_private import (BuilderEndpoint, DEFAULT_ETHEREUM_BUILDERS, build_bundle_request, evaluate_private_builder_paths, flashbots_auth_header, validate_private_endpoint)
from rudrila_mev.flash_liquidity import FlashLiquidityPlan, evaluate_flash_liquidity
from rudrila_mev.inclusion_ev import InclusionHistory, evaluate_inclusion_ev
from rudrila_mev.parallel_engine import run_parallel
from rudrila_mev.wallet_policy import WalletPolicy, evaluate_wallet_separation


class ExpansionSteps11To21Tests(unittest.TestCase):
    def test_step11_flash_liquidity_gate(self):
        p = FlashLiquidityPlan("aave", "WETH", 1000, 5, 1500, 100, 50, 50, 200)
        d = evaluate_flash_liquidity(p)
        self.assertTrue(d.accepted)
        self.assertEqual(d.expected_net_wei, 295)

    def test_step12_atomic_planner(self):
        rows = [
            OpportunityNode("a", 100, resources=frozenset({"pool1"})),
            OpportunityNode("b", 200, resources=frozenset({"pool2"})),
            OpportunityNode("c", 500, resources=frozenset({"pool1"})),
        ]
        plan = best_atomic_plan(rows)
        self.assertEqual(plan.expected_net_wei, 700)

    def test_step13_builder_bid_optimizer(self):
        q = optimize_builder_bid(
            [10, 30, 80], [2000, 8000, 9500],
            gross_profit_wei=500, gas_wei=100, other_cost_wei=50,
            safety_buffer_wei=50, min_net_profit_wei=200,
        )
        self.assertEqual(q.bid_wei, 30)

    def test_step14_inclusion_ev(self):
        d = evaluate_inclusion_ev(InclusionHistory(100, 80), net_if_included_wei=1000)
        self.assertTrue(d.accepted)
        self.assertGreater(d.conservative_probability_bps, 0)

    def test_step15_private_builder_config(self):
        ok, _ = validate_private_endpoint(DEFAULT_ETHEREUM_BUILDERS[0])
        self.assertTrue(ok)
        payload = build_bundle_request(["0x1234"], 100)
        self.assertEqual(payload["method"], "eth_sendBundle")
        paths = [
            BuilderEndpoint("a", "https://relay-a.example", frozenset({"eth_sendBundle"})),
            BuilderEndpoint("b", "https://relay-b.example", frozenset({"eth_sendBundle"})),
        ]
        redundant, _ = evaluate_private_builder_paths(paths)
        self.assertTrue(redundant)
        body, header = flashbots_auth_header(
            payload,
            "0x" + "11" * 32,
        )
        self.assertIn('"eth_sendBundle"', body)
        self.assertIn(":", header)
        self.assertTrue(header.split(":", 1)[1].startswith("0x"))

    def test_step17_parallel_workers(self):
        rows = run_parallel({"a": lambda: 1, "b": lambda: 2}, max_workers=2)
        self.assertEqual([(x.name, x.ok) for x in rows], [("a", True), ("b", True)])

    def test_step18_wallet_separation(self):
        p = WalletPolicy("0x1", "0x2", 100, 200, "external_signer")
        ok, _ = evaluate_wallet_separation(p)
        self.assertTrue(ok)

    def test_step19_dashboard_is_read_only_state(self):
        snap = HealthSnapshot(1, 100, False, False, 2, 10, 8, 0, 0, 0)
        body = render_health_json(snap)
        page = render_dashboard_html(snap)
        self.assertIn(b'"live_trading":false', body)
        self.assertIn(b'"status":"ok"', body)
        self.assertIn(b"Read-only monitoring", page)

    def test_step20_analytics_cannot_relax_safety(self):
        stats = summarize([OpportunityRecord("arb", 100, 80, True, 10, 5)])
        hint = bounded_tuning_hint(stats)
        self.assertFalse(hint["may_lower_safety_limits"])
        self.assertFalse(hint["may_enable_live_trading"])

    def test_step21_modular_pipeline(self):
        class Engine:
            def discover(self, state):
                return [Opportunity("1", "arb", 10, state)]
        class Sim:
            def simulate(self, op):
                return SimulationResult(True, op.expected_net_wei, "PASS", op.payload)
        out = RudrilaPipeline([Engine()], Sim()).discover_and_simulate({"block": 1})
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].expected_net_wei, 10)


if __name__ == "__main__":
    unittest.main()
