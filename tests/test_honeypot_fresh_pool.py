import unittest
from unittest.mock import patch

from rudrila_mev.honeypot_client import check_honeypot


def safe_payload():
    return {
        "summary": {"risk": "low", "riskLevel": 5, "flags": []},
        "simulationSuccess": True,
        "honeypotResult": {"isHoneypot": False},
        "simulationResult": {
            "buyTax": 0,
            "sellTax": 0,
            "transferTax": 0,
            "buyGas": "150000",
            "sellGas": "120000",
        },
        "holderAnalysis": {"failed": "0", "highTaxWallets": "0"},
        "contractCode": {"rootOpenSource": True, "isProxy": False},
    }


class FakeResponse:
    def __init__(self, status, payload=None, text=""):
        self.status_code = status
        self._payload = payload
        self.text = text

    @property
    def ok(self):
        return 200 <= self.status_code < 300

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append(dict(params or {}))
        return self.responses.pop(0)

    def close(self):
        pass


class FreshPoolFallbackTests(unittest.TestCase):
    def test_fallback_is_diagnostic_and_never_authorizes(self):
        session = FakeSession([
            FakeResponse(404, text="pair not indexed"),
            FakeResponse(404, text="token not indexed"),
            FakeResponse(200, safe_payload()),
        ])
        with patch("rudrila_mev.honeypot_client.requests.Session", return_value=session):
            r = check_honeypot(
                token="0x0000000000000000000000000000000000000001",
                pair="0x0000000000000000000000000000000000000002",
                chain_id=56,
            )

        self.assertTrue(r.simulation_success)
        self.assertFalse(r.accepted)
        self.assertEqual(r.raw["_rudrila_request_mode"], "simulated_liquidity")
        self.assertTrue(session.calls[2]["simulateLiquidity"])
        self.assertIn("diagnostic only", " ".join(r.reasons))

    def test_force_fallback_is_also_diagnostic(self):
        session = FakeSession([
            FakeResponse(404, text="pair not indexed"),
            FakeResponse(404, text="token not indexed"),
            FakeResponse(404, text="simulate unavailable"),
            FakeResponse(200, safe_payload()),
        ])
        with patch("rudrila_mev.honeypot_client.requests.Session", return_value=session):
            r = check_honeypot(
                token="0x0000000000000000000000000000000000000001",
                pair="0x0000000000000000000000000000000000000002",
                chain_id=56,
            )

        self.assertTrue(r.simulation_success)
        self.assertFalse(r.accepted)
        self.assertEqual(r.raw["_rudrila_request_mode"], "forced_simulated_liquidity")
        self.assertTrue(session.calls[3]["forceSimulateLiquidity"])

    def test_real_pair_success_can_pass_normal_policy(self):
        session = FakeSession([FakeResponse(200, safe_payload())])
        with patch("rudrila_mev.honeypot_client.requests.Session", return_value=session):
            r = check_honeypot(
                token="0x0000000000000000000000000000000000000001",
                pair="0x0000000000000000000000000000000000000002",
                chain_id=56,
            )

        self.assertTrue(r.accepted)
        self.assertEqual(r.raw["_rudrila_request_mode"], "pair")


if __name__ == "__main__":
    unittest.main()
