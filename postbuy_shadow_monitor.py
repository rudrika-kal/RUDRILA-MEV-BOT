from __future__ import annotations

import json
import os
import signal
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from web3 import LegacyWebSocketProvider, Web3
from web3.middleware import ExtraDataToPOAMiddleware

from rudrila_mev.abi import ERC20_ABI, EXECUTOR_ABI
from rudrila_mev.admin_safety import collect_admin_safety
from rudrila_mev.dynamic_firewall import evaluate_dynamic_token_firewall
from rudrila_mev.honeypot_client import check_honeypot
from rudrila_mev.launch_monitor import token_preflight
from rudrila_mev.ledger import ExecutionLedger, evaluate_execution_risk
from rudrila_mev.liquidity_impact import collect_v2_liquidity_impact
from rudrila_mev.liquidity_safety import (
    DEAD,
    ZERO,
    V2_LP_ABI,
    classify_liquidity_units,
    collect_uncx_v2_active_locks,
)
from rudrila_mev.postbuy_live import evaluate_live_postbuy_authorization
from rudrila_mev.postbuy_quote_shadow import (
    ReadOnlyVenue,
    quote_postbuy_v2_routes_read_only,
)
from rudrila_mev.postbuy_shadow_pipeline import evaluate_postbuy_shadow_candidate
from rudrila_mev.postbuy_trigger import (
    ConfirmedLargeBuy,
    PendingLargeBuy,
    confirm_large_buy,
    decode_pending_large_buy,
)
from rudrila_mev.private_submission import probe_default_bsc_private_paths
from rudrila_mev.runtime_reliability import RuntimeStateStore


CHAIN_ID = 56
WBNB = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"
PANCAKE_ROUTER = "0x10ED43C718714eb63d5aA57B78B54704E256024E"
BISWAP_ROUTER = "0x3a6d8cA21D1CF76F653A67577FA0D27453350dD8"
PANCAKE_FACTORY = "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73"
BISWAP_FACTORY = "0x858E3312ed3A876947EA49d572A7C42DE08af7EE"
EXECUTOR_ADDRESS = os.environ.get(
    "BSC_EXECUTOR_ADDRESS", "0xDC7b55dB3f0557de524F0fb3481f958d2A708265"
)
EXECUTION_WALLET = os.environ.get(
    "BSC_EXECUTION_WALLET", "0x2fd84c20aA82943FBAbF7633a9492Df0Fb40b883"
)
POSTBUY_MAX_AMOUNT_IN_WEI = int(
    os.environ.get("POSTBUY_MAX_AMOUNT_IN_WEI", str(10**15))
)

FACTORY_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "tokenA", "type": "address"},
            {"internalType": "address", "name": "tokenB", "type": "address"},
        ],
        "name": "getPair",
        "outputs": [{"internalType": "address", "name": "pair", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    }
]

def _rpc_urls() -> tuple[str, ...]:
    configured = [
        x.strip()
        for x in os.environ.get("MEV_RPC_URLS", "").split(",")
        if x.strip()
    ]
    primary = os.environ.get("MEV_RPC_URL", "").strip()
    defaults = [
        "https://bsc-dataseed.bnbchain.org",
        "https://bsc-dataseed-public.bnbchain.org",
        "https://bsc-dataseed.defibit.io",
        "https://bsc-rpc.publicnode.com",
    ]
    ordered = ([primary] if primary else []) + configured + defaults
    return tuple(dict.fromkeys(x for x in ordered if x))


RPC_URLS = _rpc_urls()


def _wss_urls() -> tuple[str, ...]:
    configured = [
        x.strip()
        for x in os.environ.get("MEV_WSS_URLS", "").split(",")
        if x.strip()
    ]
    primary = os.environ.get("MEV_WSS_URL", "").strip()
    defaults = ["wss://bsc.publicnode.com"]
    ordered = ([primary] if primary else []) + configured + defaults
    return tuple(dict.fromkeys(x for x in ordered if x))


