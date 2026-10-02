import unittest

from rudrila_mev.all_cost_profit import (
    evaluate_all_cost_profit,
    missing_route_profit_evidence,
)


def good(**overrides):
    kw=dict(
        amount_in_wei=1_000_000,
        expected_final_wei=1_100_000,
        floor_final_wei=1_090_000,
        gas_cost_wei=10_000,
        builder_payment_wei=5_000,
        non_embedded_cost_wei=1_000,
        dex_fee_cost_wei=77_000,
        slippage_cost_wei=88_000,
        token_tax_cost_wei=99_000,
        safety_buffer_wei=4_000,
        min_net_profit_wei=20_000,
        route_output_embeds_dex_fees=True,
        floor_output_embeds_slippage=True,
        route_output_embeds_token_tax=True,
        quoted_block=100,
        current_block=100,
        max_quote_age_blocks=2,
    )
    kw.update(overrides)
    return evaluate_all_cost_profit(**kw)


class AllCostProfitTests(unittest.TestCase):
    def test_profitable_route_passes(self):
        e=good()
        self.assertTrue(e.accepted)
        self.assertGreaterEqual(e.floor_net_after_all_costs_wei,20_000)

    def test_embedded_costs_are_not_double_counted(self):
        e=good()
        self.assertEqual(e.dex_fee_deduction_wei,0)
        self.assertEqual(e.slippage_deduction_wei,0)
        self.assertEqual(e.token_tax_deduction_wei,0)

    def test_nonembedded_tax_is_subtracted_once(self):
        e=good(route_output_embeds_token_tax=False,token_tax_cost_wei=20_000)
        self.assertEqual(e.token_tax_deduction_wei,20_000)
        self.assertTrue(e.accepted)

    def test_unknown_nonembedded_tax_blocks(self):
        e=good(route_output_embeds_token_tax=False,token_tax_cost_wei=None)
        self.assertFalse(e.accepted)

    def test_unknown_builder_payment_blocks(self):
        self.assertFalse(good(builder_payment_wei=None).accepted)

    def test_unknown_gas_blocks(self):
        self.assertFalse(good(gas_cost_wei=None).accepted)

    def test_unknown_other_cost_blocks(self):
        self.assertFalse(good(non_embedded_cost_wei=None).accepted)

    def test_stale_economics_blocks(self):
        self.assertFalse(good(current_block=103,max_quote_age_blocks=2).accepted)

    def test_below_min_net_blocks(self):
        self.assertFalse(good(floor_final_wei=1_035_000).accepted)

    def test_floor_above_expected_blocks(self):
        self.assertFalse(good(floor_final_wei=1_110_000).accepted)

    def test_missing_route_is_fail_closed(self):
        e=missing_route_profit_evidence(amount_in_wei=100,current_block=1,min_net_profit_wei=1)
        self.assertFalse(e.accepted)
        self.assertIn("unavailable",e.reasons[0])

if __name__=="__main__":
    unittest.main()
