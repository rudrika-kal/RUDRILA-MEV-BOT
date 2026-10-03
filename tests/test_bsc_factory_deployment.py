import json
import unittest
from pathlib import Path
from eth_utils import keccak, to_checksum_address


ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT / "wallet_signer" / "factory-deployment.json").read_text())


class BscFactoryDeploymentTests(unittest.TestCase):
    def test_fixed_chain_owner_factory_and_zero_value(self):
        self.assertEqual(CFG["chainId"], 56)
        self.assertEqual(CFG["value"], "0x0")
        self.assertEqual(
            CFG["owner"].lower(),
            "0x2fd84c20aa82943fbabf7633a9492df0fb40b883",
        )
        self.assertEqual(
            CFG["factory"].lower(),
            "0x4e59b44847b379578588920ca78fbf26c0b4956c",
        )

    def test_constructor_owner_is_exact_execution_wallet(self):
        data = CFG["data"][2:]
        init_code = data[64:]
        owner_tail = "0x" + init_code[-40:]
        self.assertEqual(owner_tail.lower(), CFG["owner"].lower())

    def test_create2_prediction_matches_config(self):
        data = CFG["data"][2:]
        salt = bytes.fromhex(data[:64])
        init_code = bytes.fromhex(data[64:])
        factory = bytes.fromhex(CFG["factory"][2:])
        predicted = "0x" + keccak(
            bytes([0xFF]) + factory + salt + keccak(init_code)
        )[12:].hex()
        self.assertEqual(
            to_checksum_address(predicted),
            CFG["predictedAddress"],
        )


if __name__ == "__main__":
    unittest.main()
