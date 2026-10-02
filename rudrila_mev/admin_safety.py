from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from web3 import Web3

ZERO = Web3.to_checksum_address("0x0000000000000000000000000000000000000000")
EIP1967_IMPL_SLOT = int("360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc", 16)
EIP1967_BEACON_SLOT = int("a3f0ad74e5423aebfd80d3ef4346578335a9a72aeaee59ff6cb3582b35133d50", 16)

CAPABILITY_SIGNATURES = {
    "mint": ("mint(address,uint256)", "mint(uint256)", "_mint(address,uint256)"),
    "blacklist": ("blacklist(address)", "addBlacklist(address)", "setBlacklist(address,bool)", "setBlacklisted(address,bool)", "setBot(address,bool)", "setBots(address[],bool)"),
    "pause": ("pause()", "unpause()", "setTradingEnabled(bool)", "enableTrading()", "openTrading()", "setTrading(bool)"),
    "fees": ("setFee(uint256)", "setFees(uint256,uint256)", "setTax(uint256)", "setBuyTax(uint256)", "setSellTax(uint256)", "setTaxFeePercent(uint256)", "setMarketingFee(uint256)"),
    "limits": ("setMaxTxAmount(uint256)", "setMaxTransactionAmount(uint256)", "setMaxWalletSize(uint256)", "setMaxWalletAmount(uint256)", "setLimits(uint256,uint256)", "removeLimits()"),
    "upgrade": ("upgradeTo(address)", "upgradeToAndCall(address,bytes)", "changeAdmin(address)"),
}
ADMIN_READ_SIGNATURES = (("owner()", "owner"), ("getOwner()", "getOwner"), ("admin()", "admin"))

@dataclass(frozen=True)
class AdminSafetyEvidence:
    accepted: bool
    token: str
    bytecode_present: bool
    owner: str | None
    admin: str | None
    admin_read_resolved: bool
    is_proxy: bool | None
    proxy_kind: str | None
    implementation: str | None
    implementation_checked: bool
    can_mint: bool | None
    can_blacklist: bool | None
    can_pause_trading: bool | None
    can_change_fees: bool | None
    can_change_max_tx_or_wallet: bool | None
    admin_safety_proven: bool
    reasons: tuple[str, ...]
    raw: dict[str, Any]
    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

def _selector(signature: str) -> bytes:
    return bytes(Web3.keccak(text=signature)[:4])

def selector_hits(code: bytes) -> dict[str, list[str]]:
    return {key: [sig for sig in sigs if _selector(sig) in code] for key, sigs in CAPABILITY_SIGNATURES.items()}

def classify_admin_evidence(*, token: str, bytecode_present: bool, owner: str | None, admin: str | None, admin_read_resolved: bool, is_proxy: bool | None, proxy_kind: str | None, implementation: str | None, implementation_checked: bool, hits: dict[str, list[str]], raw: dict[str, Any] | None = None) -> AdminSafetyEvidence:
    token = Web3.to_checksum_address(token)
    reasons: list[str] = []
    def has(name: str) -> bool:
        return bool(hits.get(name, []))
    nonzero_admins = []
    for value in (owner, admin):
        if value:
            value = Web3.to_checksum_address(value)
            if value != ZERO and value not in nonzero_admins:
                nonzero_admins.append(value)
    if not bytecode_present:
        reasons.append("BLOCK: token bytecode missing")
    if not admin_read_resolved:
        reasons.append("BLOCK: owner/admin authority cannot be proven absent")
    if nonzero_admins:
        reasons.append("BLOCK: non-zero owner/admin authority detected")
    if has("mint"):
        reasons.append("BLOCK: privileged mint capability selector detected")
    if has("blacklist"):
        reasons.append("BLOCK: blacklist/bot-control selector detected")
    if has("pause"):
        reasons.append("BLOCK: trading pause/enable capability selector detected")
    if has("fees"):
        reasons.append("BLOCK: mutable fee capability selector detected")
    if has("limits"):
        reasons.append("BLOCK: mutable max-tx/max-wallet capability selector detected")
    if is_proxy is None:
        reasons.append("BLOCK: proxy status unresolved")
    elif is_proxy:
        if not implementation_checked:
            reasons.append("BLOCK: proxy implementation not verified")
        else:
            reasons.append("BLOCK: upgradeable/proxy token remains disallowed")
    if has("upgrade") and is_proxy is not True:
        reasons.append("BLOCK: upgrade/admin selector detected")
    safe = not reasons
    if safe:
        reasons.append("PASS: admin read resolved to zero/no-admin, no blocked capability selectors, and proxy status verified non-proxy")
    return AdminSafetyEvidence(
        accepted=safe, token=token, bytecode_present=bool(bytecode_present),
        owner=Web3.to_checksum_address(owner) if owner else None,
        admin=Web3.to_checksum_address(admin) if admin else None,
        admin_read_resolved=bool(admin_read_resolved), is_proxy=is_proxy,
        proxy_kind=proxy_kind,
        implementation=Web3.to_checksum_address(implementation) if implementation else None,
        implementation_checked=bool(implementation_checked),
        can_mint=has("mint"), can_blacklist=has("blacklist"),
        can_pause_trading=has("pause"), can_change_fees=has("fees"),
        can_change_max_tx_or_wallet=has("limits"), admin_safety_proven=safe,
        reasons=tuple(reasons), raw=dict(raw or {}),
    )

