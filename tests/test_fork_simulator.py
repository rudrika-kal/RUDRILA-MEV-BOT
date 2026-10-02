import unittest

from rudrila_mev.fork_simulator import evaluate_roundtrip


class ForkSimulationGuardTests(unittest.TestCase):
    def test_roundtrip_passes_with_small_loss(self):
        accepted, loss_bps, reason = evaluate_roundtrip(
            amount_in_wei=10_000,
            buy_received_raw=20_000,
            base_received_back_wei=9_950,
            max_roundtrip_loss_bps=1200,
        )
        self.assertTrue(accepted)
        self.assertEqual(loss_bps, 50)
        self.assertIn("PASS", reason)

    def test_zero_buy_blocks(self):
        accepted, _, reason = evaluate_roundtrip(
            amount_in_wei=10_000,
            buy_received_raw=0,
            base_received_back_wei=9_900,
            max_roundtrip_loss_bps=1200,
        )
        self.assertFalse(accepted)
        self.assertIn("zero tokens", reason)

    def test_zero_sell_blocks(self):
        accepted, _, reason = evaluate_roundtrip(
            amount_in_wei=10_000,
            buy_received_raw=20_000,
            base_received_back_wei=0,
            max_roundtrip_loss_bps=1200,
        )
        self.assertFalse(accepted)
        self.assertIn("zero base token", reason)

    def test_excessive_loss_blocks(self):
        accepted, loss_bps, reason = evaluate_roundtrip(
            amount_in_wei=10_000,
            buy_received_raw=20_000,
            base_received_back_wei=7_000,
            max_roundtrip_loss_bps=1200,
        )
        self.assertFalse(accepted)
        self.assertEqual(loss_bps, 3000)
        self.assertIn("exceeds limit", reason)


if __name__ == "__main__":
    unittest.main()
