# Known case: direct Uniswap V3 WETH/USDC swap

## Selection

- Chain: Ethereum mainnet (`chain_id = 1`)
- Transaction: `0xc2b4b16efc7d871210ef7f48a404cd3353859ac0f2717e4b97d2268e5d62c865`
- Block: `15288837` (`0xe94a05`)
- Timestamp: `2022-08-06T12:52:59Z`
- Subject: `0xe0a36930f4b1e0a06788bf3d3a860db999bb4210`
- Router: Uniswap SwapRouter02 `0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45`
- Pool: Uniswap V3 USDC/WETH 0.05% `0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640`

This case was selected because it is a successful single-pool swap with two
standard ERC-20 `Transfer` logs and one Uniswap V3 `Swap` log. It does not use
Permit2 and it does not require general multi-hop tracing.

Public references:

- [Etherscan transaction and decoded logs](https://etherscan.io/tx/0xc2b4b16efc7d871210ef7f48a404cd3353859ac0f2717e4b97d2268e5d62c865)
- [Uniswap V3 Swap event definition](https://github.com/Uniswap/v3-core/blob/main/contracts/interfaces/pool/IUniswapV3PoolEvents.sol)
- [ERC-20 Transfer event standard](https://eips.ethereum.org/EIPS/eip-20)
- [Circle USDC Ethereum address](https://developers.circle.com/stablecoins/usdc-contract-addresses)

## Expected result written before the protocol resolver

The raw receipt contains these ERC-20 transfers, ordered by `logIndex`:

1. `logIndex = 25`: the pool transfers `17112191` raw USDC units to the
   subject. With evidenced 6 decimals, this is exactly `17.112191 USDC`.
2. `logIndex = 27`: SwapRouter02 transfers `10000000000000000` raw WETH units
   to the pool. With 18 decimals, this is exactly `0.01 WETH`.

The pool then emits `Swap` at `logIndex = 28` with:

- `amount0 = -17112191` (USDC leaves the pool);
- `amount1 = 10000000000000000` (WETH enters the pool).

No binary floating-point arithmetic is needed for these conclusions.

## Claims for later auditor fixtures

- Demonstrated: "The subject received exactly 17.112191 USDC in this transaction."
- Inflated: "The subject contributed the entire USDC/WETH pool volume."
- Insufficient: "The subject controlled SwapRouter02."

The first claim is supported by the USDC `Transfer` log. The second must not be
derived from one swap, and the third cannot be inferred from interaction alone.

## Provenance and limitations

`ethereum_rpc.json` was retrieved from public Ethereum JSON-RPC and checked
against Etherscan. `token_metadata.json` records the metadata sources used for
formatting; raw integers remain authoritative if metadata is removed.

The former hosted Uniswap V3 subgraph endpoint has been removed, and the
current decentralized endpoint requires a project API key. `the_graph.json`
therefore preserves the exact query and reports `NOT_ACQUIRED` explicitly. It
must be replaced with a captured response from the configured backend provider;
no Graph response has been fabricated for this fixture.
