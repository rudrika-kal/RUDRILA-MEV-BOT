from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class EthereumPreLiveReadiness:
    non_wallet_ready: bool
    canary_ready: bool
    state: str
    reasons: tuple[str, ...]

    def as_dict(self) -> dict:
        return asdict(self)


def evaluate_ethereum_prelive(
    *,
    python_tests_ok: bool,
    rust_tests_ok: bool,
    solidity_tests_ok: bool,
    mainnet_quote_ok: bool,
    local_fork_ok: bool,
    redundant_rpc_ok: bool,
    mev_share_sim_ok: bool,
    redundant_builders_ok: bool,
    aave_runtime_ok: bool,
    morpho_runtime_ok: bool,
    dashboard_ok: bool,
    wallet_connected: bool,
    executor_deployed: bool,
    signer_configured: bool,
    live_canary_enabled: bool,
) -> EthereumPreLiveReadiness:
    checks = {
        "Python regression suite": python_tests_ok,
        "Rust searcher tests": rust_tests_ok,
        "Solidity behavior tests": solidity_tests_ok,
        "Ethereum V3 live read-only quote": mainnet_quote_ok,
        "local mainnet fork": local_fork_ok,
        "redundant Ethereum RPCs": redundant_rpc_ok,
        "MEV-Share authenticated simulation": mev_share_sim_ok,
        "redundant private builders": redundant_builders_ok,
        "Aave runtime contracts": aave_runtime_ok,
        "Morpho runtime contracts": morpho_runtime_ok,
        "read-only dashboard": dashboard_ok,
    }
    reasons = [
        f"BLOCK: {name} not verified"
        for name, ok in checks.items()
        if not ok
    ]
    non_wallet_ready = not reasons
    if not non_wallet_ready:
        return EthereumPreLiveReadiness(
            False, False, "BLOCKED_NON_WALLET", tuple(reasons)
        )

    wallet_checks = {
        "wallet connection": wallet_connected,
        "executor deployment/allowlists": executor_deployed,
        "private signer": signer_configured,
        "explicit tiny-canary enable": live_canary_enabled,
    }
    pending = [
        f"WAIT: {name}"
        for name, ok in wallet_checks.items()
        if not ok
    ]
    if pending:
        return EthereumPreLiveReadiness(
            True, False, "WAITING_FOR_WALLET", tuple(pending)
        )
    return EthereumPreLiveReadiness(
        True,
        True,
        "CANARY_READY",
        ("PASS: all non-wallet and wallet canary gates verified",),
    )
