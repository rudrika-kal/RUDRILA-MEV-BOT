import unittest
from types import SimpleNamespace

from rudrila_mev.backrun import BackrunCandidate, evaluate_legitimate_backrun
from rudrila_mev.postbuy_live import evaluate_live_postbuy_authorization
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


def firewall(ok=True, buy_tax=0, sell_tax=0):
    return SimpleNamespace(
        accepted=ok,
        buy_tax_bps=buy_tax,
        sell_tax_bps=sell_tax,
        reasons=("PASS",) if ok else ("BLOCK: firewall",),
    )


def quote(ok=True, block=101, amount=10**15):
    profit = SimpleNamespace(
        accepted=ok,
        required_gross_profit_wei=300 if ok else None,
        reasons=("PASS",) if ok else ("BLOCK: profit",),
    )
    return SimpleNamespace(
        quoted_block=block,
        amount_in_wei=amount,
        profit=profit,
    )


def private(ok=True, public=False):
    return SimpleNamespace(
        accepted=ok,
        public_mempool_fallback_allowed=public,
    )


def risk(blocked=False):
    return SimpleNamespace(
        blocked=blocked,
        reasons=("KILL",) if blocked else ("PASS",),
    )


class PostBuyLiveAuthorizationTests(unittest.TestCase):
    def call(self, **overrides):
        args = dict(
            trigger=confirmed(),
            current_block=101,
            firewall=firewall(),
            quote=quote(),
            private_paths=private(),
            execution_risk=risk(),
            executor_paused=False,
            owner_matches=True,
            routers_allowlisted=True,
            allowance_wei=10**15,
            max_amount_in_wei=10**15,
        )
        args.update(overrides)
        return evaluate_live_postbuy_authorization(**args)

    def test_all_live_gates_pass(self):
        self.assertTrue(self.call().accepted)

    def test_paused_executor_blocks(self):
        self.assertFalse(self.call(executor_paused=True).accepted)

    def test_taxed_token_blocks_current_executor(self):
        self.assertFalse(self.call(firewall=firewall(buy_tax=100, sell_tax=100)).accepted)

    def test_public_mempool_fallback_blocks(self):
        self.assertFalse(self.call(private_paths=private(public=True)).accepted)

    def test_canary_cap_blocks_larger_size(self):
        self.assertFalse(self.call(quote=quote(amount=10**15 + 1)).accepted)

    def test_stale_or_pretrigger_quote_blocks(self):
        self.assertFalse(self.call(current_block=103, quote=quote(block=101)).accepted)
        self.assertFalse(self.call(quote=quote(block=100)).accepted)

    def test_insufficient_allowance_blocks(self):
        self.assertFalse(self.call(allowance_wei=10**15 - 1).accepted)

    def test_profit_gate_blocks(self):
        self.assertFalse(self.call(quote=quote(ok=False)).accepted)

    def test_kill_switch_blocks(self):
        self.assertFalse(self.call(execution_risk=risk(True)).accepted)

    def test_next_block_backrun_does_not_reuse_trigger_index_order(self):
        c = BackrunCandidate(
            trigger_hash="0x" + "34" * 32,
            trigger_block=101,
            observed_block=102,
            trigger_index=50,
            execution_index=0,
            expected_gross_wei=1000,
            gas_wei=100,
            builder_bid_wei=50,
            safety_buffer_wei=50,
            min_net_profit_wei=500,
            user_harm_wei=0,
        )
        self.assertTrue(evaluate_legitimate_backrun(c).accepted)


if __name__ == "__main__":
    unittest.main()
