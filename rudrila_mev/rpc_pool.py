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
        good: list[RpcEndpoint] = []
        for url in self.urls:
            endpoint = None
            try:
                w3 = Web3(
                    Web3.HTTPProvider(
                        url, request_kwargs={"timeout": self.timeout}
                    )
                )
                if w3.is_connected():
                    cid = int(w3.eth.chain_id)
                    if cid == self.expected_chain_id:
                        endpoint = RpcEndpoint(
                            url, cid, int(w3.eth.block_number)
                        )
            except Exception:
                endpoint = None

            if endpoint is not None:
                good.append(endpoint)
        return good

    def best(self) -> RpcEndpoint:
        good = self.healthy()
        if not good:
            raise RuntimeError("All RPC endpoints failed health/chain checks")
        return max(good, key=lambda x: x.block_number)
