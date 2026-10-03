import unittest

from rudrila_mev.ethereum_prelive import evaluate_ethereum_prelive


BASE = dict(
    python_tests_ok=True,
    rust_tests_ok=True,
    solidity_tests_ok=True,
    mainnet_quote_ok=True,
    local_fork_ok=True,
    redundant_rpc_ok=True,
    mev_share_sim_ok=True,
    redundant_builders_ok=True,
    aave_runtime_ok=True,
    morpho_runtime_ok=True,
    dashboard_ok=True,
)


class EthereumPreLiveTests(unittest.TestCase):
    def test_non_wallet_clear_waits_only_for_wallet_stage(self):
        d = evaluate_ethereum_prelive(
            **BASE,
            wallet_connected=False,
            executor_deployed=False,
            signer_configured=False,
            live_canary_enabled=False,
        )
        self.assertTrue(d.non_wallet_ready)
        self.assertFalse(d.canary_ready)
        self.assertEqual(d.state, "WAITING_FOR_WALLET")
        self.assertEqual(len(d.reasons), 4)

    def test_missing_non_wallet_gate_blocks(self):
        x = dict(BASE)
        x["redundant_rpc_ok"] = False
        d = evaluate_ethereum_prelive(
            **x,
            wallet_connected=False,
            executor_deployed=False,
            signer_configured=False,
            live_canary_enabled=False,
        )
        self.assertFalse(d.non_wallet_ready)
        self.assertEqual(d.state, "BLOCKED_NON_WALLET")

    def test_all_gates_canary_ready(self):
        d = evaluate_ethereum_prelive(
            **BASE,
            wallet_connected=True,
            executor_deployed=True,
            signer_configured=True,
            live_canary_enabled=True,
        )
        self.assertTrue(d.canary_ready)
        self.assertEqual(d.state, "CANARY_READY")


if __name__ == "__main__":
    unittest.main()
