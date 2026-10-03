import unittest
from rudrila_mev.private_submission import (
    PrivatePathEvidence, evaluate_private_paths,
)

def ev(name="x", ok=True):
    return PrivatePathEvidence(
        name=name,url="https://example.com",send_method="eth_sendRawTransaction",
        https=True,chain_id=56,chain_ok=True,method_supported=ok,
        private_path_verified=ok,error=None if ok else "unsupported",
    )

class PrivateSubmissionTests(unittest.TestCase):
    def test_two_private_paths_pass(self):
        r=evaluate_private_paths([ev("a"),ev("b")],required_paths=2)
        self.assertTrue(r.accepted)
        self.assertEqual(r.healthy_paths,2)

    def test_one_path_blocks(self):
        r=evaluate_private_paths([ev("a")],required_paths=2)
        self.assertFalse(r.accepted)

    def test_unhealthy_path_blocks(self):
        r=evaluate_private_paths([ev("a"),ev("b",False)],required_paths=2)
        self.assertFalse(r.accepted)

    def test_public_fallback_blocks(self):
        r=evaluate_private_paths([ev("a"),ev("b")],required_paths=2,
                                 public_mempool_fallback_allowed=True)
        self.assertFalse(r.accepted)

    def test_required_paths_cannot_be_one(self):
        r=evaluate_private_paths([ev("a")],required_paths=1)
        self.assertFalse(r.accepted)

if __name__=="__main__":
    unittest.main()