WSS_URLS = _wss_urls()
POLL_SECONDS = float(os.environ.get("POSTBUY_POLL_SECONDS", "1.5"))
WSS_POLL_SECONDS = float(os.environ.get("POSTBUY_WSS_POLL_SECONDS", "1.0"))
WATCHDOG_STALE_SECONDS = float(os.environ.get("POSTBUY_WATCHDOG_STALE_SECONDS", "30"))
CHECKPOINT_SECONDS = float(os.environ.get("POSTBUY_CHECKPOINT_SECONDS", "10"))
MAX_TRIGGER_AGE_BLOCKS = int(os.environ.get("POSTBUY_MAX_TRIGGER_AGE_BLOCKS", "8"))
MIN_TRIGGER_WEI = int(os.environ.get("POSTBUY_MIN_TRIGGER_WEI", str(10**18)))
AMOUNT_IN_WEI = int(os.environ.get("POSTBUY_AMOUNT_IN_WEI", str(10**15)))
SLIPPAGE_BPS = int(os.environ.get("POSTBUY_SLIPPAGE_BPS", "20"))
SAFETY_BUFFER_WEI = int(os.environ.get("POSTBUY_SAFETY_BUFFER_WEI", str(10**14)))
MIN_NET_PROFIT_WEI = int(os.environ.get("POSTBUY_MIN_NET_PROFIT_WEI", str(10**14)))
GAS_UNITS = int(os.environ.get("POSTBUY_GAS_UNITS", "372000"))
GAS_PRICE_BUFFER_BPS = int(os.environ.get("POSTBUY_GAS_PRICE_BUFFER_BPS", "2500"))
BUILDER_PAYMENT_RAW = os.environ.get("POSTBUY_BUILDER_PAYMENT_WEI", "")
BUILDER_PAYMENT_WEI = (
    int(BUILDER_PAYMENT_RAW) if BUILDER_PAYMENT_RAW.strip() else None
)
MIN_BASE_LIQ_WEI = int(os.environ.get("POSTBUY_MIN_BASE_LIQ_WEI", str(10**18)))
MAX_PRICE_IMPACT_BPS = int(os.environ.get("POSTBUY_MAX_PRICE_IMPACT_BPS", "250"))
MAX_TAX_BPS = int(os.environ.get("MAX_COMBINED_TOKEN_TAX_BPS", "800"))
MAX_RISK_LEVEL = int(os.environ.get("HONEYPOT_MAX_RISK_LEVEL", "19"))
PRIVATE_REQUIRED = int(os.environ.get("PRIVATE_PATH_REQUIRED", "2"))
PRIVATE_TIMEOUT = float(os.environ.get("PRIVATE_PATH_TIMEOUT_SECONDS", "6"))
LEDGER = ExecutionLedger(
    os.environ.get("POSTBUY_LEDGER_PATH", "/tmp/rudrila_postbuy_ledger.jsonl")
)
STATE_STORE = RuntimeStateStore(
    service_key="rudrila-postbuy-shadow",
    file_path=os.environ.get("POSTBUY_STATE_PATH", "/tmp/rudrila_postbuy_state.json"),
    database_url=os.environ.get("POSTBUY_DATABASE_URL") or os.environ.get("DATABASE_URL"),
    event_log_path=os.environ.get("POSTBUY_EVENT_LOG_PATH", "/tmp/rudrila_postbuy_events.jsonl"),
)
STOP_EVENT = threading.Event()
PENDING_LOCK = threading.Lock()
PENDING: dict[str, PendingLargeBuy] = {}
SCANNER_LOCK = threading.Lock()
SCANNER_GENERATION = 0
LAST_HEARTBEAT_MONOTONIC = 0.0
LAST_CHECKPOINT_MONOTONIC = 0.0
LAST_CONFIRMED_BLOCK = -1
BACKGROUND_STARTED = False


def _csv_addresses(name: str) -> tuple[str, ...]:
    out = []
    for value in os.environ.get(name, "").split(","):
        value = value.strip()
        if value:
            out.append(Web3.to_checksum_address(value))
    return tuple(out)


VERIFIED_LP_LOCKERS = _csv_addresses("VERIFIED_V2_LP_LOCKER_ADDRESSES")
TARGET_TOKENS = frozenset(
    x.lower() for x in _csv_addresses("POSTBUY_TARGET_TOKENS")
)


def _target_token_allowed(token: str) -> bool:
    return not TARGET_TOKENS or Web3.to_checksum_address(token).lower() in TARGET_TOKENS


