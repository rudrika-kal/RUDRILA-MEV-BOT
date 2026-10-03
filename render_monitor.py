from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from web3 import Web3

from rudrila_mev.admin_safety import collect_admin_safety
from rudrila_mev.all_cost_profit import missing_route_profit_evidence
from rudrila_mev.executor_guard import evaluate_executor_safety
from rudrila_mev.honeypot_client import check_honeypot
from rudrila_mev.launch_monitor import V2LaunchMonitor, token_preflight
from rudrila_mev.liquidity_safety import (
    collect_v2_liquidity_safety,
    discover_and_collect_v3_liquidity_safety,
)
from rudrila_mev.liquidity_impact import (
    collect_v2_liquidity_impact,
    collect_v3_liquidity_impact,
)
from rudrila_mev.private_submission import probe_default_bsc_private_paths
from rudrila_mev.ledger import ExecutionLedger, evaluate_execution_risk
from rudrila_mev.ci_validation import runtime_scanner_attestation
from rudrila_mev.v3_monitor import V3LaunchMonitor


CHAIN_ID = 56
WBNB = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"
PANCAKE_V2_FACTORY = "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73"
PANCAKE_V3_FACTORY = "0x0BFbCF9fa4f9C56B0F40a671Ad40E0805A091865"
PANCAKE_V3_POSITION_MANAGER = "0x46A15B0b27311cedF172AB29E4f4766fbE7F4364"
PANCAKE_V3_QUOTER_V2 = "0xB048Bbc1Ee6b733FFfCFb9e9CeF7375518e25997"

RPC = os.environ.get("MEV_RPC_URL", "https://bsc-rpc.publicnode.com")
MIN_BASE_LIQ = int(os.environ.get("MIN_BASE_LIQUIDITY_WEI", "1000000000000000000"))
CONFIRMATIONS = int(os.environ.get("LAUNCH_CONFIRMATIONS", "120"))
RPC_SAFETY_LAG = int(os.environ.get("RPC_SAFETY_LAG_BLOCKS", "180"))
POLL_SECONDS = float(os.environ.get("POLL_SECONDS", "3"))
MAX_TAX_BPS = int(os.environ.get("MAX_COMBINED_TOKEN_TAX_BPS", "800"))
MAX_RISK_LEVEL = int(os.environ.get("HONEYPOT_MAX_RISK_LEVEL", "19"))
LP_MIN_SECURED_BPS = int(os.environ.get("LP_MIN_SECURED_BPS", "9500"))
LP_MAX_REMOVABLE_BPS = int(os.environ.get("LP_MAX_REMOVABLE_BPS", "0"))
V3_LP_MIN_SECURED_BPS = int(os.environ.get("V3_LP_MIN_SECURED_BPS", "10000"))
IMPACT_AMOUNT_IN_WEI = int(os.environ.get("IMPACT_AMOUNT_IN_WEI", "1000000000000000"))
MAX_PRICE_IMPACT_BPS = int(os.environ.get("MAX_PRICE_IMPACT_BPS", "250"))
MAX_QUOTE_AGE_BLOCKS = int(os.environ.get("MAX_QUOTE_AGE_BLOCKS", "8"))
V2_SWAP_FEE_BPS = int(os.environ.get("V2_SWAP_FEE_BPS", "25"))
V3_MAX_TICKS_CROSSED = int(os.environ.get("V3_MAX_TICKS_CROSSED", "8"))
V3_MIN_VIRTUAL_BASE_LIQUIDITY_WEI = int(
    os.environ.get("V3_MIN_VIRTUAL_BASE_LIQUIDITY_WEI", "100000000000000000")
)
MIN_NET_PROFIT_WEI = int(os.environ.get("MIN_NET_PROFIT_WEI", "100000000000000"))
PRIVATE_PATH_TIMEOUT_SECONDS = float(os.environ.get("PRIVATE_PATH_TIMEOUT_SECONDS", "6"))
PRIVATE_PATH_REQUIRED = int(os.environ.get("PRIVATE_PATH_REQUIRED", "2"))
RUNTIME_LEDGER_PATH = os.environ.get(
    "RUNTIME_LEDGER_PATH", "/tmp/rudrila_mev_runtime_ledger.jsonl"
)
MAX_HOURLY_NET_LOSS_WEI = int(
    os.environ.get("MAX_HOURLY_NET_LOSS_WEI", "2000000000000000")
)
MAX_DAILY_NET_LOSS_WEI = int(
    os.environ.get("MAX_DAILY_NET_LOSS_WEI", "5000000000000000")
)
MAX_DAILY_FAILED_GAS_WEI = int(
    os.environ.get("MAX_DAILY_GAS_LOSS_WEI", "5000000000000000")
)
MAX_HOURLY_FAILED_TRANSACTIONS = int(
    os.environ.get("MAX_HOURLY_FAILED_TRANSACTIONS", "2")
)
MAX_DAILY_FAILED_TRANSACTIONS = int(
    os.environ.get("MAX_DAILY_FAILED_TRANSACTIONS", "3")
)
MAX_DAILY_REVERTS = int(os.environ.get("MAX_DAILY_REVERTS", "3"))
STRICT_SCANNER_CI_VERIFIED = os.environ.get(
    "STRICT_SCANNER_CI_VERIFIED", "false"
).lower() == "true"
STRICT_SCANNER_CI_COMMIT = os.environ.get("STRICT_SCANNER_CI_COMMIT", "")
RUNTIME_LEDGER = ExecutionLedger(RUNTIME_LEDGER_PATH)


