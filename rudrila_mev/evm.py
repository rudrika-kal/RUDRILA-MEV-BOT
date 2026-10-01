from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from typing import Any

from eth_account import Account
from web3 import Web3

from .abi import ERC20_ABI, EXECUTOR_ABI, V2_ROUTER_ABI
from .config import Settings
from .profit import GasQuote, add_bps


@dataclass(frozen=True)
class RouteQuote:
    block_number: int
    buy_quote_out: int
    min_buy_out: int
    expected_final_out: int
    min_final_out: int


class EvmClient:
    def __init__(self, settings: Settings):
        self.s = settings
        self.w3 = Web3(Web3.HTTPProvider(settings.rpc_url, request_kwargs={"timeout": 8}))
        if not self.w3.is_connected():
            raise RuntimeError("RPC connection failed")

        actual_chain = int(self.w3.eth.chain_id)
        if actual_chain != settings.chain_id:
            raise RuntimeError(f"Chain ID mismatch: config={settings.chain_id}, rpc={actual_chain}")

        self.wallet = Web3.to_checksum_address(settings.wallet_address)
        self.base = Web3.to_checksum_address(settings.base_token)
        self.quote = Web3.to_checksum_address(settings.quote_token)
        self.router_a = self.w3.eth.contract(
            address=Web3.to_checksum_address(settings.router_a), abi=V2_ROUTER_ABI
        )
        self.router_b = self.w3.eth.contract(
            address=Web3.to_checksum_address(settings.router_b), abi=V2_ROUTER_ABI
        )
        self.executor = (
            self.w3.eth.contract(
                address=Web3.to_checksum_address(settings.executor_address), abi=EXECUTOR_ABI
            )
            if settings.executor_address
            else None
        )
        self.base_token = self.w3.eth.contract(address=self.base, abi=ERC20_ABI)

        # Fail fast on accidental EOAs / wrong-chain addresses once real addresses are configured.
        for label, addr in (("base token", self.base), ("quote token", self.quote),
                            ("router A", self.router_a.address), ("router B", self.router_b.address)):
            if int(addr, 16) != 0 and len(self.w3.eth.get_code(addr)) == 0:
                raise RuntimeError(f"{label} has no contract code on chain {actual_chain}: {addr}")

        if self.executor is not None:
            if len(self.w3.eth.get_code(self.executor.address)) == 0:
                raise RuntimeError(f"Executor has no contract code: {self.executor.address}")
            contract_owner = Web3.to_checksum_address(self.executor.functions.owner().call())
            if contract_owner != self.wallet:
                raise RuntimeError(
                    f"Executor owner mismatch: contract={contract_owner}, configured wallet={self.wallet}"
                )

    def quote_router(self, router, amount_in: int, token_in: str, token_out: str, block_identifier: int) -> int:
        amounts = router.functions.getAmountsOut(
            amount_in,
            [Web3.to_checksum_address(token_in), Web3.to_checksum_address(token_out)],
        ).call(block_identifier=block_identifier)
        if len(amounts) < 2 or int(amounts[-1]) <= 0:
            raise RuntimeError("Invalid router quote")
        return int(amounts[-1])

    def route_quote(self, buy_router, sell_router, slippage_bps: int) -> RouteQuote:
        block_number = int(self.w3.eth.block_number)
        buy_out = self.quote_router(
            buy_router, self.s.amount_in_wei, self.base, self.quote, block_number
        )
        min_buy = buy_out * (10_000 - slippage_bps) // 10_000

        expected_final = self.quote_router(
            sell_router, buy_out, self.quote, self.base, block_number
        )
        # Important: recompute the second leg using the first leg's worst-case output,
        # then apply the second-leg haircut. This creates a true two-leg floor.
        sell_on_min_buy = self.quote_router(
            sell_router, min_buy, self.quote, self.base, block_number
        )
        min_final = sell_on_min_buy * (10_000 - slippage_bps) // 10_000

        return RouteQuote(
            block_number=block_number,
            buy_quote_out=buy_out,
            min_buy_out=min_buy,
            expected_final_out=expected_final,
            min_final_out=min_final,
        )

    def chain_deadline(self) -> int:
        latest = self.w3.eth.get_block("latest")
        return int(latest["timestamp"]) + self.s.deadline_seconds

    def fee_fields(self) -> tuple[int, int, int]:
        pending = self.w3.eth.get_block("pending")
        base_fee = int(pending.get("baseFeePerGas", self.w3.eth.gas_price))
        try:
            priority = int(self.w3.eth.max_priority_fee)
        except Exception:
            priority = max(1, int(self.w3.eth.gas_price) - base_fee)

        base_component = (base_fee * self.s.base_fee_multiplier_bps + 9_999) // 10_000
        priority_component = (priority * self.s.priority_fee_multiplier_bps + 9_999) // 10_000
        max_fee = base_component + priority_component
        if max_fee > self.s.max_fee_per_gas_wei:
            raise RuntimeError(
                f"Gas price safety cap exceeded: {max_fee} > {self.s.max_fee_per_gas_wei}"
            )
        return base_fee, priority, max_fee

    def estimate_gas_quote(
        self,
        *,
        buy_router_address: str,
        sell_router_address: str,
        route: RouteQuote,
        min_gross_profit: int,
        deadline: int,
    ) -> GasQuote:
        base_fee, priority, max_fee = self.fee_fields()
        source = "fallback-conservative"
        units = int(self.s.gas_units_fallback)

        if self.executor is not None:
            allowance = int(
                self.base_token.functions.allowance(
                    self.wallet, self.executor.address
                ).call()
            )
            if allowance >= self.s.amount_in_wei:
                fn = self.executor.functions.executeV2Arbitrage(
                    self.base,
                    self.quote,
                    Web3.to_checksum_address(buy_router_address),
                    Web3.to_checksum_address(sell_router_address),
                    self.s.amount_in_wei,
                    route.min_buy_out,
                    route.min_final_out,
                    int(min_gross_profit),
                    int(deadline),
                )
                try:
                    units = int(fn.estimate_gas({"from": self.wallet}))
                    source = "eth_estimateGas"
                except Exception as exc:
                    if self.s.live_trading:
                        raise RuntimeError(f"Live gas simulation failed: {exc}") from exc

        buffered_units = add_bps(units, self.s.gas_units_buffer_bps)
        cost = buffered_units * max_fee
        return GasQuote(
            gas_units=units,
            buffered_gas_units=buffered_units,
            base_fee_per_gas=base_fee,
            priority_fee_per_gas=priority,
            max_fee_per_gas=max_fee,
            worst_case_gas_cost_wei=cost,
            source=source,
        )

    def ensure_fresh_block(self, quoted_block: int) -> None:
        now_block = int(self.w3.eth.block_number)
        if now_block - quoted_block > self.s.max_quote_age_blocks:
            raise RuntimeError(
                f"Quote stale: quoted block {quoted_block}, current block {now_block}"
            )

    def send_trade(
        self,
        *,
        buy_router_address: str,
        sell_router_address: str,
        route: RouteQuote,
        min_gross_profit: int,
        gas_quote: GasQuote,
        deadline: int,
    ) -> str:
        if not self.s.live_trading:
            raise RuntimeError("Live trading is OFF")
        if self.executor is None:
            raise RuntimeError("Executor contract missing")

        self.ensure_fresh_block(route.block_number)

        nonce = self.w3.eth.get_transaction_count(self.wallet, "pending")
        fn = self.executor.functions.executeV2Arbitrage(
            self.base,
            self.quote,
            Web3.to_checksum_address(buy_router_address),
            Web3.to_checksum_address(sell_router_address),
            self.s.amount_in_wei,
            route.min_buy_out,
            route.min_final_out,
            int(min_gross_profit),
            int(deadline),
        )
        tx = fn.build_transaction(
            {
                "from": self.wallet,
                "chainId": self.s.chain_id,
                "nonce": nonce,
                "gas": gas_quote.buffered_gas_units,
                "maxFeePerGas": gas_quote.max_fee_per_gas,
                "maxPriorityFeePerGas": min(
                    gas_quote.priority_fee_per_gas * self.s.priority_fee_multiplier_bps // 10_000,
                    gas_quote.max_fee_per_gas,
                ),
                "type": 2,
            }
        )

        signed = Account.sign_transaction(tx, self.s.private_key)
        raw_hex = signed.raw_transaction.hex()

        if self.s.private_submission_rpc:
            result = _json_rpc_send(self.s.private_submission_rpc, "eth_sendRawTransaction", [raw_hex])
            if not isinstance(result, str):
                raise RuntimeError(f"Unexpected private RPC response: {result!r}")
            return result

        if not self.s.allow_public_mempool:
            raise RuntimeError("Refusing public-mempool submission")
        return self.w3.eth.send_raw_transaction(signed.raw_transaction).hex()


def _json_rpc_send(url: str, method: str, params: list[Any]) -> Any:
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "RUDRILA-MEV/0.1"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        data = json.loads(response.read().decode())
    if "error" in data:
        raise RuntimeError(f"Private RPC error: {data['error']}")
    return data.get("result")