STATE = {
    "service": "RUDRILA-POSTBUY-SHADOW",
    "mode": "READ_ONLY_POST_CONFIRMATION",
    "live_trading": False,
    "private_key_loaded": False,
    "submission_attempted": False,
    "public_mempool_fallback_allowed": False,
    "target_mode": "ALLOWLIST" if TARGET_TOKENS else "ANY_WBNB_TOKEN",
    "target_token_count": len(TARGET_TOKENS),
    "status": "starting",
    "rpc_connected": False,
    "rpc_url": None,
    "rpc_pool_size": len(RPC_URLS),
    "wss_pool_size": len(WSS_URLS),
    "wss_connected": False,
    "wss_url": None,
    "wss_pending_supported": None,
    "wss_last_error": None,
    "latest_block": None,
    "started_at": None,
    "process_restart_count": 0,
    "watchdog_restarts": 0,
    "scanner_generation": 0,
    "last_heartbeat_at": None,
    "last_scan_duration_ms": None,
    "last_checkpoint_at": None,
    "state_backend": None,
    "state_backend_error": None,
    "last_confirmed_block": None,
    "stale_candidates_dropped": 0,
    "rpc_health": {},
    "pending_candidates": 0,
    "confirmed_large_buys": 0,
    "evaluated_candidates": 0,
    "simulation_gate_passed": 0,
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


def _checkpoint(force: bool = False) -> None:
    global LAST_CHECKPOINT_MONOTONIC
    current = time.monotonic()
    if not force and current - LAST_CHECKPOINT_MONOTONIC < CHECKPOINT_SECONDS:
        return
    with LOCK:
        payload = {
            "confirmed_large_buys": STATE["confirmed_large_buys"],
            "evaluated_candidates": STATE["evaluated_candidates"],
            "simulation_gate_passed": STATE["simulation_gate_passed"],
            "last_candidate": STATE["last_candidate"],
            "last_confirmed_block": STATE["last_confirmed_block"],
            "stale_candidates_dropped": STATE["stale_candidates_dropped"],
            "process_restart_count": STATE["process_restart_count"],
        }
    STATE_STORE.save(payload)
    LAST_CHECKPOINT_MONOTONIC = current
    update(
        last_checkpoint_at=now(),
        state_backend=STATE_STORE.backend,
        state_backend_error=STATE_STORE.postgres_error,
    )


def _restore_checkpoint() -> None:
    global LAST_CONFIRMED_BLOCK
    STATE_STORE.initialize()
    saved = STATE_STORE.load() or {}
    for key in (
        "confirmed_large_buys",
        "evaluated_candidates",
        "simulation_gate_passed",
        "last_candidate",
        "stale_candidates_dropped",
    ):
        if key in saved:
            STATE[key] = saved[key]
    LAST_CONFIRMED_BLOCK = int(saved.get("last_confirmed_block") or -1)
    STATE["last_confirmed_block"] = None if LAST_CONFIRMED_BLOCK < 0 else LAST_CONFIRMED_BLOCK
    STATE["process_restart_count"] = int(saved.get("process_restart_count") or 0) + 1
    STATE["started_at"] = now()
    STATE["state_backend"] = STATE_STORE.backend
    STATE["state_backend_error"] = STATE_STORE.postgres_error
    STATE["updated_at"] = now()
    _checkpoint(force=True)


def _heartbeat(**kwargs) -> None:
    global LAST_HEARTBEAT_MONOTONIC
    LAST_HEARTBEAT_MONOTONIC = time.monotonic()
    update(last_heartbeat_at=now(), **kwargs)


def health_ok() -> bool:
    age = time.monotonic() - LAST_HEARTBEAT_MONOTONIC if LAST_HEARTBEAT_MONOTONIC else 10**9
    with LOCK:
        return bool(STATE["rpc_connected"]) and age <= WATCHDOG_STALE_SECONDS


def emit(event: dict) -> None:
    STATE_STORE.append_event(event)
    print(json.dumps(event, separators=(",", ":"), default=str), flush=True)


def _pair(w3: Web3, factory: str, token: str) -> str | None:
    c = w3.eth.contract(address=Web3.to_checksum_address(factory), abi=FACTORY_ABI)
    pair = Web3.to_checksum_address(
        c.functions.getPair(
            Web3.to_checksum_address(WBNB),
            Web3.to_checksum_address(token),
        ).call()
    )
    return None if int(pair, 16) == 0 else pair


def _burn_lock_evidence(w3: Web3, pair: str):
    pair = Web3.to_checksum_address(pair)
    c = w3.eth.contract(address=pair, abi=V2_LP_ABI)
    total = int(c.functions.totalSupply().call())

    # Burn addresses are permanently secured. User-configured locker addresses
    # remain supported, while UNCX is handled by explicit per-lock expiry proof
    # below so expired-but-unwithdrawn LP is never counted as secured.
    uncx = collect_uncx_v2_active_locks(
        w3,
        pair=pair,
        min_unlock_horizon_seconds=int(
            os.environ.get("LP_MIN_LOCK_HORIZON_SECONDS", "300")
        ),
    )
    uncx_locker = (
        Web3.to_checksum_address(uncx["locker"])
        if uncx.get("locker")
        else None
    )
    safe_holders = tuple(
        h
        for h in (ZERO, DEAD) + VERIFIED_LP_LOCKERS
        if uncx_locker is None or Web3.to_checksum_address(h) != uncx_locker
    )
    safe_balances = {}
    secured = 0
    for holder in safe_holders:
        bal = int(c.functions.balanceOf(holder).call())
        safe_balances[holder] = bal
        secured += bal

    uncx_active = (
        int(uncx.get("active_locked_units", 0))
        if uncx.get("accepted") is True
        else 0
    )
    secured = min(total, secured + uncx_active)
    unknown = max(0, total - secured)
    return classify_liquidity_units(
        dex="V2_QUICK_LOCK_PROOF",
        subject=pair,
        total_units=total,
        secured_units=secured,
        removable_units=0,
        unknown_units=unknown,
        holder_or_position_count=len(safe_holders) + int(uncx.get("lock_count", 0)),
        observed_from_block=None,
        observed_to_block=int(w3.eth.block_number),
        min_secured_bps=9500,
        max_removable_bps=0,
        raw={
            "method": "burn balances + expiry-verified UNCX V2 locks + configured lockers",
            "safe_balances": safe_balances,
            "uncx": uncx,
        },
    )


def _execution_risk():
    return evaluate_execution_risk(
        LEDGER,
        max_hourly_net_loss_wei=int(
            os.environ.get("MAX_HOURLY_NET_LOSS_WEI", "2000000000000000")
        ),
        max_daily_net_loss_wei=int(
            os.environ.get("MAX_DAILY_NET_LOSS_WEI", "5000000000000000")
        ),
        max_daily_failed_gas_wei=int(
            os.environ.get("MAX_DAILY_GAS_LOSS_WEI", "5000000000000000")
        ),
        max_hourly_failed_transactions=int(
            os.environ.get("MAX_HOURLY_FAILED_TRANSACTIONS", "2")
        ),
        max_daily_failed_transactions=int(
            os.environ.get("MAX_DAILY_FAILED_TRANSACTIONS", "3")
        ),
        max_daily_reverts=int(os.environ.get("MAX_DAILY_REVERTS", "3")),
    )


def _live_executor_preflight(
    w3: Web3,
    *,
    trigger: ConfirmedLargeBuy,
    firewall,
    best,
    private,
    risk,
) -> dict:
    if best is None:
        return {
            "accepted": False,
            "executor": EXECUTOR_ADDRESS,
            "wallet": EXECUTION_WALLET,
            "paused": None,
            "owner_matches": None,
            "routers_allowlisted": None,
            "allowance_wei": None,
            "max_amount_in_wei": POSTBUY_MAX_AMOUNT_IN_WEI,
            "reasons": ["BLOCK: no fresh profitable route to authorize"],
        }

    try:
        executor = w3.eth.contract(
            address=Web3.to_checksum_address(EXECUTOR_ADDRESS),
            abi=EXECUTOR_ABI,
        )
        wallet = Web3.to_checksum_address(EXECUTION_WALLET)
        paused = bool(executor.functions.paused().call())
        owner = Web3.to_checksum_address(executor.functions.owner().call())
        owner_matches = owner == wallet
        routers_allowlisted = bool(
            executor.functions.allowedRouters(
                Web3.to_checksum_address(best.buy_router)
            ).call()
        ) and bool(
            executor.functions.allowedRouters(
                Web3.to_checksum_address(best.sell_router)
            ).call()
        )
        base = w3.eth.contract(
            address=Web3.to_checksum_address(trigger.base_token),
            abi=ERC20_ABI,
        )
        allowance_wei = int(
            base.functions.allowance(wallet, executor.address).call()
        )
        auth = evaluate_live_postbuy_authorization(
            trigger=trigger,
            current_block=int(w3.eth.block_number),
            firewall=firewall,
            quote=best,
            private_paths=private,
            execution_risk=risk,
            executor_paused=paused,
            owner_matches=owner_matches,
            routers_allowlisted=routers_allowlisted,
            allowance_wei=allowance_wei,
            max_amount_in_wei=POSTBUY_MAX_AMOUNT_IN_WEI,
        )
        return {
            "accepted": auth.accepted,
            "executor": executor.address,
            "wallet": wallet,
            "paused": paused,
            "owner_matches": owner_matches,
            "routers_allowlisted": routers_allowlisted,
            "allowance_wei": allowance_wei,
            "max_amount_in_wei": POSTBUY_MAX_AMOUNT_IN_WEI,
            "reasons": list(auth.reasons[:20]),
        }
    except Exception as exc:
        return {
            "accepted": False,
            "executor": EXECUTOR_ADDRESS,
            "wallet": EXECUTION_WALLET,
            "paused": None,
            "owner_matches": None,
            "routers_allowlisted": None,
            "allowance_wei": None,
            "max_amount_in_wei": POSTBUY_MAX_AMOUNT_IN_WEI,
            "reasons": [
                f"BLOCK: executor live-preflight unavailable: {type(exc).__name__}: {exc}"
            ],
        }


def _collect_v2_impacts(w3: Web3, pairs: list[tuple[str, str]]):
    rows = []
    for venue, pair in pairs:
        try:
            rows.append(
                collect_v2_liquidity_impact(
                    w3,
                    pair=pair,
                    base_token=WBNB,
                    amount_in_wei=AMOUNT_IN_WEI,
                    fee_bps=25 if venue == "pancake" else 20,
                    min_base_liquidity_wei=MIN_BASE_LIQ_WEI,
                    max_price_impact_bps=MAX_PRICE_IMPACT_BPS,
                    max_quote_age_blocks=1,
                )
            )
        except Exception:
            continue
    return rows


def _impact_stale(rows) -> bool:
    return any(
        any("quote is stale" in reason for reason in row.reasons)
        for row in rows
        if not row.accepted
    )


def _evaluate_confirmed(w3: Web3, trigger: ConfirmedLargeBuy) -> dict:
    token = trigger.token
    pairs = []
    for venue, factory in (
        ("pancake", PANCAKE_FACTORY),
        ("biswap", BISWAP_FACTORY),
    ):
        try:
            pair = _pair(w3, factory, token)
        except Exception:
            pair = None
        if pair:
            pairs.append((venue, pair))

    pf = token_preflight(w3, token, min_code_bytes=32, max_decimals=24)
    hp = check_honeypot(
        token=token,
        chain_id=CHAIN_ID,
        pairs=tuple(pair_addr for _, pair_addr in pairs),
        max_combined_tax_bps=MAX_TAX_BPS,
        max_risk_level=MAX_RISK_LEVEL,
        actual_retries=int(os.environ.get("HONEYPOT_ACTUAL_RETRIES", "2")),
        retry_delay_seconds=float(
            os.environ.get("HONEYPOT_RETRY_DELAY_SECONDS", "0.25")
        ),
    )
    admin = collect_admin_safety(w3, token)

    liquidity = []
    for _, pair in pairs:
        try:
            liquidity.append(_burn_lock_evidence(w3, pair))
        except Exception:
            pass

    # Price-impact evidence is deliberately collected after the slower external
    # risk/locker checks. If BSC advances enough to make a row stale, refresh it
    # once immediately instead of rejecting a safe token because of scanner lag.
    impacts = _collect_v2_impacts(w3, pairs)
    if _impact_stale(impacts):
        impacts = _collect_v2_impacts(w3, pairs)

    firewall = evaluate_dynamic_token_firewall(
        preflight=pf,
        honeypot=hp,
        admin=admin,
        liquidity=tuple(liquidity),
        impacts=tuple(impacts),
        min_safe_pools=2,
        max_combined_token_tax_bps=MAX_TAX_BPS,
    )

    gas_price = int(w3.eth.gas_price)
    buffered_gas_price = (
        gas_price * (10_000 + GAS_PRICE_BUFFER_BPS) + 9_999
    ) // 10_000
    gas_cost = GAS_UNITS * buffered_gas_price

    routes = quote_postbuy_v2_routes_read_only(
        w3,
        venues=(
            ReadOnlyVenue("pancake", PANCAKE_ROUTER),
            ReadOnlyVenue("biswap", BISWAP_ROUTER),
        ),
        base_token=WBNB,
        token=token,
        amount_in_wei=AMOUNT_IN_WEI,
        slippage_bps_per_leg=SLIPPAGE_BPS,
        buy_tax_bps=int(hp.buy_tax_bps or 0),
        sell_tax_bps=int(hp.sell_tax_bps or 0),
        gas_cost_wei=gas_cost,
        builder_payment_wei=BUILDER_PAYMENT_WEI,
        safety_buffer_wei=SAFETY_BUFFER_WEI,
        min_net_profit_wei=MIN_NET_PROFIT_WEI,
        max_quote_age_blocks=1,
    )
    best = routes[0] if routes else None

    private = probe_default_bsc_private_paths(
        required_paths=PRIVATE_REQUIRED,
        timeout=PRIVATE_TIMEOUT,
    )
    risk = _execution_risk()

    if best is not None:
        profit = best.profit
        route_id = best.route_id
    else:
        from rudrila_mev.all_cost_profit import missing_route_profit_evidence

        profit = missing_route_profit_evidence(
            amount_in_wei=AMOUNT_IN_WEI,
            current_block=int(w3.eth.block_number),
            min_net_profit_wei=MIN_NET_PROFIT_WEI,
            reason="BLOCK: no executable read-only Pancake/Biswap quote",
        )
        route_id = None

    decision = evaluate_postbuy_shadow_candidate(
        trigger=trigger,
        current_block=int(w3.eth.block_number),
        firewall=firewall,
        route_id=route_id,
        profit=profit,
        private_paths=private,
        execution_risk=risk,
    )
    live_preflight = _live_executor_preflight(
        w3,
        trigger=trigger,
        firewall=firewall,
        best=best,
        private=private,
        risk=risk,
    )

    return {
        "time": now(),
        "event": "CONFIRMED_LARGE_BUY_POSTBUY_SHADOW",
        "trigger_hash": trigger.tx_hash,
        "trigger_block": trigger.block_number,
        "trigger_index": trigger.transaction_index,
        "trigger_amount_base_wei": trigger.pending.amount_in_wei,
        "token": token,
        "pairs": [{"venue": v, "pair": p} for v, p in pairs],
        "token_firewall": {
            "accepted": firewall.accepted,
            "buy_tax_bps": firewall.buy_tax_bps,
            "sell_tax_bps": firewall.sell_tax_bps,
            "safe_pool_count": firewall.safe_pool_count,
            "reasons": list(firewall.reasons[:20]),
        },
        "route_count": len(routes),
        "best_route": (
            {
                "route_id": best.route_id,
                "quoted_block": best.quoted_block,
                "expected_final_wei": best.expected_final_wei,
                "floor_final_wei": best.floor_final_wei,
                "floor_net_after_all_costs_wei": (
                    best.profit.floor_net_after_all_costs_wei
                ),
                "profit_gate": best.profit.accepted,
                "reasons": list(best.profit.reasons[:12]),
            }
            if best is not None
            else None
        ),
        "private_paths": {
            "accepted": private.accepted,
            "healthy": private.healthy_paths,
            "required": private.required_paths,
            "public_fallback": private.public_mempool_fallback_allowed,
        },
        "execution_risk": risk.as_dict(),
        "shadow_decision": {
            "accepted_for_simulation": decision.accepted_for_simulation,
            "route_id": decision.route_id,
            "expected_floor_net_wei": decision.expected_floor_net_wei,
            "reasons": list(decision.reasons[:20]),
        },
        "live_preflight": live_preflight,
        "live_action": "NONE",
    }


def _add_pending(candidate: PendingLargeBuy) -> None:
    if not _target_token_allowed(candidate.token):
        return
    with PENDING_LOCK:
        PENDING[candidate.tx_hash] = candidate


def _pending_count() -> int:
    with PENDING_LOCK:
        return len(PENDING)


def _record_rpc(url: str, *, ok: bool, latency_ms: int | None = None, block: int | None = None, error: str | None = None) -> None:
    with LOCK:
        health = dict(STATE.get("rpc_health") or {})
        row = dict(health.get(url) or {})
        row["last_checked_at"] = now()
        if ok:
            row["last_success_at"] = now()
            row["consecutive_failures"] = 0
            row["latency_ms"] = latency_ms
            row["block"] = block
            row["last_error"] = None
        else:
            row["consecutive_failures"] = int(row.get("consecutive_failures") or 0) + 1
            row["last_error"] = error
        health[url] = row
        STATE["rpc_health"] = health
        STATE["updated_at"] = now()


def pending_wss_loop() -> None:
    cursor = 0
    while not STOP_EVENT.is_set():
        url = WSS_URLS[cursor % len(WSS_URLS)]
        cursor += 1
        try:
            w3 = Web3(LegacyWebSocketProvider(url, websocket_timeout=6))
            w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
            if not w3.is_connected() or int(w3.eth.chain_id) != CHAIN_ID:
                raise RuntimeError("BSC WSS unavailable or wrong chain")
            update(
                wss_connected=True,
                wss_url=url,
                wss_pending_supported=None,
                wss_last_error=None,
            )
            while not STOP_EVENT.is_set():
                latest = int(w3.eth.block_number)
                try:
                    pb = w3.eth.get_block("pending", full_transactions=True)
                    update(wss_pending_supported=True, wss_last_error=None)
                    for tx in pb.get("transactions", []):
                        c = decode_pending_large_buy(
                            dict(tx),
                            supported_routers=(PANCAKE_ROUTER, BISWAP_ROUTER),
                            wrapped_native=WBNB,
                            min_trigger_wei=MIN_TRIGGER_WEI,
                            observed_pending_block=latest,
                        )
                        if c:
                            _add_pending(c)
                except Exception as exc:
                    # Some otherwise healthy BSC WSS endpoints do not expose
                    # eth_getBlockByNumber("pending"). Keep WSS as a live head
                    # backup and let the HTTP pending/finalized scanners cover
                    # candidate detection rather than declaring WSS dead.
                    update(
                        wss_connected=True,
                        wss_pending_supported=False,
                        wss_last_error=f"pending unavailable: {type(exc).__name__}",
                    )
                update(pending_candidates=_pending_count())
                STOP_EVENT.wait(WSS_POLL_SECONDS)
        except Exception as exc:
            update(
                wss_connected=False,
                wss_url=url,
                wss_last_error=f"{type(exc).__name__}: {exc}",
            )
            STOP_EVENT.wait(3)


def scanner_loop(generation: int | None = None) -> None:
    global LAST_CONFIRMED_BLOCK, SCANNER_GENERATION
    if generation is None:
        with SCANNER_LOCK:
            if SCANNER_GENERATION <= 0:
                SCANNER_GENERATION = 1
            generation = SCANNER_GENERATION
    rpc_cursor = 0
    last_confirmed_block = LAST_CONFIRMED_BLOCK
    while not STOP_EVENT.is_set() and generation == SCANNER_GENERATION:
        rpc_url = RPC_URLS[rpc_cursor % len(RPC_URLS)]
        rpc_cursor += 1
        started = time.monotonic()
        try:
            w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 8}))
            w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
            if not w3.is_connected() or int(w3.eth.chain_id) != CHAIN_ID:
                raise RuntimeError("BSC RPC unavailable or wrong chain")
            latest = int(w3.eth.block_number)
            _record_rpc(
                rpc_url,
                ok=True,
                latency_ms=int((time.monotonic() - started) * 1000),
                block=latest,
            )
            _heartbeat(
                status="running",
                rpc_connected=True,
                rpc_url=rpc_url,
                latest_block=latest,
                last_error=None,
                scanner_generation=generation,
            )

            # HTTP pending is a second advisory source in case WSS is unavailable.
            try:
                pb = w3.eth.get_block("pending", full_transactions=True)
                for tx in pb.get("transactions", []):
                    c = decode_pending_large_buy(
                        dict(tx),
                        supported_routers=(PANCAKE_ROUTER, BISWAP_ROUTER),
                        wrapped_native=WBNB,
                        min_trigger_wei=MIN_TRIGGER_WEI,
                        observed_pending_block=latest,
                    )
                    if c:
                        _add_pending(c)
            except Exception:
                pass

            stable = max(0, latest - 1)
            if last_confirmed_block < 0:
                scan_from = max(0, stable - 3)
            else:
                scan_from = max(last_confirmed_block + 1, stable - 3)
            if scan_from <= stable:
                for block_number in range(scan_from, stable + 1):
                    if STOP_EVENT.is_set() or generation != SCANNER_GENERATION:
                        return
                    try:
                        block = w3.eth.get_block(block_number, full_transactions=True)
                    except Exception:
                        continue
                    for tx in block.get("transactions", []):
                        c = decode_pending_large_buy(
                            dict(tx),
                            supported_routers=(PANCAKE_ROUTER, BISWAP_ROUTER),
                            wrapped_native=WBNB,
                            min_trigger_wei=MIN_TRIGGER_WEI,
                            observed_pending_block=block_number,
                        )
                        if c:
                            _add_pending(c)
                    last_confirmed_block = int(block_number)
                    LAST_CONFIRMED_BLOCK = last_confirmed_block
                    update(last_confirmed_block=last_confirmed_block)

            with PENDING_LOCK:
                pending_items = list(PENDING.items())
            update(pending_candidates=len(pending_items))

            for tx_hash, candidate in pending_items:
                if STOP_EVENT.is_set() or generation != SCANNER_GENERATION:
                    return
                if latest - int(candidate.observed_pending_block) > MAX_TRIGGER_AGE_BLOCKS:
                    with PENDING_LOCK:
                        PENDING.pop(tx_hash, None)
                    with LOCK:
                        STATE["stale_candidates_dropped"] += 1
                    continue
                confirmed = confirm_large_buy(w3, candidate, required_confirmations=1)
                if confirmed is None:
                    continue
                event = _evaluate_confirmed(w3, confirmed)
                emit(event)
                with LOCK:
                    STATE["confirmed_large_buys"] += 1
                    STATE["evaluated_candidates"] += 1
                    if event["shadow_decision"]["accepted_for_simulation"]:
                        STATE["simulation_gate_passed"] += 1
                    STATE["last_candidate"] = event
                    STATE["updated_at"] = now()
                with PENDING_LOCK:
                    PENDING.pop(tx_hash, None)
                _checkpoint(force=True)

            with PENDING_LOCK:
                if len(PENDING) > 5000:
                    keep = list(PENDING.items())[-2000:]
                    PENDING.clear()
                    PENDING.update(keep)
            _heartbeat(
                pending_candidates=_pending_count(),
                last_scan_duration_ms=int((time.monotonic() - started) * 1000),
            )
            _checkpoint()
            STOP_EVENT.wait(POLL_SECONDS)
        except Exception as exc:
            _record_rpc(
                rpc_url,
                ok=False,
                error=f"{type(exc).__name__}: {exc}",
            )
            update(
                status="reconnecting",
                rpc_connected=False,
                rpc_url=rpc_url,
                last_error=f"{type(exc).__name__}: {exc}",
            )
            STOP_EVENT.wait(4)


