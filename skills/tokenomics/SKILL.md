---
name: tokenomics
display_name: Tokenomics Analysis
description: Analyzes token economics, supply dynamics, and unlocks
version: 1.0.0
dependencies: ["market_scanner"]
required_apis: ["coingecko", "coinmarketcap", "messari"]
available_tools:
  - evaluate_tokenomics
  - analyze_token_unlocks
  - get_market_cap
  - get_coin_price
priority: 6
is_core: true
config:
  dilution_threshold: 0.2
  fdv_mcap_ratio_warning: 2.0
---

# Tokenomics Analysis Skill

Evaluates token economic design, supply dynamics, inflation risk, and unlock schedules.

## Capabilities

- **Supply Analysis**: Circulating vs total vs max supply ratios
- **Dilution Risk**: FDV/Market Cap ratio, future inflation calculation
- **Unlock Schedule**: Upcoming token unlocks with impact assessment
- **Token Quality Scoring**: Multi-factor tokenomics rating
- **Vesting Analysis**: Team/investor/ecosystem vesting schedules

## Tools

### evaluate_tokenomics
Comprehensive tokenomics quality score (0-10).
- Parameters: coin_data (object with supply metrics)

### analyze_token_unlocks
Analyze upcoming token unlocks and potential market impact.
- Parameters: coin_data, unlock_schedule (optional array)

### get_market_cap
Current market capitalization.
- Parameters: symbol

### get_coin_price
Current price for FDV calculation.
- Parameters: symbol, vs_currency

## Usage Examples

```
"Evaluate tokenomics for ARB - is dilution a concern?"
"Show me upcoming unlocks for OP token"
"Compare FDV/Market Cap ratios for L1 tokens"
"Analyze vesting schedule for new launch TOKEN"
"Score tokenomics for my watchlist coins"
```

## Scoring Factors (10 points max)

1. **Circulating Supply Ratio** (2 pts): >80% = 2, 50-80% = 1, <50% = 0
2. **Max Supply Status** (1 pt): Reached = 1, Low remaining <10% = 1
3. **FDV/Market Cap Ratio** (2 pts): >80% = 2, 50-80% = 1, <50% = 0
4. **Price Range** (1 pt): $0.01-$1000 = 1 (retail accessible)
5. **Liquidity (Vol/MCap)** (2 pts): >10% = 2, 5-10% = 1, <5% = 0
6. **Unlock Risk** (2 pts): Low = 2, Medium = 1, High = 0

## Ratings

- **Excellent (8-10)**: Strong tokenomics, low dilution risk
- **Good (6-7)**: Acceptable with minor concerns
- **Fair (4-5)**: Notable dilution or supply risks
- **Poor (<4)**: High dilution risk, avoid or size small

## Integration

Used by risk_analysis for fundamental risk scoring. Provides context for potential_upside calculations.