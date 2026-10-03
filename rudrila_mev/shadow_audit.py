from __future__ import annotations

from dataclasses import asdict, dataclass
from collections import Counter
from typing import Iterable


@dataclass(frozen=True)
class ShadowRecord:
    candidate_id: str
    dex: str
    trade_decision: str
    live_trading: bool
    private_key_loaded: bool
    submission_attempted: bool
    public_mempool_allowed: bool
    prior_gates_passed: bool
    blocked_reasons: tuple[str, ...]

    def as_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class ShadowAudit:
    accepted: bool
    total_samples: int
    no_trade_samples: int
    submission_attempts: int
    live_mode_samples: int
    private_key_samples: int
    public_mempool_samples: int
    unsafe_authorizations: int
    dex_counts: dict[str, int]
    block_reason_counts: dict[str, int]
    reasons: tuple[str, ...]

    def as_dict(self):
        return asdict(self)


def audit_shadow_records(
    records: Iterable[ShadowRecord],
    *,
    min_samples: int = 5000,
) -> ShadowAudit:
    rows = list(records)
    no_trade = sum(r.trade_decision == "NO_TRADE" for r in rows)
    submissions = sum(bool(r.submission_attempted) for r in rows)
    live = sum(bool(r.live_trading) for r in rows)
    keys = sum(bool(r.private_key_loaded) for r in rows)
    public = sum(bool(r.public_mempool_allowed) for r in rows)
    unsafe = sum(
        (not r.prior_gates_passed) and r.trade_decision != "NO_TRADE"
        for r in rows
    )
    dex_counts = Counter(r.dex for r in rows)
    reason_counts = Counter(
        reason
        for r in rows
        for reason in r.blocked_reasons
    )

    reasons: list[str] = []
    if len(rows) < int(min_samples):
        reasons.append(
            f"BLOCK: dry-run sample count {len(rows)} below minimum {int(min_samples)}"
        )
    if no_trade != len(rows):
        reasons.append("BLOCK: shadow mode emitted a decision other than NO_TRADE")
    if submissions:
        reasons.append(f"BLOCK: {submissions} submission attempts observed in shadow mode")
    if live:
        reasons.append(f"BLOCK: {live} shadow samples had live trading enabled")
    if keys:
        reasons.append(f"BLOCK: {keys} shadow samples reported a loaded private key")
    if public:
        reasons.append(f"BLOCK: {public} shadow samples allowed public mempool fallback")
    if unsafe:
        reasons.append(
            f"BLOCK: {unsafe} candidates bypassed failed prior gates"
        )
    if len(dex_counts) < 2:
        reasons.append("BLOCK: both V2 and V3 shadow coverage are required")

    accepted = not reasons
    if accepted:
        reasons.append(
            "PASS: large shadow audit remained read-only, fail-closed and submission-free"
        )
    return ShadowAudit(
        accepted=accepted,
        total_samples=len(rows),
        no_trade_samples=no_trade,
        submission_attempts=submissions,
        live_mode_samples=live,
        private_key_samples=keys,
        public_mempool_samples=public,
        unsafe_authorizations=unsafe,
        dex_counts=dict(sorted(dex_counts.items())),
        block_reason_counts=dict(reason_counts.most_common(20)),
        reasons=tuple(reasons),
    )


def deterministic_shadow_matrix(samples: int = 10000) -> list[ShadowRecord]:
    if samples <= 0:
        raise ValueError("samples must be positive")
    gates = (
        "honeypot",
        "liquidity_ownership",
        "admin",
        "price_impact",
        "all_cost_profit",
        "executor",
        "private_submission",
        "execution_risk",
        "strict_scanner",
    )
    out: list[ShadowRecord] = []
    for i in range(samples):
        # Deterministic failure masks exercise single and multi-gate failures.
        mask = (i * 0x9E3779B1 + 0x7F4A7C15) & ((1 << len(gates)) - 1)
        if mask == 0:
            mask = 1 << (i % len(gates))
        failed = tuple(
            f"BLOCK:{name}" for bit, name in enumerate(gates) if mask & (1 << bit)
        )
        out.append(
            ShadowRecord(
                candidate_id=f"shadow-{i:06d}",
                dex="PANCAKESWAP_V2" if i % 5 else "PANCAKESWAP_V3",
                trade_decision="NO_TRADE",
                live_trading=False,
                private_key_loaded=False,
                submission_attempted=False,
                public_mempool_allowed=False,
                prior_gates_passed=False,
                blocked_reasons=failed,
            )
        )
    return out
