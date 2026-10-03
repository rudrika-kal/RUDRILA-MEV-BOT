from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

from web3 import Web3


ZERO = Web3.to_checksum_address("0x0000000000000000000000000000000000000000")
DEAD = Web3.to_checksum_address("0x000000000000000000000000000000000000dEaD")
TRANSFER_TOPIC = Web3.keccak(text="Transfer(address,address,uint256)").hex()

# Official UNCX Network V2 locker on BNB Chain (UNCX developer contract table).
# The locker exposes tokenLocks(lpToken,index), so we count only locks whose unlock timestamp
# is still safely in the future instead of blindly trusting the locker balance.
UNCX_V2_BSC_LOCKER = Web3.to_checksum_address(
    "0xc765bddb93b0d1c1a88282ba0fa6b2d00e3e0c83"
)

UNCX_V2_LOCKER_ABI = [
    {
        "inputs": [{"internalType": "address", "name": "_lpToken", "type": "address"}],
        "name": "getNumLocksForToken",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "", "type": "address"},
            {"internalType": "uint256", "name": "", "type": "uint256"},
        ],
        "name": "tokenLocks",
        "outputs": [
            {"internalType": "uint256", "name": "lockDate", "type": "uint256"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"},
            {"internalType": "uint256", "name": "initialAmount", "type": "uint256"},
            {"internalType": "uint256", "name": "unlockDate", "type": "uint256"},
            {"internalType": "uint256", "name": "lockID", "type": "uint256"},
            {"internalType": "address", "name": "owner", "type": "address"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
]

V2_LP_ABI = [
    {
        "inputs": [],
        "name": "totalSupply",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "address", "name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]

V3_NPM_ABI = [
    {
        "inputs": [{"internalType": "uint256", "name": "tokenId", "type": "uint256"}],
        "name": "ownerOf",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "uint256", "name": "tokenId", "type": "uint256"}],
        "name": "positions",
        "outputs": [
            {"internalType": "uint96", "name": "nonce", "type": "uint96"},
            {"internalType": "address", "name": "operator", "type": "address"},
            {"internalType": "address", "name": "token0", "type": "address"},
            {"internalType": "address", "name": "token1", "type": "address"},
            {"internalType": "uint24", "name": "fee", "type": "uint24"},
            {"internalType": "int24", "name": "tickLower", "type": "int24"},
            {"internalType": "int24", "name": "tickUpper", "type": "int24"},
            {"internalType": "uint128", "name": "liquidity", "type": "uint128"},
            {"internalType": "uint256", "name": "feeGrowthInside0LastX128", "type": "uint256"},
            {"internalType": "uint256", "name": "feeGrowthInside1LastX128", "type": "uint256"},
            {"internalType": "uint128", "name": "tokensOwed0", "type": "uint128"},
            {"internalType": "uint128", "name": "tokensOwed1", "type": "uint128"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
]


@dataclass(frozen=True)
class LiquiditySafetyEvidence:
    accepted: bool
    dex: str
    subject: str
    lock_or_burn_proven: bool | None
    liquidity_removal_controlled_by_creator: bool | None
    secured_bps: int | None
    removable_bps: int | None
    unknown_bps: int | None
    total_units: int
    secured_units: int
    removable_units: int
    unknown_units: int
    observed_from_block: int | None
    observed_to_block: int | None
    holder_or_position_count: int
    reasons: tuple[str, ...]
    raw: dict

    def as_dict(self) -> dict:
        return asdict(self)


def _bps(part: int, total: int) -> int | None:
    if int(total) <= 0:
        return None
    return min(10_000, max(0, int(part)) * 10_000 // int(total))


def _addr(value: str) -> str:
    return Web3.to_checksum_address(value)


def _topic_address(topic) -> str:
    hx = topic.hex() if hasattr(topic, "hex") else str(topic)
    hx = hx[2:] if hx.startswith("0x") else hx
    return Web3.to_checksum_address("0x" + hx[-40:])


def _topic_uint(topic) -> int:
    hx = topic.hex() if hasattr(topic, "hex") else str(topic)
    return int(hx, 16)


def _log_data_uint(data) -> int:
    if isinstance(data, (bytes, bytearray)):
        return int.from_bytes(bytes(data), "big")
    hx = data.hex() if hasattr(data, "hex") else str(data)
    hx = hx[2:] if hx.startswith("0x") else hx
    return int(hx or "0", 16)


def _chunked_logs(
    w3: Web3,
    *,
    address: str,
    from_block: int,
    to_block: int,
    topics: list | None = None,
    chunk_size: int = 50,
) -> list:
    out = []
    start = int(from_block)
    end_all = int(to_block)
    while start <= end_all:
        end = min(end_all, start + int(chunk_size) - 1)
        query = {
            "fromBlock": start,
            "toBlock": end,
            "address": _addr(address),
        }
        if topics is not None:
            query["topics"] = topics
        out.extend(w3.eth.get_logs(query))
        start = end + 1
    return out


def classify_liquidity_units(
    *,
    dex: str,
    subject: str,
    total_units: int,
    secured_units: int,
    removable_units: int,
    unknown_units: int,
    holder_or_position_count: int,
    observed_from_block: int | None,
    observed_to_block: int | None,
    min_secured_bps: int = 9500,
    max_removable_bps: int = 0,
    raw: dict | None = None,
) -> LiquiditySafetyEvidence:
    total = int(total_units)
    secured = max(0, int(secured_units))
    removable = max(0, int(removable_units))
    unknown = max(0, int(unknown_units))
    reasons: list[str] = []

    if total <= 0:
        reasons.append("BLOCK: no active liquidity units were proven")
        secured_bps = removable_bps = unknown_bps = None
    else:
        secured_bps = _bps(secured, total)
        removable_bps = _bps(removable, total)
        unknown_bps = _bps(unknown, total)

        if secured_bps is None or secured_bps < int(min_secured_bps):
            reasons.append(
                f"BLOCK: secured liquidity {secured_bps} bps below required "
                f"{int(min_secured_bps)} bps"
            )
        if removable_bps is None or removable_bps > int(max_removable_bps):
            reasons.append(
                f"BLOCK: creator/provider-removable liquidity {removable_bps} bps"
            )
        if unknown > 0:
            reasons.append(
                f"BLOCK: {unknown} liquidity units have unknown holder control"
            )

    lock_or_burn = (
        total > 0
        and secured_bps is not None
        and secured_bps >= int(min_secured_bps)
        and unknown == 0
    )
    creator_control = (
        True
        if removable > 0
        else False
        if total > 0 and unknown == 0
        else None
    )

    accepted = not reasons
    if accepted:
        reasons.append("PASS: liquidity ownership is sufficiently burned/verified-locked")

    return LiquiditySafetyEvidence(
        accepted=accepted,
        dex=str(dex),
        subject=_addr(subject),
        lock_or_burn_proven=bool(lock_or_burn),
        liquidity_removal_controlled_by_creator=creator_control,
        secured_bps=secured_bps,
        removable_bps=removable_bps,
        unknown_bps=unknown_bps,
        total_units=total,
        secured_units=secured,
        removable_units=removable,
        unknown_units=unknown,
        observed_from_block=(
            int(observed_from_block) if observed_from_block is not None else None
        ),
        observed_to_block=(
            int(observed_to_block) if observed_to_block is not None else None
        ),
        holder_or_position_count=int(holder_or_position_count),
        reasons=tuple(reasons),
        raw=dict(raw or {}),
    )


def collect_uncx_v2_active_locks(
    w3: Web3,
    *,
    pair: str,
    locker: str = UNCX_V2_BSC_LOCKER,
    min_unlock_horizon_seconds: int = 300,
    max_locks: int = 128,
) -> dict:
    """Read active UNCX V2 locks for an LP token without trusting expired locks."""
    pair_addr = _addr(pair)
    locker_addr = _addr(locker)
    c = w3.eth.contract(address=locker_addr, abi=UNCX_V2_LOCKER_ABI)
    count = int(c.functions.getNumLocksForToken(pair_addr).call())
    if count < 0 or count > int(max_locks):
        return {
            "accepted": False,
            "locker": locker_addr,
            "lock_count": count,
            "active_locked_units": 0,
            "reason": "BLOCK: UNCX lock count exceeds safe enumeration limit",
            "locks": [],
        }

    latest = w3.eth.get_block("latest")
    now_ts = int(latest["timestamp"])
    required_until = now_ts + max(0, int(min_unlock_horizon_seconds))
    active = 0
    rows = []
    for index in range(count):
        try:
            row = c.functions.tokenLocks(pair_addr, index).call()
        except Exception as exc:
            return {
                "accepted": False,
                "locker": locker_addr,
                "lock_count": count,
                "active_locked_units": 0,
                "reason": f"BLOCK: UNCX lock read failed at index {index}: {type(exc).__name__}",
                "locks": rows,
            }
        if len(row) < 6:
            return {
                "accepted": False,
                "locker": locker_addr,
                "lock_count": count,
                "active_locked_units": 0,
                "reason": "BLOCK: malformed UNCX lock record",
                "locks": rows,
            }
        lock_date, amount, initial_amount, unlock_date, lock_id, owner = row[:6]
        amount = int(amount)
        unlock_date = int(unlock_date)
        still_locked = amount > 0 and unlock_date > required_until
        if still_locked:
            active += amount
        rows.append(
            {
                "index": index,
                "lock_date": int(lock_date),
                "amount": amount,
                "initial_amount": int(initial_amount),
                "unlock_date": unlock_date,
                "lock_id": int(lock_id),
                "owner": _addr(owner),
                "active_beyond_horizon": still_locked,
            }
        )

    return {
        "accepted": True,
        "locker": locker_addr,
        "lock_count": count,
        "active_locked_units": int(active),
        "required_unlock_after": int(required_until),
        "reason": "PASS: UNCX V2 active locks enumerated",
        "locks": rows,
    }


def collect_v2_liquidity_safety(
    w3: Web3,
    *,
    pair: str,
    from_block: int,
    to_block: int,
    verified_safe_holders: Iterable[str] = (),
    min_secured_bps: int = 9500,
    max_removable_bps: int = 0,
    max_holders: int = 250,
) -> LiquiditySafetyEvidence:
    pair_addr = _addr(pair)
    safe = {_addr(ZERO), _addr(DEAD)}
    safe.update(_addr(x) for x in verified_safe_holders)

    if int(from_block) > int(to_block):
        return classify_liquidity_units(
            dex="V2",
            subject=pair_addr,
            total_units=0,
            secured_units=0,
            removable_units=0,
            unknown_units=0,
            holder_or_position_count=0,
            observed_from_block=from_block,
            observed_to_block=to_block,
            min_secured_bps=min_secured_bps,
            max_removable_bps=max_removable_bps,
            raw={"error": "invalid block range"},
        )

    pair_c = w3.eth.contract(address=pair_addr, abi=V2_LP_ABI)
    total_supply = int(pair_c.functions.totalSupply().call())
    if total_supply <= 0:
        return classify_liquidity_units(
            dex="V2",
            subject=pair_addr,
            total_units=0,
            secured_units=0,
            removable_units=0,
            unknown_units=0,
            holder_or_position_count=0,
            observed_from_block=from_block,
            observed_to_block=to_block,
            min_secured_bps=min_secured_bps,
            max_removable_bps=max_removable_bps,
            raw={"total_supply": total_supply},
        )

    logs = _chunked_logs(
        w3,
        address=pair_addr,
        from_block=from_block,
        to_block=to_block,
        topics=[TRANSFER_TOPIC],
    )

    discovered = set(safe)
    for log in logs:
        topics = log.get("topics", [])
        if len(topics) < 3:
            continue
        frm = _topic_address(topics[1])
        to = _topic_address(topics[2])
        if frm != ZERO:
            discovered.add(frm)
        if to != ZERO:
            discovered.add(to)
        if len(discovered) > int(max_holders):
            return LiquiditySafetyEvidence(
                accepted=False,
                dex="V2",
                subject=pair_addr,
                lock_or_burn_proven=None,
                liquidity_removal_controlled_by_creator=None,
                secured_bps=None,
                removable_bps=None,
                unknown_bps=None,
                total_units=total_supply,
                secured_units=0,
                removable_units=0,
                unknown_units=total_supply,
                observed_from_block=int(from_block),
                observed_to_block=int(to_block),
                holder_or_position_count=len(discovered),
                reasons=("BLOCK: LP holder set exceeded safe enumeration limit",),
                raw={"holder_limit": int(max_holders), "transfer_logs": len(logs)},
            )

    balances = {}
    secured = removable = unknown = 0
    active_holders = 0

    for holder in sorted(discovered):
        try:
            bal = int(pair_c.functions.balanceOf(holder).call())
        except Exception:
            bal = 0
        if bal <= 0:
            continue
        balances[holder] = bal
        active_holders += 1
        if holder in safe:
            secured += bal
            continue
        try:
            code = bytes(w3.eth.get_code(holder))
        except Exception:
            code = b"\x01"
        if len(code) == 0:
            removable += bal
        else:
            unknown += bal

    accounted = secured + removable + unknown
    if accounted < total_supply:
        unknown += total_supply - accounted
    elif accounted > total_supply:
        return LiquiditySafetyEvidence(
            accepted=False,
            dex="V2",
            subject=pair_addr,
            lock_or_burn_proven=None,
            liquidity_removal_controlled_by_creator=None,
            secured_bps=None,
            removable_bps=None,
            unknown_bps=None,
            total_units=total_supply,
            secured_units=secured,
            removable_units=removable,
            unknown_units=unknown,
            observed_from_block=int(from_block),
            observed_to_block=int(to_block),
            holder_or_position_count=active_holders,
            reasons=("BLOCK: LP accounting exceeded total supply",),
            raw={"accounted": accounted, "total_supply": total_supply},
        )

    return classify_liquidity_units(
        dex="V2",
        subject=pair_addr,
        total_units=total_supply,
        secured_units=secured,
        removable_units=removable,
        unknown_units=unknown,
        holder_or_position_count=active_holders,
        observed_from_block=from_block,
        observed_to_block=to_block,
        min_secured_bps=min_secured_bps,
        max_removable_bps=max_removable_bps,
        raw={
            "total_supply": total_supply,
            "transfer_logs": len(logs),
            "active_balances": balances,
            "verified_safe_holders": sorted(safe),
        },
    )


def collect_v3_positions_by_ids(
    w3: Web3,
    *,
    position_manager: str,
    token_ids: Iterable[int],
    verified_safe_owners: Iterable[str] = (),
    min_secured_bps: int = 10_000,
    max_removable_bps: int = 0,
    expected_token0: str | None = None,
    expected_token1: str | None = None,
    expected_fee: int | None = None,
    observed_from_block: int | None = None,
    observed_to_block: int | None = None,
) -> LiquiditySafetyEvidence:
    npm_addr = _addr(position_manager)
    safe = {_addr(DEAD)}
    safe.update(_addr(x) for x in verified_safe_owners)
    npm = w3.eth.contract(address=npm_addr, abi=V3_NPM_ABI)

    expected_pair = None
    if expected_token0 and expected_token1:
        expected_pair = {_addr(expected_token0), _addr(expected_token1)}

    positions = []
    total = secured = removable = unknown = 0

    for token_id in sorted({int(x) for x in token_ids}):
        try:
            p = npm.functions.positions(token_id).call()
        except Exception:
            continue
        if len(p) < 8:
            continue

        token0 = _addr(p[2])
        token1 = _addr(p[3])
        fee = int(p[4])
        liquidity = int(p[7])
        if liquidity <= 0:
            continue

        if expected_pair is not None and {token0, token1} != expected_pair:
            continue
        if expected_fee is not None and fee != int(expected_fee):
            continue

        try:
            owner = _addr(npm.functions.ownerOf(token_id).call())
        except Exception:
            unknown += liquidity
            total += liquidity
            positions.append(
                {
                    "token_id": token_id,
                    "owner": None,
                    "liquidity": liquidity,
                    "token0": token0,
                    "token1": token1,
                    "fee": fee,
                    "classification": "unknown",
                }
            )
            continue

        total += liquidity
        if owner in safe:
            secured += liquidity
            cls = "secured"
        else:
            try:
                code = bytes(w3.eth.get_code(owner))
            except Exception:
                code = b"\x01"
            if len(code) == 0:
                removable += liquidity
                cls = "removable_eoa"
            else:
                unknown += liquidity
                cls = "unknown_contract"

        positions.append(
            {
                "token_id": token_id,
                "owner": owner,
                "liquidity": liquidity,
                "token0": token0,
                "token1": token1,
                "fee": fee,
                "classification": cls,
            }
        )

    return classify_liquidity_units(
        dex="V3",
        subject=npm_addr,
        total_units=total,
        secured_units=secured,
        removable_units=removable,
        unknown_units=unknown,
        holder_or_position_count=len(positions),
        observed_from_block=observed_from_block,
        observed_to_block=observed_to_block,
        min_secured_bps=min_secured_bps,
        max_removable_bps=max_removable_bps,
        raw={
            "position_manager": npm_addr,
            "positions": positions,
            "verified_safe_owners": sorted(safe),
        },
    )


def discover_and_collect_v3_liquidity_safety(
    w3: Web3,
    *,
    position_manager: str,
    token0: str,
    token1: str,
    fee: int,
    from_block: int,
    to_block: int,
    verified_safe_owners: Iterable[str] = (),
    min_secured_bps: int = 10_000,
    max_removable_bps: int = 0,
    max_minted_positions: int = 250,
) -> LiquiditySafetyEvidence:
    npm_addr = _addr(position_manager)
    zero_topic = "0x" + ("0" * 64)
    logs = _chunked_logs(
        w3,
        address=npm_addr,
        from_block=from_block,
        to_block=to_block,
        topics=[TRANSFER_TOPIC, zero_topic],
    )

    token_ids = []
    for log in logs:
        topics = log.get("topics", [])
        if len(topics) < 4:
            continue
        token_ids.append(_topic_uint(topics[3]))
        if len(token_ids) > int(max_minted_positions):
            return LiquiditySafetyEvidence(
                accepted=False,
                dex="V3",
                subject=npm_addr,
                lock_or_burn_proven=None,
                liquidity_removal_controlled_by_creator=None,
                secured_bps=None,
                removable_bps=None,
                unknown_bps=None,
                total_units=0,
                secured_units=0,
                removable_units=0,
                unknown_units=0,
                observed_from_block=int(from_block),
                observed_to_block=int(to_block),
                holder_or_position_count=len(token_ids),
                reasons=("BLOCK: V3 minted-position set exceeded safe enumeration limit",),
                raw={"position_limit": int(max_minted_positions)},
            )

    return collect_v3_positions_by_ids(
        w3,
        position_manager=npm_addr,
        token_ids=token_ids,
        verified_safe_owners=verified_safe_owners,
        min_secured_bps=min_secured_bps,
        max_removable_bps=max_removable_bps,
        expected_token0=token0,
        expected_token1=token1,
        expected_fee=fee,
        observed_from_block=from_block,
        observed_to_block=to_block,
    )
