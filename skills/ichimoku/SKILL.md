---
name: ichimoku
display_name: Ichimoku Cloud
description: Ichimoku Kinko Hyo analysis with cloud position and bias
version: 1.0.0
dependencies: ["technical_analysis"]
required_apis: ["coingecko"]
available_tools:
  - calculate_ichimoku
  - get_historical_ohlcv
priority: 23
is_core: false
config:
  tenkan: 9
  kijun: 26
  senkou_b: 52
---

# Ichimoku Cloud Skill

All-in-one trend, momentum and support/resistance system.

## Capabilities

- **Tenkan-sen** (9): short-term equilibrium
- **Kijun-sen** (26): medium-term equilibrium
- **Senkou Span A/B**: cloud boundaries (future support/resistance)
- **Chikou Span**: lagging line momentum check
- **Price Position**: above / inside / below cloud
- **Bias**: bullish / neutral / bearish with signal list

## Tools

### calculate_ichimoku
Full Ichimoku read from OHLCV.
- Parameters: ohlcv

### get_historical_ohlcv
Fetch the data (needs 60+ candles).

## Interpretation

- Price above cloud + Tenkan > Kijun + Chikou bullish: strong uptrend
- Price inside cloud: indecision — wait for breakout
- Price below cloud: downtrend; rallies into cloud are sell zones
- Cloud color (A vs B) shows forward bias

## Examples

```
"Run Ichimoku on SOL"
"Is ETH above or below the cloud?"
"Show Ichimoku bias for BTC"
```

## Integration

Trend filter for breakout_detection; confirmation for momentum_scanner.