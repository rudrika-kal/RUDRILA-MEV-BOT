# RUDRILA MEV — Post-Buy Live Readiness

Status date: 2026-10-03

## Implemented and verified

1. Dynamic BSC large-buy detector for supported V2 routers.
2. Post-confirmation-only gate: pending observations never authorize execution.
3. Dynamic token firewall: honeypot/sellability, buy/sell tax, admin/proxy, blacklist/pause, liquidity and price-impact checks.
4. Fresh post-buy PancakeSwap/Biswap route quoting.
5. All-cost profit gate: gas, private/builder payment, DEX economics, slippage/tax effects, safety buffer and minimum net profit.
6. Atomic V2 executor integration with router allowlist, exact approvals and minimum gross-profit enforcement.
7. Private-only submission adapters with public mempool fallback disabled.
8. Execution-risk / kill-switch ledger and receipt/realized-P&L audit code.
9. 24x7 Render post-buy shadow monitor with RPC rotation, dynamic ANY_WBNB_TOKEN mode and deployed-executor live preflight.

## Test evidence

- Local Python suite: 197 tests passed.
- GitHub Actions RUDRILA MEV Expansion CI for commit 3fc1e99: SUCCESS.
- Render deploy for commit 3fc1e99: LIVE.
- Live monitor has already detected and confirmed real BSC large-buy events, then correctly blocked unsafe/unprofitable candidates.

## Current live-chain state

- Executor: 0xDC7b55dB3f0557de524F0fb3481f958d2A708265
- Owner: 0x2fd84c20aA82943FBAbF7633a9492Df0Fb40b883
- Executor paused: true
- PancakeSwap V2 allowed: true
- Biswap V2 allowed: true
- Test wallet WBNB: 0.001 WBNB
- Executor allowance: 0.001 WBNB
- Public mempool fallback: disabled

Current WBNB/CAKE 0.001 WBNB round-trip snapshot remained negative on both Pancake->Biswap and Biswap->Pancake, so no loss-making canary was sent.

## Live-canary gate

A real-money canary remains capped at <=0.001 BNB-equivalent. It must not be submitted until:
- a confirmed large buy exists;
- token firewall passes;
- a fresh post-buy route exists;
- all-cost floor net profit exceeds the configured minimum;
- private path health passes;
- loss/kill-switch limits pass;
- executor state/allowance/router checks pass;
- the wallet signing/private-submission path is available.

No live-money trade was submitted while these conditions were not satisfied.
