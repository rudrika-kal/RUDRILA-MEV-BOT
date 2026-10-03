from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from eth_account import Account
from web3 import Web3

from .abi import ERC20_ABI, EXECUTOR_ABI
from .all_cost_profit import AllCostProfitEvidence, evaluate_all_cost_profit
from .dynamic_firewall import DynamicTokenFirewallDecision
from .ledger import ExecutionLedger, ExecutionRecord, ExecutionRiskDecision, utc_day, utc_now
from .postbuy_quote_shadow import ReadOnlyPostBuyQuote
from .postbuy_trigger import ConfirmedLargeBuy, post_confirmation_gate
from .private_submission import (
    DEFAULT_BSC_PRIVATE_PATHS,
    PrivatePath,
    PrivateSubmissionEvidence,
    submit_private_raw_transaction,
)


@dataclass(frozen=True)
class LivePostBuyAuthorization:
    accepted: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class PreparedPostBuyTrade:
    trigger_hash: str
    token: str
    route_id: str
    quoted_block: int
    current_block: int
    amount_in_wei: int
    gas_units: int
    buffered_gas_units: int
    max_fee_per_gas_wei: int
    required_gross_profit_wei: int
    profit: AllCostProfitEvidence
    transaction: dict[str, Any]


def evaluate_live_postbuy_authorization(
    *,
    trigger: ConfirmedLargeBuy,
    current_block: int,
    firewall: DynamicTokenFirewallDecision,
    quote: ReadOnlyPostBuyQuote,
    private_paths: PrivateSubmissionEvidence,
    execution_risk: ExecutionRiskDecision,
    executor_paused: bool,
    owner_matches: bool,
    routers_allowlisted: bool,
    allowance_wei: int,
    max_amount_in_wei: int,
) -> LivePostBuyAuthorization:
    reasons: list[str] = []
    ok, why = post_confirmation_gate(trigger, current_block=int(current_block))
    if not ok:
        reasons.append(why)

    if int(quote.quoted_block) < int(trigger.block_number):
        reasons.append("BLOCK: route quote predates confirmed large buy")
    if int(current_block) - int(quote.quoted_block) > 1:
        reasons.append("BLOCK: post-buy route quote is stale")

    if not firewall.accepted:
        reasons.append("BLOCK: dynamic token firewall failed")
        reasons.extend(firewall.reasons)

    # Current deployed V2 executor uses standard swapExactTokensForTokens.
    # Fee-on-transfer tokens are therefore fail-closed for live execution.
    if firewall.buy_tax_bps is None or firewall.sell_tax_bps is None:
        reasons.append("BLOCK: token tax is not proven")
    elif int(firewall.buy_tax_bps) != 0 or int(firewall.sell_tax_bps) != 0:
        reasons.append("BLOCK: current executor does not support taxed/FOT tokens")

    if not quote.profit.accepted:
        reasons.append("BLOCK: all-cost profitability gate failed")
        reasons.extend(quote.profit.reasons)
    if quote.profit.required_gross_profit_wei is None:
        reasons.append("BLOCK: required gross profit is unknown")

    if not private_paths.accepted or private_paths.public_mempool_fallback_allowed:
        reasons.append("BLOCK: private-only submission gate failed")
    if execution_risk.blocked:
        reasons.append("BLOCK: execution risk/kill switch is active")
        reasons.extend(execution_risk.reasons)

    if executor_paused:
        reasons.append("BLOCK: executor is paused")
    if not owner_matches:
        reasons.append("BLOCK: executor owner does not match signer")
    if not routers_allowlisted:
        reasons.append("BLOCK: route routers are not allowlisted")

    if int(quote.amount_in_wei) <= 0:
        reasons.append("BLOCK: trade amount must be positive")
    if int(quote.amount_in_wei) > int(max_amount_in_wei):
        reasons.append("BLOCK: trade exceeds authorized canary cap")
    if int(allowance_wei) < int(quote.amount_in_wei):
        reasons.append("BLOCK: executor allowance below trade amount")

    unique = tuple(dict.fromkeys(reasons))
    if unique:
        return LivePostBuyAuthorization(False, unique)
    return LivePostBuyAuthorization(
        True,
        ("PASS: confirmed post-buy live authorization gates passed",),
    )


