import unittest

from rudrila_mev.evm import _json_rpc_send


class EvmSecurityTests(unittest.TestCase):
    def test_private_rpc_rejects_plain_http(self):
        with self.assertRaises(RuntimeError):
            _json_rpc_send(
                "http://example.invalid",
                "eth_sendRawTransaction",
                ["0x00"],
            )


if __name__ == "__main__":
    unittest.main()
