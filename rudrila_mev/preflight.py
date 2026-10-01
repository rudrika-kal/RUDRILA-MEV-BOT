from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LivePreflight:
    ready: bool
    missing: tuple[str, ...]


def live_preflight(
    *,
    chain_verified: bool,
    dex_addresses_verified: bool,
    executor_deployed: bool,
    executor_source_verified: bool,
    private_relay_verified: bool,
    fork_simulation_passed: bool,
    dry_run_count: int,
    required_dry_runs: int = 1000,
) -> LivePreflight:
    missing = []
    if not chain_verified:
        missing.append("exact chain not verified")
    if not dex_addresses_verified:
        missing.append("official DEX factory/router addresses not verified")
    if not executor_deployed:
        missing.append("executor contract not deployed")
    if not executor_source_verified:
        missing.append("executor source not verified on explorer")
    if not private_relay_verified:
        missing.append("private relay not verified")
    if not fork_simulation_passed:
        missing.append("fork buy/sell simulation not passed")
    if int(dry_run_count) < int(required_dry_runs):
        missing.append(f"dry-run audit incomplete ({dry_run_count}/{required_dry_runs})")
    return LivePreflight(not missing, tuple(missing))
