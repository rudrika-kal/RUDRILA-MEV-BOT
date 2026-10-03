from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class CanaryReadiness:
    ready: bool
    prior_gates_passed: bool
    canary_mode: bool
    canary_amount_wei: int
    wallet_configured: bool
    executor_configured: bool
    private_signing_configured: bool
    private_submission_configured: bool
    public_mempool_disabled: bool
    live_trading_enabled: bool
    reasons: tuple[str, ...]

    def as_dict(self):
        return asdict(self)


def evaluate_canary_readiness(
    *,
    prior_gates_passed: bool,
    canary_mode: bool,
    canary_amount_wei: int,
    wallet_configured: bool,
    executor_configured: bool,
    private_signing_configured: bool,
    private_submission_configured: bool,
    public_mempool_disabled: bool,
    live_trading_enabled: bool,
    max_canary_amount_wei: int = 10**15,
) -> CanaryReadiness:
    reasons: list[str] = []
    if not prior_gates_passed:
        reasons.append("BLOCK: prior gates are not all verified")
    if not canary_mode:
        reasons.append("BLOCK: canary mode is disabled")
    amount = int(canary_amount_wei)
    if amount <= 0:
        reasons.append("BLOCK: canary amount must be positive")
    if amount > int(max_canary_amount_wei):
        reasons.append(
            f"BLOCK: canary amount {amount} exceeds hard cap {int(max_canary_amount_wei)}"
        )
    if not wallet_configured:
        reasons.append("BLOCK: MEV_WALLET_ADDRESS is not configured")
    if not executor_configured:
        reasons.append("BLOCK: MEV_EXECUTOR_ADDRESS is not configured")
    if not private_signing_configured:
        reasons.append("BLOCK: private signing secret/mechanism is not configured")
    if not private_submission_configured:
        reasons.append("BLOCK: private submission RPC/path is not configured")
    if not public_mempool_disabled:
        reasons.append("BLOCK: public mempool must remain disabled")
    if not live_trading_enabled:
        reasons.append("BLOCK: live trading is not explicitly enabled for canary")

    ready = not reasons
    if ready:
        reasons.append("PASS: tiny-canary prerequisites are present")
    return CanaryReadiness(
        ready=ready,
        prior_gates_passed=bool(prior_gates_passed),
        canary_mode=bool(canary_mode),
        canary_amount_wei=amount,
        wallet_configured=bool(wallet_configured),
        executor_configured=bool(executor_configured),
        private_signing_configured=bool(private_signing_configured),
        private_submission_configured=bool(private_submission_configured),
        public_mempool_disabled=bool(public_mempool_disabled),
        live_trading_enabled=bool(live_trading_enabled),
        reasons=tuple(reasons),
    )
