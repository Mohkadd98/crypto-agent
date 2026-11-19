---
name: new_token_scanner
display_name: New Token Scanner
description: Scans newly created DEX liquidity pools for early opportunities
version: 1.0.0
dependencies: ["market_scanner"]
required_apis: ["geckoterminal", "dexscreener"]
available_tools:
  - scan_new_pairs
  - get_exchange_data
priority: 25
is_core: false
config:
  default_network: "eth"
  min_liquidity_usd: 10000
  max_age_hours: 24
---

# New Token Scanner Skill

Discovers freshly created DEX pools — earliest stage of new token opportunities.

## Capabilities

- **New Pools**: GeckoTerminal new_pools per network
- **Liquidity Filter**: Exclude sub-threshold pools
- **Metrics**: Price, liquidity, 24h volume, 24h change, creation time
- **Ranking**: Sorted by liquidity
- **Multi-chain**: eth, bsc, polygon, arbitrum, base, solana

## Tools

### scan_new_pairs
New pools on a network.
- Parameters: network (default eth), limit, min_liquidity_usd

### get_exchange_data
Additional exchange context.

## Interpretation

- High liquidity on a brand-new pool: real backing, worth watching
- Low liquidity + high change: likely speculative/noise
- Always verify contract, holders and lock status before any action
- New pairs are extremely high risk — position size accordingly

## Examples

```
"Find new token pairs on Ethereum"
"Scan new pools on Base with >$50k liquidity"
"Show latest launches on Solana"
```

## Integration

Feeds risk_analysis (new-token risks) and whale_tracking (early wallet activity).