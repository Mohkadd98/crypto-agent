---
name: risk_analysis
display_name: Risk Analysis
description: Calculates risk scores and scenario analysis
version: 1.0.0
dependencies: ["technical_analysis", "tokenomics", "liquidity_analysis"]
required_apis: []
available_tools:
  - calculate_risk_score
  - rank_candidates
  - evaluate_tokenomics
  - analyze_token_unlocks
priority: 10
is_core: true
config:
  max_drawdown_threshold: 0.5
  volatility_threshold: 0.8
  liquidity_risk_threshold: 0.3
  concentration_risk_threshold: 0.4
---

# Risk Analysis Skill

Comprehensive risk assessment with multi-factor scoring and scenario analysis.

## Capabilities

- **Risk Scoring**: 0-100 risk score across multiple dimensions
- **Scenario Analysis**: Bullish/neutral/bearish price targets
- **Position Sizing**: Kelly criterion and risk-based sizing
- **Portfolio Risk**: Correlation, concentration, drawdown analysis
- **Stress Testing**: Historical worst-case scenarios

## Tools

### calculate_risk_score
Multi-factor risk score (0-100, lower = safer).
- Parameters: coin_data, ohlcv (optional)

### rank_candidates
Rank coins by risk-adjusted opportunity score.
- Parameters: candidates (array)

### evaluate_tokenomics
Tokenomics quality affecting fundamental risk.
- Parameters: coin_data

### analyze_token_unlocks
Dilution risk from upcoming unlocks.
- Parameters: coin_data, unlock_schedule

## Usage Examples

```
"Calculate risk score for my watchlist"
"Rank these 10 coins by risk-adjusted potential"
"What's the worst-case scenario for PEPE?"
"Determine position size for SOL with 2% risk"
"Stress test portfolio against 2022 crash"
```

## Risk Factors (100 points max)

### Market Cap Risk (25 pts)
- Micro <$10M: 25
- Small $10-50M: 15
- Mid $50-200M: 8
- Large $200M-1B: 3
- Mega >$1B: 0

### Liquidity Risk (20 pts)
- Vol/MCap <1%: 20
- 1-5%: 10
- 5-10%: 3
- >10%: 0

### Volatility Risk (20 pts)
- Annualized >150%: 20
- 100-150%: 12
- 60-100%: 6
- <60%: 0

### Supply/Dilution Risk (15 pts)
- Circulating <30%: 15
- 30-50%: 8
- 50-80%: 3
- >80%: 0

### Momentum Risk (10 pts)
- 24h >50%: 10 (reversal risk)
- 24h <-30%: 5 (momentum risk)
- 7d >100%: 8 (parabolic)
- Normal: 0

### Technical Risk (10 pts)
- Below all EMAs: 5
- RSI >80: 3
- At resistance: 2
- Healthy structure: 0

## Risk Levels

- **Very Low (0-15)**: Core allocation appropriate
- **Low (16-30)**: Standard position sizing
- **Moderate (31-50)**: Reduced size, strict stops
- **High (51-70)**: Small size only, experienced only
- **Extreme (71-100)**: Avoid or lottery ticket only

## Scenario Framework

For each coin, provides:
- **Bullish**: Target, probability, catalysts
- **Neutral**: Range, probability, conditions
- **Bearish**: Stop, probability, triggers

## Integration

Consumes tokenomics for fundamental risk, technical_analysis for technical risk, liquidity_analysis for execution risk. Feeds portfolio_analysis for allocation.