from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ContractRiskEvidence:
    # Honeypot / sellability
    buy_simulation_passed: bool | None = None
    sell_simulation_passed: bool | None = None
    transfer_out_passed: bool | None = None

    # Tax / transfer behavior
    buy_tax_bps: int | None = None
    sell_tax_bps: int | None = None
    roundtrip_loss_bps: int | None = None
    dynamic_tax_suspected: bool | None = None

    # Rug-pull / liquidity controls
    liquidity_lock_or_burn_proven: bool | None = None
    liquidity_removal_controlled_by_creator: bool | None = None

    # Admin / owner capabilities
    admin_safety_proven: bool | None = None
    can_mint: bool | None = None
    can_blacklist: bool | None = None
    can_pause_trading: bool | None = None
    can_change_fees: bool | None = None
    can_change_max_tx_or_wallet: bool | None = None

    # Proxy / upgradeability
    is_proxy: bool | None = None
    proxy_implementation_checked: bool | None = None

    # Generic bytecode / runtime checks
    bytecode_present: bool | None = None
    metadata_callable: bool | None = None


@dataclass(frozen=True)
class ContractRiskDecision:
    accepted: bool
    classification: str
    reasons: tuple[str, ...] = field(default_factory=tuple)


def assess_contract_risk(
    ev: ContractRiskEvidence,
    *,
    fail_closed_on_unknown: bool = True,
    require_honeypot_sell_simulation: bool = True,
    require_liquidity_lock_or_burn_proof: bool = True,
    require_admin_safety_proof: bool = True,
    max_combined_token_tax_bps: int = 800,
    max_roundtrip_loss_bps: int = 1200,
    block_proxy_tokens_without_impl_check: bool = True,
    block_tokens_with_mint_authority: bool = True,
    block_tokens_with_blacklist_authority: bool = True,
    block_tokens_with_trading_pause_authority: bool = True,
    block_tokens_with_fee_change_authority: bool = True,
    block_tokens_with_max_tx_or_wallet_authority: bool = True,
) -> ContractRiskDecision:
    reasons: list[str] = []

    def unknown(name: str, value) -> None:
        if value is None and fail_closed_on_unknown:
            reasons.append(f"UNKNOWN: {name}")

    # Basic contract validity
    if ev.bytecode_present is False:
        reasons.append("FAIL: token bytecode missing")
    unknown("token bytecode status", ev.bytecode_present)

    if ev.metadata_callable is False:
        reasons.append("FAIL: ERC-20 metadata calls failed")
    unknown("ERC-20 metadata status", ev.metadata_callable)

    # Honeypot checks
    if require_honeypot_sell_simulation:
        if ev.buy_simulation_passed is False:
            reasons.append("HONEYPOT_RISK: simulated buy failed")
        if ev.sell_simulation_passed is False:
            reasons.append("HONEYPOT_RISK: simulated sell failed")
        if ev.transfer_out_passed is False:
            reasons.append("HONEYPOT_RISK: post-buy transfer-out failed")
        unknown("buy simulation", ev.buy_simulation_passed)
        unknown("sell simulation", ev.sell_simulation_passed)
        unknown("transfer-out simulation", ev.transfer_out_passed)

    # Taxes and dynamic behavior
    if ev.dynamic_tax_suspected is True:
        reasons.append("RUG/HONEYPOT_RISK: dynamic tax behavior detected")
    unknown("dynamic-tax status", ev.dynamic_tax_suspected)

    if ev.buy_tax_bps is not None and ev.sell_tax_bps is not None:
        if int(ev.buy_tax_bps) + int(ev.sell_tax_bps) > int(max_combined_token_tax_bps):
            reasons.append("FAIL: combined token tax above limit")
    elif fail_closed_on_unknown:
        reasons.append("UNKNOWN: buy/sell tax not measured")

    if ev.roundtrip_loss_bps is not None:
        if int(ev.roundtrip_loss_bps) > int(max_roundtrip_loss_bps):
            reasons.append("FAIL: simulated round-trip loss above limit")
    elif fail_closed_on_unknown:
        reasons.append("UNKNOWN: round-trip loss not measured")

    # Liquidity / rug-pull protection
    if require_liquidity_lock_or_burn_proof:
        if ev.liquidity_lock_or_burn_proven is False:
            reasons.append("RUG_RISK: LP lock/burn proof failed")
        unknown("LP lock/burn proof", ev.liquidity_lock_or_burn_proven)

    if ev.liquidity_removal_controlled_by_creator is True:
        reasons.append("RUG_RISK: creator can remove liquidity")
    unknown("creator liquidity-removal control", ev.liquidity_removal_controlled_by_creator)

    # Admin controls
    if require_admin_safety_proof:
        if ev.admin_safety_proven is False:
            reasons.append("RUG_RISK: admin safety proof failed")
        unknown("admin safety proof", ev.admin_safety_proven)

    if block_tokens_with_mint_authority:
        if ev.can_mint is True:
            reasons.append("RUG_RISK: privileged mint capability")
        unknown("mint authority", ev.can_mint)

    if block_tokens_with_blacklist_authority:
        if ev.can_blacklist is True:
            reasons.append("HONEYPOT_RISK: blacklist authority")
        unknown("blacklist authority", ev.can_blacklist)

    if block_tokens_with_trading_pause_authority:
        if ev.can_pause_trading is True:
            reasons.append("RUG/HONEYPOT_RISK: trading pause authority")
        unknown("trading pause authority", ev.can_pause_trading)

    if block_tokens_with_fee_change_authority:
        if ev.can_change_fees is True:
            reasons.append("RUG/HONEYPOT_RISK: mutable fee authority")
        unknown("fee-change authority", ev.can_change_fees)

    if block_tokens_with_max_tx_or_wallet_authority:
        if ev.can_change_max_tx_or_wallet is True:
            reasons.append("RUG/HONEYPOT_RISK: mutable max-tx/max-wallet authority")
        unknown("max-tx/max-wallet authority", ev.can_change_max_tx_or_wallet)

    # Proxy / upgradeability
    if block_proxy_tokens_without_impl_check:
        if ev.is_proxy is True and ev.proxy_implementation_checked is not True:
            reasons.append("RUG_RISK: upgradeable proxy implementation not verified")
        unknown("proxy status", ev.is_proxy)
        if ev.is_proxy is True:
            unknown("proxy implementation check", ev.proxy_implementation_checked)

    if reasons:
        # Classification is intentionally broad and conservative.
        cls = "BLOCK"
        return ContractRiskDecision(False, cls, tuple(reasons))

    return ContractRiskDecision(
        True,
        "PASS",
        ("PASS: no configured honeypot/rug-pull risk gate failed",),
    )
