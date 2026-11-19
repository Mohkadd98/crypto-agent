---
name: historical_analysis
display_name: Historical Analysis
description: Analyzes historical price data, patterns, and cycles
version: 1.0.0
dependencies: ["market_scanner"]
required_apis: ["coingecko"]
available_tools:
  - get_historical_ohlcv
  - search_historical_patterns
  - compare_coins
  - calculate_potential_upside
priority: 2
is_core: true
config:
  default_lookback_days: 365
  pattern_min_confidence: 0.6
---

# Historical Analysis Skill

This skill analyzes historical price data to identify patterns, cycles, and comparable historical scenarios.

## Capabilities

- **Historical Data Retrieval**: Fetch OHLCV data across multiple timeframes
- **Pattern Recognition**: Identify chart patterns (double bottom/top, head & shoulders, cup & handle, flags, triangles)
- **Historical Comparison**: Compare current price action with historical precedents
- **Potential Upside Calculation**: Risk/reward scenarios with Fibonacci targets

## Tools

### get_historical_ohlcv
Get historical OHLCV data for pattern analysis.
- Parameters: symbol, timeframe, days, source

### search_historical_patterns
Search for historical chart patterns in OHLCV data.
- Parameters: ohlcv (object), pattern_type (string: all, double_bottom, double_top, head_shoulders, cup_handle, flags, triangles)

### compare_coins
Compare multiple coins across key metrics.
- Parameters: coins_data (array of objects)

### calculate_potential_upside
Calculate potential upside with risk/reward scenarios.
- Parameters: coin_data (object), ohlcv (object)

## Usage Examples

```
"Find coins with similar patterns to SOL before its 2021 rally"
"Compare BTC current structure with 2019 accumulation"
"What happened to ETH after similar RSI oversold conditions?"
"Show me historical precedents for this cup and handle formation"
"Calculate risk/reward for AVAX at current levels"
```

## Pattern Types

- **Double Bottom/Top**: Reversal patterns with two similar lows/highs
- **Head & Shoulders**: Three-peak reversal pattern
- **Cup & Handle**: Continuation pattern with U-shape and pullback
- **Flags/Pennants**: Short consolidation after strong move
- **Triangles**: Symmetrical, ascending, descending convergence

## Integration

Depends on market_scanner for initial coin data. Works with pattern_recognition and breakout_detection for confirmation.