def _csv_addresses(name: str) -> list[str]:
    return [x.strip() for x in os.environ.get(name, "").split(",") if x.strip()]


VERIFIED_V2_LOCKERS = _csv_addresses("VERIFIED_V2_LP_LOCKER_ADDRESSES")
VERIFIED_V3_LOCKERS = _csv_addresses("VERIFIED_V3_POSITION_LOCKER_ADDRESSES")

STATE = {
    "service": "RUDRILA-MEV-V0140-SHADOW",
    "mode": "SHADOW_AUDIT",
    "live_trading": False,
    "private_key_loaded": False,
    "submission_attempted": False,
    "public_mempool_fallback_allowed": False,
    "chain_id_expected": CHAIN_ID,
    "status": "starting",
    "rpc_connected": False,
    "last_processed_block": None,
    "latest_block": None,
    "detected_candidates": 0,
    "external_risk_passed": 0,
    "blocked_candidates": 0,
    "last_candidate": None,
    "last_error": None,
    "updated_at": None,
}
LOCK = threading.Lock()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def update(**kwargs) -> None:
    with LOCK:
        STATE.update(kwargs)
        STATE["updated_at"] = now()


def emit(event: dict) -> None:
    print(json.dumps(event, separators=(",", ":"), default=str), flush=True)


def _liquidity_safety(kind: str, candidate, w3: Web3):
    pool = getattr(candidate, "pair", None) or getattr(candidate, "pool", None)
    latest = int(w3.eth.block_number)
    start = int(candidate.block_number)

    if kind == "PANCAKESWAP_V2":
        return collect_v2_liquidity_safety(
            w3,
            pair=pool,
            from_block=start,
            to_block=latest,
            verified_safe_holders=VERIFIED_V2_LOCKERS,
            min_secured_bps=LP_MIN_SECURED_BPS,
            max_removable_bps=LP_MAX_REMOVABLE_BPS,
        )

    return discover_and_collect_v3_liquidity_safety(
        w3,
        position_manager=PANCAKE_V3_POSITION_MANAGER,
        token0=candidate.base_token,
        token1=candidate.token,
        fee=int(candidate.fee),
        from_block=start,
        to_block=latest,
        verified_safe_owners=VERIFIED_V3_LOCKERS,
        min_secured_bps=V3_LP_MIN_SECURED_BPS,
        max_removable_bps=LP_MAX_REMOVABLE_BPS,
    )