def _call_address(w3: Web3, token: str, signature: str) -> tuple[bool, str | None]:
    try:
        data = "0x" + _selector(signature).hex()
        out = bytes(w3.eth.call({"to": token, "data": data}))
        if len(out) < 32:
            return False, None
        return True, Web3.to_checksum_address("0x" + out[-20:].hex())
    except Exception:
        return False, None

def _storage_address(w3: Web3, token: str, slot: int) -> tuple[bool, str | None]:
    try:
        raw = bytes(w3.eth.get_storage_at(token, slot))
        if len(raw) != 32:
            return False, None
        addr = "0x" + raw[-20:].hex()
        if int(addr, 16) == 0:
            return True, None
        return True, Web3.to_checksum_address(addr)
    except Exception:
        return False, None

def _minimal_proxy_implementation(code: bytes) -> str | None:
    prefix = bytes.fromhex("363d3d373d3d3d363d73")
    suffix = bytes.fromhex("5af43d82803e903d91602b57fd5bf3")
    idx = code.find(prefix)
    if idx >= 0:
        start = idx + len(prefix)
        if len(code) >= start + 20 + len(suffix):
            impl = code[start:start+20]
            if code[start+20:start+20+len(suffix)] == suffix:
                return Web3.to_checksum_address("0x" + impl.hex())
    return None

def collect_admin_safety(w3: Web3, token: str) -> AdminSafetyEvidence:
    token = Web3.to_checksum_address(token)
    code = bytes(w3.eth.get_code(token))
    if not code:
        return classify_admin_evidence(
            token=token, bytecode_present=False, owner=None, admin=None,
            admin_read_resolved=False, is_proxy=None, proxy_kind=None,
            implementation=None, implementation_checked=False,
            hits={k: [] for k in CAPABILITY_SIGNATURES}, raw={},
        )
    reads: dict[str, dict[str, Any]] = {}
    owner = None
    admin = None
    resolved_any = False
    for sig, label in ADMIN_READ_SIGNATURES:
        ok, value = _call_address(w3, token, sig)
        reads[label] = {"resolved": ok, "value": value}
        if ok:
            resolved_any = True
            if label in ("owner", "getOwner") and owner is None:
                owner = value
            if label == "admin":
                admin = value
    impl_slot_ok, impl = _storage_address(w3, token, EIP1967_IMPL_SLOT)
    beacon_slot_ok, beacon = _storage_address(w3, token, EIP1967_BEACON_SLOT)
    minimal_impl = _minimal_proxy_implementation(code)
    proxy_kind = None
    implementation = None
    if impl:
        proxy_kind = "EIP1967_IMPLEMENTATION"
        implementation = impl
    elif beacon:
        proxy_kind = "EIP1967_BEACON"
        implementation = beacon
    elif minimal_impl:
        proxy_kind = "EIP1167_MINIMAL"
        implementation = minimal_impl
    if not (impl_slot_ok and beacon_slot_ok):
        is_proxy = None
        implementation_checked = False
    else:
        is_proxy = proxy_kind is not None
        if is_proxy:
            try:
                implementation_checked = bool(bytes(w3.eth.get_code(implementation)))
            except Exception:
                implementation_checked = False
        else:
            implementation_checked = True
    hits = selector_hits(code)
    return classify_admin_evidence(
        token=token, bytecode_present=True, owner=owner, admin=admin,
        admin_read_resolved=resolved_any, is_proxy=is_proxy, proxy_kind=proxy_kind,
        implementation=implementation, implementation_checked=implementation_checked,
        hits=hits, raw={
            "admin_reads": reads, "selector_hits": hits,
            "eip1967_impl_slot_resolved": impl_slot_ok,
            "eip1967_beacon_slot_resolved": beacon_slot_ok,
            "beacon": beacon,
        },
    )
