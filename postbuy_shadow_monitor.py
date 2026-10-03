from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

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
)
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


CHAIN_ID = 56
WBNB = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"
PANCAKE_ROUTER = "0x10ED43C718714eb63d5aA57B78B54704E256024E"
BISWAP_ROUTER = "0x3a6d8cA21D1CF76F653A67577FA0D27453350dD8"
PANCAKE_FACTORY = "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73"
BISWAP_FACTORY = "0x858E3312ed3A876947EA49d572A7C42DE08af7EE"

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
POLL_SECONDS = float(os.environ.get("POSTBUY_POLL_SECONDS", "1.5"))
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
    "latest_block": None,
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


def emit(event: dict) -> None:
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
    safe_holders = (ZERO, DEAD) + VERIFIED_LP_LOCKERS
    safe_balances = {}
    secured = 0
    for holder in safe_holders:
        bal = int(c.functions.balanceOf(holder).call())
        safe_balances[holder] = bal
        secured += bal
    secured = min(total, secured)
    unknown = max(0, total - secured)
    return classify_liquidity_units(
        dex="V2_QUICK_LOCK_PROOF",
        subject=pair,
        total_units=total,
        secured_units=secured,
        removable_units=0,
        unknown_units=unknown,
        holder_or_position_count=len(safe_holders),
        observed_from_block=None,
        observed_to_block=int(w3.eth.block_number),
        min_secured_bps=9500,
        max_removable_bps=0,
        raw={
            "method": "direct LP balances of burn/verified-locker addresses",
            "safe_balances": safe_balances,
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
        pair=pairs[0][1] if pairs else None,
        max_combined_tax_bps=MAX_TAX_BPS,
        max_risk_level=MAX_RISK_LEVEL,
    )
    admin = collect_admin_safety(w3, token)

    liquidity = []
    impacts = []
    for venue, pair in pairs:
        try:
            liquidity.append(_burn_lock_evidence(w3, pair))
        except Exception:
            pass
        try:
            impacts.append(
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
            pass

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
        "live_action": "NONE",
    }


def scanner_loop() -> None:
    pending: dict[str, PendingLargeBuy] = {}
    last_confirmed_block = -1
    rpc_cursor = 0
    while True:
        rpc_url = RPC_URLS[rpc_cursor % len(RPC_URLS)]
        rpc_cursor += 1
        try:
            w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 8}))
            # BNB Smart Chain carries proof-of-authority style extraData that is
            # longer than the Ethereum mainnet header field. Normalize it before
            # reading full pending/latest blocks.
            w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
            if not w3.is_connected() or int(w3.eth.chain_id) != CHAIN_ID:
                raise RuntimeError("BSC RPC unavailable or wrong chain")
            update(
                status="running",
                rpc_connected=True,
                rpc_url=rpc_url,
                last_error=None,
            )

            latest = int(w3.eth.block_number)
            update(latest_block=latest)

            # Advisory pending observation only. Nothing in this service signs or submits.
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
                    if c and _target_token_allowed(c.token):
                        pending[c.tx_hash] = c
            except Exception:
                pass

            # Fallback catches large buys even when a public RPC exposes no pending
            # pool. Public load-balanced RPCs can briefly advertise a head that a
            # different backend cannot serve yet, so scan a stable block and fail
            # open for detection only (execution gates still fail closed).
            stable = max(0, latest - 1)
            if stable > last_confirmed_block:
                block = None
                scanned_block = None
                lower = max(last_confirmed_block + 1, stable - 3)
                for block_number in range(stable, lower - 1, -1):
                    try:
                        block = w3.eth.get_block(
                            block_number, full_transactions=True
                        )
                        scanned_block = int(block_number)
                        break
                    except Exception:
                        continue
                if block is not None and scanned_block is not None:
                    for tx in block.get("transactions", []):
                        c = decode_pending_large_buy(
                            dict(tx),
                            supported_routers=(PANCAKE_ROUTER, BISWAP_ROUTER),
                            wrapped_native=WBNB,
                            min_trigger_wei=MIN_TRIGGER_WEI,
                            observed_pending_block=scanned_block,
                        )
                        if c and _target_token_allowed(c.token):
                            pending.setdefault(c.tx_hash, c)
                    last_confirmed_block = scanned_block

            update(pending_candidates=len(pending))

            for tx_hash, candidate in list(pending.items()):
                confirmed = confirm_large_buy(
                    w3, candidate, required_confirmations=1
                )
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
                pending.pop(tx_hash, None)

            # Bound memory if RPC keeps old pending hashes around.
            if len(pending) > 5000:
                pending = dict(list(pending.items())[-2000:])

            time.sleep(POLL_SECONDS)
        except Exception as exc:
            update(
                status="reconnecting",
                rpc_connected=False,
                rpc_url=rpc_url,
                last_error=f"{type(exc).__name__}: {exc}",
            )
            time.sleep(4)


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
    print("RUDRILA post-buy shadow monitor: READ ONLY; no signing/submission.", flush=True)
    threading.Thread(target=scanner_loop, daemon=True).start()
    port = int(os.environ.get("PORT", "10000"))
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()