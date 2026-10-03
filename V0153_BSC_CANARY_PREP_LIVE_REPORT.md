# RUDRILA MEV v0.15.3 — BSC Tiny-Canary Prep Live Report

Date: 2026-10-03

## On-chain state
- Chain: BNB Smart Chain (56)
- Owner wallet: `0x2fd84c20aA82943FBAbF7633a9492Df0Fb40b883`
- Executor: `0xDC7b55dB3f0557de524F0fb3481f958d2A708265`
- Executor owner: verified correct
- Executor paused: **true**
- PancakeSwap V2 router allowlisted: **true**
- Biswap V2 router allowlisted: **true**
- WBNB balance in owner wallet: **0.001 WBNB**
- Executor WBNB allowance: **exactly 0.001 WBNB**
- Public mempool fallback: **disabled**

## Private submission health
Read-only relay capability probe:
- 48club privacy RPC: **healthy**
- 48club puissant builder: **healthy**
- Merkle BSC: **healthy**
- Healthy paths: **3 / 3**
- Required paths: **2**
- Private submission gate: **PASS**

## Live profit gate snapshot
Canary amount: **0.001 WBNB**

Latest checked routes:
- PancakeSwap -> Biswap worst-case gross: approximately **-0.000009063 BNB**
- Biswap -> Pancake worst-case gross: approximately **-0.000007921 BNB**
- Conservative required gross: **>= 0.00022325 BNB**
  - includes buffered gas
  - 0.0001 BNB safety buffer
  - 0.0001 BNB minimum net profit

Result: **BLOCKED — no profitable canary opportunity at snapshot time.**

## Safety conclusion
Canary preparation is complete. The system must not unpause or submit a trade while the all-cost profitability gate is negative. No loss-making canary was sent.

Remaining live action is conditional, not a setup defect:
1. Wait for a route to satisfy the all-cost profit gate.
2. Re-simulate on a fresh block.
3. Use private submission only.
4. Keep canary amount <= 0.001 BNB-equivalent.
5. Audit receipt and realized P&L before any scaling.
