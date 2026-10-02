import unittest
from rudrila_mev.admin_safety import CAPABILITY_SIGNATURES, ZERO, classify_admin_evidence

TOKEN = "0x0000000000000000000000000000000000000001"

def base(**overrides):
    kwargs = dict(
        token=TOKEN, bytecode_present=True, owner=ZERO, admin=None,
        admin_read_resolved=True, is_proxy=False, proxy_kind=None,
        implementation=None, implementation_checked=True,
        hits={k: [] for k in CAPABILITY_SIGNATURES}, raw={},
    )
    kwargs.update(overrides)
    return classify_admin_evidence(**kwargs)

class AdminSafetyTests(unittest.TestCase):
    def test_safe_zero_owner_nonproxy_passes(self):
        ev = base()
        self.assertTrue(ev.accepted)
        self.assertTrue(ev.admin_safety_proven)

    def test_unknown_admin_blocks(self):
        ev = base(admin_read_resolved=False)
        self.assertFalse(ev.accepted)

    def test_nonzero_owner_blocks(self):
        ev = base(owner="0x0000000000000000000000000000000000000002")
        self.assertFalse(ev.accepted)

    def test_mint_blocks(self):
        h={k:[] for k in CAPABILITY_SIGNATURES}; h["mint"]=["mint(address,uint256)"]
        ev=base(hits=h); self.assertFalse(ev.accepted); self.assertTrue(ev.can_mint)

    def test_blacklist_blocks(self):
        h={k:[] for k in CAPABILITY_SIGNATURES}; h["blacklist"]=["setBlacklist(address,bool)"]
        ev=base(hits=h); self.assertFalse(ev.accepted); self.assertTrue(ev.can_blacklist)

    def test_pause_blocks(self):
        h={k:[] for k in CAPABILITY_SIGNATURES}; h["pause"]=["pause()"]
        ev=base(hits=h); self.assertFalse(ev.accepted); self.assertTrue(ev.can_pause_trading)

    def test_fee_change_blocks(self):
        h={k:[] for k in CAPABILITY_SIGNATURES}; h["fees"]=["setFees(uint256,uint256)"]
        ev=base(hits=h); self.assertFalse(ev.accepted); self.assertTrue(ev.can_change_fees)

    def test_limits_change_blocks(self):
        h={k:[] for k in CAPABILITY_SIGNATURES}; h["limits"]=["setMaxTxAmount(uint256)"]
        ev=base(hits=h); self.assertFalse(ev.accepted); self.assertTrue(ev.can_change_max_tx_or_wallet)

    def test_proxy_without_impl_verification_blocks(self):
        ev=base(is_proxy=True,proxy_kind="EIP1967_IMPLEMENTATION",
                implementation="0x0000000000000000000000000000000000000003",
                implementation_checked=False)
        self.assertFalse(ev.accepted)

    def test_verified_proxy_still_blocks_under_strict_policy(self):
        ev=base(is_proxy=True,proxy_kind="EIP1967_IMPLEMENTATION",
                implementation="0x0000000000000000000000000000000000000003",
                implementation_checked=True)
        self.assertFalse(ev.accepted)

    def test_unknown_proxy_state_blocks(self):
        ev=base(is_proxy=None,implementation_checked=False)
        self.assertFalse(ev.accepted)

if __name__ == "__main__":
    unittest.main()
