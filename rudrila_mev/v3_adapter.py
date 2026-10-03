from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from web3 import Web3

ALLOWED_V3_FEE_TIERS = frozenset({100, 500, 3000, 10000})

V3_QUOTER_V2_ABI = [{
    "inputs": [{
        "components": [
            {"name": "tokenIn", "type": "address"},
            {"name": "tokenOut", "type": "address"},
            {"name": "amountIn", "type": "uint256"},
            {"name": "fee", "type": "uint24"},
            {"name": "sqrtPriceLimitX96", "type": "uint160"},
        ],
        "name": "params",
        "type": "tuple",
    }],
    "name": "quoteExactInputSingle",
    "outputs": [
        {"name": "amountOut", "type": "uint256"},
        {"name": "sqrtPriceX96After", "type": "uint160"},
        {"name": "initializedTicksCrossed", "type": "uint32"},
        {"name": "gasEstimate", "type": "uint256"},
    ],
    "stateMutability": "nonpayable",
    "type": "function",
}]


def _address_bytes(address: str) -> bytes:
    value = address.lower()
    if value.startswith("0x"):
        value = value[2:]
    if len(value) != 40:
        raise ValueError("address must contain 20 bytes")
    return bytes.fromhex(value)


def encode_v3_path(tokens: list[str], fees: list[int]) -> bytes:
    if len(tokens) < 2 or len(fees) != len(tokens) - 1:
        raise ValueError("V3 path requires N tokens and N-1 fees")
    out = bytearray(_address_bytes(tokens[0]))
    for fee, token in zip(fees, tokens[1:]):
        if int(fee) not in ALLOWED_V3_FEE_TIERS:
            raise ValueError("unsupported V3 fee tier")
        out.extend(int(fee).to_bytes(3, "big"))
        out.extend(_address_bytes(token))
    return bytes(out)


@dataclass(frozen=True)
class V3Quote:
    block_number: int
    token_in: str
    token_out: str
    fee: int
    amount_in: int
    amount_out: int
    sqrt_price_x96_after: int
    initialized_ticks_crossed: int
    gas_estimate: int


class V3QuoterV2:
    def __init__(self, w3: Any, quoter_v2: str):
        self.w3 = w3
        self.quoter = w3.eth.contract(
            address=Web3.to_checksum_address(quoter_v2),
            abi=V3_QUOTER_V2_ABI,
        )

    def quote_single(
        self,
        token_in: str,
        token_out: str,
        amount_in: int,
        fee: int,
        *,
        block_number: int | None = None,
    ) -> V3Quote:
        if int(amount_in) <= 0:
            raise ValueError("amount_in must be positive")
        if int(fee) not in ALLOWED_V3_FEE_TIERS:
            raise ValueError("unsupported V3 fee tier")
        block = int(
            self.w3.eth.block_number
            if block_number is None
            else block_number
        )
        token_in = Web3.to_checksum_address(token_in)
        token_out = Web3.to_checksum_address(token_out)
        params = (token_in, token_out, int(amount_in), int(fee), 0)
        raw = self.quoter.functions.quoteExactInputSingle(params).call(
            block_identifier=block
        )
        if not isinstance(raw, (list, tuple)) or len(raw) != 4:
            raise RuntimeError("invalid QuoterV2 response")
        amount_out, sqrt_after, ticks, gas_estimate = map(int, raw)
        if amount_out <= 0:
            raise RuntimeError("V3 quote returned zero output")
        return V3Quote(
            block,
            token_in,
            token_out,
            int(fee),
            int(amount_in),
            amount_out,
            sqrt_after,
            ticks,
            gas_estimate,
        )
