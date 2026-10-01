# RUDRILA MEV v0.5 Repair & Security Report

Generated: 2026-10-01T10:37:24.081582+00:00

## Automated results
- Python compile exit: **0**
- Unit tests exit: **0**
- Solidity compile exit: **0**
- Bandit medium/high findings: **1**
- Dependency vulnerabilities: **0**
- Secret candidates needing review: **18**
- Slither exit: **255**
- Slither medium/high findings: **6**

## Hardening applied
- HTTPS-only private RPC client.
- Removed silent except/continue Bandit findings.
- Base token and quote token must be different.
- Executor router allowlist.
- Token/router contract-code checks.
- Positive minimum-profit requirement.
- Pre-existing quote-token dust excluded from trade accounting.
- Router approvals reset after swaps.
- External BSC honeypot buy/sell simulation parser.
- Buy/sell tax, gas, source/proxy, holder-failure and high-tax checks.
- Live trading remains OFF.

## Secret candidates
- .git/FETCH_HEAD:1 — Hex High Entropy String
- .github/workflows/RUDRILA_MEV_V05_REPAIR.yml:25 — Base64 High Entropy String
- .github/workflows/RUDRILA_MEV_V05_REPAIR.yml:25 — Base64 High Entropy String
- .github/workflows/RUDRILA_MEV_V05_REPAIR.yml:25 — Base64 High Entropy String
- .github/workflows/RUDRILA_MEV_V05_REPAIR.yml:25 — Base64 High Entropy String
- .github/workflows/RUDRILA_MEV_V05_REPAIR.yml:25 — Base64 High Entropy String
- .github/workflows/RUDRILA_MEV_V05_REPAIR.yml:25 — Base64 High Entropy String
- .github/workflows/RUDRILA_MEV_V05_REPAIR.yml:25 — Base64 High Entropy String
- .github/workflows/RUDRILA_MEV_V05_REPAIR.yml:25 — Base64 High Entropy String
- .github/workflows/RUDRILA_MEV_V05_REPAIR.yml:25 — Base64 High Entropy String
- .github/workflows/RUDRILA_MEV_V05_REPAIR.yml:25 — Base64 High Entropy String
- .github/workflows/RUDRILA_MEV_V05_REPAIR.yml:25 — Base64 High Entropy String
- .github/workflows/RUDRILA_MEV_V05_REPAIR.yml:25 — Base64 High Entropy String
- .github/workflows/RUDRILA_MEV_V05_REPAIR.yml:125 — Secret Keyword
- .github/workflows/RUDRILA_MEV_V05_REPAIR.yml:125 — Secret Keyword
- .github/workflows/security-audit.yml:91 — Secret Keyword
- config.example.json:7 — Secret Keyword
- config.json:7 — Secret Keyword

## Bandit medium/high
- rudrila_mev/honeypot_client.py:175 MEDIUM B113 Call to requests without timeout

