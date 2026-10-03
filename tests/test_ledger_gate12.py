import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from rudrila_mev.ledger import (
    ExecutionLedger, ExecutionRecord, evaluate_execution_risk,
)

NOW=datetime(2026,10,3,5,0,0,tzinfo=timezone.utc)

def rec(net=80, success=True, reverted=False, gas=10, gross=100, builder=5, other=5, h="0x"+"1"*64):
    return ExecutionRecord(
        timestamp=NOW.isoformat(), day=NOW.date().isoformat(), tx_hash=h if success else None,
        token="0x0000000000000000000000000000000000000001",
        gross_profit_wei=gross, gas_paid_wei=gas, realized_net_wei=net,
        success=success, reverted=reverted, builder_payment_wei=builder,
        other_cost_wei=other,
    )

class LedgerGate12Tests(unittest.TestCase):
    def ledger(self):
        td=tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        return ExecutionLedger(str(Path(td.name)/"j.jsonl"))

    def limits(self,l):
        return evaluate_execution_risk(
            l,now=NOW,max_hourly_net_loss_wei=100,max_daily_net_loss_wei=200,
            max_daily_failed_gas_wei=50,max_hourly_failed_transactions=2,
            max_daily_failed_transactions=3,max_daily_reverts=2,
        )

    def test_exact_realized_pnl_passes(self):
        l=self.ledger(); l.append(rec())
        self.assertTrue(l.audit().accepted)
        self.assertFalse(self.limits(l).blocked)

    def test_append_rejects_pnl_mismatch(self):
        l=self.ledger()
        with self.assertRaises(ValueError):
            l.append(rec(net=81))

    def test_malformed_ledger_blocks(self):
        l=self.ledger(); l.path.write_text("{bad json\n")
        self.assertTrue(self.limits(l).blocked)

    def test_hourly_net_loss_kills(self):
        l=self.ledger()
        l.append(rec(net=-100,gross=0,gas=90,builder=5,other=5,success=False))
        self.assertTrue(self.limits(l).blocked)

    def test_daily_failed_gas_kills(self):
        l=self.ledger()
        l.append(rec(net=-60,gross=0,gas=50,builder=5,other=5,success=False))
        self.assertTrue(self.limits(l).blocked)

    def test_hourly_fail_count_kills(self):
        l=self.ledger()
        for i in range(2):
            l.append(rec(net=-20,gross=0,gas=10,builder=5,other=5,success=False,h=None))
        self.assertTrue(self.limits(l).blocked)

    def test_revert_count_kills(self):
        l=self.ledger()
        for i in range(2):
            l.append(rec(net=-20,gross=0,gas=10,builder=5,other=5,success=False,reverted=True,h=None))
        self.assertTrue(self.limits(l).blocked)

if __name__=="__main__":
    unittest.main()
