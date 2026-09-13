import { BigDecimal, BigInt } from "@graphprotocol/graph-ts";
import { PairCreated } from "../generated/Factory/Factory";
import { Pair as PairTemplate } from "../generated/templates";
import { Pair, Token } from "../generated/schema";

// Minimal placeholder: real symbol/name/decimals require an ERC20 ABI +
// contract calls (add `abis: [{name: ERC20, file: ./abis/ERC20.json}]` to the
// Factory data source in subgraph.yaml, then bind and call try_symbol() /
// try_name() / try_decimals() here). Left out of this scaffold to keep it
// compiling without an extra unverified ABI file.
function getOrCreateToken(addressHex: string): Token {
  let token = Token.load(addressHex);
  if (token != null) {
    return token as Token;
  }

  token = new Token(addressHex);
  token.symbol = "UNKNOWN";
  token.name = "Unknown Token";
  token.decimals = 18;
  token.save();
  return token as Token;
}

export function handleNewPair(event: PairCreated): void {
  const token0 = getOrCreateToken(event.params.token0.toHexString());
  const token1 = getOrCreateToken(event.params.token1.toHexString());

  const pair = new Pair(event.params.pair.toHexString());
  pair.token0 = token0.id;
  pair.token1 = token1.id;
  pair.reserve0 = BigDecimal.zero();
  pair.reserve1 = BigDecimal.zero();
  pair.reserveUSD = BigDecimal.zero();
  pair.volumeUSD = BigDecimal.zero();
  pair.txCount = BigInt.zero();
  pair.createdAtBlock = event.block.number;
  pair.createdAtTimestamp = event.block.timestamp;
  pair.save();

  // Start indexing this specific pair's Swap/Sync events dynamically.
  PairTemplate.create(event.params.pair);
}
