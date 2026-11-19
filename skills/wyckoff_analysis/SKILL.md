---
name: wyckoff_analysis
display_name: Wyckoff Analysis
description: Wyckoff phase detection accumulation/distribution, spring, upthrust
version: 1.0.0
dependencies: ["technical_analysis", "volume_profile"]
required_apis: ["coingecko"]
available_tools:
  - analyze_wyckoff
  - detect_accumulation
  - get_historical_ohlcv
priority: 24
is_core: false
config:
  default_window: 60
  max_range_width_pct: 35
---

# Wyckoff Analysis Skill

Identifies institutional accumulation/distribution campaigns and their current phase.

## Capabilities

- **Structure**: accumulation / distribution / neutral
- **Phase**: A (stopping), B (building), C (spring/upthrust), D (SOS/SOW), E (markup/markdown)
- **Spring**: wick below range then recovery (accumulation shakeout)
- **Upthrust**: wick above range then rejection (distribution trap)
- **Range Metrics**: high/low, width %, prior trend
- **Volume Behavior**: increasing / decreasing / flat
- **Confidence**: 0-1 based on evidence

## Tools

### analyze_wyckoff
Phase and structure detection from OHLCV.
- Parameters: ohlcv, window (default 60)

### detect_accumulation
Complementary accumulation scoring.

### get_historical_ohlcv
Fetch the data.

## Interpretation

- Accumulation Phase C with spring: high-conviction long setup
- Distribution Phase C with upthrust: high-conviction exit/short
- Phase D sign of strength: trend confirmation
- Low confidence: range unclear, stand aside

## Examples

```
"Is SOL in a Wyckoff accumulation phase?"
"Detect a spring or upthrust on BTC"
"Analyze Wyckoff structure for ETH"
```

## Integration

Combines volume_profile (acceptance) and detect_accumulation for robust detection.