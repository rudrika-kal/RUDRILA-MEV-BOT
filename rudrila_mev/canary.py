from __future__ import annotations


def effective_trade_amount(
    *,
    normal_amount_wei: int,
    canary_mode: bool,
    canary_amount_wei: int,
) -> int:
    normal = int(normal_amount_wei)
    canary = int(canary_amount_wei)
    if normal <= 0:
        raise ValueError("normal amount must be positive")
    if not canary_mode:
        return normal
    if canary <= 0:
        raise ValueError("canary amount must be positive")
    return min(normal, canary)
