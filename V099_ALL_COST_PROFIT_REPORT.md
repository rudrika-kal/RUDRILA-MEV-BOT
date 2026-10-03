# RUDRILA MEV v0.9.9 All-Cost Minimum-Net Verification

Generated: 2026-10-03T05:14:04.959596+00:00
BSC RPC: https://bsc-rpc.publicnode.com
Chain: 56
Quoted/current block: 125426449 / 125426451
Router: 0x10ED43C718714eb63d5aA57B78B54704E256024E

## Real BSC same-router round trip
Amount in: 1000000000000000
Expected final: 995006121802385
Floor final: 991030077467187
Gas price: 50000000
Gas units: 372000
Accepted: False
Floor net after all costs: -28569922532813
DEX fee deduction: 0 (embedded in route output)
Slippage deduction: 0 (embedded in floor output)
Token-tax deduction: 0 (Gate5 CAKE tax evidence = 0)
Reasons: ['BLOCK: worst-case route has no positive gross profit', 'BLOCK: floor net profit -28569922532813 below minimum 1000000000000']

## Positive/no-double-count proof
Accepted: True
Floor net: 90000
Embedded DEX/slippage/tax deductions: 0/0/0

## Fail-closed invariants
- Unknown gas, builder/private payment, non-embedded costs, or non-embedded token tax blocks.
- Embedded DEX fees, slippage and token taxes are never subtracted twice.
- Stale economics blocks.
- Floor net must cover every non-embedded cost, safety buffer and configured minimum net profit.
- Generic scanner remains fail-closed until token-tax and live builder-payment evidence are supplied.
- Runtime remains READ-ONLY; live trading remains OFF.

## Scanner validity
- Bandit medium/high: 0
- Dependency vulnerabilities: 0
- Actionable secret candidates: 0
