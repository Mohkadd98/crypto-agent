---
name: derivatives_analysis
display_name: Derivatives Analysis
description: Funding rate, open interest, long/short ratio and crowding signals
version: 1.0.0
dependencies: ["market_scanner"]
required_apis: ["binance_public"]
available_tools:
  - get_derivatives_analysis
  - analyze_order_book
priority: 13
is_core: false
config:
  funding_extreme_pct: 0.05
  ratio_extreme: 2.0
---

# Derivatives Analysis Skill

Analyzes futures market positioning to detect crowded trades, squeeze setups, and trend confirmation.

## Capabilities

- **Funding Rate**: Current and historical funding, annualized cost, crowding detection
- **Open Interest**: OI level and change, trend confirmation
- **Long/Short Ratio**: Retail positioning (contrarian signal)
- **Crowding Score**: Composite -1 (crowded long) to +1 (crowded short)
- **Stance**: contrarian_bullish / neutral / contrarian_bearish

## Tools

### get_derivatives_analysis
Combined funding + OI + long/short analysis for a symbol.
- Parameters: symbol

### analyze_order_book
Spot order book depth and imbalance.
- Parameters: symbol, limit

## Interpretation

- Funding > +0.05%: longs overcrowded → correction risk (contrarian bearish)
- Funding < -0.05%: shorts overcrowded → squeeze potential (contrarian bullish)
- Long/short > 2.0: retail heavily long
- Long/short < 0.6: retail heavily short
- OI rising with price: trend strength; OI falling with price: deleveraging

## Examples

```
"What is the funding rate and open interest for BTC?"
"Is SOL crowded long right now?"
"Show derivatives positioning and squeeze potential for ETH"
```

## Integration

Complements technical_analysis (trend confirmation) and risk_analysis (crowding risk).