from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass

from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware


WBNB = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"
PANCAKE_V2_ROUTER = "0x10ED43C718714eb63d5aA57B78B54704E256024E"

ERC20_FORK_ABI = [
    {
        "inputs": [{"internalType": "address", "name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "spender", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"},
        ],
        "name": "approve",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"},
        ],
        "name": "transfer",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]

WBNB_ABI = ERC20_FORK_ABI + [
    {
        "inputs": [],
        "name": "deposit",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function",
    }
]

V2_ROUTER_FORK_ABI = [
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"},
        ],
        "name": "getAmountsOut",
        "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"},
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "deadline", "type": "uint256"},
        ],
        "name": "swapExactTokensForTokensSupportingFeeOnTransferTokens",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]


@dataclass(frozen=True)
class ForkRoundTripResult:
    accepted: bool
    chain_id: int
    block_number: int
    account: str
    base_token: str
    token: str
    router: str
    amount_in_wei: int
    quoted_buy_out_raw: int
    buy_received_raw: int
    buy_tax_bps: int
    transfer_out_passed: bool
    transfer_probe_raw: int
    transfer_received_raw: int
    transfer_tax_bps: int | None
    transfer_gas_used: int | None
    quoted_sell_out_wei: int
    base_received_back_wei: int
    sell_tax_bps: int
    buy_gas_used: int
    sell_gas_used: int
    roundtrip_loss_bps: int
    reason: str


