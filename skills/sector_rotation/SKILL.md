---
name: sector_rotation
display_name: Sector Rotation
description: Category/sector performance to detect capital rotation
version: 1.0.0
dependencies: ["market_scanner", "market_breadth"]
required_apis: ["coingecko"]
available_tools:
  - get_sector_performance
  - scan_momentum
priority: 16
is_core: false
config:
  min_sector_market_cap: 50000000
  leaders_count: 12
---

# Sector Rotation Skill

Tracks which narratives (AI, DeFi, L2, memes, RWA, gaming) are attracting capital.

## Capabilities

- **Sector Performance**: Market-cap weighted 24h change per category
- **Leaders & Laggards**: Hottest and coldest sectors
- **Rotation Signal**: risk_on vs mixed/defensive
- **Narrative Detection**: Identify where flow is concentrating
- **Momentum Overlay**: Strongest coins inside leading sectors

## Tools

### get_sector_performance
Ranked sector performance with rotation signal.
- Parameters: top_n (default 12)

### scan_momentum
Momentum-ranked coins for each leading sector.
- Parameters: limit, min_volume_24h

## Interpretation

- High-beta sectors (AI, memes, L2) leading → risk-on, aggressive rotation
- Defensives (stablecoins, RWA) leading → defensive, reduce risk
- One sector dominating while others fall → narrow, fragile narrative trade

## Examples

```
"Which sectors are outperforming today?"
"Is capital rotating into AI tokens or DeFi?"
"Show sector rotation and the strongest narrative"
```

## Integration

Works with market_breadth for confirmation and momentum_scanner for trade selection.