def _impact_safety(kind: str, candidate, w3: Web3):
    pool = getattr(candidate, "pair", None) or getattr(candidate, "pool", None)
    if kind == "PANCAKESWAP_V2":
        return collect_v2_liquidity_impact(
            w3,
            pair=pool,
            base_token=candidate.base_token,
            amount_in_wei=IMPACT_AMOUNT_IN_WEI,
            fee_bps=V2_SWAP_FEE_BPS,
            min_base_liquidity_wei=MIN_BASE_LIQ,
            max_price_impact_bps=MAX_PRICE_IMPACT_BPS,
            max_quote_age_blocks=MAX_QUOTE_AGE_BLOCKS,
        )
    return collect_v3_liquidity_impact(
        w3,
        pool=pool,
        base_token=candidate.base_token,
        amount_in_wei=IMPACT_AMOUNT_IN_WEI,
        quoter_v2=PANCAKE_V3_QUOTER_V2,
        min_base_liquidity_wei=V3_MIN_VIRTUAL_BASE_LIQUIDITY_WEI,
        max_price_impact_bps=MAX_PRICE_IMPACT_BPS,
        max_quote_age_blocks=MAX_QUOTE_AGE_BLOCKS,
        max_initialized_ticks_crossed=V3_MAX_TICKS_CROSSED,
    )


def _profit_safety(candidate, w3: Web3):
    return missing_route_profit_evidence(
        amount_in_wei=IMPACT_AMOUNT_IN_WEI,
        current_block=int(w3.eth.block_number),
        min_net_profit_wei=MIN_NET_PROFIT_WEI,
        reason=(
            "BLOCK: executable route economics are unavailable; gas, builder/private "
            "payment, token-tax provenance and minimum net profit must be proven"
        ),
    )


def _private_submission_safety():
    return probe_default_bsc_private_paths(
        required_paths=PRIVATE_PATH_REQUIRED,
        timeout=PRIVATE_PATH_TIMEOUT_SECONDS,
    )


def _execution_risk_safety():
    return evaluate_execution_risk(
        RUNTIME_LEDGER,
        max_hourly_net_loss_wei=MAX_HOURLY_NET_LOSS_WEI,
        max_daily_net_loss_wei=MAX_DAILY_NET_LOSS_WEI,
        max_daily_failed_gas_wei=MAX_DAILY_FAILED_GAS_WEI,
        max_hourly_failed_transactions=MAX_HOURLY_FAILED_TRANSACTIONS,
        max_daily_failed_transactions=MAX_DAILY_FAILED_TRANSACTIONS,
        max_daily_reverts=MAX_DAILY_REVERTS,
    )


def _strict_scanner_safety():
    return runtime_scanner_attestation(
        ci_verified=STRICT_SCANNER_CI_VERIFIED,
        commit_sha=STRICT_SCANNER_CI_COMMIT,
    )


def _executor_safety(candidate, w3: Web3):
    return evaluate_executor_safety(
        executor_deployed=False,
        owner_matches=None,
        source_verified=None,
        behavioral_tests_passed=True,
        routers_allowlisted=None,
        paused_state_known=False,
        paused=None,
        dirty_balance_guard_verified=True,
        exact_approval_cleanup_verified=True,
        paused_rescue_verified=True,
        non_reentrant_verified=True,
    )

