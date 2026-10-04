# RUDRILA MEV v0.11.0 Private Submission Verification

Generated: 2026-10-04T14:52:32.784993+00:00
Python tests: 204
Verified healthy private paths: 2
Public mempool fallback: DISABLED

## Paths
- 48club-privacy: verified=True chain=56 method=eth_sendRawTransaction url=https://rpc.48.club error=None
- 48club-puissant-builder: verified=True chain=56 method=eth_sendPrivateTransaction url=https://puissant-builder.48.club/ error=None
- merkle: verified=False chain=None method=eth_sendRawTransaction url=https://bsc.merkle.io error=HTTPError: 429 Client Error: Too Many Requests for url: https://bsc.merkle.io/

## Invariants
- At least two HTTPS BSC private relay/builder paths are required.
- Malformed transaction capability probes cannot broadcast a valid transaction.
- BSC send_trade uses the multi-path private adapter.
- All private paths failing causes a hard error; no public fallback is used.
- Live trading remains OFF and no private key is required for this verification.

- Bandit medium/high: 0
- Dependency vulnerabilities: 0
- Actionable secret candidates: 0
