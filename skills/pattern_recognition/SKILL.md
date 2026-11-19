---
name: pattern_recognition
display_name: Pattern Recognition
description: Recognizes chart patterns and historical similarities
version: 1.0.0
dependencies: ["historical_analysis", "technical_analysis"]
required_apis: ["coingecko"]
available_tools:
  - search_historical_patterns
  - compare_coins
  - detect_accumulation
  - full_technical_analysis
priority: 8
is_core: true
config:
  min_pattern_confidence: 0.6
  lookback_days: 365
---

# Pattern Recognition Skill

Advanced chart pattern detection and historical similarity matching.

## Capabilities

- **Classical Patterns**: Double bottom/top, head & shoulders, cup & handle
- **Continuation Patterns**: Flags, pennants, triangles (symmetrical, ascending, descending)
- **Harmonic Patterns**: Gartley, butterfly, bat, crab (Fibonacci-based)
- **Candlestick Patterns**: Doji, engulfing, hammer, shooting star, morning/evening star
- **Historical Similarity**: Find coins with similar price action to a reference
- **Pattern Completion**: Project targets from pattern measurements

## Tools

### search_historical_patterns
Detect chart patterns in OHLCV data.
- Parameters: ohlcv, pattern_type (all, double_bottom, double_top, head_shoulders, cup_handle, flags, triangles)

### compare_coins
Compare current price action with historical precedents.
- Parameters: coins_data

### detect_accumulation
Wyckoff accumulation schematic identification.
- Parameters: ohlcv

### full_technical_analysis
Complete analysis with pattern overlay.
- Parameters: ohlcv

## Usage Examples

```
"Find coins forming cup and handle patterns"
"Show me historical precedents for this head and shoulders on BTC"
"Detect harmonic patterns on SOL 4h chart"
"Find coins with similar price action to ETH 2019"
"Identify Wyckoff accumulation schematics"
"Search for bull flags on trending tokens"
```

## Pattern Types

### Reversal Patterns
- **Double Bottom** (W): Target = neckline + (neckline - bottom)
- **Double Top** (M): Target = neckline - (top - neckline)
- **Head & Shoulders**: Target = neckline - (head - neckline)
- **Inverse H&S**: Target = neckline + (neckline - head)

### Continuation Patterns
- **Bull Flag**: Pole + consolidation, target = pole height added to breakout
- **Bear Flag**: Inverse of bull flag
- **Pennant**: Triangular consolidation, same target as flag
- **Ascending Triangle**: Flat top + rising bottom, bullish
- **Descending Triangle**: Flat bottom + falling top, bearish
- **Symmetrical Triangle**: Converging, direction depends on prior trend

### Wyckoff Schematics
- **Accumulation**: Phase A (stopping), B (build), C (spring), D (sign of strength), E (markup)
- **Distribution**: Phase A (preliminary supply), B (build), C (upthrust), D (sign of weakness), E (markdown)

## Confidence Scoring

- **High (0.8+)**: Clear pattern, volume confirmation, clean structure
- **Medium (0.6-0.8)**: Pattern visible but some noise
- **Low (<0.6)**: Noisy, early formation, or conflicting signals

## Integration

Works with historical_analysis for precedent search. Feeds breakout_detection for entry timing.