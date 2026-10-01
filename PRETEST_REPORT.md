# RUDRILA MEV v0.3 — Pre-Test Completion Report

## Goal
Before any real-money testing, finish every chain-independent safety control and identify the
remaining items that cannot truthfully be marked complete without choosing and connecting to an
actual chain/DEX/RPC/relay.

## Roadmap status

| Step | Item | Status before live-chain testing |
|---:|---|---|
| 1 | Factory-list configuration | DONE |
| 2 | V2 PairCreated event signature | DONE |
| 3 | Block-range launch scanning | DONE |
| 4 | BASE/TOKEN candidate filter | DONE |
| 5 | Token bytecode check | DONE |
| 6 | decimals() validation | DONE |
| 7 | symbol() collection | DONE |
| 8 | V2 reserve reading | DONE |
| 9 | Minimum BASE liquidity | DONE |
| 10 | New-token live trading OFF | DONE |
| 11 | Sell-simulation requirement | DONE |
| 12 | Unit-tested launch safety gate | DONE |
| 13 | Exact chain configuration | TEST INPUT REQUIRED |
| 14 | Official factory/router verification | TEST INPUT REQUIRED |
| 15 | V3 PoolCreated adapter | DONE |
| 16 | Router-specific quote adapters | PARTIAL — V2 implemented; V3 quote/execution needs chosen DEX |
| 17 | Fork atomic buy→sell simulation | LIVE/FORK TEST REQUIRED |
| 18 | Fee-on-transfer / buy/sell tax detection | GATE IMPLEMENTED; LIVE/FORK MEASUREMENT REQUIRED |
| 19 | Reject unsellable token | DONE AS POLICY; LIVE/FORK PROOF REQUIRED |
| 20 | Dynamic/extreme tax rejection | DONE AS POLICY; LIVE/FORK PROOF REQUIRED |
| 21 | Blacklist/whitelist transfer failures | DONE AS POLICY; LIVE/FORK PROOF REQUIRED |
| 22 | Max-wallet/max-tx constraints | DONE AS POLICY; LIVE/FORK PROOF REQUIRED |
| 23 | Proxy implementation changes | NOT GENERICALLY PROVABLE; chain-specific inspection required |
| 24 | Paused/trading-disabled behavior | SIMULATION POLICY READY; chain-specific proof required |
| 25 | Min/max price-impact guard | DONE |
| 26 | Locked/credible liquidity verification | CHAIN/PROTOCOL-SPECIFIC TEST REQUIRED |
| 27 | Stale launch blocking | DONE |
| 28 | Reorg confirmation policy | DONE |
| 29 | Per-token cooldown | DONE |
| 30 | Duplicate-pool suppression | DONE |
| 31 | Token denylist | DONE |
| 32 | Factory allowlist | DONE |
| 33 | RPC failover | DONE |
| 34 | WebSocket block/event trigger | NOT REQUIRED FOR CORRECTNESS; pending chain endpoint |
| 35 | Private transaction relay | HOOK DONE; relay verification required |
| 36 | Realized P&L + gas ledger | DONE |
| 37 | Failed/reverted gas daily kill switch | DONE |
| 38 | Tiny-size canary mode | DONE |
| 39 | >=1,000 launch dry simulations | TEST PHASE |
| 40 | Enable new_token_live_trading | BLOCKED BY DESIGN UNTIL 13–39 PASS |

## Non-negotiable execution equation

Worst-case gross profit must be at least:

`buffered gas + extra safety reserve + configured minimum net profit`

and the Solidity executor independently checks the minimum gross-profit threshold.

## Important truth about “all tokens”

No single generic check can prove every arbitrary token safe from future owner actions, proxy
upgrades, hidden admin controls, dynamic taxes or liquidity removal. The bot therefore treats new
tokens as untrusted and requires simulation, allowlisted infrastructure, liquidity/impact limits,
staleness controls and a canary stage.

## Ready for next phase?

YES for **controlled testing**.
NO for **real-money live launch trading**.

The next phase is to pick the exact supported chain/DEX set, verify official addresses, connect an
RPC/fork provider, deploy the executor on a test/fork environment, and run the 1,000-candidate audit.
