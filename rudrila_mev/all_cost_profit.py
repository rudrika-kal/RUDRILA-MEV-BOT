from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class AllCostProfitEvidence:
    accepted: bool
    amount_in_wei: int
    expected_final_wei: int
    floor_final_wei: int
    expected_gross_profit_wei: int
    floor_gross_profit_wei: int
    gas_cost_wei: int | None
    builder_payment_wei: int | None
    non_embedded_cost_wei: int | None
    dex_fee_deduction_wei: int | None
    slippage_deduction_wei: int | None
    token_tax_deduction_wei: int | None
    safety_buffer_wei: int
    min_net_profit_wei: int
    required_gross_profit_wei: int | None
    floor_net_after_all_costs_wei: int | None
    quoted_block: int | None
    current_block: int | None
    quote_age_blocks: int | None
    route_output_embeds_dex_fees: bool
    floor_output_embeds_slippage: bool
    route_output_embeds_token_tax: bool
    reasons: tuple[str, ...]
    raw: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _cost(
    *,
    embedded: bool,
    explicit_cost_wei: int | None,
    label: str,
    reasons: list[str],
) -> int | None:
    if embedded:
        # Critical no-double-count rule: an embedded cost is never subtracted again.
        return 0
    if explicit_cost_wei is None:
        reasons.append(f"BLOCK: {label} is not embedded and explicit cost is unknown")
        return None
    if int(explicit_cost_wei) < 0:
        reasons.append(f"BLOCK: {label} cost cannot be negative")
        return None
    return int(explicit_cost_wei)


