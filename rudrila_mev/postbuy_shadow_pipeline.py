from __future__ import annotations

from dataclasses import dataclass

from .all_cost_profit import AllCostProfitEvidence
from .dynamic_firewall import DynamicTokenFirewallDecision
from .ledger import ExecutionRiskDecision
from .postbuy_trigger import ConfirmedLargeBuy, PendingLargeBuy, post_confirmation_gate
from .private_submission import PrivateSubmissionEvidence


@dataclass(frozen=True)
class PostBuyShadowDecision:
    accepted_for_simulation: bool
    trigger_hash: str
    token: str
    route_id: str | None
    expected_floor_net_wei: int | None
    reasons: tuple[str, ...]


def evaluate_postbuy_shadow_candidate(
    *,
    trigger: ConfirmedLargeBuy | PendingLargeBuy,
    current_block: int,
    firewall: DynamicTokenFirewallDecision,
    route_id: str | None,
    profit: AllCostProfitEvidence,
    private_paths: PrivateSubmissionEvidence,
    execution_risk: ExecutionRiskDecision,
) -> PostBuyShadowDecision:
    """Join all read-only gates for a confirmed post-buy candidate.

    This function authorizes simulation only. It deliberately does not sign,
    unpause, build or submit any transaction.
    """
    reasons: list[str] = []

    ok_trigger, trigger_reason = post_confirmation_gate(
        trigger, current_block=int(current_block)
    )
    if not ok_trigger:
        reasons.append(trigger_reason)

    if not firewall.accepted:
        reasons.append("BLOCK: dynamic token firewall failed")
        reasons.extend(firewall.reasons)

    if not profit.accepted:
        reasons.append("BLOCK: all-cost profitability gate failed")
        reasons.extend(profit.reasons)

    if not private_paths.accepted:
        reasons.append("BLOCK: private-path health gate failed")
        reasons.extend(private_paths.reasons)
    if private_paths.public_mempool_fallback_allowed:
        reasons.append("BLOCK: public-mempool fallback is enabled")

    if execution_risk.blocked:
        reasons.append("BLOCK: execution risk/kill switch is active")
        reasons.extend(execution_risk.reasons)

    if not route_id:
        reasons.append("BLOCK: no eligible post-buy route")

    # Remove duplicates while preserving diagnostic order.
    unique: list[str] = []
    seen: set[str] = set()
    for reason in reasons:
        if reason not in seen:
            unique.append(reason)
            seen.add(reason)

    if isinstance(trigger, ConfirmedLargeBuy):
        tx_hash = trigger.tx_hash
        token = trigger.token
    else:
        tx_hash = trigger.tx_hash
        token = trigger.token

    accepted = not unique
    if accepted:
        unique.append(
            "PASS: confirmed-trigger, token-safety, all-cost, private-path and "
            "kill-switch gates passed for read-only simulation"
        )

    return PostBuyShadowDecision(
        accepted_for_simulation=accepted,
        trigger_hash=tx_hash,
        token=token,
        route_id=route_id if accepted else None,
        expected_floor_net_wei=(
            int(profit.floor_net_after_all_costs_wei)
            if accepted and profit.floor_net_after_all_costs_wei is not None
            else None
        ),
        reasons=tuple(unique),
    )
