from __future__ import annotations

import argparse

from .config import load_settings
from .scanner import Scanner


def main() -> None:
    p = argparse.ArgumentParser(description="RUDRILA MEV Arbitrage v0.1")
    p.add_argument("--config", default="config.json")
    p.add_argument("--once", action="store_true")
    args = p.parse_args()

    settings = load_settings(args.config)
    scanner = Scanner(settings)

    print(
        f"RUDRILA MEV v0.1 | chain={settings.chain_name} | "
        f"live_trading={settings.live_trading} | public_mempool={settings.allow_public_mempool}"
    )
    if settings.live_trading:
        print("LIVE MODE: every trade still requires quote floor + gas + safety + minimum net profit.")

    if args.once:
        scanner.run_once()
    else:
        scanner.run_forever()


if __name__ == "__main__":
    main()
