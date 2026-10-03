from __future__ import annotations

from dataclasses import dataclass


WAD = 10**18
MORPHO_BLUE_ETHEREUM = "0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb"


@dataclass(frozen=True)
class MorphoPosition:
    borrower: str
    borrowed_value_wei: int
    collateral_value_wei: int
    lltv_wad: int
    expected_seized_value_wei: int


def is_liquidatable(p: MorphoPosition) -> bool:
    if p.collateral_value_wei <= 0 or p.lltv_wad <= 0:
        return False
    return p.borrowed_value_wei * WAD >= p.collateral_value_wei * p.lltv_wad


def evaluate_morpho_liquidation(
    p: MorphoPosition,
    *,
    repay_wei: int,
    gas_wei: int,
    builder_bid_wei: int,
    conversion_cost_wei: int,
    safety_buffer_wei: int,
    min_net_profit_wei: int,
) -> tuple[bool, int, tuple[str, ...]]:
    reasons: list[str] = []
    if not is_liquidatable(p):
        reasons.append("BLOCK: Morpho position not liquidatable")
    gross = p.expected_seized_value_wei - repay_wei
    net = gross - gas_wei - builder_bid_wei - conversion_cost_wei - safety_buffer_wei
    if net < min_net_profit_wei:
        reasons.append("BLOCK: Morpho liquidation below minimum net profit")
    if not reasons:
        reasons.append("PASS: Morpho liquidation is eligible and profitable")
    return (not any(x.startswith("BLOCK:") for x in reasons), net, tuple(reasons))


MORPHO_BLUE_READ_ABI = [
    {
        "inputs": [{"name": "id", "type": "bytes32"}],
        "name": "idToMarketParams",
        "outputs": [
            {"name": "loanToken", "type": "address"},
            {"name": "collateralToken", "type": "address"},
            {"name": "oracle", "type": "address"},
            {"name": "irm", "type": "address"},
            {"name": "lltv", "type": "uint256"},
        ],
        "stateMutability": "view", "type": "function",
    },
    {
        "inputs": [{"name": "id", "type": "bytes32"}, {"name": "user", "type": "address"}],
        "name": "position",
        "outputs": [
            {"name": "supplyShares", "type": "uint256"},
            {"name": "borrowShares", "type": "uint128"},
            {"name": "collateral", "type": "uint128"},
        ],
        "stateMutability": "view", "type": "function",
    },
]


@dataclass(frozen=True)
class MorphoRawPosition:
    market_id: bytes
    user: str
    lltv_wad: int
    borrow_shares: int
    collateral: int
    block_number: int


class MorphoBlueReader:
    def __init__(self, w3, address: str = MORPHO_BLUE_ETHEREUM):
        self.w3 = w3
        self.contract = w3.eth.contract(address=address, abi=MORPHO_BLUE_READ_ABI)

    def read_position(self, market_id: bytes, user: str, *, block_number: int | None = None) -> MorphoRawPosition:
        block = int(self.w3.eth.block_number if block_number is None else block_number)
        params = self.contract.functions.idToMarketParams(market_id).call(block_identifier=block)
        position = self.contract.functions.position(market_id, user).call(block_identifier=block)
        return MorphoRawPosition(market_id, user, int(params[4]), int(position[1]), int(position[2]), block)
