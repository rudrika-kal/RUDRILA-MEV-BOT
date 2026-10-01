# RUDRILA MEV Security Scan Report

Generated: 2026-10-01T09:48:32.356329+00:00

## Summary

- Existing unit tests exit code: **0**
- Bandit exit code: **1**
- pip-audit vulnerabilities reported: **0**
- detect-secrets findings: **4**
- Slither detector findings: **0**

> A zero count does not guarantee the bot is safe.

> Live trading remains OFF until runtime, fork and on-chain checks also pass.

## Existing Tests
```text
test_all_gates_pass (test_launch_guard.LaunchGuardTests.test_all_gates_pass) ... ok
test_low_liquidity_is_blocked (test_launch_guard.LaunchGuardTests.test_low_liquidity_is_blocked) ... ok
test_unknown_sellability_is_blocked (test_launch_guard.LaunchGuardTests.test_unknown_sellability_is_blocked) ... ok
test_canary_amount (test_pretest_safety.PretestSafetyTests.test_canary_amount) ... ok
test_dynamic_tax_rejected (test_pretest_safety.PretestSafetyTests.test_dynamic_tax_rejected) ... ok
test_failed_attempt_limit (test_pretest_safety.PretestSafetyTests.test_failed_attempt_limit) ... ok
test_gas_loss_kill_switch (test_pretest_safety.PretestSafetyTests.test_gas_loss_kill_switch) ... ok
test_honeypot_like_sell_failure_rejected (test_pretest_safety.PretestSafetyTests.test_honeypot_like_sell_failure_rejected) ... ok
test_live_preflight_blocks_early_live (test_pretest_safety.PretestSafetyTests.test_live_preflight_blocks_early_live) ... ok
test_price_impact (test_pretest_safety.PretestSafetyTests.test_price_impact) ... ok
test_registry_duplicate_and_cooldown (test_pretest_safety.PretestSafetyTests.test_registry_duplicate_and_cooldown) ... ok
test_stale_candidate_rejected (test_pretest_safety.PretestSafetyTests.test_stale_candidate_rejected) ... ok
test_unapproved_factory_rejected (test_pretest_safety.PretestSafetyTests.test_unapproved_factory_rejected) ... ok
test_accept_only_after_all_costs (test_profit.ProfitTests.test_accept_only_after_all_costs) ... ok
test_add_bps_rounds_up (test_profit.ProfitTests.test_add_bps_rounds_up) ... ok
test_floor_bps (test_profit.ProfitTests.test_floor_bps) ... ok
test_reject_negative_route (test_profit.ProfitTests.test_reject_negative_route) ... ok
test_reject_when_gas_consumes_profit (test_profit.ProfitTests.test_reject_when_gas_consumes_profit) ... ok
test_contract_risk_is_first_trade_gate (test_risk_guard.RiskGuardTests.test_contract_risk_is_first_trade_gate) ... ok
test_creator_liquidity_control_blocks (test_risk_guard.RiskGuardTests.test_creator_liquidity_control_blocks) ... ok
test_mutable_fee_authority_blocks (test_risk_guard.RiskGuardTests.test_mutable_fee_authority_blocks) ... ok
test_profit_never_overrides_contract_risk (test_risk_guard.RiskGuardTests.test_profit_never_overrides_contract_risk) ... ok
test_safe_contract_passes (test_risk_guard.RiskGuardTests.test_safe_contract_passes) ... ok
test_sell_failure_blocks_as_honeypot (test_risk_guard.RiskGuardTests.test_sell_failure_blocks_as_honeypot) ... ok
test_unknown_is_fail_closed (test_risk_guard.RiskGuardTests.test_unknown_is_fail_closed) ... ok
test_unlocked_liquidity_blocks (test_risk_guard.RiskGuardTests.test_unlocked_liquidity_blocks) ... ok
test_unverified_proxy_blocks (test_risk_guard.RiskGuardTests.test_unverified_proxy_blocks) ... ok

----------------------------------------------------------------------
Ran 27 tests in 0.001s

OK

```

