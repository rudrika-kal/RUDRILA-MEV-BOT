# RUDRILA MEV v0.10.0 Atomic Executor Verification

Generated: 2026-10-02T20:16:05.474508+00:00
Python tests: 99
Foundry executor tests passed: 17

## Behavioral/failure coverage
- Success path is atomic and returns only realized gross profit.
- Minimum-profit, buy-minimum and sell-minimum failures revert the entire transaction.
- Pre-existing base or quote balances fail with DIRTY_BASE / DIRTY_QUOTE; they are never auto-swept into P&L.
- Router allowlist, owner-only execution/control, deadline bounds and positive profit floor are enforced.
- Executor defaults paused; emergency pause blocks execution.
- Rescue is owner-only and available only while paused.
- Router approvals are exact/bounded and reset to zero after each swap.
- Successful execution requires zero residual base and quote balances.
- Non-reentrancy guard remains enabled.

## Static semantic proof
- Required invariants found: 15
- Missing invariants: 0
- Forbidden legacy dust sweep: 0

## Security
- Bandit medium/high: 0
- Dependency vulnerabilities: 0
- Actionable secret candidates: 0
- Slither high/medium findings: 0

## Runtime policy
- Live trading remains OFF.
- Production monitor fails closed until an executor is actually deployed, owner/source/router/pause state are verified.
- No private key or live funds are required for this verification.
