from __future__ import annotations

from dataclasses import dataclass
from web3 import Web3


@dataclass(frozen=True)
class RpcEndpoint:
    url: str
    chain_id: int
    block_number: int


class RpcPool:
    def __init__(self, urls: list[str], expected_chain_id: int, timeout: int = 5):
        self.urls = [x.strip() for x in urls if x.strip()]
        self.expected_chain_id = int(expected_chain_id)
        self.timeout = int(timeout)
        if not self.urls:
            raise RuntimeError("No RPC URLs configured")

    def healthy(self) -> list[RpcEndpoint]:
        good = []
        for url in self.urls:
            try:
                w3 = Web3(Web3.HTTPProvider(url, request_kwargs={"timeout": self.timeout}))
                if not w3.is_connected():
                    continue
                cid = int(w3.eth.chain_id)
                if cid != self.expected_chain_id:
                    continue
                good.append(RpcEndpoint(url, cid, int(w3.eth.block_number)))
            except Exception:
                continue
        return good

    def best(self) -> RpcEndpoint:
        good = self.healthy()
        if not good:
            raise RuntimeError("All RPC endpoints failed health/chain checks")
        # Prefer the endpoint reporting the newest block.
        return max(good, key=lambda x: x.block_number)
