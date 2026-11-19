"""
Paper Trading Skill for the Crypto Intelligence Agent.
Virtual trading account management and performance analytics.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from core.skill_registry import Skill, SkillStatus


@dataclass
class PaperTradingConfig:
    """Configuration for paper trading skill."""
    default_initial_balance: float = 10000.0
    default_fee_pct: float = 0.001
    max_positions_per_account: int = 10
    auto_sl_tp_check: bool = True


class PaperTradingSkill(Skill):
    """Paper trading skill implementation."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(
            name="paper_trading",
            display_name="Paper Trading",
            description="Virtual trading account management, position tracking, and performance analytics without real capital risk",
            version="1.0.0",
            status=SkillStatus.INSTALLED,
            dependencies=["market_scanner", "technical_analysis", "risk_analysis"],
            required_apis=[],
            available_tools=[
                "create_paper_account",
                "get_paper_account",
                "list_paper_accounts",
                "open_paper_position",
                "close_paper_position",
                "update_paper_positions",
                "get_paper_account_stats",
                "get_paper_trades"
            ],
            instructions="""
Paper Trading Skill Instructions:

This skill provides a complete virtual trading environment for testing strategies 
without risking real capital. All trades are simulated with realistic fee structures,
slippage, and risk controls.

Key Features:
1. Multiple paper accounts per session
2. Real-time P&L tracking with fee simulation (0.1% default)
3. Stop loss / Take profit automatic execution
4. Position sizing based on risk percentage
5. Comprehensive performance analytics (Sharpe, Sortino, Calmar, Max DD, Expectancy)

Workflow:
1. Create account: create_paper_account(session_id, name, initial_balance)
2. Open positions based on analysis: open_paper_position(account_id, symbol, side, qty, entry, sl, tp)
3. Update prices periodically: update_paper_positions(account_id, {symbol: price})
4. Monitor performance: get_paper_account_stats(account_id)
5. Close positions: close_paper_position(account_id, position_id, exit_price)

Risk Management:
- Default 2% risk per trade
- Automatic SL/TP checking on price updates
- Max positions per account limit
- Fee simulation on every trade

Integration:
- Works with technical_analysis signals for entry/exit
- Compatible with strategy_learning for backtested strategy deployment
- Trade journal integration for learning from paper trades
            """,
            config=config or {}
        )
        self.paper_config = PaperTradingConfig(**(config or {}))
    
    def get_default_config(self) -> Dict[str, Any]:
        return {
            "default_initial_balance": self.paper_config.default_initial_balance,
            "default_fee_pct": self.paper_config.default_fee_pct,
            "max_positions_per_account": self.paper_config.max_positions_per_account,
            "auto_sl_tp_check": self.paper_config.auto_sl_tp_check
        }
    
    async def initialize(self) -> bool:
        """Initialize the paper trading skill."""
        self.status = SkillStatus.ACTIVE
        return True
    
    async def shutdown(self) -> None:
        """Shutdown the skill."""
        self.status = SkillStatus.INACTIVE
    
    def get_capabilities(self) -> List[str]:
        return [
            "Virtual account management",
            "Position opening/closing with SL/TP",
            "Real-time P&L tracking",
            "Performance analytics (Sharpe, Sortino, Max DD, Expectancy)",
            "Trade history and audit trail",
            "Multi-account support",
            "Strategy integration for paper deployment"
        ]


# Factory function for skill registry
def create_paper_trading_skill(config: Optional[Dict] = None) -> PaperTradingSkill:
    return PaperTradingSkill(config)