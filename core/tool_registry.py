"""
Tool registry for the Crypto Intelligence Agent.
Manages tool registration, discovery, and execution.
"""

import inspect
import json
from typing import Dict, List, Any, Callable, Optional, Awaitable
from dataclasses import dataclass, field
from functools import wraps


@dataclass
class Tool:
    """Represents a registered tool."""
    name: str
    description: str
    function: Callable[..., Awaitable[Any]]
    parameters: Dict[str, Any]
    category: str
    skill_name: Optional[str] = None
    required_params: List[str] = field(default_factory=list)
    returns: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Derive required parameters from the JSON schema when not given."""
        if not self.required_params and isinstance(self.parameters, dict):
            self.required_params = list(self.parameters.get("required", []))


class ToolRegistry:
    """Registry for all available tools."""
    
    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        self._categories: Dict[str, List[str]] = {}
    
    def register(
        self,
        name: str,
        description: str,
        category: str,
        skill_name: Optional[str] = None,
        parameters: Optional[Dict] = None,
        required_params: Optional[List[str]] = None
    ):
        """Decorator to register a tool function."""
        def decorator(func: Callable[..., Awaitable[Any]]):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                return await func(*args, **kwargs)
            
            # Extract parameter info from function signature if not provided
            if parameters is None:
                sig = inspect.signature(func)
                params = {}
                required = []
                for param_name, param in sig.parameters.items():
                    if param_name in ('self', 'cls'):
                        continue
                    param_info = {"type": "string"}  # Default
                    if param.annotation != inspect.Parameter.empty:
                        if param.annotation == int:
                            param_info["type"] = "integer"
                        elif param.annotation == float:
                            param_info["type"] = "number"
                        elif param.annotation == bool:
                            param_info["type"] = "boolean"
                        elif param.annotation == list:
                            param_info["type"] = "array"
                        elif param.annotation == dict:
                            param_info["type"] = "object"
                    params[param_name] = param_info
                    if param.default == inspect.Parameter.empty:
                        required.append(param_name)
            else:
                params = parameters
                required = required_params or []
            
            tool = Tool(
                name=name,
                description=description,
                function=wrapper,
                parameters={
                    "type": "object",
                    "properties": params,
                    "required": required
                },
                category=category,
                skill_name=skill_name,
                required_params=required
            )
            
            self._tools[name] = tool
            
            if category not in self._categories:
                self._categories[category] = []
            self._categories[category].append(name)
            
            return wrapper
        return decorator
    
    def register_tool(self, tool: Tool) -> None:
        """Register a Tool object directly."""
        self._tools[tool.name] = tool
        if tool.category not in self._categories:
            self._categories[tool.category] = []
        if tool.name not in self._categories[tool.category]:
            self._categories[tool.category].append(tool.name)
    
    def get_tool(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def get_tools_by_category(self, category: str) -> List[Tool]:
        """Get all tools in a category."""
        tool_names = self._categories.get(category, [])
        return [self._tools[name] for name in tool_names if name in self._tools]
    
    def get_tools_by_skill(self, skill_name: str) -> List[Tool]:
        """Get all tools associated with a skill."""
        return [tool for tool in self._tools.values() if tool.skill_name == skill_name]
    
    def list_tools(self) -> List[Dict]:
        """List all registered tools."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "category": tool.category,
                "skill_name": tool.skill_name,
                "parameters": tool.parameters,
                "required_params": tool.required_params
            }
            for tool in self._tools.values()
        ]
    
    def list_categories(self) -> List[str]:
        """List all tool categories."""
        return list(self._categories.keys())
    
    async def execute(self, name: str, **kwargs) -> Any:
        """Execute a tool by name."""
        tool = self._tools.get(name)
        if not tool:
            raise ValueError(f"Tool '{name}' not found")
        
        # Validate required parameters
        for param in tool.required_params:
            if param not in kwargs:
                raise ValueError(f"Required parameter '{param}' missing for tool '{name}'")
        
        return await tool.function(**kwargs)
    
    def get_function_definitions(self, category: Optional[str] = None, skill_name: Optional[str] = None) -> List[Dict]:
        """Get OpenAI function definitions for tools."""
        tools = self._tools.values()
        
        if category:
            tools = [t for t in tools if t.category == category]
        if skill_name:
            tools = [t for t in tools if t.skill_name == skill_name]
        
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters
                }
            }
            for tool in tools
        ]
    
    def unregister(self, name: str) -> bool:
        """Unregister a tool."""
        if name in self._tools:
            tool = self._tools.pop(name)
            if tool.category in self._categories:
                self._categories[tool.category] = [
                    n for n in self._categories[tool.category] if n != name
                ]
            return True
        return False
    
    def clear(self) -> None:
        """Clear all tools."""
        self._tools.clear()
        self._categories.clear()


