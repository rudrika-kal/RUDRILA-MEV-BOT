import unittest
from types import SimpleNamespace

from rudrila_mev.postbuy_shadow_pipeline import evaluate_postbuy_shadow_candidate
from rudrila_mev.postbuy_trigger import ConfirmedLargeBuy, PendingLargeBuy


def pending():
    return PendingLargeBuy(
        tx_hash="0x" + "12" * 32,
        router="0x10ED43C718714eb63d5aA57B78B54704E256024E",
        sender="0x0000000000000000000000000000000000000001",
        base_token="0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
        token="0x0000000000000000000000000000000000000002",
        path=(
            "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
            "0x0000000000000000000000000000000000000002",
        ),
        amount_in_wei=10**18,
        observed_pending_block=100,
        deadline=999,
        swap_signature="swapExactETHForTokens(uint256,address[],address,uint256)",
        amount_is_maximum=False,
        tx_value_wei=10**18,
    )


def confirmed():
    return ConfirmedLargeBuy(
        pending=pending(),
        block_number=101,
        transaction_index=3,
        observed_block=101,
        confirmations=1,
        receipt_status=1,
    )


def firewall(ok=True):
    return SimpleNamespace(
        accepted=ok,
        reasons=("PASS",) if ok else ("BLOCK: token firewall",),
    )


def profit(ok=True):
    return SimpleNamespace(
        accepted=ok,
        floor_net_after_all_costs_wei=250 if ok else -1,
        reasons=("PASS",) if ok else ("BLOCK: net profit",),
    )


def private_paths(ok=True, public=False):
    return SimpleNamespace(
        accepted=ok,
        public_mempool_fallback_allowed=public,
        reasons=("PASS",) if ok else ("BLOCK: private paths",),
    )


def risk(blocked=False):
    return SimpleNamespace(
        blocked=blocked,
        reasons=("PASS",) if not blocked else ("KILL: risk limit",),
    )


class PostBuyShadowPipelineTests(unittest.TestCase):
    def test_all_gates_pass_for_simulation(self):
        d = evaluate_postbuy_shadow_candidate(
            trigger=confirmed(),
            current_block=101,
            firewall=firewall(),
            route_id="pancake-to-biswap",
            profit=profit(),
            private_paths=private_paths(),
            execution_risk=risk(),
        )
        self.assertTrue(d.accepted_for_simulation)
        self.assertEqual(d.expected_floor_net_wei, 250)

    def test_pending_trigger_blocks(self):
        d = evaluate_postbuy_shadow_candidate(
            trigger=pending(),
            current_block=100,
            firewall=firewall(),
            route_id="pancake-to-biswap",
            profit=profit(),
            private_paths=private_paths(),
            execution_risk=risk(),
        )
        self.assertFalse(d.accepted_for_simulation)

    def test_public_fallback_blocks(self):
        d = evaluate_postbuy_shadow_candidate(
            trigger=confirmed(),
            current_block=101,
            firewall=firewall(),
            route_id="pancake-to-biswap",
            profit=profit(),
            private_paths=private_paths(ok=True, public=True),
            execution_risk=risk(),
        )
        self.assertFalse(d.accepted_for_simulation)

    def test_profit_failure_blocks(self):
        d = evaluate_postbuy_shadow_candidate(
            trigger=confirmed(),
            current_block=101,
            firewall=firewall(),
            route_id="pancake-to-biswap",
            profit=profit(False),
            private_paths=private_paths(),
            execution_risk=risk(),
        )
        self.assertFalse(d.accepted_for_simulation)


if __name__ == "__main__":
    unittest.main()
