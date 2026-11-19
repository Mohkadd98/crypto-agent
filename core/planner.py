"""
Execution planner for the Crypto Intelligence Agent.
Creates execution plans from user requests.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum

from core.skill_registry import get_skill_registry, SkillStatus
from core.tool_registry import get_tool_registry, SKILL_TOOL_MAP


class StepType(str, Enum):
    TOOL = "tool"
    SKILL = "skill"
    AI_ANALYSIS = "ai_analysis"
    DATA_FETCH = "data_fetch"
    CALCULATION = "calculation"
    SYNTHESIS = "synthesis"


@dataclass
class ExecutionStep:
    """A single step in the execution plan."""
    step_id: str
    type: StepType
    name: str
    description: str
    skill_name: Optional[str] = None
    tool_name: Optional[str] = None
    parameters: Dict = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    estimated_time: float = 1.0
    priority: int = 0


@dataclass
class ExecutionPlan:
    """Complete execution plan."""
    plan_id: str
    user_request: str
    steps: List[ExecutionStep]
    required_skills: List[str]
    required_tools: List[str]
    estimated_total_time: float
    created_at: datetime = field(default_factory=datetime.utcnow)


class ExecutionPlanner:
    """Plans execution steps for user requests."""
    
    def __init__(self):
        self.skill_registry = get_skill_registry()
        self.tool_registry = get_tool_registry()
    
    def create_plan(self, user_request: str, context: Dict = None) -> ExecutionPlan:
        """Create an execution plan from a user request."""
        context = context or {}
        
        # Analyze request to determine required skills and tools
        required_skills = self._identify_skills(user_request, context)
        required_tools = self._identify_tools(user_request, required_skills, context)
        
        # Build execution steps
        steps = self._build_steps(user_request, required_skills, required_tools, context)
        
        # Calculate total time
        total_time = sum(step.estimated_time for step in steps)
        
        plan = ExecutionPlan(
            plan_id=f"plan_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            user_request=user_request,
            steps=steps,
            required_skills=required_skills,
            required_tools=required_tools,
            estimated_total_time=total_time
        )
        
        return plan
    
    def _identify_skills(self, request: str, context: Dict) -> List[str]:
        """Identify which skills are needed for the request."""
        request_lower = request.lower()
        skills = []
        
        # Skill keywords mapping
        skill_keywords = {
            "market_scanner": ["scan", "find", "search", "screen", "top", "market overview", "discover", "gainers", "losers"],
            "historical_analysis": ["history", "historical", "past", "previous", "compare", "pattern", "similar", "rally", "cycle"],
            "technical_analysis": ["rsi", "macd", "ema", "indicator", "technical", "support", "resistance", "trend", "moving average", "obv", "atr", "bollinger"],
            "whale_tracking": ["whale", "large wallet", "big transaction", "track wallet", "wallet analysis", "holder"],
            "smart_money": ["smart money", "institutional", "fund", "smart wallet"],
            "tokenomics": ["tokenomic", "supply", "unlock", "inflation", "fdv", "circulating", "max supply"],
            "liquidity_analysis": ["liquidity", "pool", "depth", "slippage", "dex", "amm"],
            "pattern_recognition": ["pattern", "formation", "chart pattern", "double bottom", "head and shoulders", "cup and handle", "flag", "pennant", "triangle"],
            "breakout_detection": ["breakout", "break out", "retest", "resistance break", "support break"],
            "risk_analysis": ["risk", "risk score", "danger", "safe", "conservative", "aggressive"],
            "sentiment_analysis": ["sentiment", "social", "twitter", "reddit", "news", "fear", "greed"],
            "portfolio_analysis": ["portfolio", "allocate", "allocation", "diversif", "position siz", "rebalance"],
            "derivatives_analysis": ["funding", "open interest", "long short", "derivative", "futures", "liquidation", "crowded"],
            "market_breadth": ["breadth", "advance decline", "market health", "participation", "how many coins"],
            "correlation_analysis": ["correlation", "correlated", "beta", "diversification", "matrix"],
            "sector_rotation": ["sector", "rotation", "narrative", "category", "categories", "defi index", "ai coins"],
            "order_book_analysis": ["order book", "orderbook", "depth", "imbalance", "bid ask", "walls", "spread"],
            "fibonacci_analysis": ["fibonacci", "fib", "retracement", "golden zone", "extension level"],
            "volume_profile": ["volume profile", "vpvr", "poc", "value area", "high volume node"],
            "volatility_analysis": ["volatility", "volatile", "realized vol", "drawdown", "atr regime"],
            "momentum_scanner": ["momentum", "accelerating", "strongest", "trending up", "hot coins"],
            "mean_reversion": ["mean reversion", "overextended", "z-score", "zscore", "revert", "stretched"],
            "ichimoku": ["ichimoku", "cloud", "tenkan", "kijun", "kumo"],
            "wyckoff_analysis": ["wyckoff", "spring", "upthrust", "sign of strength", "trading range"],
            "new_token_scanner": ["new token", "new tokens", "new pair", "new pairs", "new pool", "new pools", "pools", "just launched", "new listing", "fresh launch"],
            "gas_tracker": ["gas", "gwei", "transaction fee", "network fee"],
            "trade_journal": ["trade journal", "my trades", "log trade", "win rate", "position journal", "add trade"],
            "paper_trading": ["paper trade", "paper trading", "virtual trade", "simulate trade", "demo trade", "test strategy", "mock trade", "fake trade"],
            "strategy_learning": ["create strategy", "build strategy", "backtest", "backtesting", "optimize strategy", "strategy optimization", "learn pattern", "discover pattern", "self learn", "auto strategy", "find strategy", "run backtest", "test strategy", "multi backtest", "parameter optimization", "tune strategy", "create a strategy", "make a strategy", "strategy for", "optimize parameters", "tune parameters", "best parameters", "optimize my strategy", "improve strategy", "strategy tuning", "parameter tuning", "optimize strategy parameters", "tune strategy parameters", "optimize the strategy", "tune the strategy", "strategy parameters", "hyperparameter optimization", "grid search", "bayesian optimization"],
            "paper_trading": ["paper trade", "paper trading", "virtual trade", "simulate trade", "demo trade", "test strategy", "mock trade", "fake trade", "paper account", "paper position", "paper buy", "paper sell", "paper long", "paper short", "open paper", "close paper"],
        }
        
        for skill, keywords in skill_keywords.items():
            if any(kw in request_lower for kw in keywords):
                # Check if skill is available and active
                skill_obj = self.skill_registry.get_skill(skill)
                if skill_obj and skill_obj.status == SkillStatus.ACTIVE:
                    skills.append(skill)
        
        # Always include market_scanner for general queries if no specific skill matched
        if not skills:
            market_skill = self.skill_registry.get_skill("market_scanner")
            if market_skill and market_skill.status == SkillStatus.ACTIVE:
                skills.append("market_scanner")
        
        return skills
    
    def _identify_tools(self, request: str, skills: List[str], context: Dict) -> List[str]:
        """Identify specific tools needed."""
        tools = set()
        request_lower = request.lower()
        
        # Add tools from required skills. The generic market_scanner fallback is
        # deliberately skipped: it carries the whole market-data toolset, which
        # turns "what is the price of BTC" into nine slow network calls.
        for skill in skills:
            if skill == "market_scanner":
                continue
            tools.update(SKILL_TOOL_MAP.get(skill, []))
        
        # Specific tool keywords
        tool_keywords = {
            "get_market_overview": ["market overview", "global market", "total market cap", "btc dominance"],
            "search_coin": ["search", "find coin", "look for"],
            "get_coin_price": ["price of", "current price", "how much is"],
            "get_market_cap": ["market cap", "market capitalization"],
            "get_trading_volume": ["volume", "trading volume"],
            "get_historical_ohlcv": ["historical data", "ohlcv", "candles", "chart data", "price history"],
            "get_exchange_data": ["exchange data", "cex", "dex", "order book"],
            "scan_market": ["scan market", "scan for", "filter", "screen"],
            "calculate_rsi": ["rsi", "relative strength"],
            "calculate_macd": ["macd"],
            "calculate_ema": ["ema", "exponential moving average", "moving average"],
            "calculate_obv": ["obv", "on balance volume"],
            "calculate_atr": ["atr", "average true range", "volatility"],
            "detect_support_resistance": ["support", "resistance", "level"],
            "detect_breakout": ["breakout", "break out"],
            "detect_accumulation": ["accumulation", "accumulating"],
            "analyze_market_structure": ["market structure", "structure", "higher high", "higher low", "lower high", "lower low"],
            "full_technical_analysis": ["full analysis", "complete analysis", "technical analysis", "all indicators"],
            "track_wallet": ["track wallet", "wallet analysis", "analyze wallet"],
            "analyze_wallet_history": ["wallet history", "wallet transactions", "transaction history"],
            "detect_whale_transactions": ["whale transactions", "large transactions", "whale activity"],
            "analyze_exchange_flows": ["exchange flows", "exchange inflow", "exchange outflow", "inflow", "outflow"],
            "identify_wallet_clusters": ["wallet cluster", "cluster", "related wallets"],
            "monitor_token_holders": ["token holders", "holders", "top holders"],
            "get_token_info": ["token info", "token details", "contract info"],
            "compare_coins": ["compare", "vs", "versus", "against"],
            "search_historical_patterns": ["historical pattern", "similar pattern", "pattern search"],
            "web_search": ["web search", "search the web", "search news", "news search", "search the internet", "google search", "look up", "research news", "search for news"],
            "calculate_potential_upside": ["potential", "upside", "target", "price target", "risk reward"],
            "evaluate_tokenomics": ["tokenomics", "tokenomic", "supply analysis"],
            "analyze_token_unlocks": ["unlock", "token unlock", "vesting"],
            "calculate_risk_score": ["risk score", "risk assessment"],
            "rank_candidates": ["rank", "best", "top pick", "recommend"],
            "get_derivatives_analysis": ["funding", "open interest", "long short", "derivatives", "futures"],
            "get_market_breadth": ["breadth", "advance decline", "market health"],
            "calculate_correlation_matrix": ["correlation", "beta", "diversification"],
            "get_sector_performance": ["sector", "rotation", "category performance"],
            "analyze_order_book": ["order book", "orderbook", "depth", "imbalance"],
            "calculate_fibonacci": ["fibonacci", "retracement", "extension"],
            "calculate_volume_profile": ["volume profile", "poc", "value area"],
            "analyze_volatility": ["volatility", "realized vol", "drawdown"],
            "scan_momentum": ["momentum", "accelerating", "strongest"],
            "calculate_mean_reversion": ["mean reversion", "z-score", "overextended"],
            "calculate_ichimoku": ["ichimoku", "cloud", "tenkan", "kijun"],
            "analyze_wyckoff": ["wyckoff", "spring", "upthrust"],
            "scan_new_pairs": ["new token", "new tokens", "new pair", "new pairs", "new pool", "new pools", "pools", "just launched"],
            "get_gas_prices": ["gas", "gwei", "network fee"],
            "add_trade": ["add trade", "log trade", "open trade"],
            "close_trade": ["close trade", "exit trade"],
            "list_trades": ["list trades", "my trades", "trade journal"],
            "get_trade_stats": ["win rate", "trade stats", "performance"],
            # Paper Trading
            "create_paper_account": ["create paper account", "new paper account", "open paper account"],
            "get_paper_account": ["show paper account", "paper account details", "check paper account"],
            "list_paper_accounts": ["list paper accounts", "all paper accounts", "my paper accounts"],
            "open_paper_position": ["open paper position", "paper buy", "paper long", "paper short", "simulate entry", "paper buy btc", "paper long btc", "paper sell btc"],
            "close_paper_position": ["close paper position", "paper sell", "paper exit", "close paper trade"],
            "update_paper_positions": ["update paper positions", "refresh paper prices"],
            "get_paper_account_stats": ["paper account stats", "paper performance", "paper sharpe", "paper pnl"],
            "get_paper_trades": ["paper trades", "paper trade history", "paper trade log"],
            # Strategy Learning
            "create_strategy": ["create strategy", "build strategy", "new strategy", "define strategy"],
            "get_strategy": ["show strategy", "strategy details"],
            "list_strategies": ["list strategies", "all strategies", "my strategies"],
            "backtest_strategy": ["backtest", "backtesting", "test strategy", "historical test"],
            "run_multi_symbol_backtest": ["multi backtest", "multi-symbol backtest", "portfolio backtest"],
            "optimize_strategy_parameters": ["optimize strategy", "strategy optimization", "tune strategy", "best parameters"],
            "discover_patterns": ["discover patterns", "learn patterns", "find patterns", "self learn", "pattern discovery"],
            "get_learning_patterns": ["learned patterns", "discovered patterns", "my patterns"],
            "validate_pattern": ["validate pattern", "test pattern", "pattern validation"],
            "get_backtest_results": ["backtest results", "backtest history"],
            "get_strategy_performance": ["strategy performance", "strategy history", "strategy track record"]
        }
        
        for tool, keywords in tool_keywords.items():
            if any(kw in request_lower for kw in keywords):
                tools.add(tool)

        # Broad "analyze <SYMBOL>" intent: one OHLCV fetch plus the full
        # technical pass, not the entire market scanner.
        if any(k in request_lower for k in ("analyze", "analysis", "outlook", "review")):
            tools.add("get_historical_ohlcv")
            tools.add("full_technical_analysis")
            if "compare" not in request_lower:
                tools.add("calculate_risk_score")
        
        # Context-aware additions
        if context.get("current_symbol"):
            # If we have a current symbol, add relevant tools
            if "analyze" in request_lower or "analyze" in request_lower:
                tools.update(["full_technical_analysis", "calculate_potential_upside", "calculate_risk_score"])
        
        return list(tools)
    
    def _build_steps(
        self,
        request: str,
        skills: List[str],
        tools: List[str],
        context: Dict
    ) -> List[ExecutionStep]:
        """Build ordered execution steps."""
        steps = []
        step_counter = 0
        completed_outputs = set()

        # Drop tools whose required parameters cannot be satisfied from the
        # request. Otherwise a plan for "create a strategy" also schedules
        # get_strategy_performance(strategy_id=...) and fails loudly.
        runnable = []
        for name in tools:
            tool = self.tool_registry.get_tool(name)
            if tool is None:
                continue
            try:
                params = self._get_tool_params(name, request, context)
            except Exception:
                params = {}
            required = getattr(tool, "required_params", None) or []
            if all(param in params for param in required):
                runnable.append(name)
        tools = runnable
        
        # Phase 1: Data fetching
        data_tools = [t for t in tools if t.startswith("get_") or t.startswith("scan_") or t in ("search_coin", "track_wallet", "analyze_wallet_history", "detect_whale_transactions", "analyze_exchange_flows", "monitor_token_holders", "get_token_info", "list_paper_accounts", "get_paper_account", "get_paper_account_stats", "get_paper_trades", "list_strategies", "get_strategy", "get_backtest_results", "get_strategy_performance", "get_learning_patterns")]
        
        for tool_name in data_tools:
            step_counter += 1
            step = ExecutionStep(
                step_id=f"step_{step_counter}",
                type=StepType.DATA_FETCH,
                name=tool_name,
                description=f"Fetch data using {tool_name}",
                tool_name=tool_name,
                parameters=self._get_tool_params(tool_name, request, context),
                outputs=[f"{tool_name}_result"],
                estimated_time=2.0,
                priority=10
            )
            steps.append(step)
            completed_outputs.add(f"{tool_name}_result")
        
        # Phase 2: Calculations (excluding tools handled by the research phase)
        research_tool_names = {
            "compare_coins", "search_historical_patterns", "calculate_potential_upside",
            "evaluate_tokenomics", "analyze_token_unlocks", "calculate_risk_score", "web_search",
            # Strategy learning tools
            "backtest_strategy", "run_multi_symbol_backtest", "optimize_strategy_parameters",
            "discover_patterns", "validate_pattern",
        }
        calc_tools = [
            t for t in tools
            if (t.startswith("calculate_") or t.startswith("analyze_")
                or t in ("detect_support_resistance", "detect_breakout", "detect_accumulation",
                         "analyze_market_structure", "full_technical_analysis", "identify_wallet_clusters"))
            and t not in research_tool_names
        ]
        
        for tool_name in calc_tools:
            step_counter += 1
            # Depend on data fetch steps
            deps = [s.step_id for s in steps if s.type == StepType.DATA_FETCH]
            step = ExecutionStep(
                step_id=f"step_{step_counter}",
                type=StepType.CALCULATION,
                name=tool_name,
                description=f"Calculate {tool_name}",
                tool_name=tool_name,
                parameters=self._get_tool_params(tool_name, request, context),
                depends_on=deps,
                outputs=[f"{tool_name}_result"],
                estimated_time=1.0,
                priority=20
            )
            steps.append(step)
            completed_outputs.add(f"{tool_name}_result")
        
        # Phase 3: Research/Analysis
        research_tools = [t for t in tools if t in research_tool_names]
        
        for tool_name in research_tools:
            step_counter += 1
            deps = [s.step_id for s in steps if s.type in (StepType.DATA_FETCH, StepType.CALCULATION)]
            step = ExecutionStep(
                step_id=f"step_{step_counter}",
                type=StepType.TOOL,
                name=tool_name,
                description=f"Research: {tool_name}",
                tool_name=tool_name,
                parameters=self._get_tool_params(tool_name, request, context),
                depends_on=deps,
                outputs=[f"{tool_name}_result"],
                estimated_time=2.0,
                priority=30
            )
            steps.append(step)
            completed_outputs.add(f"{tool_name}_result")
        
        # Phase 4: Actions (paper trading, strategy creation)
        action_tool_names = {
            "create_paper_account", "open_paper_position", "close_paper_position", "update_paper_positions",
            "add_trade", "close_trade", "add_to_watchlist", "remove_from_watchlist",
        }
        action_tools = [t for t in tools if t in action_tool_names]
        
        for tool_name in action_tools:
            step_counter += 1
            deps = [s.step_id for s in steps if s.type in (StepType.DATA_FETCH, StepType.CALCULATION, StepType.TOOL)]
            step = ExecutionStep(
                step_id=f"step_{step_counter}",
                type=StepType.TOOL,
                name=tool_name,
                description=f"Action: {tool_name}",
                tool_name=tool_name,
                parameters=self._get_tool_params(tool_name, request, context),
                depends_on=deps,
                outputs=[f"{tool_name}_result"],
                estimated_time=1.0,
                priority=40
            )
            steps.append(step)
            completed_outputs.add(f"{tool_name}_result")
        
        # Phase 5: AI Synthesis
        step_counter += 1
        steps.append(ExecutionStep(
            step_id=f"step_{step_counter}",
            type=StepType.AI_ANALYSIS,
            name="synthesize_results",
            description="Synthesize all results into final response",
            parameters={"request": request, "context": context},
            depends_on=[s.step_id for s in steps],
            outputs=["final_response"],
            estimated_time=3.0,
            priority=100
        ))
        
        return steps
    
    def _get_tool_params(self, tool_name: str, request: str, context: Dict) -> Dict:
        """Extract parameters for a tool from request and context."""
        params = {}
        request_lower = request.lower()
        
        # Common parameter extraction
        import re
        
        # Web search: the query is the user's request itself.
        if tool_name == "web_search":
            params["query"] = request.strip()
            return params
        
        request_upper = request.upper()
        stop_words = {
            'THE', 'AND', 'FOR', 'ARE', 'BUT', 'NOT', 'YOU', 'ALL', 'CAN',
            'HOW', 'WHAT', 'WHY', 'WHEN', 'WHERE', 'WHO', 'WHICH', 'THIS',
            'THAT', 'WITH', 'FROM', 'HAVE', 'BEEN', 'WERE', 'THEY', 'THEIR',
            'THERE', 'ABOUT', 'WOULD', 'COULD', 'SHOULD', 'ON', 'IN', 'AT',
            'TO', 'OF', 'IS', 'IT', 'BE', 'AS', 'BY', 'OR', 'AN', 'IF',
            'DO', 'MY', 'UP', 'NO', 'SO', 'US', 'ME', 'WE', 'HE', 'SHE',
            'HAS', 'HAD', 'WAS', 'ITS', 'OUR', 'GET', 'SET', 'RUN', 'USE',
            'NEW', 'TOP', 'LOW', 'HIGH', 'BUY', 'SELL', 'LONG', 'SHORT',
            'GIVE', 'SHOW', 'CHECK', 'TELL', 'FIND', 'LIST', 'SCAN',
            'SPRING', 'UPTHRUST', 'WYCKOFF', 'ICHIMOKU', 'FIBONACCI',
            'BREAKOUT', 'REVERSION', 'MOMENTUM', 'VOLATILITY', 'DEPTH',
            'ORDER', 'BOOK', 'PROFILE', 'VOLUME', 'RATE', 'FUNDING',
            'MARKET', 'BREADTH', 'SECTOR', 'ROTATION', 'CORRELATION',
            'MATRIX', 'TRADE', 'JOURNAL', 'GAS', 'PRICE', 'LEVELS',
            'ANALYSIS', 'SIGNAL', 'DATA', 'CHART', 'POOLS', 'POOL',
            'CREATE', 'PAPER', 'ACCOUNT', 'STRATEGY', 'BACKTEST', 'TEST',
            'OPTIMIZE', 'LEARN', 'PATTERN', 'DISCOVER', 'RUN', 'MULTI',
            'SYMBOL', 'LAST', 'YEAR', 'MONTH', 'WEEK', 'DAY', 'HOUR',
            'OPEN', 'CLOSE', 'UPDATE', 'STATS', 'PERFORMANCE', 'POSITION',
            'NAME', 'BALANCE', 'FUND', 'WITH', 'FOR', 'FROM', 'USING',
            'BASED', 'BUILD', 'MAKE', 'GENERATE', 'AUTO', 'SELF', 'FIND',
            'USDT', 'USDC', 'BUSD', 'TUSD', 'DAI', 'STABLE', 'COIN', 'CASH',
            'DOLLAR', 'USD', 'EUR', 'CURRENCY', 'AMOUNT', 'VALUE',
            'TUNE', 'BEST', 'PARAMETER', 'HYPERPARAMETER', 'GRID', 'SEARCH',
            'BAYESIAN', 'MY', 'THE', 'A', 'AN', 'IT', 'ON', 'AT', 'BY',
            # Indicator / command abbreviations must never be read as tickers.
            'FIB', 'RSI', 'MACD', 'EMA', 'SMA', 'WMA', 'ATR', 'OBV', 'BB',
            'BOLL', 'VWAP', 'POC', 'ADX', 'CCI', 'ROC', 'MFI', 'STOCH',
            'KDJ', 'SAR', 'ICHIMOKU', 'TENKAN', 'KIJUN', 'SENKOU', 'CHIKOU',
            'LONG', 'SHORT', 'ENTRY', 'EXIT', 'STOP', 'TARGET', 'LEVERAGE',
            'SPOT', 'FUTURES', 'PERP', 'SWAP', 'YIELD', 'STAKE', 'STAKING',
            'DEX', 'CEX', 'TVL', 'FDV', 'APR', 'APY', 'DCA', 'HODL',
        }
        
        # Prefer a symbol that follows a preposition ("on SOL", "for BTC")
        symbol = None
        prep_match = re.search(
            r'\b(?:ON|FOR|OF|ABOUT)\s+\$?([A-Z]{2,6})(?![A-Z])',
            request_upper,
        )
        if prep_match and prep_match.group(1) not in stop_words:
            symbol = prep_match.group(1)
        
        # Otherwise, take the first standalone token that is not a stop word
        if not symbol:
            for m in re.finditer(r'(?<![A-Z])\$?([A-Z]{2,6})(?![A-Z])', request_upper):
                candidate = m.group(1)
                if candidate not in stop_words:
                    symbol = candidate
                    break
        
        if symbol:
            params["symbol"] = symbol
        
        # Use context symbol if no symbol in request
        if "symbol" not in params and context.get("current_symbol"):
            params["symbol"] = context["current_symbol"]
        
        def _ticker_list(extra_stop: set) -> List[str]:
            """Extract an ordered, de-duplicated list of ticker candidates."""
            found: List[str] = []
            for t in re.findall(r'(?<![A-Z])\$?([A-Z]{2,6})(?![A-Z])', request_upper):
                if t not in stop_words and t not in extra_stop and t not in found:
                    # Additional filter: must be a known-ish crypto pattern (2-6 caps, not all vowels)
                    if len(t) >= 2 and not all(c in 'AEIOU' for c in t):
                        found.append(t)
            return found

        # Correlation and comparisons need a list of symbols, not a single ticker
        if tool_name == "calculate_correlation_matrix":
            tickers = _ticker_list({
                'CHECK', 'SHOW', 'CALCULATE', 'CORRELATION', 'BETWEEN', 'BETA',
                'MATRIX', 'GIVE', 'PLEASE', 'TRADE',
            })
            params["symbols"] = tickers[:8] if len(tickers) >= 2 else ["BTC", "ETH"]
            params.pop("symbol", None)

        elif tool_name == "compare_coins":
            tickers = _ticker_list({'COMPARE', 'VERSUS', 'VS', 'AGAINST'})
            params["symbols"] = tickers[:8] if len(tickers) >= 2 else ["BTC", "ETH"]
            params.pop("symbol", None)

        # New pair scanner network
        elif tool_name == "scan_new_pairs":
            chain_aliases = {
                "ethereum": "eth", "eth": "eth", "bsc": "bsc", "bnb": "bsc",
                "polygon": "polygon", "matic": "polygon", "arbitrum": "arbitrum",
                "base": "base", "solana": "solana", "sol": "solana",
                "avalanche": "avalanche", "avax": "avalanche",
            }
            for word in request_lower.replace(",", " ").split():
                if word in chain_aliases:
                    params["network"] = chain_aliases[word]
                    break

        # Gas tracker chains
        elif tool_name == "get_gas_prices":
            chains = [w for w in request_lower.replace(",", " ").split()
                      if w in ("ethereum", "eth", "bsc", "polygon", "arbitrum", "base", "avalanche", "avax")]
            if chains:
                params["chains"] = ["ethereum" if c == "eth" else "avalanche" if c == "avax" else c for c in chains]

        # Tool-specific parameters
        if tool_name == "search_coin":
            params["query"] = params.pop("symbol", request)

        elif tool_name == "get_historical_ohlcv":
            params.setdefault("timeframe", "1d")
            params.setdefault("days", 30)
            params.setdefault("source", "coingecko")
        
        elif tool_name == "scan_market":
            params.setdefault("min_market_cap", 1_000_000)
            params.setdefault("max_market_cap", 10_000_000_000)
            params.setdefault("min_volume_24h", 50_000)
            params.setdefault("limit", 50)
        
        elif tool_name == "calculate_rsi":
            params.setdefault("period", 14)
        
        elif tool_name == "calculate_macd":
            params.setdefault("fast", 12)
            params.setdefault("slow", 26)
            params.setdefault("signal", 9)
        
        elif tool_name == "calculate_ema":
            params.setdefault("periods", [9, 21, 50, 200])
        
        elif tool_name == "calculate_atr":
            params.setdefault("period", 14)
        
        elif tool_name == "detect_support_resistance":
            params.setdefault("window", 20)
            params.setdefault("min_touches", 2)
        
        elif tool_name == "detect_breakout":
            params.setdefault("lookback", 20)
        
        elif tool_name == "track_wallet":
            params.setdefault("chain", "ethereum")
            params.setdefault("max_txs", 1000)
        
        elif tool_name == "detect_whale_transactions":
            params.setdefault("chain", "ethereum")
            params.setdefault("min_value_usd", 100000)
            params.setdefault("lookback_blocks", 100)
        
        elif tool_name == "compare_coins":
            # Will need coins_data from previous steps
            pass
        
        elif tool_name == "calculate_potential_upside":
            # Will need coin_data and ohlcv from previous steps
            pass
        
        elif tool_name == "evaluate_tokenomics":
            # Will need coin_data from previous steps
            pass
        
        elif tool_name == "calculate_risk_score":
            # Will need coin_data and optional ohlcv
            pass
        
        elif tool_name == "rank_candidates":
            # Will need candidates from scan_market
            pass
        
        # Remove the generic symbol from tools that do not accept it
        no_symbol_tools = {
            "get_gas_prices", "scan_new_pairs", "get_market_breadth",
            "get_sector_performance", "scan_momentum", "get_trade_stats",
            "get_market_overview", "get_top_coins", "scan_market",
            "list_paper_accounts", "list_strategies", "get_learning_patterns",
        }
        if tool_name in no_symbol_tools:
            params.pop("symbol", None)
        
        # Paper Trading specific parameters
        if tool_name == "create_paper_account":
            # Extract account name (words after "create paper account" or "name")
            name_match = re.search(r'(?:create|new|open)\s+paper\s+account\s+(?:named\s+|called\s+)?([a-zA-Z0-9_\-]+)', request_lower)
            if name_match:
                params["name"] = name_match.group(1)
            else:
                params["name"] = "Paper Account"
            # Extract initial balance
            balance_match = re.search(r'(?:with|balance|fund)\s+(?:of\s+)?\$?([\d,]+\.?\d*)', request_lower)
            if balance_match:
                params["initial_balance"] = float(balance_match.group(1).replace(",", ""))
            else:
                params.setdefault("initial_balance", 10000.0)
        
        elif tool_name == "open_paper_position":
            # Symbol already extracted
            if "symbol" in params:
                # Extract side
                if "short" in request_lower or "sell" in request_lower:
                    params["side"] = "short"
                else:
                    params["side"] = "long"
                # Extract quantity
                qty_match = re.search(r'(?:qty|quantity|size|amount)\s+(?:of\s+)?([\d,]+\.?\d*)', request_lower)
                if qty_match:
                    params["quantity"] = float(qty_match.group(1).replace(",", ""))
                # Extract entry price
                entry_match = re.search(r'(?:at|entry|price)\s+(?:of\s+)?\$?([\d,]+\.?\d*)', request_lower)
                if entry_match:
                    params["entry_price"] = float(entry_match.group(1).replace(",", ""))
                # Extract stop loss
                sl_match = re.search(r'(?:sl|stop.?loss|stop)\s+(?:at|of\s+)?\$?([\d,]+\.?\d*)', request_lower)
                if sl_match:
                    params["stop_loss"] = float(sl_match.group(1).replace(",", ""))
                # Extract take profit
                tp_match = re.search(r'(?:tp|take.?profit|target)\s+(?:at|of\s+)?\$?([\d,]+\.?\d*)', request_lower)
                if tp_match:
                    params["take_profit"] = float(tp_match.group(1).replace(",", ""))
        
        elif tool_name == "close_paper_position":
            if "symbol" in params:
                # Could extract position_id but usually needs explicit ID
                pass
        
        elif tool_name == "update_paper_positions":
            # Extract prices from "SYM=PRICE" format
            prices = {}
            for match in re.finditer(r'([A-Z]{2,6})\s*=\s*\$?([\d,]+\.?\d*)', request_upper):
                sym, price = match.groups()
                if sym not in stop_words:
                    prices[sym] = float(price.replace(",", ""))
            if prices:
                params["prices"] = prices
        
        # Strategy Learning specific parameters
        elif tool_name == "create_strategy":
            # Extract strategy name
            name_match = re.search(r'(?:create|new|build)\s+strategy\s+(?:named\s+|called\s+)?([a-zA-Z0-9_\- ]+)', request_lower)
            if name_match:
                params["name"] = name_match.group(1).strip()
            # Extract strategy type
            for stype in ["trend_following", "mean_reversion", "breakout"]:
                if stype.replace("_", " ") in request_lower or stype in request_lower:
                    params["strategy_type"] = stype
                    break
            params.setdefault("strategy_type", "trend_following")
            # Extract symbols
            tickers = _ticker_list(set())
            if tickers:
                params["symbols"] = tickers
            params.setdefault("timeframes", ["1d", "4h"])
        
        elif tool_name == "backtest_strategy":
            if "symbol" in params:
                params.setdefault("timeframe", "1d")
                params.setdefault("initial_balance", 10000.0)
        
        elif tool_name == "optimize_strategy_parameters":
            if "symbol" in params:
                # Extract param grid from "param=val1,val2" format
                param_grid = {}
                for match in re.finditer(r'([a-z_]+)\s*=\s*([\d,.]+)', request_lower):
                    key, vals = match.groups()
                    param_grid[key] = [float(v) if "." in v else int(v) for v in vals.split(",")]
                if param_grid:
                    params["param_grid"] = param_grid
                params.setdefault("metric", "sharpe_ratio")
        
        elif tool_name == "discover_patterns":
            if "symbol" in params:
                params.setdefault("timeframe", "1d")
                params.setdefault("lookback_days", 365)
                params.setdefault("min_occurrences", 5)
                params.setdefault("min_win_rate", 0.55)
        
        elif tool_name == "run_multi_symbol_backtest":
            tickers = _ticker_list(set())
            if tickers:
                params["symbols"] = tickers
            params.setdefault("timeframe", "1d")
            params.setdefault("initial_balance", 10000.0)
        
        return params


# Global planner instance
_planner: Optional[ExecutionPlanner] = None


def get_planner() -> ExecutionPlanner:
    """Get the global planner instance."""
    global _planner
    if _planner is None:
        _planner = ExecutionPlanner()
    return _planner