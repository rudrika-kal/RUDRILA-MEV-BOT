import unittest

from rudrila_mev.risk_guard import ContractRiskEvidence, assess_contract_risk
from rudrila_mev.trade_gate import pretrade_gate


def safe_evidence():
    return ContractRiskEvidence(
        buy_simulation_passed=True,
        sell_simulation_passed=True,
        transfer_out_passed=True,
        buy_tax_bps=100,
        sell_tax_bps=100,
        roundtrip_loss_bps=300,
        dynamic_tax_suspected=False,
        liquidity_lock_or_burn_proven=True,
        liquidity_removal_controlled_by_creator=False,
        admin_safety_proven=True,
        can_mint=False,
        can_blacklist=False,
        can_pause_trading=False,
        can_change_fees=False,
        can_change_max_tx_or_wallet=False,
        is_proxy=False,
        proxy_implementation_checked=None,
        bytecode_present=True,
        metadata_callable=True,
    )


class RiskGuardTests(unittest.TestCase):
    def test_safe_contract_passes(self):
        d = assess_contract_risk(safe_evidence())
        self.assertTrue(d.accepted)

    def test_sell_failure_blocks_as_honeypot(self):
        e = safe_evidence().__dict__.copy()
        e["sell_simulation_passed"] = False
        d = assess_contract_risk(ContractRiskEvidence(**e))
        self.assertFalse(d.accepted)
        self.assertTrue(any("HONEYPOT" in x for x in d.reasons))

    def test_unknown_is_fail_closed(self):
        d = assess_contract_risk(ContractRiskEvidence())
        self.assertFalse(d.accepted)
        self.assertTrue(any("UNKNOWN" in x for x in d.reasons))

    def test_unlocked_liquidity_blocks(self):
        e = safe_evidence().__dict__.copy()
        e["liquidity_lock_or_burn_proven"] = False
        d = assess_contract_risk(ContractRiskEvidence(**e))
        self.assertFalse(d.accepted)
        self.assertTrue(any("RUG_RISK" in x for x in d.reasons))

    def test_creator_liquidity_control_blocks(self):
        e = safe_evidence().__dict__.copy()
        e["liquidity_removal_controlled_by_creator"] = True
        d = assess_contract_risk(ContractRiskEvidence(**e))
        self.assertFalse(d.accepted)

    def test_mutable_fee_authority_blocks(self):
        e = safe_evidence().__dict__.copy()
        e["can_change_fees"] = True
        d = assess_contract_risk(ContractRiskEvidence(**e))
        self.assertFalse(d.accepted)

    def test_unverified_proxy_blocks(self):
        e = safe_evidence().__dict__.copy()
        e["is_proxy"] = True
        e["proxy_implementation_checked"] = False
        d = assess_contract_risk(ContractRiskEvidence(**e))
        self.assertFalse(d.accepted)

    def test_contract_risk_is_first_trade_gate(self):
        e = safe_evidence().__dict__.copy()
        e["can_blacklist"] = True
        risk = assess_contract_risk(ContractRiskEvidence(**e))
        d = pretrade_gate(
            contract_risk=risk,
            liquidity_ok=True,
            price_impact_ok=True,
            simulation_ok=True,
            gas_profit_ok=True,
        )
        self.assertFalse(d.allowed)
        self.assertIn("contract risk", d.reason)

    def test_profit_never_overrides_contract_risk(self):
        e = safe_evidence().__dict__.copy()
        e["sell_simulation_passed"] = False
        risk = assess_contract_risk(ContractRiskEvidence(**e))
        d = pretrade_gate(
            contract_risk=risk,
            liquidity_ok=True,
            price_impact_ok=True,
            simulation_ok=True,
            gas_profit_ok=True,
        )
        self.assertFalse(d.allowed)


if __name__ == "__main__":
    unittest.main()
