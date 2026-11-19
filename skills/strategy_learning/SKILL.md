---
name: strategy_learning
display_name: Strategy Learning & Backtesting
description: Strategy creation, backtesting engine, parameter optimization, and self-learning pattern discovery
version: 1.0.0
dependencies: ["market_scanner", "technical_analysis", "paper_trading", "risk_analysis"]
required_apis: []
available_tools:
  - create_strategy
  - get_strategy
  - list_strategies
  - backtest_strategy
  - run_multi_symbol_backtest
  - optimize_strategy_parameters
  - discover_patterns
  - get_learning_patterns
  - validate_pattern
  - get_backtest_results
  - get_strategy_performance
priority: 16
is_core: false
config:
  default_lookback_days: 365
  min_pattern_occurrences: 5
  min_pattern_win_rate: 0.55
  default_risk_per_trade: 0.02
  default_stop_loss_pct: 0.05
  default_take_profit_pct: 0.10
  optimization_metric: "sharpe_ratio"
---

# Strategy Learning & Backtesting Skill

Complete strategy lifecycle management: creation, backtesting, optimization, and self-learning.

## Capabilities

- **Strategy Definition**: Create strategies with entry/exit/risk rules
- **Vectorized Backtesting**: Fast historical simulation with detailed metrics
- **Parameter Optimization**: Grid search for optimal parameters
- **Multi-Symbol Testing**: Test strategies across multiple assets
- **Self-Learning Pattern Discovery**: Automatically find recurring profitable patterns
- **Performance Tracking**: Track strategy performance over time
- **Paper Trading Integration**: Deploy strategies to paper accounts

## Tools

### create_strategy
Create a new trading strategy.
- Parameters: session_id, name, description, strategy_type (trend_following/mean_reversion/breakout), parameters, entry_rules, exit_rules, risk_rules, symbols, timeframes

### get_strategy
Get strategy details by ID.

### list_strategies
List strategies with filters.

### backtest_strategy
Run backtest on historical data.
- Parameters: strategy_id, symbol, timeframe, start_date, end_date, initial_balance, parameters_override
- Returns: Complete metrics (Sharpe, Sortino, Calmar, Max DD, Win Rate, Profit Factor, Expectancy, equity curve)

### run_multi_symbol_backtest
Test strategy across multiple symbols simultaneously.

### optimize_strategy_parameters
Grid search optimization for best parameters.
- Parameters: strategy_id, symbol, param_grid, metric (sharpe_ratio/sortino_ratio/calmar_ratio/win_rate)

### discover_patterns
Self-learning: discover recurring patterns from price data.
- Parameters: session_id, symbol, timeframe, lookback_days, min_occurrences, min_win_rate
- Automatically finds: RSI oversold bounces, MACD crossovers, BB squeeze breakouts, volume spikes on support

### get_learning_patterns
Retrieve discovered patterns.

### validate_pattern
Validate a pattern on out-of-sample data.

### get_backtest_results
Get historical backtest results.

### get_strategy_performance
Get complete strategy performance history.

## Strategy Types

- **trend_following**: EMA crossover + RSI filter
- **mean_reversion**: RSI oversold + Bollinger Band bounce
- **breakout**: Price breaks 20-day high with volume confirmation
- **custom**: User-defined rules

## Risk Rules Parameters

- risk_per_trade: Position size as % of equity (default 2%)
- stop_loss_pct: Stop loss percentage (default 5%)
- take_profit_pct: Take profit percentage (default 10%)
- max_positions: Maximum concurrent positions

## Usage Examples

```
/strategy create "EMA Trend" "EMA crossover trend follower" trend_following \
  '{"ema_fast":12,"ema_slow":26,"rsi_period":14}' \
  '{"rsi_filter":true,"rsi_max":70}' \
  '{"rsi_exit":75,"trail_pct":0.02}' \
  '{"risk_per_trade":0.02,"stop_loss_pct":0.05,"take_profit_pct":0.10}' \
  "BTC,ETH,SOL" "1d,4h"

/backtest 1 BTC --start 2024-01-01 --end 2024-12-31

/optimize 1 BTC '{"ema_fast":[8,12,16],"ema_slow":[21,26,30],"rsi_max":[65,70,75]}' --metric sharpe_ratio

/learn BTC --days 365 --min-occ 10 --min-wr 0.55
```