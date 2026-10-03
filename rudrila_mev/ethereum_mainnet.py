from __future__ import annotations

from dataclasses import dataclass
from typing import Any

ETHEREUM_CHAIN_ID = 1
WETH = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
USDC = "0xA0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
USDT = "0xdAC17F958D2ee523a2206206994597C13D831ec7"
DAI = "0x6B175474E89094C44Da98b954EedeAC495271d0F"
UNISWAP_V3_FACTORY = "0x1F98431c8aD98523631AE4a59f267346ea31F984"
UNISWAP_QUOTER_V2 = "0x61fFE014bA17989E743c5F6cB21bF9697530B21e"
UNISWAP_SWAP_ROUTER_02 = "0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45"


@dataclass(frozen=True)
class DeploymentCheck:
    accepted: bool
    chain_id: int
    missing_code: tuple[str, ...]
    reasons: tuple[str, ...]


def verify_ethereum_mainnet(w3: Any) -> DeploymentCheck:
    chain_id = int(w3.eth.chain_id)
    reasons: list[str] = []
    if chain_id != ETHEREUM_CHAIN_ID:
        reasons.append(
            f"BLOCK: expected chain 1, got {chain_id}"
        )
    required = {
        "WETH": WETH,
        "UniswapV3Factory": UNISWAP_V3_FACTORY,
        "QuoterV2": UNISWAP_QUOTER_V2,
        "SwapRouter02": UNISWAP_SWAP_ROUTER_02,
    }
    missing = tuple(
        name
        for name, address in required.items()
        if len(bytes(w3.eth.get_code(address))) == 0
    )
    if missing:
        reasons.append(
            "BLOCK: required deployment bytecode missing: "
            + ", ".join(missing)
        )
    if not reasons:
        reasons.append(
            "PASS: Ethereum mainnet canonical contracts verified"
        )
    return DeploymentCheck(
        not any(x.startswith("BLOCK:") for x in reasons),
        chain_id,
        missing,
        tuple(reasons),
    )
