# RUDRILA MEV v0.9.4 BSC Fork Verification

Generated: 2026-10-02T10:28:46.201026+00:00

## Real fork evidence
- Selected fork RPC: `https://bsc-dataseed.bnbchain.org`
- Chain ID: **56**
- Fork block: **125276442**
- Token: `0x0E09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82`
- Router: `0x10ED43C718714eb63d5aA57B78B54704E256024E`
- Input WBNB wei: **10000000000000000**
- Buy received raw: **2985071849091040104**
- Sell returned WBNB wei: **9950062531654640**
- Buy gas used: **112641**
- Sell gas used: **114455**
- Round-trip loss: **49 bps**
- Decision: **PASS: fork buy->sell round-trip completed within loss limit**

## Safety invariants
- Simulation runs only on an ephemeral local Anvil BSC fork.
- No production wallet/private key is used.
- Zero-buy, zero-sell, and excessive-loss cases fail closed.
- Unsupported/non-V2 runtime paths remain unauthorized.
- Live trading remains OFF.

## Scanner validity
- Bandit medium/high: **0**
- Dependency vulnerabilities: **0**
- Actionable secret candidates: **0**
