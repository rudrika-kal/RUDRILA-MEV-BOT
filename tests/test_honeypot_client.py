import unittest

from rudrila_mev.honeypot_client import parse_honeypot_response


def safe_payload():
    return {
        "summary": {"risk": "low", "riskLevel": 5, "flags": []},
        "simulationSuccess": True,
        "honeypotResult": {"isHoneypot": False},
        "simulationResult": {
            "buyTax": 1.0,
            "sellTax": 2.0,
            "transferTax": 0,
            "buyGas": "150000",
            "sellGas": "120000",
        },
        "holderAnalysis": {
            "failed": "0",
            "highTaxWallets": "0",
        },
        "contractCode": {
            "rootOpenSource": True,
            "isProxy": False,
        },
    }


class HoneypotClientTests(unittest.TestCase):
    def test_safe_payload_passes(self):
        d = parse_honeypot_response(safe_payload())
        self.assertTrue(d.accepted)
        self.assertEqual(d.buy_tax_bps, 100)
        self.assertEqual(d.sell_tax_bps, 200)

    def test_honeypot_blocks(self):
        p = safe_payload()
        p["honeypotResult"]["isHoneypot"] = True
        self.assertFalse(parse_honeypot_response(p).accepted)

    def test_unknown_risk_blocks(self):
        p = safe_payload()
        p["summary"] = {"risk": "unknown"}
        self.assertFalse(parse_honeypot_response(p).accepted)

    def test_high_tax_blocks(self):
        p = safe_payload()
        p["simulationResult"]["sellTax"] = 20
        self.assertFalse(parse_honeypot_response(p).accepted)

    def test_proxy_blocks(self):
        p = safe_payload()
        p["contractCode"]["isProxy"] = True
        self.assertFalse(parse_honeypot_response(p).accepted)

    def test_closed_source_blocks(self):
        p = safe_payload()
        p["contractCode"]["rootOpenSource"] = False
        self.assertFalse(parse_honeypot_response(p).accepted)

    def test_holder_failures_block(self):
        p = safe_payload()
        p["holderAnalysis"]["failed"] = "1"
        self.assertFalse(parse_honeypot_response(p).accepted)


if __name__ == "__main__":
    unittest.main()