# Global tool registry instance
_tool_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """Get the global tool registry instance."""
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry()
    return _tool_registry


def register_all_tools() -> None:
    """Register all built-in tools."""
    registry = get_tool_registry()
    
    # Import tool modules
    from tools.market_tools import (
        get_market_overview, search_coin, get_coin_price, get_market_cap,
        get_trading_volume, get_historical_ohlcv, get_exchange_data,
        scan_market, get_top_coins, MARKET_TOOL_DEFINITIONS
    )
    from tools.technical_tools import (
        calculate_rsi, calculate_macd, calculate_ema, calculate_obv,
        calculate_atr, detect_support_resistance, detect_breakout,
        detect_accumulation, analyze_market_structure, full_technical_analysis,
        TECHNICAL_TOOL_DEFINITIONS
    )
    from tools.onchain_tools import (
        track_wallet, analyze_wallet_history, detect_whale_transactions,
        analyze_exchange_flows, identify_wallet_clusters, monitor_token_holders,
        get_token_info, get_wallet_token_balances, ONCHAIN_TOOL_DEFINITIONS
    )
    from tools.research_tools import (
        compare_coins, search_historical_patterns, calculate_potential_upside,
        evaluate_tokenomics, analyze_token_unlocks, calculate_risk_score,
        rank_candidates, web_search, RESEARCH_TOOL_DEFINITIONS
    )
    from tools.advanced_tools import (
        get_derivatives_analysis, get_market_breadth, calculate_correlation_matrix,
        get_sector_performance, analyze_order_book, calculate_fibonacci,
        calculate_volume_profile, analyze_volatility, scan_momentum,
        calculate_mean_reversion, calculate_ichimoku, analyze_wyckoff,
        scan_new_pairs, get_gas_prices, ADVANCED_TOOL_DEFINITIONS
    )
    from tools.journal_tools import (
        add_trade, close_trade, list_trades, get_trade_stats,
        TRADE_JOURNAL_TOOL_DEFINITIONS
    )
    from tools.paper_trading_tools import (
        create_paper_account, get_paper_account, list_paper_accounts,
        open_paper_position, close_paper_position, update_paper_positions,
        get_paper_account_stats, get_paper_trades, PAPER_TRADING_TOOL_DEFINITIONS
    )
    from tools.strategy_tools import (
        create_strategy, get_strategy, list_strategies, backtest_strategy,
        run_multi_symbol_backtest, optimize_strategy_parameters, discover_patterns,
        get_learning_patterns, validate_pattern, get_backtest_results,
        get_strategy_performance, STRATEGY_TOOL_DEFINITIONS
    )
    
    # Register market tools
    market_tools = [
        (get_market_overview, "Get global cryptocurrency market overview"),
        (search_coin, "Search for cryptocurrencies by name or symbol"),
        (get_coin_price, "Get current price for a specific cryptocurrency"),
        (get_market_cap, "Get market capitalization for a cryptocurrency"),
        (get_trading_volume, "Get 24h trading volume for a cryptocurrency"),
        (get_historical_ohlcv, "Get historical OHLCV data"),
        (get_exchange_data, "Get exchange data (CEX and DEX) for a symbol"),
        (scan_market, "Scan market for coins meeting specific criteria"),
        (get_top_coins, "Get top coins by market cap"),
    ]
    
    for func, desc in market_tools:
        # Find the definition
        defn = next((d for d in MARKET_TOOL_DEFINITIONS if d["function"]["name"] == func.__name__), None)
        if defn:
            registry.register_tool(Tool(
                name=func.__name__,
                description=desc,
                function=func,
                parameters=defn["function"]["parameters"],
                category="market",
                skill_name="market_scanner"
            ))
    
    # Register technical tools
    technical_tools = [
        (calculate_rsi, "Calculate Relative Strength Index (RSI)"),
        (calculate_macd, "Calculate MACD (Moving Average Convergence Divergence)"),
        (calculate_ema, "Calculate Exponential Moving Averages"),
        (calculate_obv, "Calculate On-Balance Volume"),
        (calculate_atr, "Calculate Average True Range"),
        (detect_support_resistance, "Detect support and resistance levels"),
        (detect_breakout, "Detect breakout patterns"),
        (detect_accumulation, "Detect accumulation patterns"),
        (analyze_market_structure, "Analyze market structure (trends, swing points)"),
        (full_technical_analysis, "Perform complete technical analysis with all indicators"),
    ]
    
    for func, desc in technical_tools:
        defn = next((d for d in TECHNICAL_TOOL_DEFINITIONS if d["function"]["name"] == func.__name__), None)
        if defn:
            registry.register_tool(Tool(
                name=func.__name__,
                description=desc,
                function=func,
                parameters=defn["function"]["parameters"],
                category="technical",
                skill_name="technical_analysis"
            ))
    
    # Register on-chain tools
    onchain_tools = [
        (track_wallet, "Comprehensive wallet analysis"),
        (analyze_wallet_history, "Get transaction history for a wallet"),
        (detect_whale_transactions, "Detect large whale transactions"),
        (analyze_exchange_flows, "Analyze exchange inflows and outflows"),
        (identify_wallet_clusters, "Identify clusters of wallets that interact frequently"),
        (monitor_token_holders, "Get top token holders"),
        (get_token_info, "Get ERC20 token information"),
        (get_wallet_token_balances, "Get multiple token balances for a wallet"),
    ]
    
    for func, desc in onchain_tools:
        defn = next((d for d in ONCHAIN_TOOL_DEFINITIONS if d["function"]["name"] == func.__name__), None)
        if defn:
            registry.register_tool(Tool(
                name=func.__name__,
                description=desc,
                function=func,
                parameters=defn["function"]["parameters"],
                category="onchain",
                skill_name="whale_tracking"
            ))
    
    # Register research tools
    research_tools = [
        (compare_coins, "Compare multiple coins across key metrics"),
        (search_historical_patterns, "Search for historical chart patterns"),
        (calculate_potential_upside, "Calculate potential upside with risk/reward scenarios"),
        (evaluate_tokenomics, "Evaluate tokenomics quality and dilution risk"),
        (analyze_token_unlocks, "Analyze upcoming token unlocks and potential impact"),
        (calculate_risk_score, "Calculate comprehensive risk score"),
        (rank_candidates, "Rank candidate coins by opportunity score"),
        (web_search, "Search the web for news, context and research about a topic or coin"),
    ]
    
    for func, desc in research_tools:
        defn = next((d for d in RESEARCH_TOOL_DEFINITIONS if d["function"]["name"] == func.__name__), None)
        if defn:
            registry.register_tool(Tool(
                name=func.__name__,
                description=desc,
                function=func,
                parameters=defn["function"]["parameters"],
                category="research",
                skill_name="historical_analysis"
            ))
    
    # Register advanced tools (category, skill mapping)
    advanced_tools = [
        (get_derivatives_analysis, "Analyze derivatives: funding, open interest, long/short ratio", "derivatives", "derivatives_analysis"),
        (get_market_breadth, "Measure market breadth and regime", "market", "market_breadth"),
        (calculate_correlation_matrix, "Correlation matrix and BTC beta across coins", "research", "correlation_analysis"),
        (get_sector_performance, "Sector rotation and category performance", "market", "sector_rotation"),
        (analyze_order_book, "Order book depth, imbalance and walls", "market", "order_book_analysis"),
        (calculate_fibonacci, "Fibonacci retracement and extension levels", "technical", "fibonacci_analysis"),
        (calculate_volume_profile, "Volume profile: POC and value area", "technical", "volume_profile"),
        (analyze_volatility, "Realized volatility and regime analysis", "technical", "volatility_analysis"),
        (scan_momentum, "Multi-timeframe momentum scanner", "market", "momentum_scanner"),
        (calculate_mean_reversion, "Mean-reversion z-score and Bollinger %B", "technical", "mean_reversion"),
        (calculate_ichimoku, "Ichimoku cloud analysis", "technical", "ichimoku"),
        (analyze_wyckoff, "Wyckoff accumulation/distribution phase", "technical", "wyckoff_analysis"),
        (scan_new_pairs, "Scan new DEX liquidity pools", "market", "new_token_scanner"),
        (get_gas_prices, "Gas prices across chains", "onchain", "gas_tracker"),
    ]
    
    for func, desc, category, skill_name in advanced_tools:
        defn = next((d for d in ADVANCED_TOOL_DEFINITIONS if d["function"]["name"] == func.__name__), None)
        if defn:
            registry.register_tool(Tool(
                name=func.__name__,
                description=desc,
                function=func,
                parameters=defn["function"]["parameters"],
                category=category,
                skill_name=skill_name
            ))
    
    # Register trade journal tools
    journal_tools = [
        (add_trade, "Open a new trade in the journal"),
        (close_trade, "Close an open trade and compute PnL"),
        (list_trades, "List trades from the journal"),
        (get_trade_stats, "Get aggregate trade statistics"),
    ]
    
    for func, desc in journal_tools:
        defn = next((d for d in TRADE_JOURNAL_TOOL_DEFINITIONS if d["function"]["name"] == func.__name__), None)
        if defn:
            registry.register_tool(Tool(
                name=func.__name__,
                description=desc,
                function=func,
                parameters=defn["function"]["parameters"],
                category="portfolio",
                skill_name="trade_journal"
            ))
    
    # Register paper trading tools
    paper_tools = [
        (create_paper_account, "Create a new virtual paper trading account", "portfolio", "paper_trading"),
        (get_paper_account, "Get paper account details with positions and trades", "portfolio", "paper_trading"),
        (list_paper_accounts, "List all paper accounts for a session", "portfolio", "paper_trading"),
        (open_paper_position, "Open a new paper trading position", "portfolio", "paper_trading"),
        (close_paper_position, "Close a paper trading position", "portfolio", "paper_trading"),
        (update_paper_positions, "Update position prices and check SL/TP", "portfolio", "paper_trading"),
        (get_paper_account_stats, "Get comprehensive paper account statistics", "portfolio", "paper_trading"),
        (get_paper_trades, "Get paper trade history", "portfolio", "paper_trading"),
    ]
    
    for func, desc, category, skill_name in paper_tools:
        defn = next((d for d in PAPER_TRADING_TOOL_DEFINITIONS if d["function"]["name"] == func.__name__), None)
        if defn:
            registry.register_tool(Tool(
                name=func.__name__,
                description=desc,
                function=func,
                parameters=defn["function"]["parameters"],
                category=category,
                skill_name=skill_name
            ))
    
    # Register strategy learning tools
    strategy_tools = [
        (create_strategy, "Create a new trading strategy", "research", "strategy_learning"),
        (get_strategy, "Get a strategy by ID", "research", "strategy_learning"),
        (list_strategies, "List strategies for a session", "research", "strategy_learning"),
        (backtest_strategy, "Run backtest for a strategy on historical data", "research", "strategy_learning"),
        (run_multi_symbol_backtest, "Run backtest across multiple symbols", "research", "strategy_learning"),
        (optimize_strategy_parameters, "Optimize strategy parameters via grid search", "research", "strategy_learning"),
        (discover_patterns, "Discover recurring patterns from historical data", "research", "strategy_learning"),
        (get_learning_patterns, "Get discovered learning patterns", "research", "strategy_learning"),
        (validate_pattern, "Validate a learned pattern on out-of-sample data", "research", "strategy_learning"),
        (get_backtest_results, "Get backtest results for a strategy", "research", "strategy_learning"),
        (get_strategy_performance, "Get strategy performance history", "research", "strategy_learning"),
    ]
    
    for func, desc, category, skill_name in strategy_tools:
        defn = next((d for d in STRATEGY_TOOL_DEFINITIONS if d["function"]["name"] == func.__name__), None)
        if defn:
            registry.register_tool(Tool(
                name=func.__name__,
                description=desc,
                function=func,
                parameters=defn["function"]["parameters"],
                category=category,
                skill_name=skill_name
            ))


