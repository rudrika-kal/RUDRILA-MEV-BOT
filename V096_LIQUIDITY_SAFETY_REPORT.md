# RUDRILA MEV v0.9.6 Liquidity Safety Verification

Generated: 2026-10-03T18:09:38.785236+00:00
- BSC RPC: `https://bsc-rpc.publicnode.com`
- Latest block: **125529816**

## V2 real ownership evidence
- Pair: `0xcF9F1695018d9Ea59c09B0d4FAc28B283B5C1c1A`
- Accepted: **False**
- Secured: **0 bps**
- Removable: **9999 bps**
- Unknown: **0 bps**
- Reasons: `['BLOCK: secured liquidity 0 bps below required 9500 bps', 'BLOCK: creator/provider-removable liquidity 9999 bps']`

## V3 real NFT-position evidence
- Position manager: `0x46A15B0b27311cedF172AB29E4f4766fbE7F4364`
- Accepted: **False**
- Secured: **0 bps**
- Removable: **0 bps**
- Unknown: **10000 bps**
- Reasons: `['BLOCK: secured liquidity 0 bps below required 10000 bps', 'BLOCK: 13782658851641878399399 liquidity units have unknown holder control']`

## Invariants
- V2 LP holder ownership is reconstructed/read on-chain and fails closed.
- Burn/dead or explicitly verified locker ownership can count as secured.
- Any EOA-held removable LP blocks with the current strict policy.
- Unknown contract-held LP blocks unless explicitly verified as a locker.
- V3 active position NFTs are checked through the Pancake V3 position manager.
- EOA-owned or unknown-contract-owned active V3 positions block.
- Empty/missing ownership evidence blocks.
- Runtime remains READ-ONLY; live trading remains OFF.

## Scanner validity
- Bandit medium/high: **0**
- Dependency vulnerabilities: **0**
- Actionable secret candidates: **0**
