from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_day(now: datetime | None = None) -> str:
    return (now or utc_now()).date().isoformat()


@dataclass(frozen=True)
class ExecutionRecord:
    timestamp: str
    day: str
    tx_hash: str | None
    token: str
    gross_profit_wei: int
    gas_paid_wei: int
    realized_net_wei: int
    success: bool
    reverted: bool
    note: str = ""
    builder_payment_wei: int = 0
    other_cost_wei: int = 0

    @property
    def computed_net_wei(self) -> int:
        return (
            int(self.gross_profit_wei)
            - int(self.gas_paid_wei)
            - int(self.builder_payment_wei)
            - int(self.other_cost_wei)
        )


@dataclass(frozen=True)
class LedgerAudit:
    accepted: bool
    records: int
    malformed_lines: int
    mismatched_pnl_records: int
    missing_success_tx_hashes: int
    reasons: tuple[str, ...]

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ExecutionRiskDecision:
    blocked: bool
    hourly_realized_net_wei: int
    daily_realized_net_wei: int
    hourly_failed_transactions: int
    daily_failed_transactions: int
    daily_reverts: int
    daily_failed_gas_wei: int
    audit_ok: bool
    reasons: tuple[str, ...]

    def as_dict(self) -> dict:
        return asdict(self)


class ExecutionLedger:
    def __init__(self, journal_path: str):
        self.path = Path(journal_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, r: ExecutionRecord) -> None:
        if int(r.realized_net_wei) != r.computed_net_wei:
            raise ValueError(
                f"realized P&L mismatch: supplied={r.realized_net_wei} "
                f"computed={r.computed_net_wei}"
            )
        if r.success and not r.tx_hash:
            raise ValueError("successful execution record requires tx_hash")
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(r), separators=(",", ":")) + "\n")

    def read_all_strict(self) -> tuple[list[ExecutionRecord], int]:
        if not self.path.exists():
            return [], 0
        out: list[ExecutionRecord] = []
        malformed = 0
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                out.append(ExecutionRecord(**data))
            except (json.JSONDecodeError, TypeError, ValueError):
                malformed += 1
        return out, malformed

    def read_day(self, day: str | None = None) -> list[ExecutionRecord]:
        day = day or utc_day()
        rows, _ = self.read_all_strict()
        return [x for x in rows if x.day == day]

    def read_since(self, since: datetime) -> list[ExecutionRecord]:
        since = since.astimezone(timezone.utc)
        rows, _ = self.read_all_strict()
        out = []
        for row in rows:
            try:
                ts = datetime.fromisoformat(row.timestamp.replace("Z", "+00:00"))
                ts = ts.astimezone(timezone.utc)
            except ValueError:
                continue
            if ts >= since:
                out.append(row)
        return out

    @staticmethod
    def totals(rows: Iterable[ExecutionRecord]) -> dict:
        rows = list(rows)
        return {
            "attempts": len(rows),
            "failed": sum(1 for x in rows if not x.success),
            "reverted": sum(1 for x in rows if x.reverted),
            "gas_paid_wei": sum(max(0, int(x.gas_paid_wei)) for x in rows),
            "failed_gas_wei": sum(
                max(0, int(x.gas_paid_wei)) for x in rows if not x.success
            ),
            "gross_profit_wei": sum(int(x.gross_profit_wei) for x in rows),
            "builder_payment_wei": sum(
                max(0, int(x.builder_payment_wei)) for x in rows
            ),
            "other_cost_wei": sum(max(0, int(x.other_cost_wei)) for x in rows),
            "realized_net_wei": sum(int(x.realized_net_wei) for x in rows),
        }

    def daily_totals(self, day: str | None = None) -> dict:
        return self.totals(self.read_day(day))

    def hourly_totals(self, now: datetime | None = None) -> dict:
        now = (now or utc_now()).astimezone(timezone.utc)
        return self.totals(self.read_since(now - timedelta(hours=1)))

    def audit(self) -> LedgerAudit:
        rows, malformed = self.read_all_strict()
        mismatch = sum(
            1 for x in rows if int(x.realized_net_wei) != x.computed_net_wei
        )
        missing_hashes = sum(1 for x in rows if x.success and not x.tx_hash)
        reasons: list[str] = []
        if malformed:
            reasons.append(f"BLOCK: ledger has {malformed} malformed line(s)")
        if mismatch:
            reasons.append(f"BLOCK: ledger has {mismatch} realized-P&L mismatch(es)")
        if missing_hashes:
            reasons.append(
                f"BLOCK: ledger has {missing_hashes} successful record(s) without tx hash"
            )
        accepted = not reasons
        if accepted:
            reasons.append("PASS: realized P&L ledger reconciles exactly")
        return LedgerAudit(
            accepted=accepted,
            records=len(rows),
            malformed_lines=malformed,
            mismatched_pnl_records=mismatch,
            missing_success_tx_hashes=missing_hashes,
            reasons=tuple(reasons),
        )


