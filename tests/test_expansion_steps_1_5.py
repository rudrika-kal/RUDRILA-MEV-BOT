import unittest

from rudrila_mev.market_state import InMemoryMarketState, PoolKey, PoolState
from rudrila_mev.multihop import discover_cycles, evaluate_route
from rudrila_mev.rpc_quorum import RpcSnapshot, evaluate_rpc_quorum
from rudrila_mev.v3_adapter import encode_v3_path

A = "0x" + "11" * 20
B = "0x" + "22" * 20
C = "0x" + "33" * 20


class ExpansionStepsTests(unittest.TestCase):
    def test_step1_v3_path_encoding(self):
        path = encode_v3_path([A, B, C], [500, 3000])
        self.assertEqual(len(path), 66)

    def test_step3_rpc_quorum_prefers_local(self):
        rows = [
            RpcSnapshot("local", "http://127.0.0.1:8545", 1, 100, True),
            RpcSnapshot("backup", "https://example.invalid", 1, 100, False),
        ]
        decision = evaluate_rpc_quorum(rows, expected_chain_id=1)
        self.assertTrue(decision.accepted)
        self.assertEqual(decision.primary.name, "local")

    def test_step4_rejects_stale_pool_update(self):
        state = InMemoryMarketState()
        key = PoolKey("dex", "pool")
        self.assertTrue(state.upsert(PoolState(key, "v3", A, B, 5, 11)))
        self.assertFalse(state.upsert(PoolState(key, "v3", A, B, 5, 10)))

    def test_step5_triangular_route_profit_gate(self):
        state = InMemoryMarketState()
        for pool in [
            PoolState(PoolKey("dex1", "p1"), "v2", A, B, 30, 10),
            PoolState(PoolKey("dex2", "p2"), "v3", B, C, 5, 10),
            PoolState(PoolKey("dex3", "p3"), "v3", C, A, 30, 10),
        ]:
            self.assertTrue(state.upsert(pool))
        routes = discover_cycles(state, A, max_hops=3)
        route = next(x for x in routes if len(x.legs) == 3)
        decision = evaluate_route(route, 1000, lambda leg, amount: amount + 10,
                                  min_net_profit_wei=20)
        self.assertTrue(decision.accepted)
        self.assertEqual(decision.gross_profit, 30)


if __name__ == "__main__":
    unittest.main()
