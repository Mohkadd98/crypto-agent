---
name: technical_analysis
display_name: Technical Analysis
description: Calculates technical indicators and identifies setups
version: 1.0.0
dependencies: ["market_scanner"]
required_apis: []
available_tools:
  - calculate_rsi
  - calculate_macd
  - calculate_ema
  - calculate_obv
  - calculate_atr
  - detect_support_resistance
  - detect_breakout
  - detect_accumulation
  - analyze_market_structure
  - full_technical_analysis
priority: 3
is_core: true
config:
  rsi_period: 14
  macd_fast: 12
  macd_slow: 26
  macd_signal: 9
  ema_periods: [9, 21, 50, 200]
  atr_period: 14
  bb_period: 20
  bb_std: 2.0
---

# Technical Analysis Skill

Comprehensive technical analysis with all major indicators and pattern detection.

## Capabilities

- **Momentum Indicators**: RSI, MACD with crossover detection
- **Trend Indicators**: EMA alignment (9, 21, 50, 200), market structure
- **Volume Indicators**: OBV with divergence detection
- **Volatility**: ATR with percentage calculation
- **Support/Resistance**: Dynamic level detection with touch counting
- **Breakout Detection**: Resistance/support breaks with volume confirmation
- **Accumulation Detection**: Smart money absorption patterns
- **Full Analysis**: Complete multi-indicator assessment

## Tools

### calculate_rsi
Relative Strength Index with overbought/oversold signals.
- Parameters: ohlcv, period (default: 14)

### calculate_macd
MACD with signal line and histogram.
- Parameters: ohlcv, fast (12), slow (26), signal (9)

### calculate_ema
Multiple EMAs with alignment detection.
- Parameters: ohlcv, periods (array: [9, 21, 50, 200])

### calculate_obv
On-Balance Volume with trend and divergence.
- Parameters: ohlcv

### calculate_atr
Average True Range for volatility measurement.
- Parameters: ohlcv, period (14)

### detect_support_resistance
Dynamic support/resistance levels with strength scoring.
- Parameters: ohlcv, window (20), min_touches (2)

### detect_breakout
Breakout/breakdown detection with retest confirmation.
- Parameters: ohlcv, lookback (20)

### detect_accumulation
Wyckoff-style accumulation pattern detection.
- Parameters: ohlcv

### analyze_market_structure
Higher highs/higher lows, lower highs/lower lows analysis.
- Parameters: ohlcv

### full_technical_analysis
Complete multi-indicator analysis with summary bias.
- Parameters: ohlcv

## Usage Examples

```
"Run full technical analysis on SOL"
"Check RSI and MACD for BTC"
"Find support and resistance levels for ETH"
"Is AVAX showing accumulation patterns?"
"Detect breakout on ARB 4h chart"
"Analyze market structure for PEPE"
```

## Indicator Interpretation

- **RSI**: >70 overbought, <30 oversold, 50 midpoint
- **MACD**: Bullish when MACD > Signal, crossover signals
- **EMA Stack**: Bullish when 9>21>50>200, bearish when reversed
- **OBV**: Rising OBV + falling price = bullish divergence
- **ATR**: High ATR = high volatility, use for stop placement
- **Bollinger Bands**: Position 0-1, >0.8 upper band, <0.2 lower band

## Integration

Core skill for all price-based analysis. Used by breakout_detection, pattern_recognition, risk_analysis.