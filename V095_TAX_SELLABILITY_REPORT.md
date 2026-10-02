# RUDRILA MEV v0.9.5 Tax + Sellability Verification

Generated: 2026-10-02T14:22:30.216513+00:00

## Real BSC fork evidence
- Provider: `https://bsc-dataseed.bnbchain.org`
- Block: **125307611**
- Token: `0x0E09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82`
- Buy tax: **0 bps**
- Sell tax: **0 bps**
- Transfer-out passed: **True**
- Transfer tax: **0 bps**
- Round-trip loss: **49 bps**
- Decision: **PASS: fork buy/sell, tax measurement and transfer-out safety passed**

## Fail-closed behavior
- Transfer-out failure blocks.
- Missing transfer-tax evidence blocks.
- Excess combined buy/sell tax blocks.
- Excess round-trip loss blocks.
- Live trading remains OFF.

## Scanner validity
- Bandit medium/high: **0**
- Dependency vulnerabilities: **0**
- Actionable secret candidates: **0**
