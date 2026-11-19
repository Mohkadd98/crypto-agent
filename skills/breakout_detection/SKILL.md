---
name: breakout_detection
display_name: Breakout Detection
description: Detects potential breakouts and retest setups
version: 1.0.0
dependencies: ["technical_analysis", "pattern_recognition"]
required_apis: ["coingecko", "binance"]
available_tools:
  - detect_breakout
  - detect_support_resistance
  - analyze_market_structure
  - get_historical_ohlcv
priority: 9
is_core: true
config:
  min_consolidation_days: 10
  volume_confirmation_multiplier: 1.5
  retest_tolerance_pct: 2
---

# Breakout Detection Skill

Identifies high-probability breakout setups with volume confirmation and retest validation.

## Capabilities

- **Consolidation Detection**: Find coins in tight ranges
- **Breakout Identification**: Resistance/support breaks with volume
- **Retest Validation**: Confirm breakout with successful retest
- **Failed Breakout Detection**: Identify bull/bear traps
- **Entry/Exit Levels**: Precise entry, stop-loss, and target levels
- **Multi-timeframe Confirmation**: Align breakouts across timeframes

## Tools

### detect_breakout
Detect breakout/breakdown patterns with scoring.
- Parameters: ohlcv, lookback (20)

### detect_support_resistance
Dynamic level detection for breakout reference.
- Parameters: ohlcv, window (20), min_touches (2)

### analyze_market_structure
Trend structure context for breakout direction.
- Parameters: ohlcv

### get_historical_ohlcv
Data fetch for analysis.
- Parameters: symbol, timeframe, days, source

## Usage Examples

```
"Find coins breaking out of 3-month consolidation"
"Show me retested breakouts on 4h timeframe"
"Detect failed breakouts (bull traps) on PEPE"
"Scan for volume-confirmed resistance breaks"
"Find coins at all-time high breakout levels"
```

## Breakout Criteria

### Valid Breakout
1. **Consolidation**: ≥10 days in range <20% width
2. **Volume**: Breakout volume >1.5x average
3. **Close**: Candle closes beyond level (not just wick)
4. **Momentum**: RSI >50 (upside) or <50 (downside)

### Retest Confirmation
1. **Pullback**: Price returns to broken level ±2%
2. **Support/Resistance Flip**: Former resistance becomes support
3. **Lower Volume**: Retest volume < breakout volume
4. **Bounce**: Strong rejection candle (hammer, engulfing)

### Targets
- **Conservative**: 1x consolidation height
- **Moderate**: 1.618x (Fibonacci extension)
- **Aggressive**: 2.618x or measured move

### Stop Loss
- **Tight**: Below retest low (2-3%)
- **Standard**: Below consolidation low (5-8%)
- **Wide**: Below major structure (10-15%)

## Integration

Uses technical_analysis for indicators and levels. Works with pattern_recognition for pattern-based breakouts (flag, triangle).