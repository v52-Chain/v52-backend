# `hsk-core` — starter subgraph scaffold for HashKey Chain

## Why this exists

Vector52's DeFi Subgraph Intel surface (`GET /v1/intel/defi/status`,
`POST /v1/agent/intel/defi/*`, see `../../docs/SUBGRAPHS.md`) queries a
subgraph per chain. Ethereum Mainnet and Avalanche already have public
subgraphs on The Graph's decentralized network that any operator can point
`V52_GRAPH_ENDPOINT_ETHEREUM` / `V52_GRAPH_ENDPOINT_AVALANCHE` at.

**HSK Chain does not.** Per HashKey's own docs
(<https://docs.hskchain.net/docs/Build-on-HashKey-Chain/Tools/Subgraph>),
The Graph is supported on `hashkeychain` (`eip155:177`), but no hosted/public
subgraph is published — every project deploys its own. This directory is a
Uniswap-V2-style starter (factory → pair template → swaps) so whoever indexes
a real HSK DEX doesn't start from a blank `graph init`.

**This scaffold is not deployed and is not wired into the backend by
default.** `V52_GRAPH_ENDPOINT_HSK` stays empty until someone deploys a real
instance of this (or another) subgraph against a **verified** HSK contract
address — inventing an address here would mean Vector52 could silently
report fabricated "vital points" for HSK, which is exactly what
`app/providers/the_graph.py`'s own rules forbid ("evidence is never
invented"). Until then, `/v1/intel/defi/status` reports HSK as
`configured: false`, honestly.

## What's here

```
hsk-core/
  subgraph.yaml       # manifest: Factory data source + Pair template
  schema.graphql       # Token / Pair / Swap entities
  package.json          # graph-cli / graph-ts scripts
  abis/
    Factory.json        # PairCreated(address,address,address,uint256)
    Pair.json            # Swap/Mint/Burn/Sync + ERC20 Transfer
  src/
    factory.ts           # handleNewPair -> instantiates a Pair data source
    pair.ts               # handleSwap -> writes a Swap entity per trade
```

It follows the same entity shape (`pairs`, `token0`/`token1`, `reserve0`,
`reserve1`, `swaps`) that `app/api/defi_core.py`'s `uniswap_v2` query family
already expects — so once deployed, only `.env` needs to change:

```
V52_GRAPH_ENDPOINT_HSK=<your deployed query URL>
V52_GRAPH_SCHEMA_HSK=uniswap_v2
```

## Before deploying: fill in real addresses

`subgraph.yaml` has two placeholders that **must** be replaced with a
contract address you have independently verified on HSK's block explorer —
never guessed or copied from another chain:

- `FACTORY_ADDRESS_PLACEHOLDER` — the DEX factory contract that emits
  `PairCreated`.
- `FACTORY_START_BLOCK_PLACEHOLDER` — the block the factory was deployed at
  (indexing from 0 works but is far slower).

## Deploying (per HashKey's docs)

```bash
npm install -g @graphprotocol/graph-cli
cd subgraph/hsk-core
npm install
graph codegen
graph build
# Authenticate first: graph auth --product hosted-service <ACCESS_TOKEN>
graph deploy --product hosted-service <GITHUB_USER>/<SUBGRAPH_NAME>
```

`graph init` originally used `--protocol ethereum --network hashkeychain` to
scaffold this network target; this directory already has that wiring done.

## Extending

Real HSK DeFi protocols will likely need more than swaps (fees, multi-hop
routers, concentrated-liquidity pools). Treat this as the minimum viable
skeleton for `app/api/defi_core.py`'s `uniswap_v2` shape, not a finished
protocol integration — add entities/handlers as real, verified HSK contracts
are identified.
