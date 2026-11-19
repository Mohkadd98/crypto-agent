---
name: liquidity_analysis
display_name: Liquidity Analysis
description: Analyzes DEX liquidity, pool depth, and slippage
version: 1.0.0
dependencies: ["market_scanner"]
required_apis: ["dexscreener", "geckoterminal", "blockchain_rpc"]
available_tools:
  - get_exchange_data
  - get_historical_ohlcv
priority: 7
is_core: false
config:
  min_liquidity_usd: 100000
  max_slippage_pct: 5
---

# Liquidity Analysis Skill

Analyzes decentralized exchange liquidity, pool depth, slippage, and market making quality.

## Capabilities

- **Pool Analysis**: DEX pool liquidity, depth, and composition
- **Slippage Estimation**: Expected slippage for various order sizes
- **Liquidity Distribution**: Concentration across price ranges (Uniswap v3)
- **Volume/Liquidity Ratio**: Capital efficiency metrics
- **Impermanent Loss**: IL estimation for LP positions
- **Cross-DEX Comparison**: Best routing for trades

## Tools

### get_exchange_data
Get DEX pool data for a token.
- Parameters: symbol

### get_historical_ohlcv
Historical pool price/volume data from GeckoTerminal.
- Parameters: network, pool_address, timeframe, limit

## Usage Examples

```
"Analyze liquidity for PEPE on Uniswap V2"
"Compare slippage for $10k buy across DEXs"
"Check WETH/USDC pool depth on Arbitrum"
"Estimate impermanent loss for VOLATILE/USDC pool"
"Find tokens with concentrated liquidity"
```

## Key Metrics

- **TVL (Total Value Locked)**: Total liquidity in USD
- **Pool Depth**: Liquidity within ±2%, ±5%, ±10% of spot
- **Slippage**: Price impact for $1k, $10k, $100k orders
- **Volume/TVL Ratio**: Capital efficiency (higher = better)
- **Fee Tier**: 0.01%, 0.05%, 0.3%, 1% - affects returns
- **Concentration**: Uniswap v3 tick range utilization

## Integration

Used by risk_analysis for liquidity risk. Provides execution context for breakout_detection.