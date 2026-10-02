# RUDRILA MEV v0.9.7 Admin Safety Verification

Generated: 2026-10-02T19:35:04.669948+00:00
BSC RPC: https://bsc-rpc.publicnode.com
Chain: 56
Latest block: 125349269

## Real BSC evidence
### WBNB
Token: 0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c
Accepted: False
Owner: None
Admin: None
Admin read resolved: False
Proxy: False None
Implementation checked: True
Mint selector: False
Blacklist selector: False
Pause/trading selector: False
Mutable fee selector: False
Mutable limit selector: False
Reasons: ['BLOCK: owner/admin authority cannot be proven absent']

### CAKE
Token: 0x0E09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82
Accepted: False
Owner: 0x73feaa1eE314F8c655E354234017bE2193C9E24E
Admin: None
Admin read resolved: True
Proxy: False None
Implementation checked: True
Mint selector: True
Blacklist selector: False
Pause/trading selector: False
Mutable fee selector: False
Mutable limit selector: False
Reasons: ['BLOCK: non-zero owner/admin authority detected', 'BLOCK: privileged mint capability selector detected']

## Invariants
- Unknown owner/admin authority blocks.
- Non-zero owner/admin authority blocks.
- Mint/blacklist/pause/trading/fee/max-tx/max-wallet capability selectors block.
- EIP-1967 implementation/beacon and EIP-1167 minimal proxy state is checked.
- Unknown proxy state blocks.
- Verified proxy remains blocked under strict policy.
- Runtime remains READ-ONLY; live trading remains OFF.

## Scanner validity
- Bandit medium/high: 0
- Dependency vulnerabilities: 0
- Actionable secret candidates: 0
