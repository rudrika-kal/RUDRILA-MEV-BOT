from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


def utc_day() -> str:
    return datetime.now(timezone.utc).date().isoformat()


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


class ExecutionLedger:
    def __init__(self, journal_path: str):
        self.path = Path(journal_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, r: ExecutionRecord) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(r), separators=(",", ":")) + "\n")

    def read_day(self, day: str | None = None) -> list[ExecutionRecord]:
        day = day or utc_day()
        if not self.path.exists():
            return []

        out: list[ExecutionRecord] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = None
            try:
                data = json.loads(line)
                record = ExecutionRecord(**data)
            except (json.JSONDecodeError, TypeError, ValueError):
                record = None
            if record is not None and record.day == day:
                out.append(record)
        return out

    def daily_totals(self, day: str | None = None) -> dict:
        rows = self.read_day(day)
        failed = sum(1 for x in rows if not x.success)
        reverted = sum(1 for x in rows if x.reverted)
        gas_paid = sum(max(0, int(x.gas_paid_wei)) for x in rows)
        failed_gas = sum(
            max(0, int(x.gas_paid_wei)) for x in rows if not x.success
        )
        net = sum(int(x.realized_net_wei) for x in rows)
        return {
            "attempts": len(rows),
            "failed": failed,
            "reverted": reverted,
            "gas_paid_wei": gas_paid,
            "failed_gas_wei": failed_gas,
            "realized_net_wei": net,
        }


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
