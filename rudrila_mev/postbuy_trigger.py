from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from web3 import Web3


@dataclass(frozen=True)
class SwapSpec:
    signature: str
    native_in: bool
    amount_in_slot: int | None
    path_slot: int
    deadline_slot: int
    amount_is_maximum: bool = False


def _selector(signature: str) -> str:
    return "0x" + Web3.keccak(text=signature)[:4].hex()


_SWAP_SPECS = {
    _selector("swapExactETHForTokens(uint256,address[],address,uint256)"): SwapSpec(
        "swapExactETHForTokens(uint256,address[],address,uint256)", True, None, 1, 3
    ),
    _selector("swapETHForExactTokens(uint256,address[],address,uint256)"): SwapSpec(
        "swapETHForExactTokens(uint256,address[],address,uint256)", True, None, 1, 3, True
    ),
    _selector(
        "swapExactETHForTokensSupportingFeeOnTransferTokens(uint256,address[],address,uint256)"
    ): SwapSpec(
        "swapExactETHForTokensSupportingFeeOnTransferTokens(uint256,address[],address,uint256)",
        True,
        None,
        1,
        3,
    ),
    _selector(
        "swapExactTokensForTokens(uint256,uint256,address[],address,uint256)"
    ): SwapSpec(
        "swapExactTokensForTokens(uint256,uint256,address[],address,uint256)",
        False,
        0,
        2,
        4,
    ),
    _selector(
        "swapTokensForExactTokens(uint256,uint256,address[],address,uint256)"
    ): SwapSpec(
        "swapTokensForExactTokens(uint256,uint256,address[],address,uint256)",
        False,
        1,
        2,
        4,
        True,
    ),
    _selector(
        "swapExactTokensForTokensSupportingFeeOnTransferTokens(uint256,uint256,address[],address,uint256)"
    ): SwapSpec(
        "swapExactTokensForTokensSupportingFeeOnTransferTokens(uint256,uint256,address[],address,uint256)",
        False,
        0,
        2,
        4,
    ),
}


@dataclass(frozen=True)
class PendingLargeBuy:
    tx_hash: str
    router: str
    sender: str
    base_token: str
    token: str
    path: tuple[str, ...]
    amount_in_wei: int
    observed_pending_block: int
    deadline: int | None
    swap_signature: str
    amount_is_maximum: bool
    tx_value_wei: int


@dataclass(frozen=True)
class ConfirmedLargeBuy:
    pending: PendingLargeBuy
    block_number: int
    transaction_index: int
    observed_block: int
    confirmations: int
    receipt_status: int

    @property
    def tx_hash(self) -> str:
        return self.pending.tx_hash

    @property
    def token(self) -> str:
        return self.pending.token

    @property
    def base_token(self) -> str:
        return self.pending.base_token


def _to_int(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, (bytes, bytearray)):
        return int.from_bytes(bytes(value), "big")
    return int(str(value), 0)


def _hex(value: Any) -> str:
    if value is None:
        return "0x"
    if isinstance(value, str):
        return value
    if hasattr(value, "hex"):
        out = value.hex()
        return out if str(out).startswith("0x") else "0x" + str(out)
    return str(value)


def _address(value: Any) -> str:
    return Web3.to_checksum_address(str(value))


def _word(data: bytes, slot: int) -> int:
    start = int(slot) * 32
    end = start + 32
    if start < 0 or end > len(data):
        raise ValueError("calldata word out of bounds")
    return int.from_bytes(data[start:end], "big")


def _decode_address_array(data: bytes, pointer_slot: int) -> tuple[str, ...]:
    offset = _word(data, pointer_slot)
    if offset % 32 != 0 or offset < 0 or offset + 32 > len(data):
        raise ValueError("invalid ABI dynamic-array offset")
    count = int.from_bytes(data[offset : offset + 32], "big")
    if count < 2 or count > 16:
        raise ValueError("invalid swap path length")
    out: list[str] = []
    cursor = offset + 32
    for _ in range(count):
        if cursor + 32 > len(data):
            raise ValueError("truncated swap path")
        out.append(Web3.to_checksum_address("0x" + data[cursor + 12 : cursor + 32].hex()))
        cursor += 32
    return tuple(out)


