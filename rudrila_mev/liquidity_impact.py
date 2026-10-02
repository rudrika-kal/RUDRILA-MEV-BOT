from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from web3 import Web3

BPS = 10_000
Q96 = 1 << 96

V2_PAIR_IMPACT_ABI = [
    {"inputs":[],"name":"token0","outputs":[{"type":"address","name":""}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"token1","outputs":[{"type":"address","name":""}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"getReserves","outputs":[{"type":"uint112","name":"reserve0"},{"type":"uint112","name":"reserve1"},{"type":"uint32","name":"blockTimestampLast"}],"stateMutability":"view","type":"function"},
]

V3_POOL_IMPACT_ABI = [
    {"inputs":[],"name":"token0","outputs":[{"type":"address","name":""}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"token1","outputs":[{"type":"address","name":""}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"fee","outputs":[{"type":"uint24","name":""}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"liquidity","outputs":[{"type":"uint128","name":""}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"slot0","outputs":[
        {"type":"uint160","name":"sqrtPriceX96"},{"type":"int24","name":"tick"},
        {"type":"uint16","name":"observationIndex"},{"type":"uint16","name":"observationCardinality"},
        {"type":"uint16","name":"observationCardinalityNext"},{"type":"uint32","name":"feeProtocol"},
        {"type":"bool","name":"unlocked"}],"stateMutability":"view","type":"function"},
]

V3_QUOTER_V2_ABI = [
    {"inputs":[{"components":[
        {"internalType":"address","name":"tokenIn","type":"address"},
        {"internalType":"address","name":"tokenOut","type":"address"},
        {"internalType":"uint256","name":"amountIn","type":"uint256"},
        {"internalType":"uint24","name":"fee","type":"uint24"},
        {"internalType":"uint160","name":"sqrtPriceLimitX96","type":"uint160"}],
        "internalType":"struct IQuoterV2.QuoteExactInputSingleParams","name":"params","type":"tuple"}],
     "name":"quoteExactInputSingle","outputs":[
        {"internalType":"uint256","name":"amountOut","type":"uint256"},
        {"internalType":"uint160","name":"sqrtPriceX96After","type":"uint160"},
        {"internalType":"uint32","name":"initializedTicksCrossed","type":"uint32"},
        {"internalType":"uint256","name":"gasEstimate","type":"uint256"}],
     "stateMutability":"nonpayable","type":"function"}
]


@dataclass(frozen=True)
class LiquidityImpactEvidence:
    accepted: bool
    dex: str
    pool: str
    block_number: int
    latest_block_after: int
    quote_age_blocks: int
    amount_in: int
    amount_out: int
    probe_amount_in: int
    probe_amount_out: int
    price_impact_bps: int | None
    base_liquidity_wei: int
    active_liquidity: int | None
    initialized_ticks_crossed: int | None
    reasons: tuple[str, ...]
    raw: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def price_impact_bps(*, amount_in: int, amount_out: int, probe_in: int, probe_out: int) -> int:
    if min(amount_in, amount_out, probe_in, probe_out) <= 0:
        raise ValueError("quote amounts must be positive")
    expected_out = amount_in * probe_out // probe_in
    if expected_out <= 0:
        raise ValueError("invalid marginal quote")
    if amount_out >= expected_out:
        return 0
    return (expected_out - amount_out) * BPS // expected_out


def v2_amount_out(amount_in: int, reserve_in: int, reserve_out: int, fee_bps: int) -> int:
    if min(amount_in, reserve_in, reserve_out) <= 0:
        raise ValueError("amount/reserves must be positive")
    if not 0 <= fee_bps < BPS:
        raise ValueError("invalid fee")
    effective = amount_in * (BPS - fee_bps)
    return effective * reserve_out // (reserve_in * BPS + effective)


def _probe_amount(amount_in: int) -> int:
    return max(1, amount_in // 1000)


def _decision(*, dex: str, pool: str, block_number: int, latest_after: int,
              amount_in: int, amount_out: int, probe_in: int, probe_out: int,
              base_liquidity: int, active_liquidity: int | None,
              ticks_crossed: int | None, min_base_liquidity_wei: int,
              max_price_impact_bps: int, max_quote_age_blocks: int,
              max_initialized_ticks_crossed: int | None, raw: dict[str, Any]) -> LiquidityImpactEvidence:
    reasons: list[str] = []
    age = max(0, int(latest_after) - int(block_number))
    impact = None
    try:
        impact = price_impact_bps(
            amount_in=int(amount_in), amount_out=int(amount_out),
            probe_in=int(probe_in), probe_out=int(probe_out),
        )
    except Exception:
        reasons.append("BLOCK: price-impact calculation unavailable")

    if int(base_liquidity) < int(min_base_liquidity_wei):
        reasons.append(
            f"BLOCK: base liquidity {int(base_liquidity)} below minimum "
            f"{int(min_base_liquidity_wei)}"
        )
    if amount_out <= 0 or probe_out <= 0:
        reasons.append("BLOCK: quote output is zero")
    if impact is None or impact > int(max_price_impact_bps):
        reasons.append(
            f"BLOCK: price impact {impact} bps exceeds maximum "
            f"{int(max_price_impact_bps)} bps"
        )
    if age > int(max_quote_age_blocks):
        reasons.append(
            f"BLOCK: quote is stale by {age} blocks; maximum "
            f"{int(max_quote_age_blocks)}"
        )
    if active_liquidity is not None and int(active_liquidity) <= 0:
        reasons.append("BLOCK: V3 active liquidity is zero")
    if (
        max_initialized_ticks_crossed is not None
        and ticks_crossed is not None
        and int(ticks_crossed) > int(max_initialized_ticks_crossed)
    ):
        reasons.append(
            f"BLOCK: V3 quote crosses {int(ticks_crossed)} initialized ticks; maximum "
            f"{int(max_initialized_ticks_crossed)}"
        )

    accepted = not reasons
    if accepted:
        reasons.append("PASS: fresh liquidity and price-impact bounds satisfied")
    return LiquidityImpactEvidence(
        accepted=accepted, dex=dex, pool=Web3.to_checksum_address(pool),
        block_number=int(block_number), latest_block_after=int(latest_after),
        quote_age_blocks=age, amount_in=int(amount_in), amount_out=int(amount_out),
        probe_amount_in=int(probe_in), probe_amount_out=int(probe_out),
        price_impact_bps=impact, base_liquidity_wei=int(base_liquidity),
        active_liquidity=int(active_liquidity) if active_liquidity is not None else None,
        initialized_ticks_crossed=(
            int(ticks_crossed) if ticks_crossed is not None else None
        ),
        reasons=tuple(reasons), raw=dict(raw),
    )


def collect_v2_liquidity_impact(
    w3: Web3, *, pair: str, base_token: str, amount_in_wei: int,
    fee_bps: int = 25, min_base_liquidity_wei: int = 10**18,
    max_price_impact_bps: int = 250, max_quote_age_blocks: int = 1,
) -> LiquidityImpactEvidence:
    pair = Web3.to_checksum_address(pair)
    base = Web3.to_checksum_address(base_token)
    block = int(w3.eth.block_number)
    c = w3.eth.contract(address=pair, abi=V2_PAIR_IMPACT_ABI)
    token0 = Web3.to_checksum_address(c.functions.token0().call(block_identifier=block))
    token1 = Web3.to_checksum_address(c.functions.token1().call(block_identifier=block))
    reserve0, reserve1, ts = c.functions.getReserves().call(block_identifier=block)
    if base == token0:
        reserve_in, reserve_out = int(reserve0), int(reserve1)
    elif base == token1:
        reserve_in, reserve_out = int(reserve1), int(reserve0)
    else:
        raise ValueError("base token is not in V2 pair")

    probe = _probe_amount(int(amount_in_wei))
    actual_out = v2_amount_out(int(amount_in_wei), reserve_in, reserve_out, int(fee_bps))
    probe_out = v2_amount_out(probe, reserve_in, reserve_out, int(fee_bps))
    latest_after = int(w3.eth.block_number)
    return _decision(
        dex="V2", pool=pair, block_number=block, latest_after=latest_after,
        amount_in=int(amount_in_wei), amount_out=actual_out,
        probe_in=probe, probe_out=probe_out, base_liquidity=reserve_in,
        active_liquidity=None, ticks_crossed=None,
        min_base_liquidity_wei=int(min_base_liquidity_wei),
        max_price_impact_bps=int(max_price_impact_bps),
        max_quote_age_blocks=int(max_quote_age_blocks),
        max_initialized_ticks_crossed=None,
        raw={"token0":token0,"token1":token1,"reserve0":int(reserve0),
             "reserve1":int(reserve1),"block_timestamp_last":int(ts),
             "fee_bps":int(fee_bps)},
    )


def _v3_virtual_base_liquidity(
    *, liquidity: int, sqrt_price_x96: int, base_is_token0: bool
) -> int:
    if liquidity <= 0 or sqrt_price_x96 <= 0:
        return 0
    if base_is_token0:
        return int(liquidity) * Q96 // int(sqrt_price_x96)
    return int(liquidity) * int(sqrt_price_x96) // Q96


def collect_v3_liquidity_impact(
    w3: Web3, *, pool: str, base_token: str, amount_in_wei: int,
    quoter_v2: str, min_base_liquidity_wei: int = 10**17,
    max_price_impact_bps: int = 250, max_quote_age_blocks: int = 1,
    max_initialized_ticks_crossed: int = 8,
) -> LiquidityImpactEvidence:
    pool = Web3.to_checksum_address(pool)
    base = Web3.to_checksum_address(base_token)
    quoter = Web3.to_checksum_address(quoter_v2)
    block = int(w3.eth.block_number)
    pc = w3.eth.contract(address=pool, abi=V3_POOL_IMPACT_ABI)
    token0 = Web3.to_checksum_address(pc.functions.token0().call(block_identifier=block))
    token1 = Web3.to_checksum_address(pc.functions.token1().call(block_identifier=block))
    fee = int(pc.functions.fee().call(block_identifier=block))
    liquidity = int(pc.functions.liquidity().call(block_identifier=block))
    slot0 = pc.functions.slot0().call(block_identifier=block)
    sqrt_price = int(slot0[0])
    if base == token0:
        token_out = token1
        base_is_token0 = True
    elif base == token1:
        token_out = token0
        base_is_token0 = False
    else:
        raise ValueError("base token is not in V3 pool")

    qc = w3.eth.contract(address=quoter, abi=V3_QUOTER_V2_ABI)
    probe = _probe_amount(int(amount_in_wei))
    params_actual = (base, token_out, int(amount_in_wei), fee, 0)
    params_probe = (base, token_out, probe, fee, 0)
    actual = qc.functions.quoteExactInputSingle(params_actual).call(block_identifier=block)
    marginal = qc.functions.quoteExactInputSingle(params_probe).call(block_identifier=block)
    actual_out = int(actual[0])
    probe_out = int(marginal[0])
    ticks_crossed = int(actual[2])
    virtual_base = _v3_virtual_base_liquidity(
        liquidity=liquidity, sqrt_price_x96=sqrt_price,
        base_is_token0=base_is_token0,
    )
    latest_after = int(w3.eth.block_number)
    return _decision(
        dex="V3", pool=pool, block_number=block, latest_after=latest_after,
        amount_in=int(amount_in_wei), amount_out=actual_out,
        probe_in=probe, probe_out=probe_out, base_liquidity=virtual_base,
        active_liquidity=liquidity, ticks_crossed=ticks_crossed,
        min_base_liquidity_wei=int(min_base_liquidity_wei),
        max_price_impact_bps=int(max_price_impact_bps),
        max_quote_age_blocks=int(max_quote_age_blocks),
        max_initialized_ticks_crossed=int(max_initialized_ticks_crossed),
        raw={"token0":token0,"token1":token1,"fee":fee,"sqrt_price_x96":sqrt_price,
             "tick":int(slot0[1]),"quoter_v2":quoter,
             "probe_ticks_crossed":int(marginal[2])},
    )
