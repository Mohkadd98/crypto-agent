"""
Strategy Learning & Backtesting Skill for the Crypto Intelligence Agent.
Strategy creation, backtesting, optimization, and self-learning pattern discovery.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from core.skill_registry import Skill, SkillStatus


@dataclass
class StrategyLearningConfig:
    """Configuration for strategy learning skill."""
    default_lookback_days: int = 365
    min_pattern_occurrences: int = 5
    min_pattern_win_rate: float = 0.55
    default_risk_per_trade: float = 0.02
    default_stop_loss_pct: float = 0.05
    default_take_profit_pct: float = 0.10
    optimization_metric: str = "sharpe_ratio"


class StrategyLearningSkill(Skill):
    """Strategy learning and backtesting skill implementation."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(
            name="strategy_learning",
            display_name="Strategy Learning & Backtesting",
            description="Strategy creation, backtesting engine, parameter optimization, and self-learning pattern discovery",
            version="1.0.0",
            status=SkillStatus.INSTALLED,
            dependencies=["market_scanner", "technical_analysis", "paper_trading", "risk_analysis"],
            required_apis=[],
            available_tools=[
                "create_strategy",
                "get_strategy",
                "list_strategies",
                "backtest_strategy",
                "run_multi_symbol_backtest",
                "optimize_strategy_parameters",
                "discover_patterns",
                "get_learning_patterns",
                "validate_pattern",
                "get_backtest_results",
                "get_strategy_performance"
            ],
            instructions="""
Strategy Learning & Backtesting Skill Instructions:

This skill provides a complete strategy lifecycle management system:
1. Strategy Creation: Define strategies with entry/exit/risk rules
2. Backtesting: Vectorized historical simulation with comprehensive metrics
3. Optimization: Grid search for optimal parameters
4. Self-Learning: Automatically discover profitable patterns from data
5. Paper Deployment: Test strategies in paper trading before live

Strategy Types:
- trend_following: EMA crossover with RSI filter
- mean_reversion: RSI oversold + Bollinger Band bounce
- breakout: Price breaks 20-day high with volume
- custom: User-defined rules

Backtest Metrics:
- Total Return, Annualized Return
- Win Rate, Profit Factor
- Sharpe Ratio, Sortino Ratio, Calmar Ratio
- Max Drawdown, Expectancy
- Equity curve with trade-by-trade detail

Self-Learning Patterns Discovered:
1. RSI Oversold + Above EMA20 (mean reversion)
2. MACD Bullish Crossover (momentum)
3. Bollinger Band Squeeze Breakout (volatility expansion)
4. Volume Spike on Support (accumulation)
5. EMA Trend Filter (regime detection)

Workflow:
1. Create strategy: create_strategy(...)
2. Backtest: backtest_strategy(strategy_id, symbol, timeframe, ...)
3. Optimize: optimize_strategy_parameters(strategy_id, symbol, param_grid)
4. Discover patterns: discover_patterns(session_id, symbol, ...)
5. Deploy to paper: open_paper_position(..., strategy_id=strategy_id)
6. Track performance: get_strategy_performance(strategy_id)

Integration:
- Uses market_scanner for universe selection
- Uses technical_analysis for indicator calculations
- Works with paper_trading for live simulation
- Feeds risk_analysis for position sizing
            """,
            config=config or {}
        )
        self.learning_config = StrategyLearningConfig(**(config or {}))
    
    def get_default_config(self) -> Dict[str, Any]:
        return {
            "default_lookback_days": self.learning_config.default_lookback_days,
            "min_pattern_occurrences": self.learning_config.min_pattern_occurrences,
            "min_pattern_win_rate": self.learning_config.min_pattern_win_rate,
            "default_risk_per_trade": self.learning_config.default_risk_per_trade,
            "default_stop_loss_pct": self.learning_config.default_stop_loss_pct,
            "default_take_profit_pct": self.learning_config.default_take_profit_pct,
            "optimization_metric": self.learning_config.optimization_metric
        }
    
    async def initialize(self) -> bool:
        """Initialize the strategy learning skill."""
        self.status = SkillStatus.ACTIVE
        return True
    
    async def shutdown(self) -> None:
        """Shutdown the skill."""
        self.status = SkillStatus.INACTIVE
    
    def get_capabilities(self) -> List[str]:
        return [
            "Strategy definition and management",
            "Vectorized backtesting with comprehensive metrics",
            "Parameter optimization via grid search",
            "Multi-symbol backtesting",
            "Self-learning pattern discovery from price data",
            "Pattern validation on out-of-sample data",
            "Performance tracking and history",
            "Paper trading deployment integration"
        ]


def create_strategy_learning_skill(config: Optional[Dict] = None) -> StrategyLearningSkill:
    return StrategyLearningSkill(config)