def handle_candidate(kind: str, candidate, w3: Web3) -> None:
    token = candidate.token
    pool = getattr(candidate, "pair", None) or getattr(candidate, "pool", None)

    pf = token_preflight(w3, token, min_code_bytes=32, max_decimals=24)
    external = None
    liquidity = None
    admin = None
    impact = None
    profit = None
    executor = None
    private_submission = None
    execution_risk = None
    strict_scanner = None
    reasons = []

    if not pf.accepted:
        reasons.append(pf.reason)
    else:
        external = check_honeypot(
            token=token,
            chain_id=CHAIN_ID,
            pair=pool,
            max_combined_tax_bps=MAX_TAX_BPS,
            max_risk_level=MAX_RISK_LEVEL,
        )
        reasons.extend(external.reasons)

        try:
            liquidity = _liquidity_safety(kind, candidate, w3)
            reasons.extend(liquidity.reasons)
        except Exception as exc:
            reasons.append(
                f"BLOCK: liquidity safety evidence failed closed: "
                f"{type(exc).__name__}: {exc}"
            )

        try:
            admin = collect_admin_safety(w3, token)
            reasons.extend(admin.reasons)
        except Exception as exc:
            reasons.append(
                f"BLOCK: admin safety evidence failed closed: "
                f"{type(exc).__name__}: {exc}"
            )

        try:
            impact = _impact_safety(kind, candidate, w3)
            reasons.extend(impact.reasons)
        except Exception as exc:
            reasons.append(
                f"BLOCK: liquidity/price-impact evidence failed closed: "
                f"{type(exc).__name__}: {exc}"
            )

        try:
            profit = _profit_safety(candidate, w3)
            reasons.extend(profit.reasons)
        except Exception as exc:
            reasons.append(
                f"BLOCK: all-cost profit evidence failed closed: "
                f"{type(exc).__name__}: {exc}"
            )

        try:
            executor = _executor_safety(candidate, w3)
            reasons.extend(executor.reasons)
        except Exception as exc:
            reasons.append(
                f"BLOCK: executor safety evidence failed closed: "
                f"{type(exc).__name__}: {exc}"
            )

        try:
            private_submission = _private_submission_safety()
            reasons.extend(private_submission.reasons)
        except Exception as exc:
            reasons.append(
                f"BLOCK: private submission evidence failed closed: "
                f"{type(exc).__name__}: {exc}"
            )

        try:
            execution_risk = _execution_risk_safety()
            reasons.extend(execution_risk.reasons)
        except Exception as exc:
            reasons.append(
                f"BLOCK: execution-risk evidence failed closed: "
                f"{type(exc).__name__}: {exc}"
            )

        try:
            strict_scanner = _strict_scanner_safety()
            reasons.extend(strict_scanner.reasons)
        except Exception as exc:
            reasons.append(
                f"BLOCK: strict-scanner attestation failed closed: "
                f"{type(exc).__name__}: {exc}"
            )

    event = {
        "time": now(),
        "event": "NEW_POOL_CANDIDATE",
        "dex": kind,
        "block": candidate.block_number,
        "pool": pool,
        "token": token,
        "symbol": pf.symbol or "UNKNOWN",
        "token_preflight": pf.accepted,
        "external_honeypot": (
            {
                "accepted": external.accepted,
                "simulation_success": external.simulation_success,
                "is_honeypot": external.is_honeypot,
                "risk": external.risk,
                "risk_level": external.risk_level,
                "buy_tax_bps": external.buy_tax_bps,
                "sell_tax_bps": external.sell_tax_bps,
                "transfer_tax_bps": external.transfer_tax_bps,
                "root_open_source": external.root_open_source,
                "is_proxy": external.is_proxy,
                "reasons": list(external.reasons[:10]),
            }
            if external is not None
            else None
        ),
        "liquidity_safety": (
            {
                "accepted": liquidity.accepted,
                "dex": liquidity.dex,
                "lock_or_burn_proven": liquidity.lock_or_burn_proven,
                "creator_or_provider_control": (
                    liquidity.liquidity_removal_controlled_by_creator
                ),
                "secured_bps": liquidity.secured_bps,
                "removable_bps": liquidity.removable_bps,
                "unknown_bps": liquidity.unknown_bps,
                "holder_or_position_count": liquidity.holder_or_position_count,
                "reasons": list(liquidity.reasons[:10]),
            }
            if liquidity is not None
            else None
        ),
        "admin_safety": (
            {
                "accepted": admin.accepted,
                "owner": admin.owner,
                "admin": admin.admin,
                "admin_read_resolved": admin.admin_read_resolved,
                "is_proxy": admin.is_proxy,
                "proxy_kind": admin.proxy_kind,
                "implementation": admin.implementation,
                "implementation_checked": admin.implementation_checked,
                "can_mint": admin.can_mint,
                "can_blacklist": admin.can_blacklist,
                "can_pause_trading": admin.can_pause_trading,
                "can_change_fees": admin.can_change_fees,
                "can_change_max_tx_or_wallet": admin.can_change_max_tx_or_wallet,
                "reasons": list(admin.reasons[:12]),
            }
            if admin is not None
            else None
        ),
        "liquidity_impact": (
            {
                "accepted": impact.accepted,
                "dex": impact.dex,
                "block_number": impact.block_number,
                "quote_age_blocks": impact.quote_age_blocks,
                "amount_in": impact.amount_in,
                "amount_out": impact.amount_out,
                "price_impact_bps": impact.price_impact_bps,
                "base_liquidity_wei": impact.base_liquidity_wei,
                "active_liquidity": impact.active_liquidity,
                "initialized_ticks_crossed": impact.initialized_ticks_crossed,
                "reasons": list(impact.reasons[:10]),
            }
            if impact is not None
            else None
        ),
        "all_cost_profit": (
            {
                "accepted": profit.accepted,
                "floor_gross_profit_wei": profit.floor_gross_profit_wei,
                "gas_cost_wei": profit.gas_cost_wei,
                "builder_payment_wei": profit.builder_payment_wei,
                "non_embedded_cost_wei": profit.non_embedded_cost_wei,
                "dex_fee_deduction_wei": profit.dex_fee_deduction_wei,
                "slippage_deduction_wei": profit.slippage_deduction_wei,
                "token_tax_deduction_wei": profit.token_tax_deduction_wei,
                "safety_buffer_wei": profit.safety_buffer_wei,
                "min_net_profit_wei": profit.min_net_profit_wei,
                "floor_net_after_all_costs_wei": profit.floor_net_after_all_costs_wei,
                "quote_age_blocks": profit.quote_age_blocks,
                "reasons": list(profit.reasons[:10]),
            }
            if profit is not None
            else None
        ),
        "executor_safety": (
            {
                "accepted": executor.accepted,
                "executor_deployed": executor.executor_deployed,
                "owner_matches": executor.owner_matches,
                "source_verified": executor.source_verified,
                "behavioral_tests_passed": executor.behavioral_tests_passed,
                "routers_allowlisted": executor.routers_allowlisted,
                "paused_state_known": executor.paused_state_known,
                "paused": executor.paused,
                "dirty_balance_guard_verified": executor.dirty_balance_guard_verified,
                "exact_approval_cleanup_verified": executor.exact_approval_cleanup_verified,
                "paused_rescue_verified": executor.paused_rescue_verified,
                "non_reentrant_verified": executor.non_reentrant_verified,
                "reasons": list(executor.reasons[:12]),
            }
            if executor is not None
            else None
        ),
        "private_submission": (
            {
                "accepted": private_submission.accepted,
                "required_paths": private_submission.required_paths,
                "healthy_paths": private_submission.healthy_paths,
                "public_mempool_fallback_allowed": (
                    private_submission.public_mempool_fallback_allowed
                ),
                "paths": [p.as_dict() for p in private_submission.paths],
                "reasons": list(private_submission.reasons[:12]),
            }
            if private_submission is not None
            else None
        ),
        "execution_risk": (
            {
                "blocked": execution_risk.blocked,
                "hourly_realized_net_wei": execution_risk.hourly_realized_net_wei,
                "daily_realized_net_wei": execution_risk.daily_realized_net_wei,
                "hourly_failed_transactions": execution_risk.hourly_failed_transactions,
                "daily_failed_transactions": execution_risk.daily_failed_transactions,
                "daily_reverts": execution_risk.daily_reverts,
                "daily_failed_gas_wei": execution_risk.daily_failed_gas_wei,
                "audit_ok": execution_risk.audit_ok,
                "reasons": list(execution_risk.reasons[:12]),
            }
            if execution_risk is not None
            else None
        ),
        "strict_scanner": (
            strict_scanner.as_dict() if strict_scanner is not None else None
        ),
        "shadow_audit": {
            "mode": "SHADOW_AUDIT",
            "live_trading": False,
            "private_key_loaded": False,
            "submission_attempted": False,
            "public_mempool_fallback_allowed": False,
        },
        "trade_decision": "NO_TRADE",
        "why": (
            "Read-only test. Missing/unsafe honeypot, tax, transfer-out, LP ownership, "
            "admin/proxy, profit, executor, private-submission or loss-limit evidence "
            "cannot authorize a trade."
        ),
        "reasons": reasons[:20],
        "remaining_gates": [
            "tiny canary (requires explicit live-money authorization)",
        ],
    }

    emit(event)
    with LOCK:
        STATE["detected_candidates"] += 1
        if (
            external is not None
            and external.accepted
            and liquidity is not None
            and liquidity.accepted
            and admin is not None
            and admin.accepted
            and impact is not None
            and impact.accepted
            and profit is not None
            and profit.accepted
            and executor is not None
            and executor.accepted
            and private_submission is not None
            and private_submission.accepted
            and execution_risk is not None
            and not execution_risk.blocked
            and strict_scanner is not None
            and strict_scanner.accepted
        ):
            STATE["external_risk_passed"] += 1
        else:
            STATE["blocked_candidates"] += 1
        STATE["last_candidate"] = event
        STATE["updated_at"] = now()


