import unittest
from unittest.mock import Mock

from web3 import Web3
from rudrila_mev.v3_monitor import V3LaunchMonitor, POOL_CREATED_TOPIC


def topic_address(addr: str) -> bytes:
    return bytes.fromhex("00" * 12 + addr[2:].lower())


def topic_uint(value: int) -> bytes:
    return int(value).to_bytes(32, "big")


class V3MonitorTests(unittest.TestCase):
    def test_decodes_supported_base_pool(self):
        base = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"
        token = "0x0000000000000000000000000000000000000001"
        pool = "0x0000000000000000000000000000000000000002"
        factory = "0x0BFbCF9fa4f9C56B0F40a671Ad40E0805A091865"

        topic0 = bytes.fromhex(
            POOL_CREATED_TOPIC[2:]
            if POOL_CREATED_TOPIC.startswith("0x")
            else POOL_CREATED_TOPIC
        )
        log = {
            "topics": [
                topic0,
                topic_address(token),
                topic_address(base),
                topic_uint(3000),
            ],
            "data": (
                (60).to_bytes(32, "big", signed=True)
                + bytes.fromhex("00" * 12 + pool[2:].lower())
            ),
            "address": factory,
            "blockNumber": 123,
        }

        w3 = Mock()
        w3.eth.get_logs.return_value = [log]
        m = V3LaunchMonitor(w3, [factory], base, [500, 3000, 10000])
        out = m.scan_range(123, 123)

        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].pool, Web3.to_checksum_address(pool))
        self.assertEqual(out[0].token, Web3.to_checksum_address(token))
        self.assertEqual(out[0].fee, 3000)
        self.assertEqual(out[0].tick_spacing, 60)

    def test_rejects_unapproved_fee_tier(self):
        base = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"
        token = "0x0000000000000000000000000000000000000001"
        pool = "0x0000000000000000000000000000000000000002"
        factory = "0x0BFbCF9fa4f9C56B0F40a671Ad40E0805A091865"

        topic0 = bytes.fromhex(
            POOL_CREATED_TOPIC[2:]
            if POOL_CREATED_TOPIC.startswith("0x")
            else POOL_CREATED_TOPIC
        )
        log = {
            "topics": [
                topic0,
                topic_address(token),
                topic_address(base),
                topic_uint(1234),
            ],
            "data": (
                (60).to_bytes(32, "big", signed=True)
                + bytes.fromhex("00" * 12 + pool[2:].lower())
            ),
            "address": factory,
            "blockNumber": 123,
        }

        w3 = Mock()
        w3.eth.get_logs.return_value = [log]
        m = V3LaunchMonitor(w3, [factory], base, [500, 3000, 10000])
        self.assertEqual(m.scan_range(123, 123), [])


if __name__ == "__main__":
    unittest.main()
