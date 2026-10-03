import unittest
from rudrila_mev.canary_gate import evaluate_canary_readiness

GOOD=dict(
 prior_gates_passed=True,canary_mode=True,canary_amount_wei=10**15,
 wallet_configured=True,executor_configured=True,private_signing_configured=True,
 private_submission_configured=True,public_mempool_disabled=True,
 live_trading_enabled=True,
)

class CanaryGateTests(unittest.TestCase):
    def test_ready(self):
        self.assertTrue(evaluate_canary_readiness(**GOOD).ready)
    def test_missing_wallet_blocks(self):
        x=GOOD|{"wallet_configured":False}
        self.assertFalse(evaluate_canary_readiness(**x).ready)
    def test_missing_executor_blocks(self):
        x=GOOD|{"executor_configured":False}
        self.assertFalse(evaluate_canary_readiness(**x).ready)
    def test_missing_signer_blocks(self):
        x=GOOD|{"private_signing_configured":False}
        self.assertFalse(evaluate_canary_readiness(**x).ready)
    def test_missing_private_path_blocks(self):
        x=GOOD|{"private_submission_configured":False}
        self.assertFalse(evaluate_canary_readiness(**x).ready)
    def test_public_mempool_blocks(self):
        x=GOOD|{"public_mempool_disabled":False}
        self.assertFalse(evaluate_canary_readiness(**x).ready)
    def test_live_off_blocks(self):
        x=GOOD|{"live_trading_enabled":False}
        self.assertFalse(evaluate_canary_readiness(**x).ready)
    def test_amount_cap_blocks(self):
        x=GOOD|{"canary_amount_wei":10**15+1}
        self.assertFalse(evaluate_canary_readiness(**x).ready)

if __name__=="__main__":
    unittest.main()
