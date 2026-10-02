import unittest

from rudrila_mev.liquidity_safety import classify_liquidity_units


class LiquiditySafetyClassificationTests(unittest.TestCase):
    def test_v2_fully_burned_or_locked_passes(self):
        ev = classify_liquidity_units(
            dex="V2",
            subject="0x0000000000000000000000000000000000000001",
            total_units=1_000_000,
            secured_units=1_000_000,
            removable_units=0,
            unknown_units=0,
            holder_or_position_count=1,
            observed_from_block=1,
            observed_to_block=10,
            min_secured_bps=9500,
            max_removable_bps=0,
        )
        self.assertTrue(ev.accepted)
        self.assertTrue(ev.lock_or_burn_proven)
        self.assertFalse(ev.liquidity_removal_controlled_by_creator)

    def test_v2_creator_control_blocks_even_if_small(self):
        ev = classify_liquidity_units(
            dex="V2",
            subject="0x0000000000000000000000000000000000000001",
            total_units=1_000_000,
            secured_units=990_000,
            removable_units=10_000,
            unknown_units=0,
            holder_or_position_count=2,
            observed_from_block=1,
            observed_to_block=10,
            min_secured_bps=9500,
            max_removable_bps=0,
        )
        self.assertFalse(ev.accepted)
        self.assertTrue(ev.liquidity_removal_controlled_by_creator)
        self.assertTrue(any("removable" in r for r in ev.reasons))

    def test_unknown_holder_blocks(self):
        ev = classify_liquidity_units(
            dex="V2",
            subject="0x0000000000000000000000000000000000000001",
            total_units=1_000_000,
            secured_units=999_999,
            removable_units=0,
            unknown_units=1,
            holder_or_position_count=2,
            observed_from_block=1,
            observed_to_block=10,
        )
        self.assertFalse(ev.accepted)
        self.assertIsNone(ev.liquidity_removal_controlled_by_creator)

    def test_no_liquidity_blocks(self):
        ev = classify_liquidity_units(
            dex="V2",
            subject="0x0000000000000000000000000000000000000001",
            total_units=0,
            secured_units=0,
            removable_units=0,
            unknown_units=0,
            holder_or_position_count=0,
            observed_from_block=1,
            observed_to_block=10,
        )
        self.assertFalse(ev.accepted)
        self.assertTrue(any("no active liquidity" in r for r in ev.reasons))

    def test_v3_all_verified_locked_positions_pass(self):
        ev = classify_liquidity_units(
            dex="V3",
            subject="0x0000000000000000000000000000000000000002",
            total_units=500_000,
            secured_units=500_000,
            removable_units=0,
            unknown_units=0,
            holder_or_position_count=3,
            observed_from_block=1,
            observed_to_block=10,
            min_secured_bps=10_000,
            max_removable_bps=0,
        )
        self.assertTrue(ev.accepted)

    def test_v3_eoa_position_owner_blocks(self):
        ev = classify_liquidity_units(
            dex="V3",
            subject="0x0000000000000000000000000000000000000002",
            total_units=500_000,
            secured_units=400_000,
            removable_units=100_000,
            unknown_units=0,
            holder_or_position_count=3,
            observed_from_block=1,
            observed_to_block=10,
            min_secured_bps=10_000,
            max_removable_bps=0,
        )
        self.assertFalse(ev.accepted)
        self.assertTrue(ev.liquidity_removal_controlled_by_creator)

    def test_v3_unknown_contract_owner_blocks(self):
        ev = classify_liquidity_units(
            dex="V3",
            subject="0x0000000000000000000000000000000000000002",
            total_units=500_000,
            secured_units=400_000,
            removable_units=0,
            unknown_units=100_000,
            holder_or_position_count=3,
            observed_from_block=1,
            observed_to_block=10,
            min_secured_bps=10_000,
            max_removable_bps=0,
        )
        self.assertFalse(ev.accepted)
        self.assertIsNone(ev.liquidity_removal_controlled_by_creator)


if __name__ == "__main__":
    unittest.main()
