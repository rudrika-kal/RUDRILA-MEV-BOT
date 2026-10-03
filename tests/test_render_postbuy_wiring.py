import unittest

import render_monitor


class RenderPostBuyWiringTests(unittest.TestCase):
    def test_postbuy_shadow_is_embedded_and_read_only(self):
        self.assertTrue(hasattr(render_monitor, "POSTBUY_SHADOW"))
        state = render_monitor.POSTBUY_SHADOW.STATE
        self.assertFalse(state["live_trading"])
        self.assertFalse(state["private_key_loaded"])
        self.assertFalse(state["submission_attempted"])
        self.assertFalse(state["public_mempool_fallback_allowed"])


if __name__ == "__main__":
    unittest.main()
