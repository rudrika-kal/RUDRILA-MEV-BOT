from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Iterable
import time

import requests


HONEYPOT_API = "https://api.honeypot.is/v2/IsHoneypot"


@dataclass(frozen=True)
class HoneypotEvidence:
    accepted: bool
    simulation_success: bool
    is_honeypot: bool | None
    risk: str
    risk_level: int | None
    buy_tax_bps: int | None
    sell_tax_bps: int | None
    transfer_tax_bps: int | None
    buy_gas: int | None
    sell_gas: int | None
    root_open_source: bool | None
    is_proxy: bool | None
    holder_failed: int | None
    high_tax_wallets: int | None
    reasons: tuple[str, ...]
    raw: dict[str, Any]


def _to_bps(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(round(float(value) * 100))
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_honeypot_response(
    data: dict[str, Any],
    *,
    max_combined_tax_bps: int = 800,
    max_risk_level: int = 19,
    require_open_source: bool = True,
    block_proxy: bool = True,
) -> HoneypotEvidence:
    reasons: list[str] = []

    simulation_success = data.get("simulationSuccess") is True
    if not simulation_success:
        reasons.append("BLOCK: honeypot buy/sell simulation did not succeed")

    hp = data.get("honeypotResult")
    is_honeypot = hp.get("isHoneypot") if isinstance(hp, dict) else None
    if is_honeypot is not False:
        reasons.append("BLOCK: honeypot status is true or unknown")

    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    risk = str(summary.get("risk", "unknown")).lower()
    risk_level = _to_int(summary.get("riskLevel"))
    if risk_level is None:
        reasons.append("BLOCK: risk level is unknown")
    elif risk_level > int(max_risk_level):
        reasons.append(f"BLOCK: risk level {risk_level} exceeds limit")

    sim = data.get("simulationResult") if isinstance(data.get("simulationResult"), dict) else {}
    buy_tax_bps = _to_bps(sim.get("buyTax"))
    sell_tax_bps = _to_bps(sim.get("sellTax"))
    transfer_tax_bps = _to_bps(sim.get("transferTax"))
    if buy_tax_bps is None or sell_tax_bps is None:
        reasons.append("BLOCK: buy/sell tax measurement is missing")
    elif buy_tax_bps + sell_tax_bps > int(max_combined_tax_bps):
        reasons.append("BLOCK: combined token tax exceeds configured limit")

    buy_gas = _to_int(sim.get("buyGas"))
    sell_gas = _to_int(sim.get("sellGas"))
    if buy_gas is None or sell_gas is None:
        reasons.append("BLOCK: simulated buy/sell gas is missing")

    code = data.get("contractCode") if isinstance(data.get("contractCode"), dict) else {}
    root_open_source = code.get("rootOpenSource")
    is_proxy = code.get("isProxy")
    if require_open_source and root_open_source is not True:
        reasons.append("BLOCK: root token contract is not proven open source")
    if block_proxy and is_proxy is not False:
        reasons.append("BLOCK: proxy status is true or unknown")

    holder = data.get("holderAnalysis") if isinstance(data.get("holderAnalysis"), dict) else {}
    holder_failed = _to_int(holder.get("failed"))
    high_tax_wallets = _to_int(holder.get("highTaxWallets"))
    if holder_failed is None:
        reasons.append("BLOCK: holder sell-failure analysis is missing")
    elif holder_failed > 0:
        reasons.append("BLOCK: analyzed holders include sell failures")
    if high_tax_wallets is None:
        reasons.append("BLOCK: high-tax wallet analysis is missing")
    elif high_tax_wallets > 0:
        reasons.append("BLOCK: high-tax wallets detected")

    flags = summary.get("flags")
    if not isinstance(flags, list):
        flags = data.get("flags") if isinstance(data.get("flags"), list) else []
    for flag in flags:
        if isinstance(flag, dict):
            severity = str(flag.get("severity", "")).lower()
            if severity in {"high", "critical"}:
                reasons.append(f"BLOCK: risk flag {flag.get('flag', 'unknown')} ({severity})")
        elif isinstance(flag, str):
            reasons.append(f"BLOCK: honeypot warning flag {flag}")

    return HoneypotEvidence(
        accepted=not reasons,
        simulation_success=simulation_success,
        is_honeypot=is_honeypot,
        risk=risk,
        risk_level=risk_level,
        buy_tax_bps=buy_tax_bps,
        sell_tax_bps=sell_tax_bps,
        transfer_tax_bps=transfer_tax_bps,
        buy_gas=buy_gas,
        sell_gas=sell_gas,
        root_open_source=root_open_source,
        is_proxy=is_proxy,
        holder_failed=holder_failed,
        high_tax_wallets=high_tax_wallets,
        reasons=tuple(reasons) if reasons else ("PASS: external honeypot simulation",),
        raw=data,
    )


def _evidence_score(evidence: HoneypotEvidence) -> int:
    score = 0
    if evidence.accepted:
        score += 10000
    if evidence.simulation_success:
        score += 500
    if evidence.is_honeypot is False:
        score += 500
    if evidence.risk_level is not None:
        score += 100
    if evidence.buy_tax_bps is not None and evidence.sell_tax_bps is not None:
        score += 300
    if evidence.buy_gas is not None and evidence.sell_gas is not None:
        score += 100
    if evidence.root_open_source is True:
        score += 100
    if evidence.is_proxy is False:
        score += 100
    if evidence.holder_failed is not None:
        score += 200
    if evidence.high_tax_wallets is not None:
        score += 200
    return score


def check_honeypot(
    *,
    token: str,
    chain_id: int,
    pair: str | None = None,
    pairs: Iterable[str] = (),
    timeout_seconds: int = 6,
    max_combined_tax_bps: int = 800,
    max_risk_level: int = 19,
    actual_retries: int = 1,
    retry_delay_seconds: float = 0.25,
) -> HoneypotEvidence:
    """Collect strongest actual-pair Honeypot.is evidence, fail closed on gaps.

    Explicit real pairs are tried before the API's auto-pair selection. Fresh
    pools get a short bounded retry window because indexers can lag the block
    that created/updated a pair. Synthetic-liquidity simulation remains purely
    diagnostic and is used only when no actual-pair response is available.
    """
    base_params: dict[str, Any] = {"address": token, "chainID": int(chain_id)}

    explicit_pairs: list[str] = []
    for value in ((pair,) if pair else ()) + tuple(pairs):
        value = str(value)
        if value and value.lower() not in {x.lower() for x in explicit_pairs}:
            explicit_pairs.append(value)

    actual_attempts: list[dict[str, Any]] = []
    for value in explicit_pairs:
        params = dict(base_params)
        params["pair"] = value
        actual_attempts.append(params)
    actual_attempts.append(dict(base_params))

    session = requests.Session()
    last_reason = "honeypot API unavailable"
    last_raw: dict[str, Any] = {}
    best_actual: HoneypotEvidence | None = None

    def request_once(params: dict[str, Any]) -> HoneypotEvidence | None:
        nonlocal last_reason, last_raw
        try:
            response = session.get(
                HONEYPOT_API,
                params=params,
                headers={
                    "User-Agent": "RUDRILA-MEV/0.15",
                    "Accept": "application/json",
                },
                timeout=(2.5, float(timeout_seconds)),
            )
        except requests.RequestException as exc:
            last_reason = f"honeypot API request failed: {type(exc).__name__}"
            last_raw = {
                "used_pair": "pair" in params,
                "exception": type(exc).__name__,
            }
            return None

        if not response.ok:
            try:
                preview = (response.text or "").strip().replace("\n", " ")[:240]
            except Exception:
                preview = ""
            last_reason = f"honeypot API HTTP {response.status_code}"
            last_raw = {
                "http_status": int(response.status_code),
                "used_pair": "pair" in params,
                "body_preview": preview,
            }
            return None

        try:
            data = response.json()
        except ValueError:
            last_reason = "honeypot API returned invalid JSON"
            last_raw = {
                "http_status": int(response.status_code),
                "used_pair": "pair" in params,
            }
            return None
        if not isinstance(data, dict):
            last_reason = "honeypot API returned non-object data"
            last_raw = {
                "http_status": int(response.status_code),
                "used_pair": "pair" in params,
            }
            return None

        if "pair" in params:
            request_mode = "pair"
        elif params.get("simulateLiquidity") is True:
            request_mode = "simulated_liquidity"
        elif params.get("forceSimulateLiquidity") is True:
            request_mode = "forced_simulated_liquidity"
        else:
            request_mode = "auto_pair"

        data = dict(data)
        data["_rudrila_request_mode"] = request_mode
        if "pair" in params:
            data["_rudrila_requested_pair"] = str(params["pair"])

        evidence = parse_honeypot_response(
            data,
            max_combined_tax_bps=max_combined_tax_bps,
            max_risk_level=max_risk_level,
        )

        # Ensure a pair-specific response actually describes the requested pool.
        if "pair" in params:
            returned = data.get("pairAddress")
            pair_obj = data.get("pair")
            if not returned and isinstance(pair_obj, dict):
                nested = pair_obj.get("pair")
                if isinstance(nested, dict):
                    returned = nested.get("address")
            if returned and str(returned).lower() != str(params["pair"]).lower():
                evidence = replace(
                    evidence,
                    accepted=False,
                    reasons=evidence.reasons + (
                        "BLOCK: honeypot response pair does not match requested pool",
                    ),
                )
        return evidence

    try:
        rounds = max(1, int(actual_retries))
        for round_index in range(rounds):
            for params in actual_attempts:
                evidence = request_once(params)
                if evidence is None:
                    continue
                if evidence.accepted:
                    return evidence
                if best_actual is None or _evidence_score(evidence) > _evidence_score(best_actual):
                    best_actual = evidence
            if best_actual is not None:
                # An actual-pair response is authoritative even when it blocks.
                # Retrying can fill transient missing holder/indexer fields, but
                # synthetic liquidity must never override real-pair risk evidence.
                if round_index + 1 >= rounds:
                    return best_actual
            if round_index + 1 < rounds:
                time.sleep(max(0.0, float(retry_delay_seconds)))

        if best_actual is not None:
            return best_actual

        # No actual-pair response at all: collect synthetic diagnostics only.
        synthetic_attempts = []
        for key in ("simulateLiquidity", "forceSimulateLiquidity"):
            params = dict(base_params)
            params[key] = True
            synthetic_attempts.append(params)
        for params in synthetic_attempts:
            evidence = request_once(params)
            if evidence is None:
                continue
            return replace(
                evidence,
                accepted=False,
                reasons=evidence.reasons + (
                    "BLOCK: synthetic-liquidity fallback is diagnostic only; "
                    "actual-pair/fork sellability proof is still required",
                ),
            )
    finally:
        session.close()

    return HoneypotEvidence(
        accepted=False,
        simulation_success=False,
        is_honeypot=None,
        risk="unknown",
        risk_level=None,
        buy_tax_bps=None,
        sell_tax_bps=None,
        transfer_tax_bps=None,
        buy_gas=None,
        sell_gas=None,
        root_open_source=None,
        is_proxy=None,
        holder_failed=None,
        high_tax_wallets=None,
        reasons=(f"BLOCK: {last_reason}",),
        raw=last_raw,
    )
