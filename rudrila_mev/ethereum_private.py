from __future__ import annotations

from dataclasses import dataclass


FLASHBOTS_RELAY = "https://relay.flashbots.net"


@dataclass(frozen=True)
class BuilderEndpoint:
    name: str
    url: str
    methods: frozenset[str]


DEFAULT_ETHEREUM_BUILDERS = (
    BuilderEndpoint("flashbots", FLASHBOTS_RELAY, frozenset({"eth_sendBundle", "mev_sendBundle", "mev_simBundle"})),
)


def validate_private_endpoint(endpoint: BuilderEndpoint) -> tuple[bool, tuple[str, ...]]:
    reasons: list[str] = []
    if not endpoint.url.startswith("https://"):
        reasons.append("BLOCK: private builder endpoint must use HTTPS")
    if not endpoint.methods:
        reasons.append("BLOCK: no private submission methods configured")
    forbidden = {"eth_sendRawTransaction"}
    if endpoint.methods.intersection(forbidden):
        reasons.append("BLOCK: public mempool method configured")
    if not reasons:
        reasons.append("PASS: private Ethereum builder endpoint configuration")
    return (not any(x.startswith("BLOCK:") for x in reasons), tuple(reasons))


def build_bundle_request(signed_txs: list[str], block_number: int, builders: list[str] | None = None) -> dict:
    if not signed_txs or any(not x.startswith("0x") for x in signed_txs):
        raise ValueError("signed bundle transactions required")
    params = {"txs": signed_txs, "blockNumber": hex(int(block_number))}
    if builders:
        params["builders"] = list(builders)
    return {"jsonrpc": "2.0", "id": 1, "method": "eth_sendBundle", "params": [params]}


def evaluate_private_builder_paths(endpoints: list[BuilderEndpoint], *, required_paths: int = 2) -> tuple[bool, tuple[str, ...]]:
    reasons: list[str] = []
    healthy = 0
    seen_urls: set[str] = set()
    for endpoint in endpoints:
        ok, _ = validate_private_endpoint(endpoint)
        if ok and endpoint.url not in seen_urls:
            healthy += 1
            seen_urls.add(endpoint.url)
    if required_paths < 2:
        reasons.append("BLOCK: at least two independent private paths required")
    if healthy < required_paths:
        reasons.append(f"BLOCK: only {healthy} independent private endpoints configured; {required_paths} required")
    if not reasons:
        reasons.append("PASS: redundant private Ethereum builder paths configured")
    return (not any(x.startswith("BLOCK:") for x in reasons), tuple(reasons))


def flashbots_auth_header(payload: dict, auth_private_key: str) -> tuple[str, str]:
    import json
    from eth_account import Account
    from eth_account.messages import encode_defunct
    from web3 import Web3

    body = json.dumps(payload, separators=(",", ":"), sort_keys=False)
    body_hash_hex = Web3.keccak(text=body).hex()
    message = encode_defunct(text=body_hash_hex)
    account = Account.from_key(auth_private_key)
    signed = Account.sign_message(message, private_key=auth_private_key)
    return body, f"{account.address}:{signed.signature.hex()}"
