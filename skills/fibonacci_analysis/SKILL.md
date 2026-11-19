---
name: fibonacci_analysis
display_name: Fibonacci Analysis
description: Fibonacci retracement and extension levels with golden zone
version: 1.0.0
dependencies: ["technical_analysis"]
required_apis: ["coingecko"]
available_tools:
  - calculate_fibonacci
  - get_historical_ohlcv
  - detect_support_resistance
priority: 18
is_core: false
config:
  default_lookback: 120
  golden_zone: [0.382, 0.618]
---

# Fibonacci Analysis Skill

Maps retracement and extension levels to find high-probability entry and target zones.

## Capabilities

- **Swing Detection**: Automatic swing high/low over lookback
- **Retracement Levels**: 0.236, 0.382, 0.5, 0.618, 0.786
- **Extension Levels**: 1.272, 1.618, 2.618 (targets)
- **Golden Zone**: 0.382–0.618 retracement entry area
- **Nearest Level**: Distance to closest fib level
- **Range Position**: Where price sits within the swing (%)

## Tools

### calculate_fibonacci
All fib levels from OHLCV.
- Parameters: ohlcv, lookback (default 120)

### get_historical_ohlcv
Fetch the data to analyze.

### detect_support_resistance
Confirm fib levels with actual touch counts.

## Interpretation

- Uptrend + price in golden zone: prime long entry area
- Price at 1.618 extension in uptrend: take-profit zone
- Fib level coinciding with support/resistance: high-confluence level
- Price beyond 0.786: trend likely failing

## Examples

```
"Calculate Fibonacci levels for SOL"
"Is BTC in the golden zone?"
"Where is ETH relative to its fib retracement?"
```

## Integration

Confluence layer for breakout_detection and pattern_recognition.