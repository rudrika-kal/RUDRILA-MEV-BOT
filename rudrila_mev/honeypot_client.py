from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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


def check_honeypot(
    *,
    token: str,
    chain_id: int,
    pair: str | None = None,
    timeout_seconds: int = 10,
    max_combined_tax_bps: int = 800,
    max_risk_level: int = 19,
) -> HoneypotEvidence:
    params: dict[str, Any] = {"address": token, "chainID": int(chain_id)}
    if pair:
        params["pair"] = pair

    session = requests.Session()
    try:
        response = session.get(
            HONEYPOT_API,
            params=params,
            headers={"User-Agent": "RUDRILA-MEV/0.6"},
            timeout=(3.05, float(timeout_seconds)),
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
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
            reasons=(f"BLOCK: honeypot API unavailable or invalid: {type(exc).__name__}",),
            raw={},
        )
    finally:
        session.close()

    if not isinstance(data, dict):
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
            reasons=("BLOCK: honeypot API returned non-object data",),
            raw={},
        )

    return parse_honeypot_response(
        data,
        max_combined_tax_bps=max_combined_tax_bps,
        max_risk_level=max_risk_level,
    )
