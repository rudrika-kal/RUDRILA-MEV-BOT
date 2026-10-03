from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations


@dataclass(frozen=True)
class OpportunityNode:
    opportunity_id: str
    expected_net_wei: int
    dependencies: frozenset[str] = frozenset()
    resources: frozenset[str] = frozenset()


@dataclass(frozen=True)
class AtomicPlan:
    nodes: tuple[OpportunityNode, ...]
    expected_net_wei: int


def _valid(nodes: tuple[OpportunityNode, ...]) -> bool:
    ids = {x.opportunity_id for x in nodes}
    used: set[str] = set()
    for node in nodes:
        if not node.dependencies.issubset(ids):
            return False
        if used.intersection(node.resources):
            return False
        used.update(node.resources)
    return True


def best_atomic_plan(candidates: list[OpportunityNode], *, max_nodes: int = 6) -> AtomicPlan | None:
    positive = [x for x in candidates if x.expected_net_wei > 0]
    if len(positive) > 14:
        positive = sorted(positive, key=lambda x: x.expected_net_wei, reverse=True)[:14]
    best: AtomicPlan | None = None
    limit = min(max_nodes, len(positive))
    for size in range(1, limit + 1):
        for combo in combinations(positive, size):
            if not _valid(combo):
                continue
            net = sum(x.expected_net_wei for x in combo)
            if best is None or net > best.expected_net_wei:
                best = AtomicPlan(tuple(combo), net)
    return best
