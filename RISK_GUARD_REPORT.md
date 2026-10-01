# RUDRILA MEV v0.4 — Mandatory Honeypot / Rug-Pull Gate

## Priority
Contract risk is checked **before** liquidity, price-impact and profit calculations can authorize a trade.

## Fail-closed rule
If a mandatory risk check returns UNKNOWN, the token is blocked. Unknown is not treated as safe.

## Mandatory honeypot checks
- simulated buy must succeed;
- simulated sell must succeed;
- post-buy transfer-out must succeed;
- buy/sell taxes must be measured;
- round-trip loss must stay below the configured limit;
- dynamic/extreme tax behavior blocks the token;
- blacklist, pause, mutable fees and mutable max-wallet/max-tx privileges block the token.

## Mandatory rug-pull checks
- liquidity lock/burn proof required;
- creator-controlled liquidity removal blocks the token;
- privileged mint capability blocks the token;
- admin safety proof required;
- upgradeable proxy is blocked unless its implementation is explicitly checked.

## Trade authorization order
1. Contract-risk gate
2. Liquidity gate
3. Price-impact gate
4. Buy/sell simulation gate
5. Gas + all fees + safety buffer + minimum net-profit gate
6. Atomic execution contract

A token failing step 1 can never be rescued by a large apparent profit.

## Important limitation
No static detector can guarantee that an arbitrary token can never rug in the future.
The bot therefore uses conservative, fail-closed rules and requires runtime/fork evidence before a
new token can be traded.
