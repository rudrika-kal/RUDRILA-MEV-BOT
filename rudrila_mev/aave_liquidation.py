from __future__ import annotations

from dataclasses import dataclass


WAD = 10**18


@dataclass(frozen=True)
class AavePosition:
    user: str
    health_factor_wad: int
    debt_to_cover_wei: int
    expected_collateral_value_wei: int
    liquidation_bonus_bps: int


@dataclass(frozen=True)
class LiquidationDecision:
    accepted: bool
    expected_gross_wei: int
    expected_net_wei: int
    reasons: tuple[str, ...]


def evaluate_aave_liquidation(
    p: AavePosition,
    *,
    gas_wei: int,
    builder_bid_wei: int,
    swap_cost_wei: int,
    safety_buffer_wei: int,
    min_net_profit_wei: int,
) -> LiquidationDecision:
    reasons: list[str] = []
    if p.health_factor_wad >= WAD:
        reasons.append("BLOCK: Aave health factor is not below 1")
    if p.debt_to_cover_wei <= 0 or p.expected_collateral_value_wei <= 0:
        reasons.append("BLOCK: invalid liquidation amounts")
    gross = p.expected_collateral_value_wei - p.debt_to_cover_wei
    net = gross - gas_wei - builder_bid_wei - swap_cost_wei - safety_buffer_wei
    if net < min_net_profit_wei:
        reasons.append("BLOCK: Aave liquidation below minimum net profit")
    if not reasons:
        reasons.append("PASS: Aave liquidation is eligible and profitable")
    return LiquidationDecision(not any(x.startswith("BLOCK:") for x in reasons), gross, net, tuple(reasons))


AAVE_V3_ETHEREUM_POOL = "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2"
AAVE_ACCOUNT_ABI = [{
    "inputs": [{"name": "user", "type": "address"}],
    "name": "getUserAccountData",
    "outputs": [
        {"name": "totalCollateralBase", "type": "uint256"},
        {"name": "totalDebtBase", "type": "uint256"},
        {"name": "availableBorrowsBase", "type": "uint256"},
        {"name": "currentLiquidationThreshold", "type": "uint256"},
        {"name": "ltv", "type": "uint256"},
        {"name": "healthFactor", "type": "uint256"},
    ],
    "stateMutability": "view",
    "type": "function",
}]


@dataclass(frozen=True)
class AaveAccountSnapshot:
    user: str
    total_collateral_base: int
    total_debt_base: int
    health_factor_wad: int
    block_number: int


class AaveAccountReader:
    def __init__(self, w3, pool_address: str = AAVE_V3_ETHEREUM_POOL):
        self.w3 = w3
        self.pool = w3.eth.contract(address=pool_address, abi=AAVE_ACCOUNT_ABI)

    def read(self, user: str, *, block_number: int | None = None) -> AaveAccountSnapshot:
        block = int(self.w3.eth.block_number if block_number is None else block_number)
        values = self.pool.functions.getUserAccountData(user).call(block_identifier=block)
        return AaveAccountSnapshot(user, int(values[0]), int(values[1]), int(values[5]), block)

    def liquidatable(self, users: list[str], *, block_number: int | None = None) -> tuple[AaveAccountSnapshot, ...]:
        rows = [self.read(user, block_number=block_number) for user in users]
        return tuple(x for x in rows if x.total_debt_base > 0 and x.health_factor_wad < WAD)
