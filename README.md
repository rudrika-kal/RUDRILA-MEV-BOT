# RUDRILA MEV Arbitrage v0.2 — Launch-Aware

**New in v0.2:** generic V2-compatible token-launch discovery for supported EVM chains.

The bot can now discover newly created BASE/TOKEN pairs from configured factory contracts.
A newly launched token is only a **candidate**. Discovery never equals permission to buy.

## New-token safety path

`PairCreated -> base-token match -> bytecode check -> ERC-20 metadata check -> liquidity floor
-> buy/sell quote availability -> sellability simulation -> gas/fee/slippage calculation
-> safety buffer -> minimum net profit -> atomic executor`

**Critical rule:** `new_token_live_trading` remains `false` by default. A newly launched token
must prove sellability through simulation before live execution is permitted.

This is designed for legitimate launch monitoring/arbitrage, not victim-targeted sandwiching
or mempool manipulation.

## "Any token launch" scope

v0.2 is generic across **V2-compatible EVM DEX factories** once their official factory/router
addresses are configured. V3 pools and non-EVM chains need separate adapters; they are on the
roadmap rather than being falsely treated as universal.


# RUDRILA MEV Arbitrage v0.1

**Status: safe foundation complete. `live_trading` is OFF by default.**

This project is a two-DEX, V2-router-style **atomic arbitrage** bot. It does not implement
sandwiching or user-targeted front-running.

## Non-negotiable trade rule

The bot executes only when the **worst-case two-leg output** covers:

1. principal;
2. buffered gas cost;
3. extra safety reserve; and
4. configured minimum net profit.

The execution contract receives:

`minGrossProfit = bufferedGas + safetyReserve + desiredNetProfit`

and reverts unless the BASE-token gain reaches that value.

### Why BASE must be wrapped-native in v0.1

Gas is paid in the chain's native asset. v0.1 therefore requires the base token to be its
1:1 wrapped form (for example WETH on Ethereum). This avoids guessing an oracle conversion
when comparing gas against trade profit.

## Safety gates implemented

1. Same-block DEX quote collection.
2. Both arbitrage directions checked: A→B and B→A.
3. First-leg slippage floor.
4. Second leg re-quoted using the first leg's **minimum** output.
5. Second-leg slippage floor.
6. EIP-1559 base/priority fee read from RPC.
7. Gas-unit buffer.
8. Maximum gas-price hard cap.
9. Minimum desired net-profit rule.
10. Extra safety reserve.
11. Quote age/block freshness check.
12. Short transaction deadline.
13. Atomic two-swap Solidity executor.
14. On-chain `minGrossProfit` assertion.
15. Owner-only execution.
16. Reentrancy guard.
17. Private-submission requirement available for live mode.
18. Public mempool disabled by default.
19. Private key read only from environment.
20. Live trading OFF by default.

## Setup

Python 3.12+:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp config.example.json config.json
```

Set these environment variables:

```bash
export MEV_RPC_URL='YOUR_RPC'
export MEV_WALLET_ADDRESS='0x...'
```

For dry-run scanning, configure `config.json` with real token/router addresses and run:

```bash
python -m rudrila_mev.main --config config.json --once
```

Continuous:

```bash
python -m rudrila_mev.main --config config.json
```

## Before live mode

Do **not** turn on live mode until all of these are completed:

- choose the exact EVM chain;
- verify token and router addresses from official sources;
- deploy `RudrilaArbExecutor.sol`;
- verify the source on the chain explorer;
- approve only the intended trade allowance from a dedicated low-balance bot wallet;
- set `MEV_EXECUTOR_ADDRESS`;
- configure a private transaction relay/RPC;
- run fork tests against real historical blocks;
- run at least 1,000 dry-run opportunities and compare predicted vs. realized/fork-simulated outputs;
- test gas spikes, RPC outages, stale blocks, token reverts and liquidity removal;
- only then enable `live_trading`.

## Build roadmap

### Phase 1 — completed in v0.1
1. Project isolation from the existing RUDRILA Bitget bot.
2. EVM RPC validation and chain-ID guard.
3. Two-router quote engine.
4. Two-direction arbitrage scan.
5. Two-leg slippage floor.
6. Conservative gas fee engine.
7. Gas hard cap.
8. Net-profit decision engine.
9. Safety reserve.
10. Atomic Solidity executor.
11. On-chain minimum-profit guard.
12. Stale-quote guard.
13. Short deadline.
14. Private-key environment handling.
15. Private submission hook.
16. Public mempool OFF default.
17. Unit tests.
18. Docker deployment files.
19. Render worker definition.
20. JSON structured logs.

### Phase 2 — next
21. Exact chain + official DEX address configuration.
22. Fork-based integration tests.
23. Contract compilation/deployment script.
24. ERC-20 approval helper with amount cap.
25. Private relay integration test.
26. Receipt monitoring and realized P&L.
27. Failed/reverted gas accounting.
28. Daily gas-loss kill switch.
29. Per-route cooldown after failures.
30. RPC failover.
31. WebSocket block trigger.
32. Multi-pool fee-tier support.
33. V3 Quoter/Universal Router adapters.
34. Liquidity-depth and price-impact checks.
35. Token allowlist / denylist.
36. Honeypot / fee-on-transfer rejection.
37. Database journal.
38. Dashboard/API health endpoint.
39. 1,000+ opportunity dry-run audit.
40. Tiny-size live canary mode, still protected by all gates.

## Important limitation

No trading system can guarantee profit. A reverted transaction can still cost gas depending on
how it is submitted. Private transaction systems can reduce some failed-transaction and
front-running risks, but they do not make market risk mathematically zero.


## v0.3 pre-test controls
See `PRETEST_REPORT.md` for the exact step-by-step status before controlled testing.


## v0.4 mandatory risk guard
Honeypot/rug-pull screening is now the first pre-trade gate. Unknown mandatory checks fail closed. See `RISK_GUARD_REPORT.md`.
