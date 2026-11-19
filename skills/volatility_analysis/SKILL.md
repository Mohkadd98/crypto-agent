---
name: volatility_analysis
display_name: Volatility Analysis
description: Realized volatility, drawdown and volatility regime detection
version: 1.0.0
dependencies: ["technical_analysis"]
required_apis: ["coingecko"]
available_tools:
  - analyze_volatility
  - calculate_atr
  - get_historical_ohlcv
priority: 20
is_core: false
config:
  high_vol_threshold: 90
  extreme_vol_threshold: 150
---

# Volatility Analysis Skill

Quantifies risk via realized volatility and detects expansion/compression regimes.

## Capabilities

- **Realized Volatility**: 7d, 30d and full-window annualized
- **ATR & ATR%**: Average true range for stop sizing
- **Max Drawdown**: Worst peak-to-trough decline
- **Regime**: low / normal / high / extreme
- **State**: expanding / contracting / stable
- **Actionable Note**: sizing and breakout guidance

## Tools

### analyze_volatility
Complete volatility profile from OHLCV.
- Parameters: ohlcv

### calculate_atr
ATR for a specific period.

### get_historical_ohlcv
Fetch the data.

## Interpretation

- Vol expanding: reduce size, widen stops
- Vol compressing: breakout setup forming — watch for expansion
- Extreme vol (>150% annualized): lottery-ticket risk, tiny size only
- Use ATR% to size stops (e.g., 2×ATR)

## Examples

```
"What is SOL's realized volatility?"
"Is volatility compressing on BTC?"
"How much is ETH's max drawdown?"
"Suggest stop distance using ATR for AVAX"
```

## Integration

Core input for risk_analysis and position sizing in portfolio_analysis.