def prepare_dynamic_postbuy_trade(
    w3: Web3,
    *,
    executor_address: str,
    wallet_address: str,
    trigger: ConfirmedLargeBuy,
    firewall: DynamicTokenFirewallDecision,
    quote: ReadOnlyPostBuyQuote,
    private_paths: PrivateSubmissionEvidence,
    execution_risk: ExecutionRiskDecision,
    max_amount_in_wei: int,
    gas_units_buffer_bps: int = 2000,
    gas_price_buffer_bps: int = 2500,
    deadline_seconds: int = 90,
) -> PreparedPostBuyTrade:
    wallet = Web3.to_checksum_address(wallet_address)
    executor = w3.eth.contract(
        address=Web3.to_checksum_address(executor_address), abi=EXECUTOR_ABI
    )
    base = Web3.to_checksum_address(trigger.base_token)
    token = Web3.to_checksum_address(trigger.token)
    buy_router = Web3.to_checksum_address(quote.buy_router)
    sell_router = Web3.to_checksum_address(quote.sell_router)
    current_block = int(w3.eth.block_number)

    owner_matches = Web3.to_checksum_address(executor.functions.owner().call()) == wallet
    paused = bool(executor.functions.paused().call())
    allowlisted = bool(executor.functions.allowedRouters(buy_router).call()) and bool(
        executor.functions.allowedRouters(sell_router).call()
    )
    base_token = w3.eth.contract(address=base, abi=ERC20_ABI)
    allowance = int(base_token.functions.allowance(wallet, executor.address).call())

    auth = evaluate_live_postbuy_authorization(
        trigger=trigger,
        current_block=current_block,
        firewall=firewall,
        quote=quote,
        private_paths=private_paths,
        execution_risk=execution_risk,
        executor_paused=paused,
        owner_matches=owner_matches,
        routers_allowlisted=allowlisted,
        allowance_wei=allowance,
        max_amount_in_wei=int(max_amount_in_wei),
    )
    if not auth.accepted:
        raise RuntimeError("; ".join(auth.reasons))

    latest = w3.eth.get_block("latest")
    deadline = int(latest["timestamp"]) + min(300, max(1, int(deadline_seconds)))
    preliminary_required = int(quote.profit.required_gross_profit_wei or 1)
    fn = executor.functions.executeV2Arbitrage(
        base,
        token,
        buy_router,
        sell_router,
        int(quote.amount_in_wei),
        int(quote.floor_token_out),
        int(quote.floor_final_wei),
        preliminary_required,
        deadline,
    )
    gas_units = int(fn.estimate_gas({"from": wallet}))
    buffered_gas_units = (
        gas_units * (10_000 + int(gas_units_buffer_bps)) + 9_999
    ) // 10_000
    gas_price = int(w3.eth.gas_price)
    max_fee = (
        gas_price * (10_000 + int(gas_price_buffer_bps)) + 9_999
    ) // 10_000

    exact_profit = evaluate_all_cost_profit(
        amount_in_wei=int(quote.amount_in_wei),
        expected_final_wei=int(quote.expected_final_wei),
        floor_final_wei=int(quote.floor_final_wei),
        gas_cost_wei=int(buffered_gas_units * max_fee),
        builder_payment_wei=quote.profit.builder_payment_wei,
        non_embedded_cost_wei=quote.profit.non_embedded_cost_wei,
        dex_fee_cost_wei=None,
        slippage_cost_wei=None,
        token_tax_cost_wei=None,
        safety_buffer_wei=int(quote.profit.safety_buffer_wei),
        min_net_profit_wei=int(quote.profit.min_net_profit_wei),
        route_output_embeds_dex_fees=True,
        floor_output_embeds_slippage=True,
        route_output_embeds_token_tax=True,
        quoted_block=int(quote.quoted_block),
        current_block=current_block,
        max_quote_age_blocks=1,
        raw={"mode": "LIVE_POSTBUY_PREPARE", "trigger_hash": trigger.tx_hash},
    )
    if not exact_profit.accepted or exact_profit.required_gross_profit_wei is None:
        raise RuntimeError("; ".join(exact_profit.reasons))

    fn = executor.functions.executeV2Arbitrage(
        base,
        token,
        buy_router,
        sell_router,
        int(quote.amount_in_wei),
        int(quote.floor_token_out),
        int(quote.floor_final_wei),
        int(exact_profit.required_gross_profit_wei),
        deadline,
    )
    nonce = int(w3.eth.get_transaction_count(wallet, "pending"))
    tx = fn.build_transaction(
        {
            "from": wallet,
            "chainId": int(w3.eth.chain_id),
            "nonce": nonce,
            "gas": int(buffered_gas_units),
            "gasPrice": int(max_fee),
        }
    )
    return PreparedPostBuyTrade(
        trigger_hash=trigger.tx_hash,
        token=token,
        route_id=quote.route_id,
        quoted_block=int(quote.quoted_block),
        current_block=current_block,
        amount_in_wei=int(quote.amount_in_wei),
        gas_units=gas_units,
        buffered_gas_units=buffered_gas_units,
        max_fee_per_gas_wei=max_fee,
        required_gross_profit_wei=int(exact_profit.required_gross_profit_wei),
        profit=exact_profit,
        transaction=tx,
    )


