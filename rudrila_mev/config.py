from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ZERO = "0x0000000000000000000000000000000000000000"


def _env_required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


@dataclass(frozen=True)
class Settings:
    chain_name: str
    chain_id: int
    rpc_url: str
    private_submission_rpc: str | None
    wallet_address: str
    private_key_env: str
    executor_address: str | None
    base_token: str
    quote_token: str
    router_a: str
    router_b: str
    base_token_is_wrapped_native: bool
    amount_in_wei: int
    slippage_bps_per_leg: int
    gas_units_fallback: int
    gas_units_buffer_bps: int
    base_fee_multiplier_bps: int
    priority_fee_multiplier_bps: int
    max_fee_per_gas_wei: int
    min_net_profit_wei: int
    extra_safety_buffer_wei: int
    max_quote_age_blocks: int
    deadline_seconds: int
    scan_interval_seconds: float
    live_trading: bool
    allow_public_mempool: bool
    require_private_submission_for_live: bool
    journal_path: str
    max_daily_gas_loss_wei: int
    max_daily_failed_transactions: int
    max_hourly_net_loss_wei: int
    max_daily_net_loss_wei: int
    max_hourly_failed_transactions: int
    max_daily_reverts: int

    @property
    def private_key(self) -> str:
        return _env_required(self.private_key_env)


def load_settings(path: str | Path) -> Settings:
    raw: dict[str, Any] = json.loads(Path(path).read_text())
    rpc_url = _env_required(raw["rpc_url_env"])
    wallet_address = _env_required(raw["wallet_address_env"])
    executor_address = os.environ.get(raw["executor_address_env"], "").strip() or None
    private_rpc = os.environ.get(raw["private_submission_rpc_env"], "").strip() or None

    s = Settings(
        chain_name=str(raw["chain_name"]),
        chain_id=int(raw["chain_id"]),
        rpc_url=rpc_url,
        private_submission_rpc=private_rpc,
        wallet_address=wallet_address,
        private_key_env=str(raw["private_key_env"]),
        executor_address=executor_address,
        base_token=str(raw["base_token_address"]),
        quote_token=str(raw["quote_token_address"]),
        router_a=str(raw["router_a_address"]),
        router_b=str(raw["router_b_address"]),
        base_token_is_wrapped_native=bool(raw["base_token_is_wrapped_native"]),
        amount_in_wei=int(raw["amount_in_wei"]),
        slippage_bps_per_leg=int(raw["slippage_bps_per_leg"]),
        gas_units_fallback=int(raw["gas_units_fallback"]),
        gas_units_buffer_bps=int(raw["gas_units_buffer_bps"]),
        base_fee_multiplier_bps=int(raw["base_fee_multiplier_bps"]),
        priority_fee_multiplier_bps=int(raw["priority_fee_multiplier_bps"]),
        max_fee_per_gas_wei=int(raw["max_fee_per_gas_wei"]),
        min_net_profit_wei=int(raw["min_net_profit_wei"]),
        extra_safety_buffer_wei=int(raw["extra_safety_buffer_wei"]),
        max_quote_age_blocks=int(raw["max_quote_age_blocks"]),
        deadline_seconds=int(raw["deadline_seconds"]),
        scan_interval_seconds=float(raw["scan_interval_seconds"]),
        live_trading=bool(raw["live_trading"]),
        allow_public_mempool=bool(raw["allow_public_mempool"]),
        require_private_submission_for_live=bool(raw["require_private_submission_for_live"]),
        journal_path=str(raw.get("journal_path", "state/mev_journal.jsonl")),
        max_daily_gas_loss_wei=int(raw.get("max_daily_gas_loss_wei", "5000000000000000")),
        max_daily_failed_transactions=int(raw.get("max_daily_failed_transactions", 3)),
        max_hourly_net_loss_wei=int(raw.get("max_hourly_net_loss_wei", "2000000000000000")),
        max_daily_net_loss_wei=int(raw.get("max_daily_net_loss_wei", "5000000000000000")),
        max_hourly_failed_transactions=int(raw.get("max_hourly_failed_transactions", 2)),
        max_daily_reverts=int(raw.get("max_daily_reverts", 3)),
    )
    validate_settings(s)
    return s


def validate_settings(s: Settings) -> None:
    if not s.base_token_is_wrapped_native:
        raise RuntimeError(
            "v0.1 requires the base token to be the wrapped native gas asset "
            "(for example WETH) so gas cost can be compared 1:1 in base-token wei."
        )
    if s.amount_in_wei <= 0:
        raise RuntimeError("amount_in_wei must be positive")
    if not 0 <= s.slippage_bps_per_leg <= 500:
        raise RuntimeError("slippage_bps_per_leg must be between 0 and 500 bps")
    if s.min_net_profit_wei <= 0:
        raise RuntimeError("min_net_profit_wei must be positive")
    if s.extra_safety_buffer_wei < 0:
        raise RuntimeError("extra_safety_buffer_wei cannot be negative")
    if s.gas_units_buffer_bps < 0:
        raise RuntimeError("gas_units_buffer_bps cannot be negative")
    if min(
        s.max_daily_gas_loss_wei,
        s.max_daily_failed_transactions,
        s.max_hourly_net_loss_wei,
        s.max_daily_net_loss_wei,
        s.max_hourly_failed_transactions,
        s.max_daily_reverts,
    ) <= 0:
        raise RuntimeError("execution kill-switch limits must be positive")
    if s.live_trading and not s.executor_address:
        raise RuntimeError("Live trading requires MEV_EXECUTOR_ADDRESS")
    if s.live_trading and s.require_private_submission_for_live and not s.private_submission_rpc:
        raise RuntimeError("Live trading requires a private submission RPC in this configuration")
    if s.live_trading and not s.allow_public_mempool and not s.private_submission_rpc:
        raise RuntimeError("Public mempool is disabled and no private submission RPC is configured")
