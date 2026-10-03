import unittest

from rudrila_mev.postbuy_trigger import (
    ConfirmedLargeBuy,
    PendingLargeBuy,
    post_confirmation_gate,
)


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


class PostConfirmationGateTests(unittest.TestCase):
    def test_pending_never_authorizes_post_trigger_evaluation(self):
        ok, reason = post_confirmation_gate(pending(), current_block=100)
        self.assertFalse(ok)
        self.assertIn("pending", reason.lower())

    def test_confirmed_success_allows_post_trigger_evaluation(self):
        c = ConfirmedLargeBuy(
            pending=pending(),
            block_number=101,
            transaction_index=3,
            observed_block=101,
            confirmations=1,
            receipt_status=1,
        )
        ok, _ = post_confirmation_gate(c, current_block=101)
        self.assertTrue(ok)

    def test_state_before_trigger_is_blocked(self):
        c = ConfirmedLargeBuy(
            pending=pending(),
            block_number=101,
            transaction_index=3,
            observed_block=101,
            confirmations=1,
            receipt_status=1,
        )
        ok, _ = post_confirmation_gate(c, current_block=100)
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
