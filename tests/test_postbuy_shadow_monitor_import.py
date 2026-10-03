import unittest

import postbuy_shadow_monitor as monitor


class PostBuyShadowMonitorImportTests(unittest.TestCase):
    def test_runtime_is_read_only_by_construction(self):
        self.assertFalse(monitor.STATE["live_trading"])
        self.assertFalse(monitor.STATE["private_key_loaded"])
        self.assertFalse(monitor.STATE["submission_attempted"])
        self.assertFalse(monitor.STATE["public_mempool_fallback_allowed"])
        self.assertEqual(monitor.CHAIN_ID, 56)

    def test_builder_payment_unknown_fails_closed_by_default(self):
        if not monitor.BUILDER_PAYMENT_RAW.strip():
            self.assertIsNone(monitor.BUILDER_PAYMENT_WEI)


if __name__ == "__main__":
    unittest.main()
