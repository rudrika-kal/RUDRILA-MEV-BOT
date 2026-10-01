from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


def norm_addr(x: str) -> str:
    return x.lower()


@dataclass(frozen=True)
class CandidatePolicyDecision:
    accepted: bool
    reason: str


def candidate_policy(
    *,
    token: str,
    factory: str,
    current_block: int,
    discovered_block: int,
    confirmations: int,
    required_confirmations: int,
    max_age_blocks: int,
    denylist: Iterable[str],
    approved_factories: Iterable[str],
) -> CandidatePolicyDecision:
    token_l = norm_addr(token)
    factory_l = norm_addr(factory)
    deny = {norm_addr(x) for x in denylist}
    approved = {norm_addr(x) for x in approved_factories}

    if token_l in deny:
        return CandidatePolicyDecision(False, "REJECT: token is denylisted")
    if approved and factory_l not in approved:
        return CandidatePolicyDecision(False, "REJECT: factory is not allowlisted")

    age = int(current_block) - int(discovered_block)
    if age < 0:
        return CandidatePolicyDecision(False, "REJECT: candidate block is in the future")
    if age > int(max_age_blocks):
        return CandidatePolicyDecision(False, "REJECT: launch candidate is stale")
    if int(confirmations) < int(required_confirmations):
        return CandidatePolicyDecision(False, "REJECT: insufficient confirmations / reorg safety")

    return CandidatePolicyDecision(True, "PASS: candidate policy")