def evaluate_all_cost_profit(
    *,
    amount_in_wei: int,
    expected_final_wei: int,
    floor_final_wei: int,
    gas_cost_wei: int | None,
    builder_payment_wei: int | None,
    non_embedded_cost_wei: int | None,
    dex_fee_cost_wei: int | None,
    slippage_cost_wei: int | None,
    token_tax_cost_wei: int | None,
    safety_buffer_wei: int,
    min_net_profit_wei: int,
    route_output_embeds_dex_fees: bool,
    floor_output_embeds_slippage: bool,
    route_output_embeds_token_tax: bool,
    quoted_block: int | None = None,
    current_block: int | None = None,
    max_quote_age_blocks: int = 1,
    raw: dict[str, Any] | None = None,
) -> AllCostProfitEvidence:
    reasons: list[str] = []
    vals = {
        "amount_in_wei": amount_in_wei,
        "expected_final_wei": expected_final_wei,
        "floor_final_wei": floor_final_wei,
        "safety_buffer_wei": safety_buffer_wei,
        "min_net_profit_wei": min_net_profit_wei,
    }
    if any(int(v) < 0 for v in vals.values()):
        reasons.append("BLOCK: monetary values cannot be negative")
    if int(amount_in_wei) <= 0:
        reasons.append("BLOCK: amount in must be positive")
    if int(floor_final_wei) > int(expected_final_wei):
        reasons.append("BLOCK: floor output cannot exceed expected output")

    gas = None if gas_cost_wei is None else int(gas_cost_wei)
    builder = None if builder_payment_wei is None else int(builder_payment_wei)
    other = None if non_embedded_cost_wei is None else int(non_embedded_cost_wei)
    if gas is None:
        reasons.append("BLOCK: gas cost is unknown")
    elif gas < 0:
        reasons.append("BLOCK: gas cost cannot be negative")
        gas = None
    if builder is None:
        reasons.append("BLOCK: builder/private-submission payment is unknown")
    elif builder < 0:
        reasons.append("BLOCK: builder payment cannot be negative")
        builder = None
    if other is None:
        reasons.append("BLOCK: non-embedded protocol/relay costs are unknown")
    elif other < 0:
        reasons.append("BLOCK: non-embedded cost cannot be negative")
        other = None

    dex = _cost(
        embedded=bool(route_output_embeds_dex_fees),
        explicit_cost_wei=dex_fee_cost_wei,
        label="DEX fee",
        reasons=reasons,
    )
    slip = _cost(
        embedded=bool(floor_output_embeds_slippage),
        explicit_cost_wei=slippage_cost_wei,
        label="slippage",
        reasons=reasons,
    )
    tax = _cost(
        embedded=bool(route_output_embeds_token_tax),
        explicit_cost_wei=token_tax_cost_wei,
        label="token tax",
        reasons=reasons,
    )

    age = None
    if quoted_block is None or current_block is None:
        reasons.append("BLOCK: quote block freshness is unknown")
    else:
        age = max(0, int(current_block) - int(quoted_block))
        if age > int(max_quote_age_blocks):
            reasons.append(
                f"BLOCK: route economics stale by {age} blocks; maximum "
                f"{int(max_quote_age_blocks)}"
            )

    expected_gross = int(expected_final_wei) - int(amount_in_wei)
    floor_gross = int(floor_final_wei) - int(amount_in_wei)
    if floor_gross <= 0:
        reasons.append("BLOCK: worst-case route has no positive gross profit")

    deductions = (gas, builder, other, dex, slip, tax)
    required_gross = None
    floor_net = None
    if all(v is not None for v in deductions):
        explicit = sum(int(v) for v in deductions)
        required_gross = explicit + int(safety_buffer_wei) + int(min_net_profit_wei)
        floor_net = floor_gross - explicit - int(safety_buffer_wei)
        if floor_net < int(min_net_profit_wei):
            reasons.append(
                f"BLOCK: floor net profit {floor_net} below minimum "
                f"{int(min_net_profit_wei)}"
            )

    accepted = not reasons
    if accepted:
        reasons.append(
            "PASS: floor output covers gas, builder/private payment, non-embedded "
            "costs, non-embedded taxes/fees, safety buffer and minimum net profit"
        )

    return AllCostProfitEvidence(
        accepted=accepted,
        amount_in_wei=int(amount_in_wei),
        expected_final_wei=int(expected_final_wei),
        floor_final_wei=int(floor_final_wei),
        expected_gross_profit_wei=expected_gross,
        floor_gross_profit_wei=floor_gross,
        gas_cost_wei=gas,
        builder_payment_wei=builder,
        non_embedded_cost_wei=other,
        dex_fee_deduction_wei=dex,
        slippage_deduction_wei=slip,
        token_tax_deduction_wei=tax,
        safety_buffer_wei=int(safety_buffer_wei),
        min_net_profit_wei=int(min_net_profit_wei),
        required_gross_profit_wei=required_gross,
        floor_net_after_all_costs_wei=floor_net,
        quoted_block=int(quoted_block) if quoted_block is not None else None,
        current_block=int(current_block) if current_block is not None else None,
        quote_age_blocks=age,
        route_output_embeds_dex_fees=bool(route_output_embeds_dex_fees),
        floor_output_embeds_slippage=bool(floor_output_embeds_slippage),
        route_output_embeds_token_tax=bool(route_output_embeds_token_tax),
        reasons=tuple(reasons),
        raw=dict(raw or {}),
    )


def missing_route_profit_evidence(
    *,
    amount_in_wei: int,
    current_block: int | None,
    min_net_profit_wei: int,
    reason: str = "BLOCK: executable route economics are unavailable",
) -> AllCostProfitEvidence:
    return AllCostProfitEvidence(
        accepted=False,
        amount_in_wei=int(amount_in_wei),
        expected_final_wei=0,
        floor_final_wei=0,
        expected_gross_profit_wei=-int(amount_in_wei),
        floor_gross_profit_wei=-int(amount_in_wei),
        gas_cost_wei=None,
        builder_payment_wei=None,
        non_embedded_cost_wei=None,
        dex_fee_deduction_wei=None,
        slippage_deduction_wei=None,
        token_tax_deduction_wei=None,
        safety_buffer_wei=0,
        min_net_profit_wei=int(min_net_profit_wei),
        required_gross_profit_wei=None,
        floor_net_after_all_costs_wei=None,
        quoted_block=None,
        current_block=int(current_block) if current_block is not None else None,
        quote_age_blocks=None,
        route_output_embeds_dex_fees=False,
        floor_output_embeds_slippage=False,
        route_output_embeds_token_tax=False,
        reasons=(reason,),
        raw={},
    )
