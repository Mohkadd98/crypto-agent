---
name: trade_journal
display_name: Trade Journal
description: Record trades and analyze win rate, PnL and profit factor
version: 1.0.0
dependencies: []
required_apis: []
available_tools:
  - add_trade
  - close_trade
  - list_trades
  - get_trade_stats
priority: 27
is_core: false
config:
  default_risk_pct: 2.0
---

# Trade Journal Skill

Turns the agent into a disciplined trading journal with performance analytics.

## Capabilities

- **Log Trades**: Symbol, side, entry, size, stop, target, notes, tags
- **Close Trades**: Exit price → automatic PnL and PnL%
- **List Trades**: Filter by status (open/closed) and symbol
- **Statistics**: Win rate, total/average PnL, best/worst, profit factor

## Tools

### add_trade
Open a new journal entry.
- Parameters: symbol, side (long/short), entry_price, quantity, stop_loss, take_profit, notes, tags

### close_trade
Close a trade and compute PnL.
- Parameters: trade_id, exit_price, notes

### list_trades
List journal entries.
- Parameters: status, symbol, limit

### get_trade_stats
Aggregate performance.
- Parameters: none

## Interpretation

- Win rate > 50% with profit factor > 1.5: healthy edge
- Profit factor < 1: strategy loses money — review process
- Large gap between best and worst trade: sizing inconsistency
- Use tags (setup, sector) to find what actually works

## Examples

```
"Add a long trade on SOL at 145 with 2% risk"
"Close trade 3 at 172"
"Show my open trades"
"What is my win rate and profit factor?"
```

## Integration

Consumes risk_analysis sizing; stores results in the session database.