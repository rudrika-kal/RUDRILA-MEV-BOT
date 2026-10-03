import unittest
from unittest.mock import patch

from rudrila_mev.honeypot_client import check_honeypot
from rudrila_mev.liquidity_safety import collect_uncx_v2_active_locks


PAIR1 = "0x0000000000000000000000000000000000000011"
PAIR2 = "0x0000000000000000000000000000000000000022"
TOKEN = "0x0000000000000000000000000000000000000033"
OWNER = "0x0000000000000000000000000000000000000044"


def safe_payload(pair):
    return {
        "simulationSuccess": True,
        "honeypotResult": {"isHoneypot": False},
        "summary": {"risk": "low", "riskLevel": 1, "flags": []},
        "simulationResult": {
            "buyTax": 0,
            "sellTax": 0,
            "transferTax": 0,
            "buyGas": "100000",
            "sellGas": "100000",
        },
        "contractCode": {"rootOpenSource": True, "isProxy": False},
        "holderAnalysis": {"failed": "0", "highTaxWallets": "0"},
        "pairAddress": pair,
    }


class FakeResponse:
    def __init__(self, status, payload=None, text=""):
        self.status_code = status
        self.ok = 200 <= status < 300
        self._payload = payload
        self.text = text

    def json(self):
        return self._payload


class Call:
    def __init__(self, value):
        self.value = value

    def call(self):
        return self.value


class LockerFunctions:
    def __init__(self, rows):
        self.rows = rows

    def getNumLocksForToken(self, pair):
        return Call(len(self.rows))

    def tokenLocks(self, pair, index):
        return Call(self.rows[index])


class LockerContract:
    def __init__(self, rows):
        self.functions = LockerFunctions(rows)


class FakeEth:
    def __init__(self, rows, timestamp):
        self.rows = rows
        self.timestamp = timestamp

    def contract(self, address, abi):
        return LockerContract(self.rows)

    def get_block(self, block):
        return {"timestamp": self.timestamp}


class FakeW3:
    def __init__(self, rows, timestamp):
        self.eth = FakeEth(rows, timestamp)


class FirewallEvidenceImprovementTests(unittest.TestCase):
    def test_honeypot_tries_second_real_pair_before_blocking(self):
        first = safe_payload(PAIR1)
        first.pop("holderAnalysis")
        responses = [
            FakeResponse(200, first),
            FakeResponse(200, safe_payload(PAIR2)),
        ]
        with patch("requests.Session.get", side_effect=responses):
            ev = check_honeypot(
                token=TOKEN,
                chain_id=56,
                pairs=(PAIR1, PAIR2),
                actual_retries=1,
                retry_delay_seconds=0,
            )
        self.assertTrue(ev.accepted)
        self.assertEqual(ev.raw["_rudrila_requested_pair"].lower(), PAIR2.lower())

    def test_honeypot_rejects_pair_mismatch(self):
        payload = safe_payload(PAIR2)
        with patch(
            "requests.Session.get",
            return_value=FakeResponse(200, payload),
        ):
            ev = check_honeypot(
                token=TOKEN,
                chain_id=56,
                pair=PAIR1,
                actual_retries=1,
                retry_delay_seconds=0,
            )
        # Auto-pair response can still be accepted later, but a mismatched
        # pair-specific response itself must never authorize the requested pool.
        if ev.raw.get("_rudrila_request_mode") == "pair":
            self.assertFalse(ev.accepted)

    def test_uncx_counts_only_locks_beyond_horizon(self):
        now = 1_000_000
        rows = [
            (900_000, 700, 700, now + 3600, 1, OWNER),
            (900_000, 500, 500, now + 100, 2, OWNER),
            (900_000, 0, 500, now + 3600, 3, OWNER),
        ]
        ev = collect_uncx_v2_active_locks(
            FakeW3(rows, now),
            pair=PAIR1,
            min_unlock_horizon_seconds=300,
        )
        self.assertTrue(ev["accepted"])
        self.assertEqual(ev["active_locked_units"], 700)
        self.assertEqual(ev["lock_count"], 3)

    def test_uncx_lock_count_limit_fails_closed(self):
        now = 1_000_000
        rows = [(1, 1, 1, now + 3600, i, OWNER) for i in range(4)]
        ev = collect_uncx_v2_active_locks(
            FakeW3(rows, now),
            pair=PAIR1,
            max_locks=3,
        )
        self.assertFalse(ev["accepted"])
        self.assertEqual(ev["active_locked_units"], 0)


if __name__ == "__main__":
    unittest.main()
