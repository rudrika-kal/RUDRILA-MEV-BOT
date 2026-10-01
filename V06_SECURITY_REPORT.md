# RUDRILA MEV v0.6 Security Report

Generated: 2026-10-01T12:33:55.734547+00:00

- Bandit medium/high: **0**
- Dependency vulnerabilities: **0**
- Slither medium/high: **3**
- Actionable secret candidates: **0**

## Notes
- Live trading remains OFF.
- Slither non-zero process exit alone is not treated as a failure; actual medium/high detector findings are the gate.
- config.json private_key_env is an environment-variable name, not a private-key value.

## Remaining before live trading
- Validate honeypot/tax simulation on real new pools.
- Add LP lock/burn proof and admin privilege evidence.
- Fork-test the executor and failure paths.
- Validate all-cost net-profit gate end to end.
- Validate private submission.
- Complete large dry-run audit, then tiny canary only after all gates pass.

## Slither findings
- High / reentrancy-balance — Reentrancy in RudrilaArbExecutor._execute(RudrilaArbExecutor.ArbRequest) (contracts/RudrilaArbExecutor.sol#96-152):
	External call allowing reentrancy:
	- sellReported = _swap(r.routerSell,r.quoteToken,r.baseToken,acquiredQuote,r.minBaseOut,r.deadline) (contracts/RudrilaArbExecutor.sol#121-128)
		- (ok,ret) = token.call(data) (contracts/RudrilaArbExecutor.sol#237)
		- amounts = IV2RouterLike(router).swapExactTokensForTokens(amountIn,minOut,path,address(this),deadline) (contracts/RudrilaArbExecutor.sol#182-188)
	Balance read before the call:
	- acquiredQuote = quote.balanceOf(address(this)) (contracts/RudrilaArbExecutor.sol#118)
	Possible stale balance used after the call in a condition:
	- require(bool,string)(sellReported >= r.minBaseOut,SELL_ROUTER_TOO_LOW) (contracts/RudrilaArbExecutor.sol#129)
		- stale variable `sellReported`
- Medium / incorrect-equality — RudrilaArbExecutor._execute(RudrilaArbExecutor.ArbRequest) (contracts/RudrilaArbExecutor.sol#96-152) uses a dangerous strict equality:
	- require(bool,string)(base.balanceOf(address(this)) == 0,BASE_DIRTY) (contracts/RudrilaArbExecutor.sol#103)
- Medium / incorrect-equality — RudrilaArbExecutor._execute(RudrilaArbExecutor.ArbRequest) (contracts/RudrilaArbExecutor.sol#96-152) uses a dangerous strict equality:
	- require(bool,string)(quote.balanceOf(address(this)) == 0,QUOTE_DIRTY) (contracts/RudrilaArbExecutor.sol#104)
