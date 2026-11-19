---
name: mean_reversion
display_name: Mean Reversion
description: Z-score, Bollinger %B and RSI-based reversion signals
version: 1.0.0
dependencies: ["technical_analysis"]
required_apis: ["coingecko"]
available_tools:
  - calculate_mean_reversion
  - calculate_rsi
  - get_historical_ohlcv
priority: 22
is_core: false
config:
  oversold_z: -2.0
  overbought_z: 2.0
---

# Mean Reversion Skill

Identifies statistically stretched prices likely to revert to their mean.

## Capabilities

- **Z-Score**: (price − SMA20) / STD20
- **Bollinger %B**: Position within 2σ bands
- **RSI(14)**: Wilder's RSI
- **Distance from SMA20**: Percent deviation
- **Trend Context**: Price vs SMA50
- **Signal**: strong_buy / buy / neutral / sell / strong_sell reversion

## Tools

### calculate_mean_reversion
All reversion metrics from OHLCV.
- Parameters: ohlcv

### calculate_rsi
Standalone RSI.

### get_historical_ohlcv
Fetch the data.

## Interpretation

- Z ≤ −2: statistically oversold — bounce candidate (if trend intact)
- Z ≥ +2: statistically overbought — fade candidate
- %B > 1: above upper band; < 0: below lower band
- Only trade reversion with the higher-timeframe trend or at strong support

## Examples

```
"Is BTC statistically overextended?"
"Find oversold coins with z-score below -2"
"Calculate mean reversion for SOL"
```

## Integration

Pairs with fibonacci_analysis (entry zones) and risk_analysis (avoid catching knives).