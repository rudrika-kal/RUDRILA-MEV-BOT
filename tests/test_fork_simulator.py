import unittest

from rudrila_mev.fork_simulator import (
    evaluate_roundtrip,
    evaluate_token_behavior,
    measure_tax_bps,
)


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

    def test_tax_measurement(self):
        self.assertEqual(measure_tax_bps(10_000, 9_800), 200)
        self.assertEqual(measure_tax_bps(10_000, 10_000), 0)
        self.assertEqual(measure_tax_bps(10_000, 10_050), 0)

    def test_transfer_failure_blocks(self):
        accepted, reason = evaluate_token_behavior(
            transfer_out_passed=False,
            buy_tax_bps=0,
            sell_tax_bps=0,
            transfer_tax_bps=0,
            max_combined_tax_bps=800,
            max_transfer_tax_bps=800,
        )
        self.assertFalse(accepted)
        self.assertIn("transfer-out", reason)

    def test_high_combined_tax_blocks(self):
        accepted, reason = evaluate_token_behavior(
            transfer_out_passed=True,
            buy_tax_bps=500,
            sell_tax_bps=400,
            transfer_tax_bps=0,
            max_combined_tax_bps=800,
            max_transfer_tax_bps=800,
        )
        self.assertFalse(accepted)
        self.assertIn("combined", reason)

    def test_missing_transfer_tax_blocks(self):
        accepted, reason = evaluate_token_behavior(
            transfer_out_passed=True,
            buy_tax_bps=0,
            sell_tax_bps=0,
            transfer_tax_bps=None,
            max_combined_tax_bps=800,
            max_transfer_tax_bps=800,
        )
        self.assertFalse(accepted)
        self.assertIn("missing", reason)

    def test_safe_behavior_passes(self):
        accepted, reason = evaluate_token_behavior(
            transfer_out_passed=True,
            buy_tax_bps=100,
            sell_tax_bps=100,
            transfer_tax_bps=50,
            max_combined_tax_bps=800,
            max_transfer_tax_bps=800,
        )
        self.assertTrue(accepted)
        self.assertIn("PASS", reason)


if __name__ == "__main__":
    unittest.main()
