---
name: market_breadth
display_name: Market Breadth
description: Measures market participation, advance/decline and risk regime
version: 1.0.0
dependencies: ["market_scanner"]
required_apis: ["coingecko"]
available_tools:
  - get_market_breadth
  - get_market_overview
  - get_sector_performance
priority: 14
is_core: false
config:
  universe_size: 150
---

# Market Breadth Skill

Measures how broad a market move is — the single best filter between a healthy trend and a fragile one.

## Capabilities

- **Advance/Decline**: Advancing vs declining coins in the top universe
- **Participation**: % of coins positive on 24h / 7d / 30d
- **Median & Mean Change**: Robust central tendency of the market
- **Breadth Score**: 0-100 composite
- **Regime**: strong_bull, bull, mixed, bear, strong_bear
- **Leaders & Laggards**: Top 5 and bottom 5 performers

## Tools

### get_market_breadth
Breadth metrics across the top N coins.
- Parameters: top_n (default 150)

### get_market_overview
Global market cap, volume, BTC/ETH dominance.

### get_sector_performance
Category-level performance for rotation context.

## Interpretation

- Breadth > 70 and rising: broad bull, risk-on
- Breadth 45-55: selective market, stock-picker's regime
- Breadth < 30: broad decline, capital preservation
- Price up but breadth falling: internal divergence → fragile rally

## Examples

```
"What is the current market breadth?"
"Is the BTC rally broad or narrow?"
"How many coins are positive over 7 days?"
```

## Integration

Feeds risk_analysis (regime risk) and sector_rotation (participation by sector).