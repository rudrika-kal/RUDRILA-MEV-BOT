from __future__ import annotations

from web3 import Web3

from .rpc_quorum import RpcSnapshot


def probe_http_rpc(
    name: str,
    url: str,
    *,
    local: bool = False,
    timeout_seconds: int = 5,
) -> RpcSnapshot:
    w3 = Web3(
        Web3.HTTPProvider(
            url,
            request_kwargs={"timeout": int(timeout_seconds)},
        )
    )
    if not w3.is_connected():
        raise RuntimeError(f"RPC not connected: {name}")
    return RpcSnapshot(
        name=name,
        url=url,
        chain_id=int(w3.eth.chain_id),
        block_number=int(w3.eth.block_number),
        local=bool(local),
    )
