import unittest
from rudrila_mev.shadow_audit import (
    ShadowRecord, audit_shadow_records, deterministic_shadow_matrix,
)

def row(**kw):
    d=dict(
        candidate_id="x", dex="PANCAKESWAP_V2", trade_decision="NO_TRADE",
        live_trading=False, private_key_loaded=False,
        submission_attempted=False, public_mempool_allowed=False,
        prior_gates_passed=False, blocked_reasons=("BLOCK:test",),
    )
    d.update(kw)
    return ShadowRecord(**d)

class ShadowAuditTests(unittest.TestCase):
    def test_large_matrix_passes(self):
        a=audit_shadow_records(deterministic_shadow_matrix(5000),min_samples=5000)
        self.assertTrue(a.accepted)
        self.assertEqual(a.submission_attempts,0)
        self.assertEqual(a.no_trade_samples,5000)
        self.assertIn("PANCAKESWAP_V2",a.dex_counts)
        self.assertIn("PANCAKESWAP_V3",a.dex_counts)

    def test_small_sample_blocks(self):
        self.assertFalse(audit_shadow_records([row()],min_samples=2).accepted)

    def test_submission_attempt_blocks(self):
        rows=[row(submission_attempted=True),row(dex="PANCAKESWAP_V3")]
        self.assertFalse(audit_shadow_records(rows,min_samples=2).accepted)

    def test_live_mode_blocks(self):
        rows=[row(live_trading=True),row(dex="PANCAKESWAP_V3")]
        self.assertFalse(audit_shadow_records(rows,min_samples=2).accepted)

    def test_private_key_blocks(self):
        rows=[row(private_key_loaded=True),row(dex="PANCAKESWAP_V3")]
        self.assertFalse(audit_shadow_records(rows,min_samples=2).accepted)

    def test_public_mempool_blocks(self):
        rows=[row(public_mempool_allowed=True),row(dex="PANCAKESWAP_V3")]
        self.assertFalse(audit_shadow_records(rows,min_samples=2).accepted)

    def test_failed_gate_authorization_blocks(self):
        rows=[row(trade_decision="TRADE"),row(dex="PANCAKESWAP_V3")]
        self.assertFalse(audit_shadow_records(rows,min_samples=2).accepted)

if __name__=="__main__":
    unittest.main()
