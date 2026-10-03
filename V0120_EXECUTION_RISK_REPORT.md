# RUDRILA MEV v0.12.0 Execution Risk Verification

Generated: 2026-10-03T05:34:55.995643+00:00
Python tests: 129

## Verified
- Exact realized P&L = gross profit - gas - builder payment - other cost.
- Malformed or unreconciled ledger blocks.
- Hourly realized-loss limit blocks.
- Daily realized-loss limit blocks.
- Daily failed-gas limit blocks.
- Hourly/daily failed-transaction limits block.
- Daily revert limit blocks.
- Live scanner checks kill switch before submission.
- Included transaction receipt gas + ArbitrageExecuted gross profit are journaled.
- Live trading remains OFF.

- Bandit medium/high: 0
- Dependency vulnerabilities: 0
- Actionable secret candidates: 0
