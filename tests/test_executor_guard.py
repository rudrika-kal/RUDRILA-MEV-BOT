import unittest
from rudrila_mev.executor_guard import evaluate_executor_safety

def good(**overrides):
    kw=dict(
        executor_deployed=True,
        owner_matches=True,
        source_verified=True,
        behavioral_tests_passed=True,
        routers_allowlisted=True,
        paused_state_known=True,
        paused=False,
        dirty_balance_guard_verified=True,
        exact_approval_cleanup_verified=True,
        paused_rescue_verified=True,
        non_reentrant_verified=True,
    )
    kw.update(overrides)
    return evaluate_executor_safety(**kw)

class ExecutorGuardTests(unittest.TestCase):
    def test_all_evidence_passes(self):
        self.assertTrue(good().accepted)
    def test_missing_deploy_blocks(self):
        self.assertFalse(good(executor_deployed=False).accepted)
    def test_paused_blocks(self):
        self.assertFalse(good(paused=True).accepted)
    def test_unknown_pause_blocks(self):
        self.assertFalse(good(paused_state_known=False,paused=None).accepted)
    def test_owner_mismatch_blocks(self):
        self.assertFalse(good(owner_matches=False).accepted)
    def test_unverified_source_blocks(self):
        self.assertFalse(good(source_verified=None).accepted)
    def test_missing_behavior_tests_blocks(self):
        self.assertFalse(good(behavioral_tests_passed=None).accepted)
    def test_unallowlisted_router_blocks(self):
        self.assertFalse(good(routers_allowlisted=False).accepted)
    def test_dirty_guard_unknown_blocks(self):
        self.assertFalse(good(dirty_balance_guard_verified=None).accepted)
    def test_approval_cleanup_unknown_blocks(self):
        self.assertFalse(good(exact_approval_cleanup_verified=None).accepted)
    def test_rescue_guard_unknown_blocks(self):
        self.assertFalse(good(paused_rescue_verified=None).accepted)
    def test_reentrancy_unknown_blocks(self):
        self.assertFalse(good(non_reentrant_verified=None).accepted)

if __name__=="__main__":
    unittest.main()
