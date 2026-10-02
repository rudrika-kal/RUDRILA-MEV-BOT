from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ExecutorSafetyEvidence:
    accepted: bool
    executor_deployed: bool
    owner_matches: bool | None
    source_verified: bool | None
    behavioral_tests_passed: bool | None
    routers_allowlisted: bool | None
    paused_state_known: bool
    paused: bool | None
    dirty_balance_guard_verified: bool | None
    exact_approval_cleanup_verified: bool | None
    paused_rescue_verified: bool | None
    non_reentrant_verified: bool | None
    reasons: tuple[str, ...]

    def as_dict(self) -> dict:
        return asdict(self)


def evaluate_executor_safety(
    *,
    executor_deployed: bool,
    owner_matches: bool | None,
    source_verified: bool | None,
    behavioral_tests_passed: bool | None,
    routers_allowlisted: bool | None,
    paused_state_known: bool,
    paused: bool | None,
    dirty_balance_guard_verified: bool | None,
    exact_approval_cleanup_verified: bool | None,
    paused_rescue_verified: bool | None,
    non_reentrant_verified: bool | None,
) -> ExecutorSafetyEvidence:
    reasons: list[str] = []

    def require_true(label: str, value: bool | None) -> None:
        if value is not True:
            reasons.append(f"BLOCK: {label} is not proven")

    if not executor_deployed:
        reasons.append("BLOCK: executor contract is not deployed")
    require_true("executor owner match", owner_matches)
    require_true("executor source/build verification", source_verified)
    require_true("executor behavioral/failure tests", behavioral_tests_passed)
    require_true("router allowlist", routers_allowlisted)
    if not paused_state_known or paused is None:
        reasons.append("BLOCK: executor pause state is unknown")
    elif paused:
        reasons.append("BLOCK: executor is paused")
    require_true("dirty-balance accounting guard", dirty_balance_guard_verified)
    require_true("exact approval cleanup", exact_approval_cleanup_verified)
    require_true("paused-only rescue", paused_rescue_verified)
    require_true("non-reentrancy", non_reentrant_verified)

    accepted = not reasons
    if accepted:
        reasons.append("PASS: atomic executor readiness evidence satisfied")

    return ExecutorSafetyEvidence(
        accepted=accepted,
        executor_deployed=bool(executor_deployed),
        owner_matches=owner_matches,
        source_verified=source_verified,
        behavioral_tests_passed=behavioral_tests_passed,
        routers_allowlisted=routers_allowlisted,
        paused_state_known=bool(paused_state_known),
        paused=paused,
        dirty_balance_guard_verified=dirty_balance_guard_verified,
        exact_approval_cleanup_verified=exact_approval_cleanup_verified,
        paused_rescue_verified=paused_rescue_verified,
        non_reentrant_verified=non_reentrant_verified,
        reasons=tuple(reasons),
    )