def watchdog_loop() -> None:
    global SCANNER_GENERATION
    while not STOP_EVENT.wait(max(5.0, WATCHDOG_STALE_SECONDS / 3)):
        age = time.monotonic() - LAST_HEARTBEAT_MONOTONIC if LAST_HEARTBEAT_MONOTONIC else 10**9
        if age <= WATCHDOG_STALE_SECONDS:
            continue
        with SCANNER_LOCK:
            SCANNER_GENERATION += 1
            generation = SCANNER_GENERATION
            with LOCK:
                STATE["watchdog_restarts"] += 1
                STATE["scanner_generation"] = generation
                STATE["status"] = "watchdog_restart"
                STATE["updated_at"] = now()
            threading.Thread(
                target=scanner_loop,
                args=(generation,),
                daemon=True,
                name=f"postbuy-scanner-{generation}",
            ).start()


def start_background_workers() -> None:
    global BACKGROUND_STARTED, SCANNER_GENERATION, LAST_HEARTBEAT_MONOTONIC
    with SCANNER_LOCK:
        if BACKGROUND_STARTED:
            return
        BACKGROUND_STARTED = True
        _restore_checkpoint()
        SCANNER_GENERATION += 1
        generation = SCANNER_GENERATION
        LAST_HEARTBEAT_MONOTONIC = time.monotonic()
        update(scanner_generation=generation, last_heartbeat_at=now())
        threading.Thread(
            target=scanner_loop,
            args=(generation,),
            daemon=True,
            name=f"postbuy-scanner-{generation}",
        ).start()
        threading.Thread(
            target=pending_wss_loop,
            daemon=True,
            name="postbuy-wss-pending",
        ).start()
        threading.Thread(
            target=watchdog_loop,
            daemon=True,
            name="postbuy-watchdog",
        ).start()


def shutdown_background_workers() -> None:
    STOP_EVENT.set()
    try:
        _checkpoint(force=True)
    except Exception:
        pass


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ("/", "/health", "/status"):
            self.send_response(404)
            self.end_headers()
            return
        with LOCK:
            payload = dict(STATE)
        payload["health_ok"] = health_ok()
        body = json.dumps(payload, indent=2, default=str).encode()
        self.send_response(200 if self.path != "/health" or payload["health_ok"] else 503)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        return


if __name__ == "__main__":
    print("RUDRILA post-buy shadow monitor: READ ONLY; no signing/submission.", flush=True)
    start_background_workers()
    port = int(os.environ.get("PORT", "10000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)

    def _stop_signal(signum, frame):
        shutdown_background_workers()
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, _stop_signal)
    signal.signal(signal.SIGINT, _stop_signal)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        shutdown_background_workers()
        server.server_close()
