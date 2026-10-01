from __future__ import annotations

from dataclasses import dataclass
from web3 import Web3


POOL_CREATED_TOPIC = Web3.keccak(text="PoolCreated(address,address,uint24,int24,address)").hex()


def _topic_address(topic) -> str:
    hx = topic.hex() if hasattr(topic, "hex") else str(topic)
    hx = hx[2:] if hx.startswith("0x") else hx
    return Web3.to_checksum_address("0x" + hx[-40:])


def _topic_uint(topic) -> int:
    hx = topic.hex() if hasattr(topic, "hex") else str(topic)
    return int(hx, 16)


@dataclass(frozen=True)
class V3PoolCandidate:
    factory: str
    pool: str
    token: str
    base_token: str
    fee: int
    tick_spacing: int
    block_number: int


class V3LaunchMonitor:
    def __init__(self, w3: Web3, factories: list[str], base_token: str, allowed_fee_tiers: list[int]):
        self.w3 = w3
        self.factories = [Web3.to_checksum_address(x) for x in factories]
        self.base = Web3.to_checksum_address(base_token)
        self.allowed_fee_tiers = {int(x) for x in allowed_fee_tiers}

    def scan_range(self, from_block: int, to_block: int) -> list[V3PoolCandidate]:
        if not self.factories or from_block > to_block:
            return []
        logs = self.w3.eth.get_logs({
            "fromBlock": int(from_block),
            "toBlock": int(to_block),
            "address": self.factories,
            "topics": [POOL_CREATED_TOPIC],
        })
        out = []
        for log in logs:
            if len(log["topics"]) < 4:
                continue
            token0 = _topic_address(log["topics"][1])
            token1 = _topic_address(log["topics"][2])
            fee = _topic_uint(log["topics"][3])
            if fee not in self.allowed_fee_tiers:
                continue
            if self.base not in (token0, token1):
                continue

            data = bytes(log["data"])
            # ABI data: int24 tickSpacing padded to 32 bytes, address pool padded to 32 bytes.
            if len(data) < 64:
                continue
            tick_raw = int.from_bytes(data[:32], "big", signed=True)
            pool = Web3.to_checksum_address("0x" + data[44:64].hex())
            token = token1 if token0 == self.base else token0
            out.append(V3PoolCandidate(
                factory=Web3.to_checksum_address(log["address"]),
                pool=pool,
                token=token,
                base_token=self.base,
                fee=fee,
                tick_spacing=tick_raw,
                block_number=int(log["blockNumber"]),
            ))
        return out