def measure_tax_bps(quoted_amount: int, actual_amount: int) -> int:
    quoted = int(quoted_amount)
    actual = int(actual_amount)
    if quoted <= 0:
        return 10_000
    if actual >= quoted:
        return 0
    return min(10_000, (quoted - max(0, actual)) * 10_000 // quoted)


def evaluate_roundtrip(
    *,
    amount_in_wei: int,
    buy_received_raw: int,
    base_received_back_wei: int,
    max_roundtrip_loss_bps: int,
) -> tuple[bool, int, str]:
    if amount_in_wei <= 0:
        return False, 10_000, "BLOCK: invalid fork simulation input amount"
    if buy_received_raw <= 0:
        return False, 10_000, "BLOCK: fork buy produced zero tokens"
    if base_received_back_wei <= 0:
        return False, 10_000, "BLOCK: fork sell produced zero base token"

    loss = max(0, int(amount_in_wei) - int(base_received_back_wei))
    loss_bps = min(10_000, loss * 10_000 // int(amount_in_wei))
    if loss_bps > int(max_roundtrip_loss_bps):
        return (
            False,
            loss_bps,
            f"BLOCK: fork round-trip loss {loss_bps} bps exceeds limit "
            f"{int(max_roundtrip_loss_bps)} bps",
        )

    return True, loss_bps, "PASS: fork buy->sell round-trip completed within loss limit"


def evaluate_token_behavior(
    *,
    transfer_out_passed: bool,
    buy_tax_bps: int,
    sell_tax_bps: int,
    transfer_tax_bps: int | None,
    max_combined_tax_bps: int,
    max_transfer_tax_bps: int,
) -> tuple[bool, str]:
    if not transfer_out_passed:
        return False, "BLOCK: post-buy transfer-out probe failed"

    if int(buy_tax_bps) + int(sell_tax_bps) > int(max_combined_tax_bps):
        return False, "BLOCK: measured combined buy/sell tax exceeds limit"

    if transfer_tax_bps is None:
        return False, "BLOCK: transfer tax measurement missing"
    if int(transfer_tax_bps) > int(max_transfer_tax_bps):
        return False, "BLOCK: measured transfer tax exceeds limit"

    return True, "PASS: measured taxes and transfer-out behavior within limits"


def _require_code(w3: Web3, label: str, address: str) -> str:
    addr = Web3.to_checksum_address(address)
    if len(w3.eth.get_code(addr)) == 0:
        raise RuntimeError(f"{label} has no contract code: {addr}")
    return addr


def _snapshot(w3: Web3) -> str:
    response = w3.provider.make_request("evm_snapshot", [])
    snap = response.get("result") if isinstance(response, dict) else None
    if not isinstance(snap, str) or not snap:
        raise RuntimeError("Fork RPC does not support evm_snapshot")
    return snap


def _revert_snapshot(w3: Web3, snapshot_id: str) -> None:
    response = w3.provider.make_request("evm_revert", [snapshot_id])
    ok = response.get("result") if isinstance(response, dict) else None
    if ok is not True:
        raise RuntimeError("Fork RPC failed evm_revert")


def simulate_v2_roundtrip(
    *,
    local_rpc_url: str,
    token: str,
    amount_in_wei: int,
    router: str = PANCAKE_V2_ROUTER,
    base_token: str = WBNB,
    max_roundtrip_loss_bps: int = 1200,
    max_combined_tax_bps: int = 800,
    max_transfer_tax_bps: int = 800,
    timeout_seconds: int = 20,
) -> ForkRoundTripResult:
    w3 = Web3(
        Web3.HTTPProvider(
            local_rpc_url,
            request_kwargs={"timeout": int(timeout_seconds)},
        )
    )
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

    if not w3.is_connected():
        raise RuntimeError("Local fork RPC is not connected")

    chain_id = int(w3.eth.chain_id)
    if chain_id != 56:
        raise RuntimeError(f"Fork chain ID mismatch: expected 56, got {chain_id}")

    accounts = list(w3.eth.accounts)
    if len(accounts) < 2:
        raise RuntimeError("Fork RPC needs at least two unlocked local test accounts")
    account = Web3.to_checksum_address(accounts[0])
    transfer_recipient = Web3.to_checksum_address(accounts[1])

    base = _require_code(w3, "base token", base_token)
    quote = _require_code(w3, "token", token)
    router_addr = _require_code(w3, "router", router)

    if base == quote:
        raise RuntimeError("Base token and token must differ")

    base_contract = w3.eth.contract(address=base, abi=WBNB_ABI)
    token_contract = w3.eth.contract(address=quote, abi=ERC20_FORK_ABI)
    router_contract = w3.eth.contract(address=router_addr, abi=V2_ROUTER_FORK_ABI)

    wrap_tx = base_contract.functions.deposit().transact(
        {"from": account, "value": int(amount_in_wei)}
    )
    wrap_receipt = w3.eth.wait_for_transaction_receipt(wrap_tx, timeout=timeout_seconds)
    if int(wrap_receipt.status) != 1:
        raise RuntimeError("Fork WBNB deposit reverted")

    approve_buy = base_contract.functions.approve(router_addr, int(amount_in_wei)).transact(
        {"from": account}
    )
    approve_buy_receipt = w3.eth.wait_for_transaction_receipt(
        approve_buy, timeout=timeout_seconds
    )
    if int(approve_buy_receipt.status) != 1:
        raise RuntimeError("Fork WBNB approval reverted")

    block_number = int(w3.eth.block_number)
    buy_quote = router_contract.functions.getAmountsOut(
        int(amount_in_wei), [base, quote]
    ).call()
    quoted_buy_out = int(buy_quote[-1]) if len(buy_quote) >= 2 else 0
    if quoted_buy_out <= 0:
        raise RuntimeError("Fork router returned invalid buy quote")

    token_before = int(token_contract.functions.balanceOf(account).call())
    deadline = int(time.time()) + 600

    buy_tx = router_contract.functions.swapExactTokensForTokensSupportingFeeOnTransferTokens(
        int(amount_in_wei),
        1,
        [base, quote],
        account,
        deadline,
    ).transact({"from": account})
    buy_receipt = w3.eth.wait_for_transaction_receipt(buy_tx, timeout=timeout_seconds)
    if int(buy_receipt.status) != 1:
        raise RuntimeError("Fork buy transaction reverted")

    token_after = int(token_contract.functions.balanceOf(account).call())
    buy_received = token_after - token_before
    if buy_received <= 0:
        raise RuntimeError("Fork buy completed but token balance did not increase")

    buy_tax_bps = measure_tax_bps(quoted_buy_out, buy_received)

    transfer_snapshot = _snapshot(w3)
    transfer_probe = max(1, int(buy_received) // 100)
    transfer_received = 0
    transfer_gas_used: int | None = None
    transfer_tax_bps: int | None = None
    transfer_out_passed = False

    try:
        recipient_before = int(
            token_contract.functions.balanceOf(transfer_recipient).call()
        )
        transfer_tx = token_contract.functions.transfer(
            transfer_recipient, transfer_probe
        ).transact({"from": account})
        transfer_receipt = w3.eth.wait_for_transaction_receipt(
            transfer_tx, timeout=timeout_seconds
        )
        if int(transfer_receipt.status) == 1:
            recipient_after = int(
                token_contract.functions.balanceOf(transfer_recipient).call()
            )
            transfer_received = max(0, recipient_after - recipient_before)
            transfer_gas_used = int(transfer_receipt.gasUsed)
            transfer_tax_bps = measure_tax_bps(transfer_probe, transfer_received)
            transfer_out_passed = transfer_received > 0
    except Exception:
        transfer_out_passed = False
    finally:
        _revert_snapshot(w3, transfer_snapshot)

    sell_quote = router_contract.functions.getAmountsOut(
        int(buy_received), [quote, base]
    ).call()
    quoted_sell_out = int(sell_quote[-1]) if len(sell_quote) >= 2 else 0
    if quoted_sell_out <= 0:
        raise RuntimeError("Fork router returned invalid sell quote")

    approve_sell = token_contract.functions.approve(router_addr, int(buy_received)).transact(
        {"from": account}
    )
    approve_sell_receipt = w3.eth.wait_for_transaction_receipt(
        approve_sell, timeout=timeout_seconds
    )
    if int(approve_sell_receipt.status) != 1:
        raise RuntimeError("Fork token approval reverted")

    base_before_sell = int(base_contract.functions.balanceOf(account).call())
    sell_tx = router_contract.functions.swapExactTokensForTokensSupportingFeeOnTransferTokens(
        int(buy_received),
        1,
        [quote, base],
        account,
        deadline,
    ).transact({"from": account})
    sell_receipt = w3.eth.wait_for_transaction_receipt(sell_tx, timeout=timeout_seconds)
    if int(sell_receipt.status) != 1:
        raise RuntimeError("Fork sell transaction reverted")

    base_after_sell = int(base_contract.functions.balanceOf(account).call())
    base_received_back = base_after_sell - base_before_sell
    sell_tax_bps = measure_tax_bps(quoted_sell_out, base_received_back)

    roundtrip_ok, loss_bps, roundtrip_reason = evaluate_roundtrip(
        amount_in_wei=int(amount_in_wei),
        buy_received_raw=int(buy_received),
        base_received_back_wei=int(base_received_back),
        max_roundtrip_loss_bps=int(max_roundtrip_loss_bps),
    )
    behavior_ok, behavior_reason = evaluate_token_behavior(
        transfer_out_passed=transfer_out_passed,
        buy_tax_bps=buy_tax_bps,
        sell_tax_bps=sell_tax_bps,
        transfer_tax_bps=transfer_tax_bps,
        max_combined_tax_bps=int(max_combined_tax_bps),
        max_transfer_tax_bps=int(max_transfer_tax_bps),
    )

    accepted = roundtrip_ok and behavior_ok
    reason = (
        "PASS: fork buy/sell, tax measurement and transfer-out safety passed"
        if accepted
        else "; ".join(
            reason
            for ok, reason in (
                (roundtrip_ok, roundtrip_reason),
                (behavior_ok, behavior_reason),
            )
            if not ok
        )
    )

    return ForkRoundTripResult(
        accepted=accepted,
        chain_id=chain_id,
        block_number=block_number,
        account=account,
        base_token=base,
        token=quote,
        router=router_addr,
        amount_in_wei=int(amount_in_wei),
        quoted_buy_out_raw=int(quoted_buy_out),
        buy_received_raw=int(buy_received),
        buy_tax_bps=int(buy_tax_bps),
        transfer_out_passed=bool(transfer_out_passed),
        transfer_probe_raw=int(transfer_probe),
        transfer_received_raw=int(transfer_received),
        transfer_tax_bps=(
            int(transfer_tax_bps) if transfer_tax_bps is not None else None
        ),
        transfer_gas_used=(
            int(transfer_gas_used) if transfer_gas_used is not None else None
        ),
        quoted_sell_out_wei=int(quoted_sell_out),
        base_received_back_wei=int(base_received_back),
        sell_tax_bps=int(sell_tax_bps),
        buy_gas_used=int(buy_receipt.gasUsed),
        sell_gas_used=int(sell_receipt.gasUsed),
        roundtrip_loss_bps=int(loss_bps),
        reason=reason,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="RUDRILA BSC fork token-behavior simulator")
    parser.add_argument("--rpc", default="http://127.0.0.1:8545")
    parser.add_argument("--token", required=True)
    parser.add_argument("--amount-wei", type=int, default=10_000_000_000_000_000)
    parser.add_argument("--max-loss-bps", type=int, default=1200)
    parser.add_argument("--max-tax-bps", type=int, default=800)
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    result = simulate_v2_roundtrip(
        local_rpc_url=args.rpc,
        token=args.token,
        amount_in_wei=args.amount_wei,
        max_roundtrip_loss_bps=args.max_loss_bps,
        max_combined_tax_bps=args.max_tax_bps,
        max_transfer_tax_bps=args.max_tax_bps,
    )
    payload = asdict(result)
    print(json.dumps(payload, sort_keys=True))
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
            fh.write("\n")
    return 0 if result.accepted else 2


if __name__ == "__main__":
    raise SystemExit(main())
