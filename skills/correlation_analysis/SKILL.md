---
name: correlation_analysis
display_name: Correlation Analysis
description: Return correlation matrix and BTC beta for diversification
version: 1.0.0
dependencies: ["market_scanner", "historical_analysis"]
required_apis: ["coingecko"]
available_tools:
  - calculate_correlation_matrix
  - compare_coins
priority: 15
is_core: false
config:
  default_days: 90
  high_correlation_threshold: 0.8
---

# Correlation Analysis Skill

Quantifies how assets move together, exposes hidden concentration, and measures market sensitivity.

## Capabilities

- **Correlation Matrix**: Pairwise return correlations
- **Average Correlation**: Portfolio diversification quality
- **BTC Beta**: Sensitivity of each asset to Bitcoin
- **Most/Least Correlated Pairs**: Pair selection for hedging or diversification
- **Diversification Verdict**: poor / moderate / good

## Tools

### calculate_correlation_matrix
Correlation matrix + betas for a list of symbols.
- Parameters: symbols (array), days (default 90)

### compare_coins
Compare fundamentals alongside correlation.

## Interpretation

- Correlation > 0.8: near-duplicate exposure — adding it does not diversify
- Avg correlation > 0.8: portfolio is effectively one BTC bet
- Beta > 1.5: high-beta, amplifies BTC moves both ways
- Beta < 0.8: relative resilience in drawdowns
- Negative/low correlation: genuine diversifier (rare in crypto)

## Examples

```
"What is the correlation between BTC, ETH, SOL and AVAX?"
"Which of my coins are most correlated?"
"Calculate beta to BTC for these alts"
"Find the least correlated pair among these tokens"
```

## Integration

Used by portfolio_analysis for allocation and by risk_analysis for concentration risk.