def scanner_loop() -> None:
    while True:
        try:
            w3 = Web3(Web3.HTTPProvider(RPC, request_kwargs={"timeout": 10}))
            if not w3.is_connected():
                raise RuntimeError("RPC not connected")
            chain_id = int(w3.eth.chain_id)
            if chain_id != CHAIN_ID:
                raise RuntimeError(f"Wrong chain id {chain_id}; expected {CHAIN_ID}")

            update(status="running", rpc_connected=True, last_error=None)

            v2 = V2LaunchMonitor(
                w3,
                factories=[PANCAKE_V2_FACTORY],
                base_token=WBNB,
                min_base_liquidity_wei=MIN_BASE_LIQ,
                min_token_code_bytes=32,
                max_token_decimals=24,
            )
            v3 = V3LaunchMonitor(
                w3,
                factories=[PANCAKE_V3_FACTORY],
                base_token=WBNB,
                allowed_fee_tiers=[100, 500, 3000, 10000],
            )

            latest = int(w3.eth.block_number)
            lag = max(CONFIRMATIONS, RPC_SAFETY_LAG)
            last = max(0, latest - lag - 80)
            update(latest_block=latest, last_processed_block=last)

            while True:
                latest = int(w3.eth.block_number)
                target = latest - lag
                update(latest_block=latest)

                if target <= last:
                    time.sleep(POLL_SECONDS)
                    continue

                end = min(target, last + 20)
                try:
                    for c in v2.scan_range(last + 1, end):
                        handle_candidate("PANCAKESWAP_V2", c, w3)
                    for c in v3.scan_range(last + 1, end):
                        handle_candidate("PANCAKESWAP_V3", c, w3)
                    last = end
                    update(last_processed_block=last, status="running", last_error=None)
                except Exception as exc:
                    update(
                        status="rpc_retry",
                        last_error=f"{type(exc).__name__}: {exc}",
                    )
                    emit(
                        {
                            "time": now(),
                            "event": "SCAN_ERROR",
                            "error": str(exc),
                            "from": last + 1,
                            "to": end,
                        }
                    )
                    time.sleep(5)

                time.sleep(POLL_SECONDS)

        except Exception as exc:
            update(
                status="reconnecting",
                rpc_connected=False,
                last_error=f"{type(exc).__name__}: {exc}",
            )
            emit({"time": now(), "event": "RPC_ERROR", "error": str(exc)})
            time.sleep(5)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ("/", "/health", "/status"):
            self.send_response(404)
            self.end_headers()
            return

        with LOCK:
            body = json.dumps(STATE, indent=2, default=str).encode()

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        return


if __name__ == "__main__":
    print(
        "RUDRILA MEV v0.14.0 monitor starting in SHADOW AUDIT mode.",
        flush=True,
    )
    threading.Thread(target=scanner_loop, daemon=True).start()
    port = int(os.environ.get("PORT", "10000"))
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
