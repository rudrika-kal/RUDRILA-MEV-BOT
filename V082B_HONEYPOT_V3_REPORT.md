# RUDRILA MEV v0.8.2b Fresh-Pool / V3 Verification

Generated: 2026-10-02T09:02:49.565809+00:00

- Fresh-pool Honeypot fallback: pair -> auto-pair -> simulateLiquidity -> forceSimulateLiquidity.
- Synthetic-liquidity results are always fail-closed and cannot authorize a live trade.
- Actual-pair/fork sellability proof remains mandatory.
- V3 decoding + allowed-fee filtering have deterministic unit tests.
- Bandit medium/high: **0**
- Dependency vulnerabilities: **0**
- Actionable secret candidates: **0**

## Live Honeypot smoke
```
CAKE {'accepted': True, 'simulation_success': True, 'risk': 'low', 'risk_level': 1, 'mode': 'auto_pair', 'reasons': ('PASS: external honeypot simulation',)}
RECENT_FRESH_TOKEN {'accepted': False, 'simulation_success': True, 'risk': 'low', 'risk_level': 1, 'mode': 'simulated_liquidity', 'reasons': ('BLOCK: holder sell-failure analysis is missing', 'BLOCK: high-tax wallet analysis is missing', 'BLOCK: synthetic-liquidity fallback is diagnostic only; actual-pair/fork sellability proof is still required')}

```