@dataclass(frozen=True)
class KillSwitchDecision:
    blocked: bool
    reason: str


def daily_kill_switch(
    *,
    failed_gas_wei: int,
    failed_transactions: int,
    max_daily_gas_loss_wei: int,
    max_daily_failed_transactions: int,
) -> KillSwitchDecision:
    if int(failed_gas_wei) >= int(max_daily_gas_loss_wei):
        return KillSwitchDecision(True, "KILL: daily failed-gas limit reached")
    if int(failed_transactions) >= int(max_daily_failed_transactions):
        return KillSwitchDecision(
            True, "KILL: daily failed-transaction limit reached"
        )
    return KillSwitchDecision(False, "PASS: daily execution limits")


def evaluate_execution_risk(
    ledger: ExecutionLedger,
    *,
    now: datetime | None = None,
    max_hourly_net_loss_wei: int,
    max_daily_net_loss_wei: int,
    max_daily_failed_gas_wei: int,
    max_hourly_failed_transactions: int,
    max_daily_failed_transactions: int,
    max_daily_reverts: int,
) -> ExecutionRiskDecision:
    now = (now or utc_now()).astimezone(timezone.utc)
    audit = ledger.audit()
    hour = ledger.hourly_totals(now)
    day = ledger.daily_totals(now.date().isoformat())
    reasons: list[str] = list(audit.reasons if not audit.accepted else ())

    if int(hour["realized_net_wei"]) <= -abs(int(max_hourly_net_loss_wei)):
        reasons.append("KILL: hourly realized net-loss limit reached")
    if int(day["realized_net_wei"]) <= -abs(int(max_daily_net_loss_wei)):
        reasons.append("KILL: daily realized net-loss limit reached")
    if int(day["failed_gas_wei"]) >= int(max_daily_failed_gas_wei):
        reasons.append("KILL: daily failed-gas limit reached")
    if int(hour["failed"]) >= int(max_hourly_failed_transactions):
        reasons.append("KILL: hourly failed-transaction limit reached")
    if int(day["failed"]) >= int(max_daily_failed_transactions):
        reasons.append("KILL: daily failed-transaction limit reached")
    if int(day["reverted"]) >= int(max_daily_reverts):
        reasons.append("KILL: daily revert limit reached")

    blocked = bool(reasons)
    if not blocked:
        reasons.append("PASS: execution loss/revert limits and realized P&L audit")
    return ExecutionRiskDecision(
        blocked=blocked,
        hourly_realized_net_wei=int(hour["realized_net_wei"]),
        daily_realized_net_wei=int(day["realized_net_wei"]),
        hourly_failed_transactions=int(hour["failed"]),
        daily_failed_transactions=int(day["failed"]),
        daily_reverts=int(day["reverted"]),
        daily_failed_gas_wei=int(day["failed_gas_wei"]),
        audit_ok=audit.accepted,
        reasons=tuple(reasons),
    )
