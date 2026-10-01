import unittest

from rudrila_mev.profit import add_bps, evaluate_profit, floor_bps


class ProfitTests(unittest.TestCase):
    def test_floor_bps(self):
        self.assertEqual(floor_bps(1_000_000, 20), 998_000)

    def test_add_bps_rounds_up(self):
        self.assertEqual(add_bps(100, 2000), 120)

    def test_reject_when_gas_consumes_profit(self):
        d = evaluate_profit(
            amount_in_wei=1_000_000,
            expected_final_wei=1_020_000,
            floor_final_wei=1_015_000,
            gas_cost_wei=14_000,
            extra_safety_buffer_wei=2_000,
            desired_net_profit_wei=1_000,
        )
        self.assertFalse(d.accepted)

    def test_accept_only_after_all_costs(self):
        d = evaluate_profit(
            amount_in_wei=1_000_000,
            expected_final_wei=1_050_000,
            floor_final_wei=1_045_000,
            gas_cost_wei=20_000,
            extra_safety_buffer_wei=5_000,
            desired_net_profit_wei=10_000,
        )
        self.assertTrue(d.accepted)
        self.assertEqual(d.floor_net_after_all_costs_wei, 20_000)
        self.assertEqual(d.required_gross_profit_wei, 35_000)

    def test_reject_negative_route(self):
        d = evaluate_profit(
            amount_in_wei=1_000_000,
            expected_final_wei=999_000,
            floor_final_wei=995_000,
            gas_cost_wei=1_000,
            extra_safety_buffer_wei=1_000,
            desired_net_profit_wei=1_000,
        )
        self.assertFalse(d.accepted)
        self.assertIn("not profitable", d.reason)


if __name__ == "__main__":
    unittest.main()
