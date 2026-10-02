import unittest
from rudrila_mev.liquidity_impact import (
    _decision, price_impact_bps, v2_amount_out,
)

POOL="0x0000000000000000000000000000000000000001"

class LiquidityImpactTests(unittest.TestCase):
    def test_v2_amount_out_decreases_from_spot(self):
        out=v2_amount_out(1000,1_000_000,2_000_000,25)
        self.assertGreater(out,0)
        self.assertLess(out,2000)

    def test_impact_zero_for_linear_quote(self):
        self.assertEqual(price_impact_bps(amount_in=1000,amount_out=2000,probe_in=10,probe_out=20),0)

    def test_impact_detected(self):
        self.assertEqual(price_impact_bps(amount_in=1000,amount_out=1900,probe_in=10,probe_out=20),500)

    def test_low_liquidity_blocks(self):
        e=_decision(dex="V2",pool=POOL,block_number=10,latest_after=10,
          amount_in=1000,amount_out=1900,probe_in=10,probe_out=20,
          base_liquidity=99,active_liquidity=None,ticks_crossed=None,
          min_base_liquidity_wei=100,max_price_impact_bps=1000,
          max_quote_age_blocks=1,max_initialized_ticks_crossed=None,raw={})
        self.assertFalse(e.accepted)

    def test_high_impact_blocks(self):
        e=_decision(dex="V2",pool=POOL,block_number=10,latest_after=10,
          amount_in=1000,amount_out=1800,probe_in=10,probe_out=20,
          base_liquidity=1000,active_liquidity=None,ticks_crossed=None,
          min_base_liquidity_wei=100,max_price_impact_bps=500,
          max_quote_age_blocks=1,max_initialized_ticks_crossed=None,raw={})
        self.assertFalse(e.accepted)

    def test_stale_quote_blocks(self):
        e=_decision(dex="V2",pool=POOL,block_number=10,latest_after=12,
          amount_in=1000,amount_out=1990,probe_in=10,probe_out=20,
          base_liquidity=1000,active_liquidity=None,ticks_crossed=None,
          min_base_liquidity_wei=100,max_price_impact_bps=500,
          max_quote_age_blocks=1,max_initialized_ticks_crossed=None,raw={})
        self.assertFalse(e.accepted)

    def test_v3_zero_active_liquidity_blocks(self):
        e=_decision(dex="V3",pool=POOL,block_number=10,latest_after=10,
          amount_in=1000,amount_out=1990,probe_in=10,probe_out=20,
          base_liquidity=1000,active_liquidity=0,ticks_crossed=0,
          min_base_liquidity_wei=100,max_price_impact_bps=500,
          max_quote_age_blocks=1,max_initialized_ticks_crossed=8,raw={})
        self.assertFalse(e.accepted)

    def test_v3_excess_tick_crossing_blocks(self):
        e=_decision(dex="V3",pool=POOL,block_number=10,latest_after=10,
          amount_in=1000,amount_out=1990,probe_in=10,probe_out=20,
          base_liquidity=1000,active_liquidity=1000,ticks_crossed=9,
          min_base_liquidity_wei=100,max_price_impact_bps=500,
          max_quote_age_blocks=1,max_initialized_ticks_crossed=8,raw={})
        self.assertFalse(e.accepted)

    def test_safe_evidence_passes(self):
        e=_decision(dex="V3",pool=POOL,block_number=10,latest_after=10,
          amount_in=1000,amount_out=1990,probe_in=10,probe_out=20,
          base_liquidity=1000,active_liquidity=1000,ticks_crossed=1,
          min_base_liquidity_wei=100,max_price_impact_bps=500,
          max_quote_age_blocks=1,max_initialized_ticks_crossed=8,raw={})
        self.assertTrue(e.accepted)

if __name__=="__main__":
    unittest.main()