def sign_and_submit_private(
    prepared: PreparedPostBuyTrade,
    *,
    private_key: str,
    expected_wallet: str,
    paths: tuple[PrivatePath, ...] = DEFAULT_BSC_PRIVATE_PATHS,
) -> tuple[str, str]:
    account = Account.from_key(private_key)
    if account.address.lower() != Web3.to_checksum_address(expected_wallet).lower():
        raise RuntimeError("signing key does not match configured execution wallet")
    signed = Account.sign_transaction(prepared.transaction, private_key)
    raw_hex = signed.raw_transaction.hex()
    return submit_private_raw_transaction(raw_hex, paths)


def audit_postbuy_receipt(
    w3: Web3,
    *,
    tx_hash: str,
    executor_address: str,
    token: str,
    ledger: ExecutionLedger,
    builder_payment_wei: int = 0,
    other_cost_wei: int = 0,
    timeout: int = 90,
) -> ExecutionRecord:
    executor = w3.eth.contract(
        address=Web3.to_checksum_address(executor_address), abi=EXECUTOR_ABI
    )
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=int(timeout))
    status = int(receipt.get("status", 0))
    gas_used = int(receipt.get("gasUsed", 0))
    gas_price = int(receipt.get("effectiveGasPrice", receipt.get("gasPrice", 0)))
    gas_paid = gas_used * gas_price
    gross = 0
    if status == 1:
        logs = executor.events.ArbitrageExecuted().process_receipt(receipt)
        if len(logs) != 1:
            raise RuntimeError("successful receipt missing unique ArbitrageExecuted event")
        gross = int(logs[0]["args"]["grossProfit"])
    net = gross - gas_paid - int(builder_payment_wei) - int(other_cost_wei)
    record = ExecutionRecord(
        timestamp=utc_now().isoformat(),
        day=utc_day(),
        tx_hash=tx_hash if status == 1 else None,
        token=Web3.to_checksum_address(token),
        gross_profit_wei=gross,
        gas_paid_wei=gas_paid,
        builder_payment_wei=int(builder_payment_wei),
        other_cost_wei=int(other_cost_wei),
        realized_net_wei=net,
        success=status == 1,
        reverted=status != 1,
        note=f"postbuy_dynamic;block={int(receipt.get('blockNumber', 0))}",
    )
    ledger.append(record)
    return record
