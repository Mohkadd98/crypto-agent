---
name: portfolio_analysis
display_name: Portfolio Analysis
description: Portfolio tracking, performance, and optimization
version: 1.0.0
dependencies: ["market_scanner", "risk_analysis", "technical_analysis"]
required_apis: ["coingecko"]
available_tools:
  - compare_coins
  - calculate_potential_upside
  - calculate_risk_score
  - rank_candidates
priority: 12
is_core: true
config:
  rebalance_threshold: 0.1
  max_position_pct: 0.2
  risk_budget: 0.02
---

# Portfolio Analysis Skill

Portfolio management, performance tracking, risk budgeting, and optimization.

## Capabilities

- **Portfolio Tracking**: Real-time P&L, allocation, performance
- **Risk Budgeting**: Position sizing based on risk parity
- **Correlation Analysis**: Asset correlation matrix
- **Rebalancing Signals**: Drift detection and rebalance recommendations
- **Performance Attribution**: Return decomposition by asset/sector
- **Optimization**: Mean-variance, risk parity, max diversification

## Tools

### compare_coins
Multi-asset comparison for allocation decisions.
- Parameters: coins_data

### calculate_potential_upside
Risk/reward for each position.
- Parameters: coin_data, ohlcv

### calculate_risk_score
Individual asset risk for budgeting.
- Parameters: coin_data, ohlcv

### rank_candidates
Opportunity ranking for new positions.
- Parameters: candidates

## Usage Examples

```
"Show my portfolio performance and allocation"
"Calculate risk parity weights for my holdings"
"When should I rebalance my portfolio?"
"Analyze correlation between my positions"
"Find best risk-adjusted additions to portfolio"
"Stress test portfolio against -50% BTC drop"
```

## Portfolio Metrics

- **Total Value**: Current portfolio value
- **Allocation %**: Per asset and sector
- **Unrealized P&L**: Per asset and total
- **Risk Contribution**: Marginal risk per position
- **Sharpe Ratio**: Risk-adjusted return
- **Max Drawdown**: Peak-to-trough decline
- **Correlation Matrix**: Pairwise correlations
- **Beta to BTC/ETH**: Market sensitivity

## Risk Budgeting

- **Risk per Trade**: 1-2% of portfolio (configurable)
- **Max Position**: 10-20% per asset
- **Sector Limits**: 30% per sector (DeFi, L1, AI, etc.)
- **Stablecoin Reserve**: 5-10% for opportunities

## Rebalancing

- **Threshold**: 10% drift from target (configurable)
- **Frequency**: Check daily, execute weekly max
- **Tax Awareness**: Prefer long-term holdings
- **Cost Optimization**: Batch trades, use limit orders

## Integration

Core skill for portfolio management. Consumes risk_analysis for risk budgeting, technical_analysis for entry/exit timing, market_scanner for opportunity discovery.