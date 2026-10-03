# RUDRILA MEV v0.14.0 Large Dry-Run / Shadow Audit

Generated: 2026-10-03T05:34:44.114310+00:00
Python tests: 129
Deterministic shadow samples: 10000
NO_TRADE samples: 10000
Submission attempts: 0
Unsafe authorizations: 0
DEX coverage: {'PANCAKESWAP_V2': 8000, 'PANCAKESWAP_V3': 2000}

## Runtime invariants
- Monitor is SHADOW_AUDIT only.
- Live trading is hard false.
- No private key is loaded by the monitor.
- No public-mempool fallback is allowed.
- Monitor contains no transaction submission call.
- Every shadow candidate is NO_TRADE.

## Real Railway observation (pre-gate deployment evidence)
- 304 recent real BSC candidate events inspected.
- 304/304 emitted NO_TRADE.
- V2: 280; V3: 24.
- No valid transaction was submitted.

## Security
- Bandit medium/high: 0
- Dependency vulnerabilities: 0
- Actionable secret candidates: 0

Gate 15 remains blocked pending explicit live-money canary authorization.
