from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PoolKey:
    dex: str
    pool: str


@dataclass(frozen=True)
class PoolState:
    key: PoolKey
    kind: str
    token0: str
    token1: str
    fee_bps: int
    block_number: int
    reserve0: int | None = None
    reserve1: int | None = None
    sqrt_price_x96: int | None = None
    liquidity: int | None = None
    tick: int | None = None


@dataclass
class InMemoryMarketState:
    pools: dict[PoolKey, PoolState] = field(default_factory=dict)
    adjacency: dict[str, set[PoolKey]] = field(
        default_factory=dict
    )
    changed: set[PoolKey] = field(default_factory=set)

    def upsert(self, state: PoolState) -> bool:
        old = self.pools.get(state.key)
        if (
            old is not None
            and int(state.block_number) < int(old.block_number)
        ):
            return False
        self.pools[state.key] = state
        self.adjacency.setdefault(
            state.token0.lower(), set()
        ).add(state.key)
        self.adjacency.setdefault(
            state.token1.lower(), set()
        ).add(state.key)
        self.changed.add(state.key)
        return True

    def neighbors(self, token: str) -> tuple[PoolState, ...]:
        keys = self.adjacency.get(token.lower(), set())
        return tuple(self.pools[x] for x in keys)

    def consume_changed(self) -> tuple[PoolState, ...]:
        rows = tuple(self.pools[x] for x in self.changed)
        self.changed.clear()
        return rows
