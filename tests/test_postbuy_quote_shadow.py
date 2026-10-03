import unittest

from rudrila_mev.postbuy_quote_shadow import (
    ReadOnlyVenue,
    quote_postbuy_v2_routes_read_only,
)


P = "0x10ED43C718714eb63d5aA57B78B54704E256024E"
B = "0x3a6d8cA21D1CF76F653A67577FA0D27453350dD8"
W = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"
T = "0x0000000000000000000000000000000000000002"


class Call:
    def __init__(self, value):
        self.value = value

    def call(self, block_identifier=None):
        return self.value


class Functions:
    def __init__(self, address):
        self.address = address

    def getAmountsOut(self, amount, path):
        # P buy is strong, B sell is strong enough for a positive read-only route.
        if self.address.lower() == P.lower() and path[0].lower() == W.lower():
            return Call([amount, 1200])
        if self.address.lower() == B.lower() and path[0].lower() == T.lower():
            return Call([amount, 1300])
        # Opposite direction is deliberately weak.
        if self.address.lower() == B.lower() and path[0].lower() == W.lower():
            return Call([amount, 900])
        return Call([amount, 800])


class Contract:
    def __init__(self, address):
        self.functions = Functions(address)


class Eth:
    block_number = 100

    def contract(self, address, abi):
        return Contract(address)


class W3:
    eth = Eth()


class PostBuyQuoteShadowTests(unittest.TestCase):
    def test_quotes_both_directions_and_ranks_best(self):
        rows = quote_postbuy_v2_routes_read_only(
            W3(),
            venues=(ReadOnlyVenue("pancake", P), ReadOnlyVenue("biswap", B)),
            base_token=W,
            token=T,
            amount_in_wei=1000,
            slippage_bps_per_leg=0,
            buy_tax_bps=0,
            sell_tax_bps=0,
            gas_cost_wei=10,
            builder_payment_wei=0,
            safety_buffer_wei=10,
            min_net_profit_wei=100,
            max_quote_age_blocks=1,
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].route_id, "pancake->biswap")
        self.assertTrue(rows[0].profit.accepted)

    def test_unknown_builder_payment_fails_closed(self):
        rows = quote_postbuy_v2_routes_read_only(
            W3(),
            venues=(ReadOnlyVenue("pancake", P), ReadOnlyVenue("biswap", B)),
            base_token=W,
            token=T,
            amount_in_wei=1000,
            slippage_bps_per_leg=0,
            buy_tax_bps=0,
            sell_tax_bps=0,
            gas_cost_wei=10,
            builder_payment_wei=None,
            safety_buffer_wei=10,
            min_net_profit_wei=100,
        )
        self.assertTrue(rows)
        self.assertFalse(rows[0].profit.accepted)


if __name__ == "__main__":
    unittest.main()