## Bandit
```text
Run started:2026-10-01 09:48:21.068543+00:00

Test results:
>> Issue: [B310:blacklist] Audit url open for permitted schemes. Allowing use of file:/ or custom schemes is often unexpected.
   Severity: Medium   Confidence: High
   CWE: CWE-22 (https://cwe.mitre.org/data/definitions/22.html)
   More Info: https://bandit.readthedocs.io/en/1.9.4/blacklists/blacklist_calls.html#b310-urllib-urlopen
   Location: rudrila_mev/evm.py:247:9
246	    )
247	    with urllib.request.urlopen(req, timeout=10) as response:
248	        data = json.loads(response.read().decode())

--------------------------------------------------
>> Issue: [B112:try_except_continue] Try, Except, Continue detected.
   Severity: Low   Confidence: High
   CWE: CWE-703 (https://cwe.mitre.org/data/definitions/703.html)
   More Info: https://bandit.readthedocs.io/en/1.9.4/plugins/b112_try_except_continue.html
   Location: rudrila_mev/launch_monitor.py:137:12
136	                r0, r1, _ = pair_c.functions.getReserves().call()
137	            except Exception:
138	                continue
139	

--------------------------------------------------
>> Issue: [B112:try_except_continue] Try, Except, Continue detected.
   Severity: Low   Confidence: High
   CWE: CWE-703 (https://cwe.mitre.org/data/definitions/703.html)
   More Info: https://bandit.readthedocs.io/en/1.9.4/plugins/b112_try_except_continue.html
   Location: rudrila_mev/ledger.py:48:12
47	                    out.append(ExecutionRecord(**d))
48	            except Exception:
49	                continue
50	        return out

--------------------------------------------------
>> Issue: [B112:try_except_continue] Try, Except, Continue detected.
   Severity: Low   Confidence: High
   CWE: CWE-703 (https://cwe.mitre.org/data/definitions/703.html)
   More Info: https://bandit.readthedocs.io/en/1.9.4/plugins/b112_try_except_continue.html
   Location: rudrila_mev/rpc_pool.py:33:12
32	                good.append(RpcEndpoint(url, cid, int(w3.eth.block_number)))
33	            except Exception:
34	                continue
35	        return good

--------------------------------------------------

Code scanned:
	Total lines of code: 1333
	Total lines skipped (#nosec): 0
	Total potential issues skipped due to specifically being disabled (e.g., #nosec BXXX): 0

Run metrics:
	Total issues (by severity):
		Undefined: 0
		Low: 3
		Medium: 1
		High: 0
	Total issues (by confidence):
		Undefined: 0
		Low: 0
		Medium: 0
		High: 4
Files skipped (0):

```

## Slither
```text
Traceback (most recent call last):
  File "/opt/hostedtoolcache/Python/3.12.14/x64/lib/python3.12/site-packages/crytic_compile/platform/solc.py", line 639, in _run_solc
    ret: dict = json.loads(stdout)
                ^^^^^^^^^^^^^^^^^^
  File "/opt/hostedtoolcache/Python/3.12.14/x64/lib/python3.12/json/__init__.py", line 346, in loads
    return _default_decoder.decode(s)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/hostedtoolcache/Python/3.12.14/x64/lib/python3.12/json/decoder.py", line 338, in decode
    obj, end = self.raw_decode(s, idx=_w(s, 0).end())
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/hostedtoolcache/Python/3.12.14/x64/lib/python3.12/json/decoder.py", line 356, in raw_decode
    raise JSONDecodeError("Expecting value", s, err.value) from None
json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/opt/hostedtoolcache/Python/3.12.14/x64/bin/slither", line 6, in <module>
    sys.exit(main())
             ^^^^^^
  File "/opt/hostedtoolcache/Python/3.12.14/x64/lib/python3.12/site-packages/slither/__main__.py", line 815, in main
    main_impl(all_detector_classes=detectors, all_printer_classes=printers)
  File "/opt/hostedtoolcache/Python/3.12.14/x64/lib/python3.12/site-packages/slither/__main__.py", line 936, in main_impl
    ) = process_all(filename, args, detector_classes, printer_classes)
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/hostedtoolcache/Python/3.12.14/x64/lib/python3.12/site-packages/slither/__main__.py", line 100, in process_all
    compilations = compile_all(target, **vars(args))
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/hostedtoolcache/Python/3.12.14/x64/lib/python3.12/site-packages/crytic_compile/crytic_compile.py", line 870, in compile_all
    compilations.append(CryticCompile(target, **kwargs))
                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/hostedtoolcache/Python/3.12.14/x64/lib/python3.12/site-packages/crytic_compile/crytic_compile.py", line 279, in __init__
    self._compile(**kwargs)
  File "/opt/hostedtoolcache/Python/3.12.14/x64/lib/python3.12/site-packages/crytic_compile/crytic_compile.py", line 725, in _compile
    self._platform.compile(self, **kwargs)
  File "/opt/hostedtoolcache/Python/3.12.14/x64/lib/python3.12/site-packages/crytic_compile/platform/solc.py", line 195, in compile
    targets_json = _get_targets_json(compilation_unit, self._target, **kwargs)
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/hostedtoolcache/Python/3.12.14/x64/lib/python3.12/site-packages/crytic_compile/platform/solc.py", line 324, in _get_targets_json
    return _run_solc(
           ^^^^^^^^^^
  File "/opt/hostedtoolcache/Python/3.12.14/x64/lib/python3.12/site-packages/crytic_compile/platform/solc.py", line 642, in _run_solc
    raise InvalidCompilation(f"Invalid solc compilation {stderr}")
crytic_compile.platform.exceptions.InvalidCompilation: Invalid solc compilation Error: Stack too deep. Try compiling with `--via-ir` (cli) or the equivalent `viaIR: true` (standard JSON) while enabling the optimizer. Otherwise, try removing local variables.
   --> contracts/RudrilaArbExecutor.sol:128:23:
    |
128 |         _safeTransfer(baseToken, msg.sender, returnedBase);
    |                       ^^^^^^^^^


Multiple frameworks detected: solc, Solc-json. Using solc (highest priority). Use --compile-force-framework to override.
'solc --version' running
'solc contracts/RudrilaArbExecutor.sol --combined-json abi,ast,bin,bin-runtime,srcmap,srcmap-runtime,userdoc,devdoc,hashes --allow-paths .,/home/runner/work/RUDRILA-MEV-BOT/RUDRILA-MEV-BOT/contracts' running
Compilation warnings/errors on contracts/RudrilaArbExecutor.sol:
Error: Stack too deep. Try compiling with `--via-ir` (cli) or the equivalent `viaIR: true` (standard JSON) while enabling the optimizer. Otherwise, try removing local variables.
   --> contracts/RudrilaArbExecutor.sol:128:23:
    |
128 |         _safeTransfer(baseToken, msg.sender, returnedBase);
    |                       ^^^^^^^^^



```

