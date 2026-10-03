# RUDRILA MEV v0.11.0 Private Submission Verification

Generated: 2026-10-03T05:08:53.477710+00:00
Python tests: 111
Verified healthy private paths: 3
Public mempool fallback: DISABLED

## Paths
- 48club-privacy: verified=True chain=56 method=eth_sendRawTransaction url=https://rpc.48.club error=None
- 48club-puissant-builder: verified=True chain=56 method=eth_sendPrivateTransaction url=https://puissant-builder.48.club/ error=None
- merkle: verified=True chain=56 method=eth_sendRawTransaction url=https://bsc.merkle.io error=None

## Invariants
- At least two HTTPS BSC private relay/builder paths are required.
- Malformed transaction capability probes cannot broadcast a valid transaction.
- BSC send_trade uses the multi-path private adapter.
- All private paths failing causes a hard error; no public fallback is used.
- Live trading remains OFF and no private key is required for this verification.

- Bandit medium/high: 0
- Dependency vulnerabilities: 0
- Actionable secret candidates: 0
