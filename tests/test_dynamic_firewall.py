import unittest
from types import SimpleNamespace

from rudrila_mev.dynamic_firewall import evaluate_dynamic_token_firewall
from rudrila_mev.launch_monitor import TokenPreflight


TOKEN = "0x0000000000000000000000000000000000000002"


def hp(ok=True):
    return SimpleNamespace(
        accepted=ok,
        simulation_success=ok,
        is_honeypot=False if ok else True,
        risk="low" if ok else "high",
        risk_level=0 if ok else 100,
        buy_tax_bps=0,
        sell_tax_bps=0,
        holder_failed=0,
        high_tax_wallets=0,
        reasons=("PASS",) if ok else ("BLOCK: honeypot",),
    )


def admin(ok=True):
    return SimpleNamespace(
        accepted=ok,
        admin_safety_proven=ok,
        can_mint=False,
        can_blacklist=False,
        can_pause_trading=False,
        can_change_fees=False,
        can_change_max_tx_or_wallet=False,
        is_proxy=False,
        implementation_checked=True,
        reasons=("PASS",) if ok else ("BLOCK: admin",),
    )


def liq(ok=True):
    return SimpleNamespace(
        accepted=ok,
        lock_or_burn_proven=True if ok else False,
        liquidity_removal_controlled_by_creator=False if ok else True,
        reasons=("PASS",) if ok else ("BLOCK: liquidity",),
    )


def impact(ok=True):
    return SimpleNamespace(
        accepted=ok,
        reasons=("PASS",) if ok else ("BLOCK: impact",),
    )


class DynamicFirewallTests(unittest.TestCase):
    def setUp(self):
        self.pf = TokenPreflight(
            True, TOKEN, 100, 18, "TEST", "PASS"
        )

    def test_all_required_evidence_accepts(self):
        d = evaluate_dynamic_token_firewall(
            preflight=self.pf,
            honeypot=hp(True),
            admin=admin(True),
            liquidity=(liq(True), liq(True)),
            impacts=(impact(True), impact(True)),
        )
        self.assertTrue(d.accepted)
        self.assertEqual(d.safe_pool_count, 2)

    def test_honeypot_failure_blocks(self):
        d = evaluate_dynamic_token_firewall(
            preflight=self.pf,
            honeypot=hp(False),
            admin=admin(True),
            liquidity=(liq(True), liq(True)),
            impacts=(impact(True), impact(True)),
        )
        self.assertFalse(d.accepted)

    def test_requires_two_safe_pools(self):
        d = evaluate_dynamic_token_firewall(
            preflight=self.pf,
            honeypot=hp(True),
            admin=admin(True),
            liquidity=(liq(True),),
            impacts=(impact(True),),
        )
        self.assertFalse(d.accepted)


if __name__ == "__main__":
    unittest.main()