## Slither medium/high
- High / reentrancy-balance — Reentrancy in RudrilaArbExecutor._execute(RudrilaArbExecutor.ArbRequest) (contracts/RudrilaArbExecutor.sol#112-167):
	External call allowing reentrancy:
	- _swap(r.routerBuy,r.baseToken,r.quoteToken,r.amountIn,r.minQuoteOut,r.deadline) (contracts/RudrilaArbExecutor.sol#123-130)
		- (ok,ret) = token.call(data) (contracts/RudrilaArbExecutor.sol#251)
		- IV2RouterLike(router).swapExactTokensForTokens(amountIn,minOut,path,address(this),deadline) (contracts/RudrilaArbExecutor.sol#200-206)
	Balance read before the call:
	- baseBefore = base.balanceOf(address(this)) (contracts/RudrilaArbExecutor.sol#118)
	Possible stale balance used after the call in a condition:
	- require(bool,string)(baseAfter >= baseBefore + r.amountIn,NO_GROSS_PROFIT) (contracts/RudrilaArbExecutor.sol#147)
		- stale variable `baseBefore`
	- require(bool,string)(grossProfit >= r.minGrossProfit,MIN_PROFIT_NOT_MET) (contracts/RudrilaArbExecutor.sol#150)
		- stale variable `grossProfit`
- High / reentrancy-balance — Reentrancy in RudrilaArbExecutor._execute(RudrilaArbExecutor.ArbRequest) (contracts/RudrilaArbExecutor.sol#112-167):
	External call allowing reentrancy:
	- _swap(r.routerSell,r.quoteToken,r.baseToken,acquiredQuote,r.minBaseOut,r.deadline) (contracts/RudrilaArbExecutor.sol#137-144)
		- (ok,ret) = token.call(data) (contracts/RudrilaArbExecutor.sol#251)
		- IV2RouterLike(router).swapExactTokensForTokens(amountIn,minOut,path,address(this),deadline) (contracts/RudrilaArbExecutor.sol#200-206)
	Balance read before the call:
	- baseBefore = base.balanceOf(address(this)) (contracts/RudrilaArbExecutor.sol#118)
	Possible stale balance used after the call in a condition:
	- require(bool,string)(baseAfter >= baseBefore + r.amountIn,NO_GROSS_PROFIT) (contracts/RudrilaArbExecutor.sol#147)
		- stale variable `baseBefore`
	- require(bool,string)(grossProfit >= r.minGrossProfit,MIN_PROFIT_NOT_MET) (contracts/RudrilaArbExecutor.sol#150)
		- stale variable `grossProfit`
- High / reentrancy-balance — Reentrancy in RudrilaArbExecutor._execute(RudrilaArbExecutor.ArbRequest) (contracts/RudrilaArbExecutor.sol#112-167):
	External call allowing reentrancy:
	- _swap(r.routerBuy,r.baseToken,r.quoteToken,r.amountIn,r.minQuoteOut,r.deadline) (contracts/RudrilaArbExecutor.sol#123-130)
		- (ok,ret) = token.call(data) (contracts/RudrilaArbExecutor.sol#251)
		- IV2RouterLike(router).swapExactTokensForTokens(amountIn,minOut,path,address(this),deadline) (contracts/RudrilaArbExecutor.sol#200-206)
	Balance read before the call:
	- quoteBefore = quote.balanceOf(address(this)) (contracts/RudrilaArbExecutor.sol#119)
	Possible stale balance used after the call in a condition:
	- require(bool,string)(acquiredQuote >= r.minQuoteOut,BUY_TOO_LOW) (contracts/RudrilaArbExecutor.sol#135)
		- stale variable `acquiredQuote`
	- require(bool,string)(quoteAfterBuy >= quoteBefore,QUOTE_BALANCE_DECREASED) (contracts/RudrilaArbExecutor.sol#133)
		- stale variable `quoteBefore`
- High / reentrancy-balance — Reentrancy in RudrilaArbExecutor._execute(RudrilaArbExecutor.ArbRequest) (contracts/RudrilaArbExecutor.sol#112-167):
	External call allowing reentrancy:
	- _safeTransferFrom(r.baseToken,msg.sender,address(this),r.amountIn) (contracts/RudrilaArbExecutor.sol#121)
		- (ok,ret) = token.call(data) (contracts/RudrilaArbExecutor.sol#251)
	Balance read before the call:
	- quoteBefore = quote.balanceOf(address(this)) (contracts/RudrilaArbExecutor.sol#119)
	Possible stale balance used after the call in a condition:
	- require(bool,string)(acquiredQuote >= r.minQuoteOut,BUY_TOO_LOW) (contracts/RudrilaArbExecutor.sol#135)
		- stale variable `acquiredQuote`
	- require(bool,string)(quoteAfterBuy >= quoteBefore,QUOTE_BALANCE_DECREASED) (contracts/RudrilaArbExecutor.sol#133)
		- stale variable `quoteBefore`
- High / reentrancy-balance — Reentrancy in RudrilaArbExecutor._execute(RudrilaArbExecutor.ArbRequest) (contracts/RudrilaArbExecutor.sol#112-167):
	External call allowing reentrancy:
	- _safeTransferFrom(r.baseToken,msg.sender,address(this),r.amountIn) (contracts/RudrilaArbExecutor.sol#121)
		- (ok,ret) = token.call(data) (contracts/RudrilaArbExecutor.sol#251)
	Balance read before the call:
	- baseBefore = base.balanceOf(address(this)) (contracts/RudrilaArbExecutor.sol#118)
	Possible stale balance used after the call in a condition:
	- require(bool,string)(baseAfter >= baseBefore + r.amountIn,NO_GROSS_PROFIT) (contracts/RudrilaArbExecutor.sol#147)
		- stale variable `baseBefore`
	- require(bool,string)(grossProfit >= r.minGrossProfit,MIN_PROFIT_NOT_MET) (contracts/RudrilaArbExecutor.sol#150)
		- stale variable `grossProfit`
- Medium / unused-return — RudrilaArbExecutor._swap(address,address,address,uint256,uint256,uint256) (contracts/RudrilaArbExecutor.sol#186-209) ignores return value by IV2RouterLike(router).swapExactTokensForTokens(amountIn,minOut,path,address(this),deadline) (contracts/RudrilaArbExecutor.sol#200-206)

## Remaining before live trading
- Validate external honeypot API against live newly launched candidates.
- Add independent admin/mint/blacklist/pause/fee-change evidence source.
- Add V2 LP burn/lock proof; V3 live trading remains blocked until equivalent proof exists.
- Fork-test the hardened executor and failure paths.
- Validate gas + DEX fee + tax + slippage + safety reserve + minimum NET profit end to end.
- Validate private transaction submission.
- Complete large dry-run audit and tiny canary only after every critical gate passes.