## Dependency Audit
```json
{
  "dependencies": [
    {
      "name": "web3",
      "version": "8.0.0",
      "vulns": []
    },
    {
      "name": "eth-account",
      "version": "0.14.0",
      "vulns": []
    },
    {
      "name": "aiohttp",
      "version": "3.14.3",
      "vulns": []
    },
    {
      "name": "multidict",
      "version": "6.9.1",
      "vulns": []
    },
    {
      "name": "yarl",
      "version": "1.25.1",
      "vulns": []
    },
    {
      "name": "aiohappyeyeballs",
      "version": "2.7.1",
      "vulns": []
    },
    {
      "name": "aiosignal",
      "version": "1.4.0",
      "vulns": []
    },
    {
      "name": "attrs",
      "version": "26.1.0",
      "vulns": []
    },
    {
      "name": "bitarray",
      "version": "3.11.0",
      "vulns": []
    },
    {
      "name": "ckzg",
      "version": "2.1.8",
      "vulns": []
    },
    {
      "name": "eth-abi",
      "version": "6.0.0",
      "vulns": []
    },
    {
      "name": "parsimonious",
      "version": "0.10.0",
      "vulns": []
    },
    {
      "name": "eth-hash",
      "version": "0.8.0",
      "vulns": []
    },
    {
      "name": "pycryptodome",
      "version": "3.23.0",
      "vulns": []
    },
    {
      "name": "eth-keyfile",
      "version": "0.10.0",
      "vulns": []
    },
    {
      "name": "eth-keys",
      "version": "0.8.0",
      "vulns": []
    },
    {
      "name": "eth-rlp",
      "version": "3.0.0",
      "vulns": []
    },
    {
      "name": "eth-typing",
      "version": "6.0.0",
      "vulns": []
    },
    {
      "name": "eth-utils",
      "version": "6.0.0",
      "vulns": []
    },
    {
      "name": "pydantic",
      "version": "2.13.5",
      "vulns": []
    },
    {
      "name": "pydantic-core",
      "version": "2.46.5",
      "vulns": []
    },
    {
      "name": "annotated-types",
      "version": "0.8.0",
      "vulns": []
    },
    {
      "name": "cytoolz",
      "version": "1.1.0",
      "vulns": []
    },
    {
      "name": "frozenlist",
      "version": "1.8.0",
      "vulns": []
    },
    {
      "name": "hexbytes",
      "version": "2.0.0",
      "vulns": []
    },
    {
      "name": "idna",
      "version": "3.20",
      "vulns": []
    },
    {
      "name": "propcache",
      "version": "0.5.4",
      "vulns": []
    },
    {
      "name": "py-ecc",
      "version": "8.0.0",
      "vulns": []
    },
    {
      "name": "pyunormalize",
      "version": "18.0.0",
      "vulns": []
    },
    {
      "name": "regex",
      "version": "2026.9.29",
      "vulns": []
    },
    {
      "name": "requests",
      "version": "2.34.2",
      "vulns": []
    },
    {
      "name": "charset-normalizer",
      "version": "3.5.2",
      "vulns": []
    },
    {
      "name": "urllib3",
      "version": "2.8.0",
      "vulns": []
    },
    {
      "name": "certifi",
      "version": "2026.7.22",
      "vulns": []
    },
    {
      "name": "rlp",
      "version": "5.0.0",
      "vulns": []
    },
    {
      "name": "toolz",
      "version": "1.1.0",
      "vulns": []
    },
    {
      "name": "typing-extensions",
      "version": "4.16.0",
      "vulns": []
    },
    {
      "name": "typing-inspection",
      "version": "0.4.4",
      "vulns": []
    },
    {
      "name": "websockets",
      "version": "17.1",
      "vulns": []
    }
  ],
  "fixes": []
}
```

## Secret Scan
Detected candidate secret entries: **4**

## Mandatory manual/runtime items still required
- Verify router/factory addresses from official sources.
- Fork buy -> sell simulation on candidate tokens.
- Measure actual buy/sell tax and round-trip loss.
- Verify LP/admin/proxy/mint/blacklist/pause/fee-change risks.
- Verify gas + all fees + slippage + safety reserve leaves minimum net profit.
- Test executor on fork/test environment.
- Verify private submission path.
- Complete large dry-run audit before any real-money canary.