def decode_pending_large_buy(
    tx: dict[str, Any],
    *,
    supported_routers: Iterable[str],
    wrapped_native: str,
    min_trigger_wei: int,
    observed_pending_block: int,
) -> PendingLargeBuy | None:
    """Decode a pending V2-style WBNB->token buy.

    This function is detection-only. It never creates or submits a transaction.
    Only router calls whose first path token is wrapped_native and whose final
    path token differs from wrapped_native are considered buys.
    """

    router = tx.get("to")
    if not router:
        return None
    try:
        router = _address(router)
        wrapped = _address(wrapped_native)
        allowed = {_address(x) for x in supported_routers}
    except Exception:
        return None
    if router not in allowed:
        return None

    calldata_hex = _hex(tx.get("input") or tx.get("data") or "0x")
    if not calldata_hex.startswith("0x") or len(calldata_hex) < 10:
        return None
    selector = calldata_hex[:10].lower()
    spec = _SWAP_SPECS.get(selector)
    if spec is None:
        return None

    try:
        payload = bytes.fromhex(calldata_hex[10:])
        path = _decode_address_array(payload, spec.path_slot)
        if path[0] != wrapped or path[-1] == wrapped:
            return None
        tx_value = _to_int(tx.get("value"))
        amount_in = tx_value if spec.native_in else _word(payload, int(spec.amount_in_slot))
        if amount_in < int(min_trigger_wei):
            return None
        deadline = _word(payload, spec.deadline_slot)
        sender = _address(tx.get("from"))
        tx_hash = _hex(tx.get("hash"))
        if not tx_hash.startswith("0x") or len(tx_hash) != 66:
            return None
    except Exception:
        return None

    return PendingLargeBuy(
        tx_hash=tx_hash,
        router=router,
        sender=sender,
        base_token=wrapped,
        token=path[-1],
        path=path,
        amount_in_wei=int(amount_in),
        observed_pending_block=int(observed_pending_block),
        deadline=int(deadline),
        swap_signature=spec.signature,
        amount_is_maximum=bool(spec.amount_is_maximum),
        tx_value_wei=int(tx_value),
    )


def confirm_large_buy(
    w3: Web3,
    pending: PendingLargeBuy,
    *,
    required_confirmations: int = 1,
) -> ConfirmedLargeBuy | None:
    """Return confirmation evidence only after the trigger is mined successfully.

    No execution path should be allowed to accept PendingLargeBuy directly.
    """

    need = max(1, int(required_confirmations))
    try:
        receipt = w3.eth.get_transaction_receipt(pending.tx_hash)
    except Exception:
        return None
    if receipt is None:
        return None

    status = _to_int(receipt.get("status"))
    if status != 1:
        return None
    block = _to_int(receipt.get("blockNumber"))
    tx_index = _to_int(receipt.get("transactionIndex"))
    latest = int(w3.eth.block_number)
    confirmations = max(0, latest - block + 1)
    if confirmations < need:
        return None

    return ConfirmedLargeBuy(
        pending=pending,
        block_number=block,
        transaction_index=tx_index,
        observed_block=latest,
        confirmations=confirmations,
        receipt_status=status,
    )


def post_confirmation_gate(
    trigger: ConfirmedLargeBuy | PendingLargeBuy,
    *,
    current_block: int,
) -> tuple[bool, str]:
    if isinstance(trigger, PendingLargeBuy):
        return False, "BLOCK: trigger is still pending; no pre-trigger submission allowed"
    if trigger.receipt_status != 1:
        return False, "BLOCK: trigger receipt was not successful"
    if int(current_block) < int(trigger.block_number):
        return False, "BLOCK: current state predates confirmed trigger"
    return True, "PASS: trigger is confirmed; post-trigger evaluation may begin"
