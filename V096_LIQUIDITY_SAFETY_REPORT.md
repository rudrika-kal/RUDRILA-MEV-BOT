# RUDRILA MEV v0.9.6 Liquidity Safety Verification

Generated: 2026-10-02T19:31:16.293814+00:00
- BSC RPC: `https://bsc-rpc.publicnode.com`
- Latest block: **125348761**

## V2 real ownership evidence
- Pair: `0xc53B47Fc99d710736DF5A6b1D021001055263Fd8`
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
- Reasons: `['BLOCK: secured liquidity 0 bps below required 10000 bps', 'BLOCK: 19307851905816 liquidity units have unknown holder control']`

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
