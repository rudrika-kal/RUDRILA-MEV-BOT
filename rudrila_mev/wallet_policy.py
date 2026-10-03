from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WalletPolicy:
    hot_wallet: str
    treasury_wallet: str
    hot_native_balance_wei: int
    max_hot_native_balance_wei: int
    signer_source: str
    private_key_in_source: bool = False


def evaluate_wallet_separation(p: WalletPolicy) -> tuple[bool, tuple[str, ...]]:
    reasons: list[str] = []
    if p.hot_wallet.lower() == p.treasury_wallet.lower():
        reasons.append("BLOCK: hot wallet and treasury must be separate")
    if p.hot_native_balance_wei < 0 or p.hot_native_balance_wei > p.max_hot_native_balance_wei:
        reasons.append("BLOCK: hot-wallet native balance outside configured cap")
    if p.private_key_in_source:
        reasons.append("BLOCK: private key must never be stored in source")
    if p.signer_source not in {"kms", "hardware", "external_signer", "env_canary"}:
        reasons.append("BLOCK: signer source is not approved")
    if not reasons:
        reasons.append("PASS: dedicated capped hot wallet separated from treasury")
    return (not any(x.startswith("BLOCK:") for x in reasons), tuple(reasons))
