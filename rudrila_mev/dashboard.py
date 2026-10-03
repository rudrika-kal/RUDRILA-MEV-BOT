from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


@dataclass(frozen=True)
class HealthSnapshot:
    chain_id: int
    block_number: int
    live_trading: bool
    public_mempool: bool
    healthy_rpc_count: int
    opportunities_seen: int
    simulations_passed: int
    submitted: int
    included: int
    realized_net_wei: int


def render_health_json(snapshot: HealthSnapshot) -> bytes:
    payload = asdict(snapshot)
    payload["status"] = "ok" if not snapshot.public_mempool else "blocked"
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def make_health_handler(snapshot_provider):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/":
                body = render_dashboard_html(snapshot_provider())
                self.send_response(200)
                self.send_header("content-type", "text/html; charset=utf-8")
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path not in {"/health", "/api/health"}:
                self.send_response(404); self.end_headers(); return
            body = render_health_json(snapshot_provider())
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, format, *args):
            return
    return Handler


def render_dashboard_html(snapshot: HealthSnapshot) -> bytes:
    rows = asdict(snapshot)
    cells = "".join(
        f"<tr><th>{key}</th><td>{value}</td></tr>"
        for key, value in rows.items()
    )
    status = "OK" if not snapshot.public_mempool else "BLOCKED"
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>RUDRILA MEV Dashboard</title>"
        "<meta http-equiv='refresh' content='5'></head><body>"
        f"<h1>RUDRILA MEV — {status}</h1><table>{cells}</table>"
        "<p>Read-only monitoring. No trading controls are exposed here.</p>"
        "</body></html>"
    ).encode()


def ethereum_rpc_snapshot() -> HealthSnapshot:
    """Read Ethereum chain/block health from redundant public RPCs only."""
    import os
    import requests

    urls = [
        x.strip()
        for x in os.environ.get(
            "ETH_READONLY_RPCS",
            "https://rpc.flashbots.net,https://eth.drpc.org,https://ethereum.publicnode.com",
        ).split(",")
        if x.strip()
    ]
    healthy_blocks: list[int] = []
    for url in urls:
        try:
            payload = {"jsonrpc": "2.0", "id": 1, "method": "eth_blockNumber", "params": []}
            row = requests.post(url, json=payload, timeout=4).json()
            healthy_blocks.append(int(row["result"], 16))
        except Exception:
            continue
    return HealthSnapshot(
        chain_id=1,
        block_number=max(healthy_blocks) if healthy_blocks else 0,
        live_trading=False,
        public_mempool=False,
        healthy_rpc_count=len(healthy_blocks),
        opportunities_seen=0,
        simulations_passed=0,
        submitted=0,
        included=0,
        realized_net_wei=0,
    )


def run_read_only_dashboard(
    port: int,
    snapshot_provider=ethereum_rpc_snapshot,
    host: str | None = None,
) -> None:
    """Serve health/dashboard only. No trading or signing controls exist.

    Default to loopback so accidentally starting this helper never exposes a
    listener publicly. A deployment that intentionally needs external health
    access must opt in with DASHBOARD_BIND_HOST.
    """
    import os

    bind_host = host or os.environ.get("DASHBOARD_BIND_HOST", "127.0.0.1")
    ThreadingHTTPServer(
        (bind_host, int(port)),
        make_health_handler(snapshot_provider),
    ).serve_forever()
