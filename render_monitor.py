from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from web3 import Web3

from rudrila_mev.honeypot_client import check_honeypot
from rudrila_mev.launch_monitor import V2LaunchMonitor, token_preflight
from rudrila_mev.v3_monitor import V3LaunchMonitor


CHAIN_ID = 56
WBNB = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"
PANCAKE_V2_FACTORY = "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73"
PANCAKE_V3_FACTORY = "0x0BFbCF9fa4f9C56B0F40a671Ad40E0805A091865"

RPC = os.environ.get("MEV_RPC_URL", "https://bsc-rpc.publicnode.com")
MIN_BASE_LIQ = int(
    os.environ.get("MIN_BASE_LIQUIDITY_WEI", "1000000000000000000")
)
CONFIRMATIONS = int(os.environ.get("LAUNCH_CONFIRMATIONS", "120"))
RPC_SAFETY_LAG = int(os.environ.get("RPC_SAFETY_LAG_BLOCKS", "180"))
POLL_SECONDS = float(os.environ.get("POLL_SECONDS", "3"))
MAX_TAX_BPS = int(os.environ.get("MAX_COMBINED_TOKEN_TAX_BPS", "800"))
MAX_RISK_LEVEL = int(os.environ.get("HONEYPOT_MAX_RISK_LEVEL", "19"))

STATE = {
    "service": "RUDRILA-MEV-V05-MONITOR",
    "mode": "READ_ONLY_TEST",
    "live_trading": False,
    "private_key_loaded": False,
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


def handle_candidate(kind: str, candidate, w3: Web3) -> None:
    token = candidate.token
    pool = getattr(candidate, "pair", None) or getattr(candidate, "pool", None)

    pf = token_preflight(w3, token, min_code_bytes=32, max_decimals=24)
    if not pf.accepted:
        external = None
        decision = "NO_TRADE"
        reasons = [pf.reason]
    else:
        external = check_honeypot(
            token=token,
            chain_id=CHAIN_ID,
            pair=pool,
            max_combined_tax_bps=MAX_TAX_BPS,
            max_risk_level=MAX_RISK_LEVEL,
        )
        decision = "NO_TRADE"
        reasons = list(external.reasons)

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
                "buy_gas": external.buy_gas,
                "sell_gas": external.sell_gas,
                "root_open_source": external.root_open_source,
                "is_proxy": external.is_proxy,
                "reasons": list(external.reasons[:10]),
            }
            if external is not None
            else None
        ),
        "trade_decision": decision,
        "why": (
            "Read-only test. Even an external honeypot PASS cannot authorize a trade "
            "until LP/admin/privilege checks, net-profit checks, executor tests and "
            "private submission tests are complete."
        ),
        "remaining_gates": [
            "LP lock/burn or protocol-specific liquidity safety",
            "admin/mint/blacklist/pause/fee-change authority",
            "gas + DEX fees + slippage + safety buffer + minimum net profit",
            "atomic executor fork/test",
            "private submission path",
            "large dry-run audit",
        ],
    }

    emit(event)
    with LOCK:
        STATE["detected_candidates"] += 1
        if external is not None and external.accepted:
            STATE["external_risk_passed"] += 1
        else:
            STATE["blocked_candidates"] += 1
        STATE["last_candidate"] = event
        STATE["updated_at"] = now()


def scanner_loop() -> None:
    while True:
        try:
            w3 = Web3(
                Web3.HTTPProvider(RPC, request_kwargs={"timeout": 10})
            )
            if not w3.is_connected():
                raise RuntimeError("RPC not connected")
            chain_id = int(w3.eth.chain_id)
            if chain_id != CHAIN_ID:
                raise RuntimeError(
                    f"Wrong chain id {chain_id}; expected {CHAIN_ID}"
                )

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
                    update(
                        last_processed_block=last,
                        status="running",
                        last_error=None,
                    )
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
            emit(
                {
                    "time": now(),
                    "event": "RPC_ERROR",
                    "error": str(exc),
                }
            )
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
        "RUDRILA MEV v0.5 monitor starting in READ-ONLY TEST mode.",
        flush=True,
    )
    threading.Thread(target=scanner_loop, daemon=True).start()
    port = int(os.environ.get("PORT", "10000"))
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
