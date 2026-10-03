#!/bin/sh
set -eu

# Production template: keep RPC on localhost.
# Node installation/sync is a separate host operation.
exec reth node \
  --chain mainnet \
  --http \
  --http.addr 127.0.0.1 \
  --http.port 8545 \
  --http.api eth,net,web3 \
  --ws \
  --ws.addr 127.0.0.1 \
  --ws.port 8546 \
  --ws.api eth,net,web3
