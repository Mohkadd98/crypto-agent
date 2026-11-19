---
name: order_book_analysis
display_name: Order Book Analysis
description: Order book depth, imbalance, walls and spread quality
version: 1.0.0
dependencies: ["market_scanner"]
required_apis: ["binance_public"]
available_tools:
  - analyze_order_book
  - get_exchange_data
priority: 17
is_core: false
config:
  default_levels: 100
  wall_multiple: 4
---

# Order Book Analysis Skill

Reads live order book structure to gauge near-term supply/demand and execution quality.

## Capabilities

- **Spread**: Absolute and percentage spread, liquidity quality
- **Imbalance**: Bid vs ask volume (−100 to +100)
- **Walls**: Levels with >4x average size (support/resistance shelves)
- **Notional Depth**: Bid/ask notional within the sampled levels
- **Pressure**: buy / balanced / sell

## Tools

### analyze_order_book
Depth, imbalance, walls and spread for a symbol.
- Parameters: symbol, limit (default 100)

### get_exchange_data
Cross-exchange context.

## Interpretation

- Imbalance > +15%: bid-heavy, buyers absorbing → short-term bullish
- Imbalance < −15%: ask-heavy → short-term bearish
- Large bid wall: potential support but can be spoofed
- Wide spread (>0.2%): poor execution — use limit orders or avoid

## Examples

```
"Analyze the BTC order book imbalance"
"Where are the big bid and ask walls for SOL?"
"Is ETH order book buy or sell heavy?"
```

## Integration

Timing tool for breakout_detection entries; complements derivatives_analysis positioning.