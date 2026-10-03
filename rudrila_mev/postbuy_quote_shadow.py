from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from web3 import Web3

from .abi import V2_ROUTER_ABI
from .all_cost_profit import AllCostProfitEvidence, evaluate_all_cost_profit


@dataclass(frozen=True)
class ReadOnlyVenue:
    name: str
    router: str


@dataclass(frozen=True)
class ReadOnlyPostBuyQuote:
    route_id: str
    buy_router: str
    sell_router: str
    quoted_block: int
    amount_in_wei: int
    expected_token_out: int
    expected_final_wei: int
    floor_token_out: int
    floor_final_wei: int
    profit: AllCostProfitEvidence


def _quote(router, amount_in: int, token_in: str, token_out: str, block: int) -> int:
    amounts = router.functions.getAmountsOut(
        int(amount_in),
        [Web3.to_checksum_address(token_in), Web3.to_checksum_address(token_out)],
    ).call(block_identifier=int(block))
    if len(amounts) < 2 or int(amounts[-1]) <= 0:
        raise RuntimeError("invalid read-only DEX quote")
    return int(amounts[-1])


def _haircut(value: int, bps: int) -> int:
    if not 0 <= int(bps) <= 10_000:
        raise ValueError("invalid bps")
    return int(value) * (10_000 - int(bps)) // 10_000


def quote_postbuy_v2_routes_read_only(
    w3: Web3,
    *,
    venues: Iterable[ReadOnlyVenue],
    base_token: str,
    token: str,
    amount_in_wei: int,
    slippage_bps_per_leg: int,
    buy_tax_bps: int,
    sell_tax_bps: int,
    gas_cost_wei: int,
    builder_payment_wei: int | None,
    safety_buffer_wei: int,
    min_net_profit_wei: int,
    max_quote_age_blocks: int = 1,
) -> tuple[ReadOnlyPostBuyQuote, ...]:
    """Quote fresh post-inclusion routes without building or submitting a tx."""
    base = Web3.to_checksum_address(base_token)
    quote_token = Web3.to_checksum_address(token)
    block = int(w3.eth.block_number)
    routers = [
        (
            v,
            w3.eth.contract(
                address=Web3.to_checksum_address(v.router),
                abi=V2_ROUTER_ABI,
            ),
        )
        for v in venues
    ]

    rows: list[ReadOnlyPostBuyQuote] = []
    for buy_venue, buy_router in routers:
        for sell_venue, sell_router in routers:
            if buy_venue.name == sell_venue.name:
                continue
            try:
                raw_token = _quote(
                    buy_router, amount_in_wei, base, quote_token, block
                )
                expected_token = _haircut(raw_token, buy_tax_bps)
                expected_final_raw = _quote(
                    sell_router, expected_token, quote_token, base, block
                )
                expected_final = _haircut(expected_final_raw, sell_tax_bps)

                floor_token = _haircut(raw_token, slippage_bps_per_leg)
                floor_token = _haircut(floor_token, buy_tax_bps)
                floor_final_raw = _quote(
                    sell_router, floor_token, quote_token, base, block
                )
                floor_final = _haircut(floor_final_raw, slippage_bps_per_leg)
                floor_final = _haircut(floor_final, sell_tax_bps)
                current_block = int(w3.eth.block_number)

                profit = evaluate_all_cost_profit(
                    amount_in_wei=int(amount_in_wei),
                    expected_final_wei=int(expected_final),
                    floor_final_wei=int(floor_final),
                    gas_cost_wei=int(gas_cost_wei),
                    builder_payment_wei=(
                        int(builder_payment_wei)
                        if builder_payment_wei is not None
                        else None
                    ),
                    non_embedded_cost_wei=0,
                    dex_fee_cost_wei=None,
                    slippage_cost_wei=None,
                    token_tax_cost_wei=None,
                    safety_buffer_wei=int(safety_buffer_wei),
                    min_net_profit_wei=int(min_net_profit_wei),
                    route_output_embeds_dex_fees=True,
                    floor_output_embeds_slippage=True,
                    route_output_embeds_token_tax=True,
                    quoted_block=block,
                    current_block=current_block,
                    max_quote_age_blocks=int(max_quote_age_blocks),
                    raw={
                        "mode": "READ_ONLY_POST_BUY_QUOTE",
                        "buy_venue": buy_venue.name,
                        "sell_venue": sell_venue.name,
                        "buy_tax_bps": int(buy_tax_bps),
                        "sell_tax_bps": int(sell_tax_bps),
                    },
                )
                rows.append(
                    ReadOnlyPostBuyQuote(
                        route_id=f"{buy_venue.name}->{sell_venue.name}",
                        buy_router=Web3.to_checksum_address(buy_venue.router),
                        sell_router=Web3.to_checksum_address(sell_venue.router),
                        quoted_block=block,
                        amount_in_wei=int(amount_in_wei),
                        expected_token_out=int(expected_token),
                        expected_final_wei=int(expected_final),
                        floor_token_out=int(floor_token),
                        floor_final_wei=int(floor_final),
                        profit=profit,
                    )
                )
            except Exception:
                continue

    return tuple(
        sorted(
            rows,
            key=lambda x: (
                x.profit.floor_net_after_all_costs_wei
                if x.profit.floor_net_after_all_costs_wei is not None
                else -(10**100)
            ),
            reverse=True,
        )
    )
