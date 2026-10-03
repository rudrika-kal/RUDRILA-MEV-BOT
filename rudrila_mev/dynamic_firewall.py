from __future__ import annotations

from dataclasses import dataclass

from .admin_safety import AdminSafetyEvidence
from .honeypot_client import HoneypotEvidence
from .launch_monitor import TokenPreflight
from .liquidity_impact import LiquidityImpactEvidence
from .liquidity_safety import LiquiditySafetyEvidence
from .risk_guard import ContractRiskDecision, ContractRiskEvidence, assess_contract_risk


@dataclass(frozen=True)
class DynamicTokenFirewallDecision:
    accepted: bool
    token: str
    buy_tax_bps: int | None
    sell_tax_bps: int | None
    safe_pool_count: int
    contract_risk: ContractRiskDecision
    reasons: tuple[str, ...]


def _all_false_or_none(values: tuple[bool | None, ...]) -> bool | None:
    if not values:
        return None
    if any(v is True for v in values):
        return True
    if all(v is False for v in values):
        return False
    return None


def evaluate_dynamic_token_firewall(
    *,
    preflight: TokenPreflight,
    honeypot: HoneypotEvidence,
    admin: AdminSafetyEvidence,
    liquidity: tuple[LiquiditySafetyEvidence, ...],
    impacts: tuple[LiquidityImpactEvidence, ...],
    min_safe_pools: int = 2,
    max_combined_token_tax_bps: int = 800,
    max_roundtrip_loss_bps: int = 1200,
) -> DynamicTokenFirewallDecision:
    """Fail-closed aggregation for arbitrary tokens.

    Unknown or stale evidence never authorizes a live trade. The caller may
    collect the expensive checks while the trigger is pending, but execution
    remains impossible until the trigger is confirmed separately.
    """

    reasons: list[str] = []
    if not preflight.accepted:
        reasons.append(f"BLOCK: basic token preflight failed: {preflight.reason}")
    if not honeypot.accepted:
        reasons.extend(honeypot.reasons)
    if not admin.accepted:
        reasons.extend(admin.reasons)

    safe_liq = [x for x in liquidity if x.accepted]
    safe_impacts = [x for x in impacts if x.accepted]
    if len(safe_liq) < int(min_safe_pools):
        reasons.append(
            f"BLOCK: only {len(safe_liq)} liquidity-safe pools; {int(min_safe_pools)} required"
        )
    if len(safe_impacts) < int(min_safe_pools):
        reasons.append(
            f"BLOCK: only {len(safe_impacts)} fresh low-impact pools; {int(min_safe_pools)} required"
        )
    for row in liquidity:
        if not row.accepted:
            reasons.extend(row.reasons)
    for row in impacts:
        if not row.accepted:
            reasons.extend(row.reasons)

    buy_tax = honeypot.buy_tax_bps
    sell_tax = honeypot.sell_tax_bps
    combined_tax = (
        int(buy_tax) + int(sell_tax)
        if buy_tax is not None and sell_tax is not None
        else None
    )

    liquidity_lock = (
        True
        if safe_liq and all(x.lock_or_burn_proven is True for x in safe_liq)
        else False
        if liquidity and any(x.lock_or_burn_proven is False for x in liquidity)
        else None
    )
    creator_remove = _all_false_or_none(
        tuple(x.liquidity_removal_controlled_by_creator for x in liquidity)
    )

    ev = ContractRiskEvidence(
        buy_simulation_passed=(
            True if honeypot.simulation_success and honeypot.is_honeypot is False else False
        ),
        sell_simulation_passed=(
            True if honeypot.simulation_success and honeypot.is_honeypot is False else False
        ),
        transfer_out_passed=(
            True
            if honeypot.holder_failed == 0 and honeypot.high_tax_wallets == 0
            else False
            if honeypot.holder_failed is not None or honeypot.high_tax_wallets is not None
            else None
        ),
        buy_tax_bps=buy_tax,
        sell_tax_bps=sell_tax,
        roundtrip_loss_bps=combined_tax,
        dynamic_tax_suspected=(
            False
            if buy_tax is not None
            and sell_tax is not None
            and honeypot.high_tax_wallets == 0
            else None
        ),
        liquidity_lock_or_burn_proven=liquidity_lock,
        liquidity_removal_controlled_by_creator=creator_remove,
        admin_safety_proven=admin.admin_safety_proven,
        can_mint=admin.can_mint,
        can_blacklist=admin.can_blacklist,
        can_pause_trading=admin.can_pause_trading,
        can_change_fees=admin.can_change_fees,
        can_change_max_tx_or_wallet=admin.can_change_max_tx_or_wallet,
        is_proxy=admin.is_proxy,
        proxy_implementation_checked=admin.implementation_checked,
        bytecode_present=preflight.code_bytes > 0,
        metadata_callable=preflight.decimals is not None,
    )
    contract = assess_contract_risk(
        ev,
        fail_closed_on_unknown=True,
        require_honeypot_sell_simulation=True,
        require_liquidity_lock_or_burn_proof=True,
        require_admin_safety_proof=True,
        max_combined_token_tax_bps=int(max_combined_token_tax_bps),
        max_roundtrip_loss_bps=int(max_roundtrip_loss_bps),
        block_proxy_tokens_without_impl_check=True,
        block_tokens_with_mint_authority=True,
        block_tokens_with_blacklist_authority=True,
        block_tokens_with_trading_pause_authority=True,
        block_tokens_with_fee_change_authority=True,
        block_tokens_with_max_tx_or_wallet_authority=True,
    )
    if not contract.accepted:
        reasons.extend(contract.reasons)

    # Preserve first-seen order while removing duplicate BLOCK reasons.
    unique: list[str] = []
    seen: set[str] = set()
    for reason in reasons:
        if reason not in seen:
            unique.append(reason)
            seen.add(reason)

    accepted = not unique and contract.accepted
    if accepted:
        unique.append(
            "PASS: honeypot/sellability, tax, liquidity, admin, proxy and impact gates passed"
        )

    return DynamicTokenFirewallDecision(
        accepted=accepted,
        token=preflight.token,
        buy_tax_bps=buy_tax,
        sell_tax_bps=sell_tax,
        safe_pool_count=min(len(safe_liq), len(safe_impacts)),
        contract_risk=contract,
        reasons=tuple(unique),
    )
