import tempfile
import unittest
from pathlib import Path
from rudrila_mev import prelive_canary as p

class PreLiveCanaryTests(unittest.TestCase):
    def test_hard_canary_cap(self):
        self.assertLessEqual(p.CANARY_AMOUNT_WEI, 10**15)

    def test_public_mempool_is_hard_off(self):
        self.assertFalse(p.PUBLIC_MEMPOOL_FALLBACK)

    def test_two_router_addresses_are_distinct(self):
        self.assertNotEqual(p.PANCAKE_V2_ROUTER, p.BISWAP_V2_ROUTER)

    def test_reports_fail_closed_if_missing(self):
        with tempfile.TemporaryDirectory() as d:
            ok,reasons=p._reports_ok(Path(d))
            self.assertFalse(ok)
            self.assertTrue(reasons)

    def test_required_reports_cover_gates_5_to_14(self):
        names=" ".join(p.REQUIRED_REPORTS)
        for gate in ("095","096","097","098","099","0100","0110","0120","0130","0140"):
            self.assertIn(gate,names)

if __name__=="__main__":
    unittest.main()
