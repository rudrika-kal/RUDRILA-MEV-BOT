# Token Launch / New Pool Roadmap

## Implemented in v0.2
1. Factory-list configuration.
2. V2 PairCreated event signature.
3. Block-range launch scanning.
4. Only BASE/TOKEN pairs accepted.
5. ERC-20 bytecode existence check.
6. decimals() validation.
7. symbol() collection.
8. Pair reserve reading.
9. Minimum BASE liquidity threshold.
10. New-token live trading OFF by default.
11. Sell-simulation requirement flag.
12. Unit-tested launch safety gate.

## Must be completed before live launch trading
13. Configure exact chain.
14. Verify official factories and routers.
15. Add V3 PoolCreated adapter.
16. Add router-specific quote adapters.
17. Fork simulation that buys then sells the candidate token atomically.
18. Detect fee-on-transfer / buy-tax / sell-tax behavior.
19. Reject tokens that cannot be sold in simulation.
20. Reject extreme dynamic tax changes.
21. Detect blacklist/whitelist-dependent transfer failures.
22. Detect max-wallet/max-tx constraints via simulation.
23. Detect proxy implementation changes where possible.
24. Detect paused/trading-disabled state changes where exposed.
25. Require minimum and maximum price impact.
26. Require minimum locked/credible liquidity where verifiable.
27. Block stale launch candidates.
28. Add reorg-safe confirmation policy.
29. Add per-token cooldown.
30. Add duplicate-pool suppression.
31. Add token denylist.
32. Add approved-factory allowlist.
33. Add RPC failover.
34. Add WebSocket new-block/event trigger.
35. Add private transaction relay.
36. Add realized P&L and gas ledger.
37. Add failed/reverted gas daily kill switch.
38. Add tiny-size canary mode.
39. Run >=1,000 launch-candidate dry simulations.
40. Only then consider enabling new_token_live_trading.
