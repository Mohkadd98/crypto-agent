---
name: momentum_scanner
display_name: Momentum Scanner
description: Multi-timeframe momentum scanner with acceleration
version: 1.0.0
dependencies: ["market_scanner"]
required_apis: ["coingecko"]
available_tools:
  - scan_momentum
  - get_top_coins
priority: 21
is_core: false
config:
  min_volume_24h: 1000000
  default_limit: 20
---

# Momentum Scanner Skill

Ranks the market by weighted multi-timeframe momentum and detects acceleration.

## Capabilities

- **Weighted Momentum**: 24h (50%), 7d (30%), 30d (20%)
- **Acceleration**: 24h vs 7d average — catching inflection points
- **Liquidity Filter**: Excludes thin names
- **Top Candidates**: Ranked with all timeframe changes
- **Accelerating Subset**: Coins turning up fastest

## Tools

### scan_momentum
Ranked momentum candidates.
- Parameters: limit (default 20), min_volume_24h (default 1,000,000)

### get_top_coins
Baseline market data.

## Interpretation

- High score + positive acceleration: strongest trend, early leg
- High 30d but negative 24h: momentum fading
- Low 30d but positive acceleration: potential reversal/turn
- Always confirm with volume and structure

## Examples

```
"Which coins have the strongest momentum?"
"Show me accelerating coins"
"Find momentum leaders with high volume"
```

## Integration

Feeds breakout_detection and rank_candidates; confirms sector_rotation leaders.