# Tool definitions for each skill
SKILL_TOOL_MAP = {
    "market_scanner": [
        "get_market_overview", "search_coin", "get_coin_price", "get_market_cap",
        "get_trading_volume", "get_historical_ohlcv", "get_exchange_data",
        "scan_market", "get_top_coins"
    ],
    "historical_analysis": [
        "get_historical_ohlcv", "search_historical_patterns", "compare_coins",
        "calculate_potential_upside"
    ],
    "technical_analysis": [
        "calculate_rsi", "calculate_macd", "calculate_ema", "calculate_obv",
        "calculate_atr", "detect_support_resistance", "detect_breakout",
        "detect_accumulation", "analyze_market_structure", "full_technical_analysis"
    ],
    "whale_tracking": [
        "track_wallet", "analyze_wallet_history", "detect_whale_transactions",
        "analyze_exchange_flows", "identify_wallet_clusters", "monitor_token_holders"
    ],
    "smart_money": [
        "track_wallet", "analyze_wallet_history", "identify_wallet_clusters",
        "analyze_exchange_flows"
    ],
    "tokenomics": [
        "evaluate_tokenomics", "analyze_token_unlocks", "get_market_cap", "get_coin_price"
    ],
    "liquidity_analysis": [
        "get_exchange_data", "get_historical_ohlcv"
    ],
    "pattern_recognition": [
        "search_historical_patterns", "compare_coins", "detect_accumulation",
        "full_technical_analysis"
    ],
    "breakout_detection": [
        "detect_breakout", "detect_support_resistance", "analyze_market_structure",
        "get_historical_ohlcv"
    ],
    "risk_analysis": [
        "calculate_risk_score", "rank_candidates", "evaluate_tokenomics",
        "analyze_token_unlocks"
    ],
    "sentiment_analysis": [],
    "portfolio_analysis": [
        "compare_coins", "calculate_potential_upside", "calculate_risk_score",
        "rank_candidates"
    ],
    "derivatives_analysis": [
        "get_derivatives_analysis", "analyze_order_book"
    ],
    "market_breadth": [
        "get_market_breadth", "get_market_overview", "get_sector_performance"
    ],
    "correlation_analysis": [
        "calculate_correlation_matrix", "compare_coins"
    ],
    "sector_rotation": [
        "get_sector_performance", "scan_momentum"
    ],
    "order_book_analysis": [
        "analyze_order_book", "get_exchange_data"
    ],
    "fibonacci_analysis": [
        "calculate_fibonacci", "get_historical_ohlcv", "detect_support_resistance"
    ],
    "volume_profile": [
        "calculate_volume_profile", "get_historical_ohlcv"
    ],
    "volatility_analysis": [
        "analyze_volatility", "calculate_atr", "get_historical_ohlcv"
    ],
    "momentum_scanner": [
        "scan_momentum", "get_top_coins"
    ],
    "mean_reversion": [
        "calculate_mean_reversion", "calculate_rsi", "get_historical_ohlcv"
    ],
    "ichimoku": [
        "calculate_ichimoku", "get_historical_ohlcv"
    ],
    "wyckoff_analysis": [
        "analyze_wyckoff", "detect_accumulation", "get_historical_ohlcv"
    ],
    "new_token_scanner": [
        "scan_new_pairs", "get_exchange_data"
    ],
    "gas_tracker": [
        "get_gas_prices"
    ],
    "trade_journal": [
        "add_trade", "close_trade", "list_trades", "get_trade_stats"
    ],
    "paper_trading": [
        "create_paper_account", "get_paper_account", "list_paper_accounts",
        "open_paper_position", "close_paper_position", "update_paper_positions",
        "get_paper_account_stats", "get_paper_trades"
    ],
    "strategy_learning": [
        "create_strategy", "get_strategy", "list_strategies", "backtest_strategy",
        "run_multi_symbol_backtest", "optimize_strategy_parameters",
        "discover_patterns", "get_learning_patterns", "validate_pattern",
        "get_backtest_results", "get_strategy_performance"
    ]
}