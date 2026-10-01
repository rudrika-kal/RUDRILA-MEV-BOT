from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LaunchSafetyDecision:
    accepted_for_live: bool
    basic_checks_passed: bool
    sell_simulation_passed: bool
    liquidity_passed: bool
    reason: str


def evaluate_new_token(
    *,
    basic_checks_passed: bool,
    sell_simulation_passed: bool,
    base_liquidity_wei: int,
    min_base_liquidity_wei: int,
    require_sell_simulation: bool = True,
) -> LaunchSafetyDecision:
    liquidity_passed = int(base_liquidity_wei) >= int(min_base_liquidity_wei)

    if not basic_checks_passed:
        return LaunchSafetyDecision(False, False, sell_simulation_passed, liquidity_passed,
                                    "REJECT: token preflight failed")
    if not liquidity_passed:
        return LaunchSafetyDecision(False, True, sell_simulation_passed, False,
                                    "REJECT: launch liquidity below threshold")
    if require_sell_simulation and not sell_simulation_passed:
        return LaunchSafetyDecision(False, True, False, True,
                                    "REJECT: sellability simulation not proven")
    return LaunchSafetyDecision(True, True, sell_simulation_passed, True,
                                "PASS: token checks, liquidity and sellability requirements satisfied")
