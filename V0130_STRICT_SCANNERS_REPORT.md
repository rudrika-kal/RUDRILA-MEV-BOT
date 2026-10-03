# RUDRILA MEV v0.13.0 Strict Scanner Verification

Generated: 2026-10-03T07:53:20.881547+00:00
Python tests: 165
Foundry tests: 19

## Strict scanner evidence
- Bandit medium/high: 0 (exit 1)
- Dependency vulnerabilities: 0 (exit 0)
- Actionable secrets: 0 (exit 0)
- Slither medium/high: 0 (exit 255)
- Tracked pycache/pyc artifacts: 0

## Invariants
- Missing/empty/invalid JSON scanner output is a hard failure.
- Actual Python and Foundry test counts must be non-zero and successful.
- Scanner exit codes are captured separately from parsed findings.
- Bandit/Slither medium-high, dependency vulnerabilities, actionable secrets block.
- Tracked __pycache__ and .pyc artifacts block.
- Live trading remains OFF.
