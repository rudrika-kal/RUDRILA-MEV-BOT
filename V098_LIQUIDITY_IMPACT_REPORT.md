# RUDRILA MEV v0.9.8 Liquidity + Price Impact Verification

Generated: 2026-10-04T14:53:07.348112+00:00
BSC RPC: https://bsc-rpc.publicnode.com
Chain: 56
Latest block: 125695570
Probe amount: 1000000000000000 wei WBNB

## Real V2 evidence
Pool: 0x16b9a82891338f9bA80E2D6970FddA79D1eb0daE
Accepted: True
Base liquidity wei: 50788804498848472813555
Price impact bps: 0
Quote age blocks: 0
Reasons: ['PASS: fresh liquidity and price-impact bounds satisfied']

## Real V3 evidence
Pool: 0x172fcD41E0913e95784454622d1c3724f546f849
Fee tier: 100
Accepted: True
Virtual base liquidity wei: 176723193309210677825338
Active liquidity: 4957823970147574659095462
Price impact bps: 0
Initialized ticks crossed: 1
Quote age blocks: 0
Reasons: ['PASS: fresh liquidity and price-impact bounds satisfied']

## Fail-closed invariants
- V2 uses fresh block-pinned reserves and fee-aware constant-product quote.
- V3 uses fresh block-pinned QuoterV2 exact quote plus active concentrated liquidity.
- Low liquidity, excessive price impact, stale quotes, zero active V3 liquidity, or excessive initialized tick crossing blocks.
- Runtime remains READ-ONLY and live trading remains OFF.

## Scanner validity
- Bandit medium/high: 0
- Dependency vulnerabilities: 0
- Actionable secret candidates: 0
