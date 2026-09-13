import { BigDecimal, BigInt } from "@graphprotocol/graph-ts";
import { Swap as SwapEvent, Sync } from "../generated/templates/Pair/Pair";
import { Pair, Swap } from "../generated/schema";

// Placeholder: a real deployment should divide by each token's decimals
// (from the Token entity) instead of returning the raw integer as a decimal.
function toDecimal(value: BigInt): BigDecimal {
  return value.toBigDecimal();
}

export function handleSwap(event: SwapEvent): void {
  const pair = Pair.load(event.address.toHexString());
  if (pair == null) {
    return; // Swap on a pair this subgraph never saw PairCreated for.
  }

  pair.txCount = pair.txCount.plus(BigInt.fromI32(1));
  pair.save();

  const swap = new Swap(
    event.transaction.hash.toHexString() + "-" + event.logIndex.toString()
  );
  swap.pair = pair.id;
  swap.transaction = event.transaction.hash;
  swap.timestamp = event.block.timestamp;
  swap.sender = event.params.sender;
  swap.to = event.params.to;
  swap.amount0In = toDecimal(event.params.amount0In);
  swap.amount1In = toDecimal(event.params.amount1In);
  swap.amount0Out = toDecimal(event.params.amount0Out);
  swap.amount1Out = toDecimal(event.params.amount1Out);
  // Placeholder: a real deployment prices this in USD via a stablecoin/oracle
  // pair, as the Uniswap/Trader Joe subgraphs this schema mirrors do.
  swap.amountUSD = BigDecimal.zero();
  swap.save();
}

export function handleSync(event: Sync): void {
  const pair = Pair.load(event.address.toHexString());
  if (pair == null) {
    return;
  }
  pair.reserve0 = toDecimal(event.params.reserve0);
  pair.reserve1 = toDecimal(event.params.reserve1);
  pair.save();
}
