import unittest

from rudrila_mev.launch_guard import evaluate_new_token


class LaunchGuardTests(unittest.TestCase):
    def test_unknown_sellability_is_blocked(self):
        d = evaluate_new_token(
            basic_checks_passed=True,
            sell_simulation_passed=False,
            base_liquidity_wei=10,
            min_base_liquidity_wei=5,
            require_sell_simulation=True,
        )
        self.assertFalse(d.accepted_for_live)
        self.assertIn("sellability", d.reason)

    def test_low_liquidity_is_blocked(self):
        d = evaluate_new_token(
            basic_checks_passed=True,
            sell_simulation_passed=True,
            base_liquidity_wei=4,
            min_base_liquidity_wei=5,
            require_sell_simulation=True,
        )
        self.assertFalse(d.accepted_for_live)
        self.assertIn("liquidity", d.reason)

    def test_all_gates_pass(self):
        d = evaluate_new_token(
            basic_checks_passed=True,
            sell_simulation_passed=True,
            base_liquidity_wei=10,
            min_base_liquidity_wei=5,
            require_sell_simulation=True,
        )
        self.assertTrue(d.accepted_for_live)


if __name__ == "__main__":
    unittest.main()
