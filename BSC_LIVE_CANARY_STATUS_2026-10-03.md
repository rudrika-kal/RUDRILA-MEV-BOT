# RUDRILA BSC Live Canary Status — 2026-10-03

## Current on-chain executor

- Chain: BNB Smart Chain (56)
- Owner wallet: `0x2fd84c20aA82943FBAbF7633a9492Df0Fb40b883`
- Executor: `0xDC7b55dB3f0557de524F0fb3481f958d2A708265`
- Runtime code present: yes
- Owner verified on-chain: yes
- Paused: **true**
- PancakeSwap V2 allowlisted: **false**
- Biswap V2 allowlisted: **false**
- Wallet native BNB: 0.0387899647 BNB at last check
- Wallet WBNB: 0
- WBNB allowance to executor: 0

## Router administration readiness

Read-only gas simulation at 0.05 gwei:

- PancakeSwap allowlist: 48,730 gas (~0.0000024365 BNB)
- Biswap allowlist: 48,730 gas (~0.0000024365 BNB)
- Unpause estimate: 27,782 gas (~0.0000013891 BNB)

A mobile admin page is deployed at:
`https://rudrila-bnb-signer.onrender.com/setup.html?v=f96a071`

The page only allowlists the two routers and deliberately leaves the executor paused.

## Private submission checks

Observed on BSC:

- 48club privacy RPC: chain 56; `eth_sendRawTransaction` recognized
- 48club puissant builder: chain 56; `eth_sendPrivateTransaction` recognized
- Merkle BSC: malformed private-send payload rejected by the transaction parser, but the chain-id probe did not return a usable result in this check

Public mempool fallback remains prohibited for MEV execution.

## Current tiny-canary economics

Canary size: 0.001 BNB-equivalent (1e15 wei).

At block 125494928, before gas:

- Pancake -> Biswap: final 0.000995337036033920 BNB-equivalent
  - gross: **-0.000004662963966080 BNB** (-46.63 bps)
- Biswap -> Pancake: final 0.000995634562022027 BNB-equivalent
  - gross: **-0.000004365437977973 BNB** (-43.65 bps)

Gas at 0.05 gwei would add further cost. Therefore the hard net-profit rule correctly blocks a live canary at this snapshot.

## Safety tests

Standard-library safety suite rerun on the authorized Mac:

- canary gate
- executor guard
- all-cost profit gate
- profit gate

Result: **36/36 PASS**.

## Remaining live-canary gates

1. Allowlist PancakeSwap V2 with owner-wallet approval.
2. Allowlist Biswap V2 with owner-wallet approval.
3. Keep executor paused while no profitable canary exists.
4. For unattended/private execution, provision a separate hot execution signer/operator path. The deployed executor is owner-only, so the main Trust Wallet key must not be copied to a server.
5. When a profitable route passes all-cost simulation, prepare exactly 0.001 BNB-equivalent funding/allowance, re-simulate at a fresh block, require positive floor net profit after all costs and safety buffer, then unpause only for the controlled canary.
6. Submit only through verified private paths; never fall back to public mempool.
7. After receipt, verify event, gas paid, realized gross/net P&L, then re-pause and record the audit.

## Current verdict

**Platform/deployment: ready.**
**Router setup: awaiting two owner-wallet approvals.**
**Live trade: correctly BLOCKED at current market economics.**
**24x7 unattended private signer: not yet provisioned; do not use the main Trust Wallet private key on the server.**
