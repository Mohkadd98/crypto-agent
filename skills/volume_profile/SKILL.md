---
name: volume_profile
display_name: Volume Profile
description: Volume-at-price analysis with POC, value area and HVNs
version: 1.0.0
dependencies: ["technical_analysis"]
required_apis: ["coingecko"]
available_tools:
  - calculate_volume_profile
  - get_historical_ohlcv
priority: 19
is_core: false
config:
  default_bins: 24
  value_area_pct: 70
---

# Volume Profile Skill

Shows where volume actually traded (not when), revealing acceptance and rejection zones.

## Capabilities

- **POC (Point of Control)**: Price with most traded volume
- **Value Area**: 70% of volume → high/low boundaries
- **High Volume Nodes**: Top 3 price shelves
- **Price Location**: above / inside / below value area
- **Bias**: bullish above POC, bearish below

## Tools

### calculate_volume_profile
Full volume profile from OHLCV.
- Parameters: ohlcv, bins (default 24)

### get_historical_ohlcv
Fetch the data.

## Interpretation

- Price above value area: acceptance higher → bullish continuation
- Price below value area: rejection → bearish
- Inside value area: balance, wait for breakout
- POC acts as magnet; HVNs are strong support/resistance
- Thin zones between HVNs: price moves fast through them

## Examples

```
"Where is the POC for BTC?"
"Calculate volume profile and value area for ETH"
"Is SOL above or below its value area?"
```

## Integration

Pairs with fibonacci_analysis and detect_support_resistance for confluence.