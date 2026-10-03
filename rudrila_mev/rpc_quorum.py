from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RpcSnapshot:
    name: str
    url: str
    chain_id: int
    block_number: int
    local: bool = False


@dataclass(frozen=True)
class RpcQuorumDecision:
    accepted: bool
    primary: RpcSnapshot | None
    healthy: tuple[RpcSnapshot, ...]
    reasons: tuple[str, ...]


def evaluate_rpc_quorum(
    snapshots: list[RpcSnapshot],
    *,
    expected_chain_id: int,
    min_healthy: int = 2,
    max_block_spread: int = 1,
    require_local_primary: bool = True,
) -> RpcQuorumDecision:
    good = [
        x for x in snapshots
        if int(x.chain_id) == int(expected_chain_id)
    ]
    reasons: list[str] = []
    if len(good) < int(min_healthy):
        reasons.append(
            f"BLOCK: only {len(good)} healthy RPCs; "
            f"{min_healthy} required"
        )
    if good:
        blocks = [int(x.block_number) for x in good]
        if max(blocks) - min(blocks) > int(max_block_spread):
            reasons.append(
                "BLOCK: RPC block disagreement exceeds limit"
            )
    local = [x for x in good if x.local]
    if require_local_primary and not local:
        reasons.append("BLOCK: no healthy local Ethereum node")
    primary = (
        max(local or good, key=lambda x: x.block_number)
        if good else None
    )
    if not reasons:
        reasons.append(
            "PASS: local primary + backup RPC quorum healthy"
        )
    return RpcQuorumDecision(
        not any(x.startswith("BLOCK:") for x in reasons),
        primary,
        tuple(good),
        tuple(reasons),
    )
