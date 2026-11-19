---
name: market_scanner
display_name: Market Scanner
description: Scans markets for opportunities based on volume, price action, and liquidity
version: 1.0.0
dependencies: []
required_apis: ["coingecko", "binance"]
available_tools:
  - get_market_overview
  - search_coin
  - get_coin_price
  - get_market_cap
  - get_trading_volume
  - get_historical_ohlcv
  - get_exchange_data
  - scan_market
  - get_top_coins
priority: 1
is_core: true
config:
  default_scan_limit: 50
  min_market_cap: 1000000
  max_market_cap: 10000000000
  min_volume_24h: 50000
---

# Market Scanner Skill

This skill provides comprehensive market scanning capabilities to discover trading opportunities.

## Capabilities

- **Market Overview**: Global market statistics (total market cap, volume, BTC/ETH dominance)
- **Coin Search**: Find coins by name or symbol with fuzzy matching
- **Price Data**: Real-time and historical pricing
- **Market Scanning**: Filter coins by market cap, volume, price change criteria
- **Top Coins**: Rank coins by market cap with key metrics

## Tools

### get_market_overview
Get global cryptocurrency market overview including total market cap, volume, BTC/ETH dominance.

### search_coin
Search for cryptocurrencies by name or symbol.
- Parameters: query (string)

### get_coin_price
Get current price for a specific cryptocurrency.
- Parameters: symbol (string), vs_currency (string, default: "usd")

### get_market_cap
Get market capitalization for a cryptocurrency.
- Parameters: symbol (string)

### get_trading_volume
Get 24h trading volume for a cryptocurrency.
- Parameters: symbol (string)

### get_historical_ohlcv
Get historical OHLCV (Open, High, Low, Close, Volume) data.
- Parameters: symbol (string), timeframe (string: 1h, 4h, 1d, 1w), days (integer), source (string)

### get_exchange_data
Get exchange data (CEX and DEX) for a symbol.
- Parameters: symbol (string)

### scan_market
Scan market for coins meeting specific criteria.
- Parameters: min_market_cap, max_market_cap, min_volume_24h, min_price_change_24h, max_price_change_24h, limit

### get_top_coins
Get top coins by market cap.
- Parameters: limit (integer), vs_currency (string)

## Usage Examples

```
"Scan for coins with market cap between $10M and $100M with high volume"
"Find top 20 gainers in the last 24h"
"Show me coins accumulating with low volatility"
"Get market overview and BTC dominance"
"Search for AI-related tokens"
```

## Integration

This skill is a core skill and loads automatically. It provides foundational market data for other skills.