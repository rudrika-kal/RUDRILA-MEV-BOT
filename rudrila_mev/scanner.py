from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from .config import Settings
from .evm import EvmClient
from .all_cost_profit import AllCostProfitEvidence, evaluate_all_cost_profit


@dataclass(frozen=True)
class Opportunity:
    direction: str
    block_number: int
    buy_router: str
    sell_router: str
    decision: AllCostProfitEvidence
    gas: dict
    route: dict
    live_submitted: bool = False
    tx_hash: str | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Scanner:
    def __init__(self, settings: Settings):
        self.s = settings
        self.evm = EvmClient(settings)

    def inspect_direction(self, direction: str) -> Opportunity:
        if direction == "A_TO_B":
            buy_router = self.evm.router_a
            sell_router = self.evm.router_b
            buy_addr = self.s.router_a
            sell_addr = self.s.router_b
        else:
            buy_router = self.evm.router_b
            sell_router = self.evm.router_a
            buy_addr = self.s.router_b
            sell_addr = self.s.router_a

        route = self.evm.route_quote(
            buy_router, sell_router, self.s.slippage_bps_per_leg
        )
        deadline = self.evm.chain_deadline()

        # First gas pass uses the configured conservative fallback or a real estimate
        # if the executor is already deployed/approved. minGrossProfit=0 is only for
        # estimation; the actual transaction always gets the final protected threshold.
        gas = self.evm.estimate_gas_quote(
            buy_router_address=buy_addr,
            sell_router_address=sell_addr,
            route=route,
            min_gross_profit=0,
            deadline=deadline,
        )

        decision = evaluate_all_cost_profit(
            amount_in_wei=self.s.amount_in_wei,
            expected_final_wei=route.expected_final_out,
            floor_final_wei=route.min_final_out,
            gas_cost_wei=gas.worst_case_gas_cost_wei,
            builder_payment_wei=0 if not self.s.live_trading else None,
            non_embedded_cost_wei=0,
            dex_fee_cost_wei=None,
            slippage_cost_wei=None,
            token_tax_cost_wei=None,
            safety_buffer_wei=self.s.extra_safety_buffer_wei,
            min_net_profit_wei=self.s.min_net_profit_wei,
            route_output_embeds_dex_fees=True,
            floor_output_embeds_slippage=True,
            route_output_embeds_token_tax=False,
            quoted_block=route.block_number,
            current_block=int(self.evm.w3.eth.block_number),
            max_quote_age_blocks=self.s.max_quote_age_blocks,
            raw={"token_tax_evidence": "missing -> fail closed"},
        )

        submitted = False
        tx_hash = None
        if decision.accepted and self.s.live_trading:
            self.evm.ensure_fresh_block(route.block_number)

            # Re-estimate with the exact on-chain minimum gross-profit requirement.
            gas = self.evm.estimate_gas_quote(
                buy_router_address=buy_addr,
                sell_router_address=sell_addr,
                route=route,
                min_gross_profit=decision.required_gross_profit_wei,
                deadline=deadline,
            )
            decision = evaluate_all_cost_profit(
                amount_in_wei=self.s.amount_in_wei,
                expected_final_wei=route.expected_final_out,
                floor_final_wei=route.min_final_out,
                gas_cost_wei=gas.worst_case_gas_cost_wei,
                builder_payment_wei=None,
                non_embedded_cost_wei=0,
                dex_fee_cost_wei=None,
                slippage_cost_wei=None,
                token_tax_cost_wei=None,
                safety_buffer_wei=self.s.extra_safety_buffer_wei,
                min_net_profit_wei=self.s.min_net_profit_wei,
                route_output_embeds_dex_fees=True,
                floor_output_embeds_slippage=True,
                route_output_embeds_token_tax=False,
                quoted_block=route.block_number,
                current_block=int(self.evm.w3.eth.block_number),
                max_quote_age_blocks=self.s.max_quote_age_blocks,
                raw={
                    "builder_payment_evidence": "missing until private submission gate",
                    "token_tax_evidence": "missing -> fail closed",
                },
            )
            if decision.accepted:
                tx_hash = self.evm.send_trade(
                    buy_router_address=buy_addr,
                    sell_router_address=sell_addr,
                    route=route,
                    min_gross_profit=decision.required_gross_profit_wei,
                    gas_quote=gas,
                    deadline=deadline,
                )
                submitted = True

        return Opportunity(
            direction=direction,
            block_number=route.block_number,
            buy_router=buy_addr,
            sell_router=sell_addr,
            decision=decision,
            gas=asdict(gas),
            route=asdict(route),
            live_submitted=submitted,
            tx_hash=tx_hash,
        )

    def run_once(self) -> list[Opportunity]:
        results = []
        for direction in ("A_TO_B", "B_TO_A"):
            try:
                op = self.inspect_direction(direction)
                print(json.dumps({"time": _now(), **asdict(op)}, separators=(",", ":")))
                results.append(op)
            except Exception as exc:
                print(json.dumps({
                    "time": _now(),
                    "direction": direction,
                    "status": "ERROR",
                    "error": f"{type(exc).__name__}: {exc}",
                }, separators=(",", ":")))
        return results

    def run_forever(self) -> None:
        while True:
            self.run_once()
            time.sleep(self.s.scan_interval_seconds)
