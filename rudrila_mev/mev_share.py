from __future__ import annotations

from dataclasses import dataclass


FLASHBOTS_RELAY = "https://relay.flashbots.net"


@dataclass(frozen=True)
class MevShareBackrunPlan:
    target_hash: str
    signed_backrun_tx: str
    block_number: int
    max_block_number: int
    builders: tuple[str, ...] = ()
    can_revert: bool = False


def build_mev_send_bundle(plan: MevShareBackrunPlan) -> dict:
    if not plan.target_hash.startswith("0x") or len(plan.target_hash) != 66:
        raise ValueError("target hash must be 32 bytes")
    if not plan.signed_backrun_tx.startswith("0x") or len(plan.signed_backrun_tx) < 4:
        raise ValueError("signed backrun transaction required")
    if plan.max_block_number < plan.block_number:
        raise ValueError("max block before first block")
    if plan.can_revert:
        raise ValueError("RUDRILA backrun transaction must fail closed")
    body = [
        {"hash": plan.target_hash},
        {"tx": plan.signed_backrun_tx, "canRevert": False},
    ]
    payload = {
        "version": "v0.1",
        "inclusion": {
            "block": hex(plan.block_number),
            "maxBlock": hex(plan.max_block_number),
        },
        "body": body,
    }
    if plan.builders:
        payload["privacy"] = {"builders": list(plan.builders)}
    return {"jsonrpc": "2.0", "id": 1, "method": "mev_sendBundle", "params": [payload]}


def prepare_authenticated_mev_share_request(
    payload: dict,
    auth_private_key: str,
    *,
    relay_url: str = FLASHBOTS_RELAY,
) -> tuple[str, dict[str, str], str]:
    from .ethereum_private import flashbots_auth_header

    if payload.get("method") not in {"mev_sendBundle", "mev_simBundle"}:
        raise ValueError("MEV-Share request must be bundle send or simulation")
    body, signature = flashbots_auth_header(payload, auth_private_key)
    headers = {
        "content-type": "application/json",
        "accept": "application/json",
        "X-Flashbots-Signature": signature,
    }
    return relay_url, headers, body
