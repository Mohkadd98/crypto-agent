---
name: smart_money
display_name: Smart Money Detection
description: Identifies smart money movements and institutional activity
version: 1.0.0
dependencies: ["whale_tracking"]
required_apis: ["blockchain_rpc", "nansen", "arkham"]
available_tools:
  - track_wallet
  - analyze_wallet_history
  - identify_wallet_clusters
  - analyze_exchange_flows
priority: 5
is_core: false
config:
  known_smart_wallets: []
  min_confidence: 0.7
---

# Smart Money Detection Skill

Identifies institutional and "smart money" activity through advanced wallet labeling and behavioral analysis.

## Capabilities

- **Institutional Wallet Identification**: Known fund/VC/institution wallets
- **Accumulation Detection**: Smart money accumulation patterns
- **Distribution Detection**: Smart money distribution/selling
- **Behavioral Analysis**: Win rate, holding period, position sizing analysis
- **Copy Trading Signals**: Actionable signals from smart money moves

## Tools

### track_wallet
Analyze wallet for smart money characteristics.
- Parameters: chain, address, max_txs

### analyze_wallet_history
Deep dive into wallet trading behavior.
- Parameters: chain, address, limit, include_tokens

### identify_wallet_clusters
Find networks of related smart money wallets.
- Parameters: chain, addresses, min_shared_txs

### analyze_exchange_flows
Track institutional exchange deposit/withdrawal patterns.
- Parameters: chain, exchange_addresses, lookback_blocks

## Usage Examples

```
"Identify smart money wallets accumulating ARB"
"Show me wallets with >70% win rate on SOL"
"Track institutional flows for new token launches"
"Find wallets that bought ETH at $1000 and still hold"
"Analyze VC wallet unlock and sell patterns"
```

## Smart Money Labels

- **Institution**: Known fund, bank, corporate treasury
- **VC/Investor**: Venture capital, early investor
- **Market Maker**: Liquidity provider, market maker
- **Whale**: Large holder, unclear sophistication
- **Insider**: Team, advisor, early contributor
- **Smart Retail**: High win rate, sophisticated retail

## Data Sources

- Nansen API (institutional labels, smart money tags)
- Arkham Intelligence (entity labeling, flow tracking)
- Custom wallet database (curated known addresses)
- On-chain heuristics (behavioral patterns)

## Configuration

Requires additional API keys:
```
NANSEN_API_KEY=your_key
ARKHAM_API_KEY=your_key
```

## Integration

Builds on whale_tracking for base on-chain data. Enhances risk_analysis with smart money signals.