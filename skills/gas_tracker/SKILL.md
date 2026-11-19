---
name: gas_tracker
display_name: Gas Tracker
description: Gas prices and transaction cost estimates across chains
version: 1.0.0
dependencies: ["market_scanner"]
required_apis: ["blockchain_rpc"]
available_tools:
  - get_gas_prices
priority: 26
is_core: false
config:
  default_chains: ["ethereum", "bsc", "polygon", "arbitrum", "base", "avalanche"]
---

# Gas Tracker Skill

Monitors network congestion and transaction costs across supported chains.

## Capabilities

- **Gas Price**: gwei per chain
- **EIP-1559**: Base fee and priority fee where available
- **Cost Estimates**: Transfer, swap, NFT mint in native token
- **Cheapest Chain**: Lowest current gas
- **RPC Health**: Per-chain errors surfaced

## Tools

### get_gas_prices
Gas across multiple chains.
- Parameters: chains (optional array)

## Interpretation

- High gas: network demand — time-sensitive actions cost more
- Low gas: good window for non-urgent on-chain actions
- Arbitrum/Base usually cheapest for swaps
- Native-token cost estimates help compare execution venues

## Examples

```
"What are current gas prices?"
"Which chain has the cheapest gas right now?"
"Check Ethereum and Base gas"
```

## Integration

Execution-context tool for liquidity_analysis and new_token_scanner.