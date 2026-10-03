from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

import requests


@dataclass(frozen=True)
class PrivatePath:
    name: str
    url: str
    send_method: str
    chain_id: int = 56


@dataclass(frozen=True)
class PrivatePathEvidence:
    name: str
    url: str
    send_method: str
    https: bool
    chain_id: int | None
    chain_ok: bool
    method_supported: bool
    private_path_verified: bool
    error: str | None

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class PrivateSubmissionEvidence:
    accepted: bool
    required_paths: int
    healthy_paths: int
    paths: tuple[PrivatePathEvidence, ...]
    public_mempool_fallback_allowed: bool
    reasons: tuple[str, ...]

    def as_dict(self) -> dict:
        return {
            "accepted": self.accepted,
            "required_paths": self.required_paths,
            "healthy_paths": self.healthy_paths,
            "paths": [p.as_dict() for p in self.paths],
            "public_mempool_fallback_allowed": self.public_mempool_fallback_allowed,
            "reasons": list(self.reasons),
        }


DEFAULT_BSC_PRIVATE_PATHS = (
    PrivatePath(
        name="48club-privacy",
        url="https://rpc.48.club",
        send_method="eth_sendRawTransaction",
    ),
    PrivatePath(
        name="48club-puissant-builder",
        url="https://puissant-builder.48.club/",
        send_method="eth_sendPrivateTransaction",
    ),
    PrivatePath(
        name="merkle",
        url="https://bsc.merkle.io",
        send_method="eth_sendRawTransaction",
    ),
)


def _rpc(url: str, method: str, params: list, timeout: float) -> dict:
    if not url.lower().startswith("https://"):
        raise ValueError("private submission endpoint must use HTTPS")
    r = requests.post(
        url,
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        headers={"content-type": "application/json"},
        timeout=timeout,
    )
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, dict):
        raise RuntimeError("invalid JSON-RPC response")
    return data


def _supports_send_method(path: PrivatePath, timeout: float) -> tuple[bool, str | None]:
    # Deliberately malformed one-byte payload. A private relay that recognizes
    # the method should reject the transaction as malformed/invalid rather than
    # returning JSON-RPC method-not-found. No valid transaction can be broadcast.
    try:
        data = _rpc(path.url, path.send_method, ["0x00"], timeout)
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"

    error = data.get("error")
    if error is None:
        # A valid tx hash here would be unexpected for malformed input.
        return False, "malformed transaction unexpectedly accepted"

    code = error.get("code") if isinstance(error, dict) else None
    message = str(error.get("message", "")) if isinstance(error, dict) else str(error)
    if code == -32601 or "method not found" in message.lower():
        return False, message or "method not found"

    # Any other structured rejection proves the relay recognized the method.
    return True, message or None


def probe_private_path(path: PrivatePath, timeout: float = 8.0) -> PrivatePathEvidence:
    https = path.url.lower().startswith("https://")
    chain_id = None
    chain_ok = False
    method_supported = False
    error = None

    if not https:
        return PrivatePathEvidence(
            name=path.name,
            url=path.url,
            send_method=path.send_method,
            https=False,
            chain_id=None,
            chain_ok=False,
            method_supported=False,
            private_path_verified=False,
            error="endpoint is not HTTPS",
        )

    try:
        data = _rpc(path.url, "eth_chainId", [], timeout)
        result = data.get("result")
        if not isinstance(result, str):
            raise RuntimeError(f"eth_chainId missing: {data!r}")
        chain_id = int(result, 16)
        chain_ok = chain_id == int(path.chain_id)
        if not chain_ok:
            error = f"wrong chain id {chain_id}"
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"

    if chain_ok:
        method_supported, method_error = _supports_send_method(path, timeout)
        if not method_supported:
            error = method_error or "private send method unsupported"

    return PrivatePathEvidence(
        name=path.name,
        url=path.url,
        send_method=path.send_method,
        https=True,
        chain_id=chain_id,
        chain_ok=chain_ok,
        method_supported=method_supported,
        private_path_verified=bool(chain_ok and method_supported),
        error=error,
    )


def evaluate_private_paths(
    evidence: Iterable[PrivatePathEvidence],
    *,
    required_paths: int = 2,
    public_mempool_fallback_allowed: bool = False,
) -> PrivateSubmissionEvidence:
    rows = tuple(evidence)
    healthy = sum(1 for x in rows if x.private_path_verified)
    reasons: list[str] = []

    if public_mempool_fallback_allowed:
        reasons.append("BLOCK: public mempool fallback is enabled")
    if int(required_paths) < 2:
        reasons.append("BLOCK: at least two independent private paths are required")
    if healthy < int(required_paths):
        reasons.append(
            f"BLOCK: only {healthy} verified private paths; "
            f"{int(required_paths)} required"
        )
    degraded = [
        row for row in rows if not row.private_path_verified
    ]
    accepted = not any(r.startswith("BLOCK:") for r in reasons)
    if accepted:
        reasons.append(
            "PASS: multiple HTTPS BSC private-submission paths verified; "
            "public mempool fallback disabled"
        )
        for row in degraded:
            reasons.append(
                f"WARN: optional private path {row.name} unavailable/unverified"
                + (f": {row.error}" if row.error else "")
            )
    return PrivateSubmissionEvidence(
        accepted=accepted,
        required_paths=int(required_paths),
        healthy_paths=healthy,
        paths=rows,
        public_mempool_fallback_allowed=bool(public_mempool_fallback_allowed),
        reasons=tuple(reasons),
    )


def probe_default_bsc_private_paths(
    *,
    required_paths: int = 2,
    timeout: float = 8.0,
) -> PrivateSubmissionEvidence:
    evidence = tuple(probe_private_path(p, timeout=timeout) for p in DEFAULT_BSC_PRIVATE_PATHS)
    return evaluate_private_paths(
        evidence,
        required_paths=required_paths,
        public_mempool_fallback_allowed=False,
    )


def submit_private_raw_transaction(
    raw_tx: str,
    paths: Iterable[PrivatePath],
    *,
    timeout: float = 8.0,
) -> tuple[str, str]:
    if not isinstance(raw_tx, str) or not raw_tx.startswith("0x") or len(raw_tx) < 4:
        raise ValueError("raw signed transaction is required")
    errors = []
    for path in paths:
        try:
            data = _rpc(path.url, path.send_method, [raw_tx], timeout)
            result = data.get("result")
            if isinstance(result, str) and result.startswith("0x") and len(result) == 66:
                return path.name, result
            errors.append(f"{path.name}: {data.get('error') or data!r}")
        except Exception as exc:
            errors.append(f"{path.name}: {type(exc).__name__}: {exc}")
    raise RuntimeError("all private submission paths failed; public fallback refused: " + "; ".join(errors))
