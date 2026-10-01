from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Iterable

from web3 import Web3

from .abi import ERC20_META_ABI, V2_FACTORY_ABI, V2_PAIR_ABI


PAIR_CREATED_TOPIC = Web3.keccak(text="PairCreated(address,address,address,uint256)").hex()


@dataclass(frozen=True)
class LaunchCandidate:
    factory: str
    pair: str
    token: str
    base_token: str
    block_number: int
    base_reserve_wei: int
    token_reserve_raw: int
    symbol: str
    decimals: int


@dataclass(frozen=True)
class TokenPreflight:
    accepted: bool
    token: str
    code_bytes: int
    decimals: int | None
    symbol: str | None
    reason: str


def _topic_address(topic) -> str:
    # indexed address occupies the low 20 bytes of a 32-byte topic
    hx = topic.hex() if hasattr(topic, "hex") else str(topic)
    hx = hx[2:] if hx.startswith("0x") else hx
    return Web3.to_checksum_address("0x" + hx[-40:])


def token_preflight(w3: Web3, token: str, min_code_bytes: int = 32, max_decimals: int = 24) -> TokenPreflight:
    token = Web3.to_checksum_address(token)
    code = bytes(w3.eth.get_code(token))
    if len(code) < min_code_bytes:
        return TokenPreflight(False, token, len(code), None, None, "REJECT: token has insufficient contract bytecode")

    c = w3.eth.contract(address=token, abi=ERC20_META_ABI)
    try:
        decimals = int(c.functions.decimals().call())
    except Exception:
        return TokenPreflight(False, token, len(code), None, None, "REJECT: decimals() failed")

    if decimals < 0 or decimals > max_decimals:
        return TokenPreflight(False, token, len(code), decimals, None, "REJECT: suspicious token decimals")

    try:
        symbol = str(c.functions.symbol().call())[:64]
    except Exception:
        symbol = "UNKNOWN"

    return TokenPreflight(True, token, len(code), decimals, symbol, "PASS: basic ERC-20 metadata/code checks")


class V2LaunchMonitor:
    """
    Watches PairCreated logs from configured V2-compatible factories.

    Safety design:
      - discovery alone NEVER authorizes a trade;
      - only pairs containing the configured wrapped-native/base token are candidates;
      - pair liquidity must exceed the configured minimum;
      - token code + decimals are checked;
      - live trading of a new token remains blocked elsewhere until sell simulation passes.
    """

    def __init__(
        self,
        w3: Web3,
        *,
        factories: Iterable[str],
        base_token: str,
        min_base_liquidity_wei: int,
        min_token_code_bytes: int = 32,
        max_token_decimals: int = 24,
    ):
        self.w3 = w3
        self.factories = [Web3.to_checksum_address(x) for x in factories]
        self.base = Web3.to_checksum_address(base_token)
        self.min_base_liquidity_wei = int(min_base_liquidity_wei)
        self.min_token_code_bytes = int(min_token_code_bytes)
        self.max_token_decimals = int(max_token_decimals)

    def scan_range(self, from_block: int, to_block: int) -> list[LaunchCandidate]:
        if not self.factories:
            return []
        if from_block > to_block:
            return []

        logs = self.w3.eth.get_logs({
            "fromBlock": int(from_block),
            "toBlock": int(to_block),
            "address": self.factories,
            "topics": [PAIR_CREATED_TOPIC],
        })

        out: list[LaunchCandidate] = []
        for log in logs:
            # PairCreated has token0 and token1 indexed; pair address is in data.
            if len(log["topics"]) < 3:
                continue
            token0 = _topic_address(log["topics"][1])
            token1 = _topic_address(log["topics"][2])
            if self.base not in (token0, token1):
                continue

            data = bytes(log["data"])
            if len(data) < 32:
                continue
            pair = Web3.to_checksum_address("0x" + data[12:32].hex())
            token = token1 if token0 == self.base else token0

            pf = token_preflight(
                self.w3,
                token,
                min_code_bytes=self.min_token_code_bytes,
                max_decimals=self.max_token_decimals,
            )
            if not pf.accepted:
                continue

            pair_c = self.w3.eth.contract(address=pair, abi=V2_PAIR_ABI)
            try:
                r0, r1, _ = pair_c.functions.getReserves().call()
            except Exception:
                continue

            if token0 == self.base:
                base_reserve, token_reserve = int(r0), int(r1)
            else:
                base_reserve, token_reserve = int(r1), int(r0)

            if base_reserve < self.min_base_liquidity_wei:
                continue

            out.append(LaunchCandidate(
                factory=Web3.to_checksum_address(log["address"]),
                pair=pair,
                token=token,
                base_token=self.base,
                block_number=int(log["blockNumber"]),
                base_reserve_wei=base_reserve,
                token_reserve_raw=token_reserve,
                symbol=pf.symbol or "UNKNOWN",
                decimals=int(pf.decimals or 0),
            ))
        return out
