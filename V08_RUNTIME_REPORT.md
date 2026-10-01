# RUDRILA MEV v0.8 Runtime Report

Generated: 2026-10-01T15:37:07.567807+00:00

- Bandit medium/high: **0**
- Dependency vulnerabilities: **0**
- Actionable secret candidates: **0**
- Slither medium/high: **0**

## Runtime fix
- Honeypot pair-specific HTTP failure retries token+chain only.
- HTTP errors remain fail-closed and record status/body preview.
- API failure can never authorize a trade.
- Live trading remains OFF.

## Honeypot API smoke
```
accepted= True
simulation_success= True
risk= low
risk_level= 1
reasons= ('PASS: external honeypot simulation',)

```
