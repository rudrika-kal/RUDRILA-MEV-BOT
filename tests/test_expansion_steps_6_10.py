import unittest

from rudrila_mev.aave_liquidation import AavePosition, evaluate_aave_liquidation, WAD
from rudrila_mev.backrun import BackrunCandidate, BackrunRouteQuote, LegitimateBackrunEngine, evaluate_legitimate_backrun
from rudrila_mev.mev_share import MevShareBackrunPlan, build_mev_send_bundle, prepare_authenticated_mev_share_request
from rudrila_mev.morpho_liquidation import MorphoPosition, evaluate_morpho_liquidation
from rudrila_mev.optimal_size import solve_optimal_size


class ExpansionSteps6To10Tests(unittest.TestCase):
    def test_step6_legitimate_backrun(self):
        c = BackrunCandidate("0x" + "12" * 32, 100, 100, 3, 4, 1000, 100, 50, 50, 500)
        d = evaluate_legitimate_backrun(c)
        self.assertTrue(d.accepted)
        self.assertEqual(d.expected_net_wei, 800)

    def test_step6_blocks_user_harm(self):
        c = BackrunCandidate("0x" + "12" * 32, 100, 100, 3, 4, 1000, 100, 50, 50, 500, 1)
        self.assertFalse(evaluate_legitimate_backrun(c).accepted)

    def test_step6_next_block_is_post_trigger_even_with_lower_index(self):
        c = BackrunCandidate("0x" + "12" * 32, 100, 101, 9, 0, 1000, 100, 50, 50, 500)
        self.assertTrue(evaluate_legitimate_backrun(c).accepted)

    def test_step6_engine_ranks_only_accepted_backruns(self):
        routes = [
            BackrunRouteQuote("good", 1000, 100, 50, 50, 500),
            BackrunRouteQuote("bad", 200, 100, 50, 50, 500),
        ]
        out = LegitimateBackrunEngine().evaluate_routes(
            trigger_hash="0x" + "12" * 32,
            trigger_block=100,
            observed_block=100,
            trigger_index=1,
            execution_index=2,
            routes=routes,
        )
        self.assertEqual([x[0] for x in out], ["good"])

    def test_step7_mev_share_backrun_payload(self):
        p = MevShareBackrunPlan("0x" + "34" * 32, "0x1234", 100, 102)
        x = build_mev_send_bundle(p)
        self.assertEqual(x["method"], "mev_sendBundle")
        self.assertEqual(len(x["params"][0]["body"]), 2)
        self.assertFalse(x["params"][0]["body"][1]["canRevert"])
        url, headers, body = prepare_authenticated_mev_share_request(
            x, "0x" + "11" * 32
        )
        self.assertEqual(url, "https://relay.flashbots.net")
        self.assertIn("X-Flashbots-Signature", headers)
        self.assertIn('"mev_sendBundle"', body)

    def test_step8_aave_liquidation(self):
        p = AavePosition("0x1", WAD - 1, 1000, 1400, 500)
        d = evaluate_aave_liquidation(
            p, gas_wei=50, builder_bid_wei=25, swap_cost_wei=25,
            safety_buffer_wei=50, min_net_profit_wei=200
        )
        self.assertTrue(d.accepted)
        self.assertEqual(d.expected_net_wei, 250)

    def test_step9_morpho_liquidation(self):
        p = MorphoPosition("0x1", 900, 1000, int(0.86 * WAD), 1200)
        ok, net, _ = evaluate_morpho_liquidation(
            p, repay_wei=900, gas_wei=30, builder_bid_wei=20,
            conversion_cost_wei=10, safety_buffer_wei=20, min_net_profit_wei=200
        )
        self.assertTrue(ok)
        self.assertEqual(net, 220)

    def test_step10_optimal_size(self):
        best = solve_optimal_size(
            [100, 200, 300],
            lambda x: {100: 140, 200: 290, 300: 370}[x],
            lambda x: 10,
            safety_buffer_wei=10,
            min_net_profit_wei=10,
        )
        self.assertIsNotNone(best)
        self.assertEqual(best.amount_in, 200)
        self.assertEqual(best.net_profit, 70)


if __name__ == "__main__":
    unittest.main()
