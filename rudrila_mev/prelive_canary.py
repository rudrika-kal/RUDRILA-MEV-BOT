from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from web3 import Web3

from .abi import V2_ROUTER_ABI
from .private_submission import probe_default_bsc_private_paths

CHAIN_ID = 56
WBNB = Web3.to_checksum_address("0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c")
CAKE = Web3.to_checksum_address("0x0E09Fabb73Bd3Ade0a17ECC321fD13a19e81cE82")
PANCAKE_V2_ROUTER = Web3.to_checksum_address("0x10ED43C718714eb63d5aA57B78B54704E256024E")
BISWAP_V2_ROUTER = Web3.to_checksum_address("0x3a6d8cA21D1CF76F653A67577FA0D27453350dD8")
CANARY_AMOUNT_WEI = 1_000_000_000_000_000
PUBLIC_MEMPOOL_FALLBACK = False

REQUIRED_REPORTS = (
    "V095_TAX_SELLABILITY_REPORT.md",
    "V096_LIQUIDITY_SAFETY_REPORT.md",
    "V097_ADMIN_SAFETY_REPORT.md",
    "V098_LIQUIDITY_IMPACT_REPORT.md",
    "V099_ALL_COST_PROFIT_REPORT.md",
    "V0100_EXECUTOR_REPORT.md",
    "V0110_PRIVATE_SUBMISSION_REPORT.md",
    "V0120_EXECUTION_RISK_REPORT.md",
    "V0130_STRICT_SCANNERS_REPORT.md",
    "V0140_SHADOW_AUDIT_REPORT.md",
)


@dataclass(frozen=True)
class PreLiveStatus:
    platform_ready: bool
    wallet_connected: bool
    live_test_started: bool
    chain_id: int | None
    latest_block: int | None
    pancake_quote_out: int | None
    biswap_quote_out: int | None
    healthy_private_paths: int
    public_mempool_fallback: bool
    canary_amount_wei: int
    prior_gate_reports_ok: bool
    reasons: tuple[str, ...]

    def as_dict(self):
        return asdict(self)


def _reports_ok(repo_root: Path) -> tuple[bool, list[str]]:
    missing = [name for name in REQUIRED_REPORTS if not (repo_root / name).exists()]
    if missing:
        return False, [f"missing report: {x}" for x in missing]
    return True, []


def inspect_prelive(*, repo_root: str | Path = ".", rpc_url: str | None = None) -> PreLiveStatus:
    reasons: list[str] = []
    root = Path(repo_root)
    reports_ok, report_reasons = _reports_ok(root)
    reasons.extend(report_reasons)

    wallet = os.environ.get("MEV_WALLET_ADDRESS", "").strip()
    wallet_connected = False
    if wallet:
        try:
            Web3.to_checksum_address(wallet)
            wallet_connected = True
        except Exception:
            reasons.append("wallet address is present but invalid")

    live_test_started = os.environ.get("CANARY_LIVE_TEST_STARTED", "").strip().lower() == "true"
    rpc = (rpc_url or os.environ.get("MEV_RPC_URL", "")).strip()
    chain_id = None
    latest_block = None
    pancake_quote = None
    biswap_quote = None

    if not rpc:
        reasons.append("MEV_RPC_URL missing")
    else:
        try:
            w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 12}))
            if not w3.is_connected():
                raise RuntimeError("RPC not connected")
            chain_id = int(w3.eth.chain_id)
            if chain_id != CHAIN_ID:
                reasons.append(f"wrong chain id {chain_id}; expected {CHAIN_ID}")
            latest_block = int(w3.eth.block_number)
            for label, address in (
                ("WBNB", WBNB), ("CAKE", CAKE),
                ("Pancake router", PANCAKE_V2_ROUTER),
                ("Biswap router", BISWAP_V2_ROUTER),
            ):
                if len(w3.eth.get_code(address)) == 0:
                    reasons.append(f"{label} has no contract code")
            p = w3.eth.contract(address=PANCAKE_V2_ROUTER, abi=V2_ROUTER_ABI)
            b = w3.eth.contract(address=BISWAP_V2_ROUTER, abi=V2_ROUTER_ABI)
            pancake_quote = int(p.functions.getAmountsOut(
                CANARY_AMOUNT_WEI, [WBNB, CAKE]
            ).call(block_identifier=latest_block)[-1])
            biswap_quote = int(b.functions.getAmountsOut(
                CANARY_AMOUNT_WEI, [WBNB, CAKE]
            ).call(block_identifier=latest_block)[-1])
            if min(pancake_quote, biswap_quote) <= 0:
                reasons.append("one or more read-only router quotes are zero")
        except Exception as exc:
            reasons.append(f"BSC read-only preflight failed: {type(exc).__name__}: {exc}")

    healthy_private = 0
    try:
        private = probe_default_bsc_private_paths(
            required_paths=2,
            timeout=6.0,
        )
        healthy_private = int(private.healthy_paths)
        if not private.accepted:
            reasons.extend(private.reasons)
    except Exception as exc:
        reasons.append(f"private-path read-only probe failed: {type(exc).__name__}: {exc}")

    if PUBLIC_MEMPOOL_FALLBACK:
        reasons.append("public mempool fallback unexpectedly enabled")
    if CANARY_AMOUNT_WEI > 1_000_000_000_000_000:
        reasons.append("canary amount exceeds hard cap")

    platform_ready = (
        reports_ok
        and chain_id == CHAIN_ID
        and pancake_quote is not None and pancake_quote > 0
        and biswap_quote is not None and biswap_quote > 0
        and healthy_private >= 2
        and not PUBLIC_MEMPOOL_FALLBACK
        and CANARY_AMOUNT_WEI <= 1_000_000_000_000_000
    )
    if platform_ready:
        reasons.append("PASS: pre-live platform is ready; wallet connection/live testing are intentionally not performed")
    return PreLiveStatus(
        platform_ready=platform_ready,
        wallet_connected=wallet_connected,
        live_test_started=live_test_started,
        chain_id=chain_id,
        latest_block=latest_block,
        pancake_quote_out=pancake_quote,
        biswap_quote_out=biswap_quote,
        healthy_private_paths=healthy_private,
        public_mempool_fallback=PUBLIC_MEMPOOL_FALLBACK,
        canary_amount_wei=CANARY_AMOUNT_WEI,
        prior_gate_reports_ok=reports_ok,
        reasons=tuple(reasons),
    )


def main() -> int:
    status = inspect_prelive(repo_root=Path(__file__).resolve().parents[1])
    print(json.dumps({"event":"PRELIVE_CANARY_STATUS", **status.as_dict()}, separators=(",", ":")))
    if not status.platform_ready:
        return 2
    if not status.wallet_connected:
        print(json.dumps({
            "event":"WAITING_FOR_WALLET",
            "safe":True,
            "live_test_started":False,
            "message":"Platform ready. No signing/broadcast capability is used by this service."
        }, separators=(",", ":")))
    else:
        print(json.dumps({
            "event":"WALLET_ADDRESS_PRESENT",
            "safe":True,
            "live_test_started":False,
            "message":"Wallet address detected; live testing still requires a separate explicit step."
        }, separators=(",", ":")))
    while True:
        time.sleep(300)


if __name__ == "__main__":
    raise SystemExit(main())
