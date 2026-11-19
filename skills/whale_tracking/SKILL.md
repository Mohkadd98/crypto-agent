---
name: whale_tracking
display_name: Whale Tracking
description: Tracks whale wallets and large transactions
version: 1.0.0
dependencies: ["market_scanner"]
required_apis: ["blockchain_rpc", "etherscan", "bscscan"]
available_tools:
  - track_wallet
  - analyze_wallet_history
  - detect_whale_transactions
  - analyze_exchange_flows
  - identify_wallet_clusters
  - monitor_token_holders
priority: 4
is_core: false
config:
  min_whale_value_usd: 100000
  lookback_blocks: 100
  top_holders_limit: 100
---

# Whale Tracking Skill

Monitors large wallet activity, whale transactions, and institutional movements on-chain.

## Capabilities

- **Wallet Analysis**: Comprehensive wallet profiling (balance, transaction history, labels)
- **Transaction History**: Detailed transaction analysis with token transfers
- **Whale Detection**: Large transaction monitoring in recent blocks
- **Exchange Flows**: Exchange inflow/outflow tracking
- **Wallet Clustering**: Identify related wallet groups
- **Token Holder Monitoring**: Top holder concentration analysis

## Tools

### track_wallet
Comprehensive wallet analysis including balance, transaction count, labels.
- Parameters: chain (string), address (string), max_txs (integer)

### analyze_wallet_history
Get transaction history for a wallet with token transfers.
- Parameters: chain, address, limit (100), include_tokens (boolean)

### detect_whale_transactions
Detect large whale transactions in recent blocks.
- Parameters: chain, min_value_usd (100000), lookback_blocks (100)

### analyze_exchange_flows
Analyze exchange inflows and outflows for specific addresses.
- Parameters: chain, exchange_addresses (array), lookback_blocks (1000)

### identify_wallet_clusters
Identify clusters of wallets that interact frequently.
- Parameters: chain, addresses (array), min_shared_txs (3)

### monitor_token_holders
Get top token holders with balance distribution.
- Parameters: chain, token_address, limit (100)

## Usage Examples

```
"Track whale wallet 0x123... on Ethereum"
"Show me large transactions >$100k on BSC in last 100 blocks"
"Analyze exchange flows for Binance hot wallets"
"Find wallet clusters for PEPE token"
"Monitor top 50 holders of SHIB"
"Analyze transaction history of 0xabc... on Arbitrum"
```

## Supported Chains

- Ethereum (requires ETH_RPC_URL, ETHERSCAN_API_KEY)
- BSC (requires BSC_RPC_URL, BSCSCAN_API_KEY)
- Polygon (requires POLYGON_RPC_URL, POLYGONSCAN_API_KEY)
- Arbitrum (requires ARBITRUM_RPC_URL, ARBISCAN_API_KEY)
- Optimism (requires OPTIMISM_RPC_URL, OPTIMISTIC_ETHERSCAN_API_KEY)
- Base (requires BASE_RPC_URL, BASESCAN_API_KEY)
- Avalanche (requires AVALANCHE_RPC_URL, SNOWTRACE_API_KEY)

## Configuration

Requires RPC endpoints and block explorer API keys in config/api_keys.env:
```
ETH_RPC_URL=https://eth-mainnet.g.alchemy.com/v2/your_key
ETHERSCAN_API_KEY=your_key
BSC_RPC_URL=https://bsc-dataseed1.binance.org
BSCSCAN_API_KEY=your_key
```

## Integration

Works with smart_money for institutional detection. Provides on-chain context for technical_analysis signals.