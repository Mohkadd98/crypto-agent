---
name: paper_trading
display_name: Paper Trading
description: Virtual trading account management, position tracking, and performance analytics without real capital risk
version: 1.0.0
dependencies: ["market_scanner", "technical_analysis", "risk_analysis"]
required_apis: []
available_tools:
  - create_paper_account
  - get_paper_account
  - list_paper_accounts
  - open_paper_position
  - close_paper_position
  - update_paper_positions
  - get_paper_account_stats
  - get_paper_trades
priority: 15
is_core: false
config:
  default_initial_balance: 10000.0
  default_fee_pct: 0.001
  max_positions_per_account: 10
  auto_sl_tp_check: true
---

# Paper Trading Skill

Virtual trading environment for testing strategies without real capital risk.

## Capabilities

- **Account Management**: Create and manage multiple paper trading accounts
- **Position Management**: Open, close, and monitor virtual positions
- **Real-time P&L**: Track unrealized and realized P&L with fee simulation
- **Risk Controls**: Stop loss, take profit, position sizing
- **Performance Analytics**: Win rate, Sharpe ratio, max drawdown, expectancy
- **Trade History**: Complete audit trail of all paper trades

## Tools

### create_paper_account
Create a new virtual trading account.
- Parameters: session_id, name, initial_balance (default 10000 USDT)

### get_paper_account
Get account details including open positions and recent trades.
- Parameters: account_id

### list_paper_accounts
List all paper accounts for a session.
- Parameters: session_id

### open_paper_position
Open a new paper trading position.
- Parameters: account_id, symbol, side (long/short), quantity, entry_price, stop_loss, take_profit, strategy_id, signal_data, market_context

### close_paper_position
Close a position fully or partially.
- Parameters: account_id, position_id, exit_price, quantity, reason

### update_paper_positions
Update current prices for all positions and check SL/TP.
- Parameters: account_id, prices (symbol -> price mapping)

### get_paper_account_stats
Get comprehensive performance statistics.
- Parameters: account_id

### get_paper_trades
Get trade history for an account.
- Parameters: account_id, symbol (optional), limit (default 100)

## Usage Examples

```
/paper create "Test Account" 50000
/paper open 1 BTC long 0.1 45000 --sl 43000 --tp 50000
/paper close 1 5 47000 --reason take_profit
/paper stats 1
/paper trades 1
```