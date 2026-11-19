"""
Main Agent class for the Crypto Intelligence Agent.
Orchestrates all components and handles user interactions.
"""

import asyncio
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, AsyncGenerator
from dataclasses import dataclass

from core.config import get_settings, reload_settings
from core.conversation import get_conversation_manager, ConversationRole, ConversationContext
from core.planner import get_planner, ExecutionPlan
from core.executor import get_executor, ExecutionEngine, ExecutionResult, ExecutionStatus
from core.tool_registry import get_tool_registry, register_all_tools
from core.skill_registry import get_skill_registry, initialize_skills
from core.memory import get_memory_manager
from providers.kilo_api import get_ai_provider, get_kilo_provider, close_kilo_provider, ModelTask, ChatMessage
from providers.market_data import get_market_data_provider, close_market_data_provider
from providers.blockchain import get_blockchain_provider, close_blockchain_provider
from database.storage import get_db_manager, close_db_manager


@dataclass
class AgentStatus:
    """Current agent status."""
    initialized: bool = False
    kilo_connected: bool = False
    market_data_connected: bool = False
    blockchain_connected: bool = False
    active_skills: int = 0
    total_skills: int = 0
    current_session: Optional[str] = None
    current_model: str = ""
    last_activity: Optional[datetime] = None


class CryptoIntelligenceAgent:
    """Main agent class."""
    
    def __init__(self):
        self.status = AgentStatus()
        self._initialized = False
        self._running = False
    
    async def initialize(self) -> bool:
        """Initialize all components."""
        try:
            # Load settings
            settings = get_settings()
            
            # Initialize database
            db = await get_db_manager()
            
            # Initialize AI provider (Gemini when configured via GEMINI_API_KEY, else Kilo)
            ai = await get_ai_provider()
            self._ai_provider = ai
            self.status.kilo_connected = await ai.health_check()
            self.status.current_model = getattr(getattr(ai, "settings", None), "default_model", None) or settings.kilo_api.default_model
            
            # Initialize market data. Probe Binance first: it answers in
            # milliseconds, while CoinGecko's /global endpoint is rate limited
            # and can add 30s+ to startup.
            market = await get_market_data_provider()
            try:
                price = await market.get_binance_price("BTC")
                if price is None:
                    await market.get_market_overview()
                self.status.market_data_connected = True
            except Exception:
                self.status.market_data_connected = False
            
            # Initialize blockchain
            self._blockchain_provider = await get_blockchain_provider()
            self.status.blockchain_connected = len(self._blockchain_provider._web3_clients) > 0
            
            # Register all tools
            register_all_tools()
            
            # Initialize skills
            skill_results = await initialize_skills()
            skill_registry = get_skill_registry()
            self.status.total_skills = len(skill_registry._skills)
            self.status.active_skills = len(skill_registry.get_active_skills())
            
            # Initialize conversation
            conversation = get_conversation_manager()
            session = await conversation.initialize()
            self.status.current_session = session.session_id
            
            # Initialize memory
            memory = await get_memory_manager()
            
            self._initialized = True
            self.status.initialized = True
            self.status.last_activity = datetime.utcnow()
            
            return True
            
        except Exception as e:
            print(f"Initialization failed: {e}")
            return False
    
    async def shutdown(self) -> None:
        """Shutdown all components."""
        await close_kilo_provider()
        await close_market_data_provider()
        await close_blockchain_provider()
        await close_db_manager()
        self._initialized = False
        self.status.initialized = False
    
    async def process_message(self, user_input: str) -> AsyncGenerator[str, None]:
        """Process a user message and yield response chunks."""
        if not self._initialized:
            yield "Agent not initialized. Please wait..."
            return
        
        self.status.last_activity = datetime.utcnow()
        conversation = get_conversation_manager()
        executor = get_executor()
        
        # Add user message to conversation
        await conversation.add_message(ConversationRole.USER, user_input)
        
        # Check for commands
        if user_input.startswith("/"):
            async for chunk in self._handle_command(user_input):
                yield chunk
            return
        
        # Create execution plan
        planner = get_planner()
        context = conversation.get_context()
        plan = planner.create_plan(user_input, context.__dict__)
        
        # Execute plan with streaming updates
        execution_result = await executor.execute_plan(plan)
        
        # Stream final result
        if execution_result.final_output:
            yield execution_result.final_output
        else:
            fallback = self._summarize_results(execution_result)
            yield fallback or "I couldn't complete the analysis. Please try again."

    def _summarize_results(self, execution_result) -> str:
        """Render tool results without AI when synthesis is unavailable.

        Keeps the agent useful when no Kilo API key is configured: instead of a
        bare error, show the computed data.
        """
        blocks: List[str] = []
        for step in execution_result.step_results:
            if step.status != ExecutionStatus.COMPLETED:
                continue
            output = step.output
            if not isinstance(output, dict) or not output.get("success"):
                continue
            data = output.get("data")
            if data is None:
                continue
            name = step.step_id
            blocks.append(self._format_data_block(name, data))
        if not blocks:
            failed = [s for s in execution_result.step_results if s.status == ExecutionStatus.FAILED]
            if failed:
                reasons = "; ".join(str(s.error)[:120] for s in failed[:3] if s.error)
                return f"No AI synthesis available (set KILO_API_KEY). Steps failed: {reasons}"
            return ""

        header = "RESULTS (raw data — set KILO_API_KEY for AI synthesis)\n" + "=" * 70
        return header + "\n\n" + "\n\n".join(b for b in blocks if b)

    def _format_data_block(self, name: str, data: Any, max_items: int = 10) -> str:
        """Format a single tool result into readable terminal text."""
        lines = [f"[{name}]", "-" * 70]

        def fmt(value: Any) -> str:
            if isinstance(value, float):
                return f"{value:,.6g}"
            if isinstance(value, (dict, list)):
                text = str(value)
                return text if len(text) <= 120 else text[:117] + "..."
            return str(value)

        def walk(obj: Any, prefix: str = "") -> None:
            if len(lines) > 60:
                return
            if isinstance(obj, dict):
                for k, v in obj.items():
                    label = f"{prefix}{k}"
                    if isinstance(v, (dict, list)):
                        if isinstance(v, list) and v and not isinstance(v[0], (dict, list)):
                            lines.append(f"  {label:<28}: {', '.join(fmt(x) for x in v[:max_items])}")
                        elif isinstance(v, list):
                            lines.append(f"  {label:<28}: {len(v)} item(s)")
                            for i, item in enumerate(v[:3], 1):
                                walk(item, f"{prefix}{k}[{i}].")
                        else:
                            walk(v, f"{label}.")
                    else:
                        lines.append(f"  {label:<28}: {fmt(v)}")
            else:
                lines.append(f"  {prefix or 'value'}: {fmt(obj)}")

        walk(data)
        return "\n".join(lines)
    
    async def _handle_command(self, command: str) -> AsyncGenerator[str, None]:
        """Handle CLI commands."""
        parts = command[1:].split()
        cmd = parts[0].lower() if parts else ""
        args = parts[1:] if len(parts) > 1 else []
        
        if cmd == "help":
            yield self._get_help_text()
        
        elif cmd == "status":
            yield self._get_status_text()
        
        elif cmd == "models":
            if args and args[0] == "set":
                yield await self._set_model(args[1] if len(args) > 1 else "")
            else:
                yield await self._list_models()
        
        elif cmd == "scan":
            yield await self._handle_scan(args)
        
        elif cmd == "derivs":
            if args:
                yield await self._handle_derivs(args[0])
            else:
                yield "Usage: /derivs <SYMBOL>"
        
        elif cmd == "correlation":
            if len(args) >= 2:
                yield await self._handle_correlation(args)
            else:
                yield "Usage: /correlation <SYM1> <SYM2> [SYM3 ...]"
        
        elif cmd == "orderbook":
            if args:
                yield await self._handle_orderbook(args[0])
            else:
                yield "Usage: /orderbook <SYMBOL>"
        
        elif cmd in ("fib", "fibonacci"):
            if args:
                yield await self._handle_fib(args[0])
            else:
                yield "Usage: /fib <SYMBOL>"
        
        elif cmd in ("profile", "vp"):
            if args:
                yield await self._handle_profile(args[0])
            else:
                yield "Usage: /profile <SYMBOL>"
        
        elif cmd in ("volatility", "vol"):
            if args:
                yield await self._handle_volatility(args[0])
            else:
                yield "Usage: /volatility <SYMBOL>"
        
        elif cmd == "reversion":
            if args:
                yield await self._handle_reversion(args[0])
            else:
                yield "Usage: /reversion <SYMBOL>"
        
        elif cmd == "ichimoku":
            if args:
                yield await self._handle_ichimoku(args[0])
            else:
                yield "Usage: /ichimoku <SYMBOL>"
        
        elif cmd == "wyckoff":
            if args:
                yield await self._handle_wyckoff(args[0])
            else:
                yield "Usage: /wyckoff <SYMBOL>"
        
        elif cmd == "gas":
            yield await self._handle_gas(args)
        
        elif cmd == "journal":
            yield await self._handle_journal(args)
        
        elif cmd == "paper":
            yield await self._handle_paper(args)
        
        elif cmd in ("strategy", "strat"):
            yield await self._handle_strategy(args)
        
        elif cmd == "analyze":
            if args:
                yield await self._handle_analyze(args[0])
            else:
                yield "Usage: /analyze <SYMBOL>"
        
        elif cmd == "compare":
            if len(args) >= 2:
                yield await self._handle_compare(args[0], args[1])
            else:
                yield "Usage: /compare <SYMBOL1> <SYMBOL2>"
        
        elif cmd == "whales":
            if args:
                yield await self._handle_whales(args[0])
            else:
                yield "Usage: /whales <SYMBOL>"
        
        elif cmd == "wallet":
            if len(args) >= 2:
                yield await self._handle_wallet(args[0], args[1])
            else:
                yield "Usage: /wallet <CHAIN> <ADDRESS>"
        
        elif cmd == "watchlist":
            yield await self._handle_watchlist(args)
        
        elif cmd == "skills":
            yield await self._handle_skills(args)
        
        elif cmd == "memory":
            yield await self._handle_memory(args)
        
        elif cmd == "history":
            yield await self._handle_history(args)
        
        elif cmd == "report":
            yield await self._handle_report(args)
        
        elif cmd == "config":
            yield await self._handle_config(args)
        
        elif cmd == "clear":
            conversation = get_conversation_manager()
            await conversation.clear_history()
            yield "Conversation history cleared."
        
        elif cmd == "exit":
            yield "Goodbye!"
            self._running = False
        
        else:
            yield f"Unknown command: {cmd}. Type /help for available commands."
    
    def _get_help_text(self) -> str:
        """Get help text."""
        return """
CRYPTO INTELLIGENCE AGENT - Commands

General:
  /help                    - Show this help
  /status                  - Show agent status
  /models                  - List available models
  /model set <name>        - Set active model
  /clear                   - Clear conversation history
  /exit                    - Exit the agent

Market Data:
  /scan [type] [args]      - Scan market. Types:
                               top [N]            top coins by market cap
                               accumulation       accumulation candidates
                               breakout           breakout candidates
                               breadth [N]        market breadth & regime
                               momentum [N]       momentum scanner
                               sectors [N]        sector rotation
                               newpairs [net] [N] new DEX pools
  /analyze <SYMBOL>        - Analyze a cryptocurrency
  /compare <SYM1> <SYM2>   - Compare two cryptocurrencies
  /whales <SYMBOL>         - Track whale activity for a symbol
  /wallet <CHAIN> <ADDR>   - Analyze a wallet address

Advanced Analytics:
  /derivs <SYMBOL>         - Funding, open interest, long/short ratio
  /correlation <S1> <S2> [S3 ...] - Correlation matrix + BTC beta
  /orderbook <SYMBOL>      - Order book depth, imbalance, walls
  /fib <SYMBOL>            - Fibonacci retracement & extension levels
  /profile <SYMBOL>        - Volume profile (POC, value area)
  /volatility <SYMBOL>     - Realized volatility, ATR, regime
  /reversion <SYMBOL>      - Mean-reversion z-score & RSI
  /ichimoku <SYMBOL>       - Ichimoku cloud analysis
  /wyckoff <SYMBOL>        - Wyckoff accumulation/distribution phase
  /gas [chain ...]         - Gas prices across chains

Journal & Portfolio:
  /journal list [status]             - List trades (open/closed)
  /journal add <SYM> <side> <entry> [qty] - Open a trade
  /journal close <ID> <exit_price>   - Close a trade
  /journal stats                     - Win rate, PnL, profit factor

Management:
  /watchlist [add|remove|list] [SYMBOL] - Manage watchlist
  /skills [list|enable|disable|inspect] [NAME] - Manage skills
  /memory [search|export|clear] - Manage memory
  /history [search] <QUERY> - Search conversation history
  /report                  - Generate research report
  /config [show|set]       - View or modify configuration

Natural Language:
  You can also just type naturally:
  "Find coins accumulating before breakout"
  "Analyze SOL and compare with AVAX"
  "Show me tokens with similar patterns to BTC 2020"
  "What's the risk score for PEPE?"
"""
    
    def _get_status_text(self) -> str:
        """Get status text."""
        s = self.status
        bc_chains = len(self._blockchain_provider._web3_clients) if hasattr(self, '_blockchain_provider') and self._blockchain_provider else 0
        provider_name = getattr(self._ai_provider, "provider_name", "Kilo API") if getattr(self, "_ai_provider", None) else "Kilo API"
        return f"""
CRYPTO INTELLIGENCE AGENT
Version: 1.0.0
AI Provider: {provider_name} ({'Connected' if s.kilo_connected else 'Disconnected'})
Model: {s.current_model}
Market Data: {'Connected' if s.market_data_connected else 'Disconnected'}
Blockchain: {'Connected' if s.blockchain_connected else 'Disconnected'} ({bc_chains} chains)
Skills: {s.active_skills}/{s.total_skills} Active
Session: {s.current_session or 'None'}
Last Activity: {s.last_activity.strftime('%H:%M:%S') if s.last_activity else 'Never'}
"""
    
    async def _list_models(self) -> str:
        """List available models."""
        kilo = self._ai_provider or await get_kilo_provider()
        try:
            models = await kilo.list_models()
            if models:
                lines = ["Available Models:"]
                for m in models:
                    lines.append(f"  - {m.get('id', 'unknown')}: {m.get('name', 'Unknown')}")
                return "\n".join(lines)
            else:
                return "No models found."
        except Exception as e:
            return f"Failed to list models: {e}"
    
    async def _set_model(self, model_name: str) -> str:
        """Set active model."""
        if not model_name:
            return "Usage: /model set <model_name>"
        
        settings = get_settings()
        # Validate model exists
        kilo = self._ai_provider or await get_kilo_provider()
        models = await kilo.list_models()
        model_ids = [m.get('id') for m in models]
        
        if model_name not in model_ids:
            return f"Model '{model_name}' not found. Available: {', '.join(model_ids[:5])}..."
        
        settings.kilo_api.default_model = model_name
        self.status.current_model = model_name
        return f"Model set to: {model_name}"
    
    async def _handle_scan(self, args: List[str]) -> str:
        """Handle scan command."""
        scan_type = args[0].lower() if args else "top"
        market = await get_market_data_provider()
        
        if scan_type == "top":
            limit = int(args[1]) if len(args) > 1 else 20
            coins = await market.get_coins_markets(order="market_cap_desc", per_page=min(max(limit, 1), 250))
            if coins:
                lines = [f"TOP {min(limit, len(coins))} COINS BY MARKET CAP", "-" * 78]
                for i, coin in enumerate(coins[:limit], 1):
                    chg = coin.price_change_percentage_24h or 0.0
                    price = coin.current_price or 0.0
                    mcap = coin.market_cap or 0.0
                    lines.append(
                        f"{i:>3}. {coin.symbol:<10} ${price:>12,.4f}  "
                        f"MC ${mcap:>16,.0f}  24h {chg:+6.2f}%"
                    )
                return "\n".join(lines)
            return "Scan failed: no market data returned."
        
        elif scan_type == "accumulation":
            coins = await market.scan_market(min_volume_24h=100000, limit=20)
            if coins:
                lines = ["POTENTIAL ACCUMULATION CANDIDATES", "-" * 78]
                for coin in coins[:15]:
                    chg = coin.price_change_percentage_24h or 0.0
                    lines.append(
                        f"  {coin.symbol:<10} ${(coin.current_price or 0):>12,.6f}  "
                        f"Vol ${(coin.total_volume or 0):>14,.0f}  24h {chg:+6.2f}%"
                    )
                return "\n".join(lines)
            return "No accumulation candidates matched the filters."
        
        elif scan_type == "breakout":
            coins = await market.scan_market(min_price_change_24h=5, max_price_change_24h=50, limit=20)
            if coins:
                lines = ["POTENTIAL BREAKOUT CANDIDATES", "-" * 78]
                for coin in coins[:15]:
                    chg = coin.price_change_percentage_24h or 0.0
                    lines.append(
                        f"  {coin.symbol:<10} ${(coin.current_price or 0):>12,.4f}  "
                        f"24h {chg:+6.2f}%  Vol ${(coin.total_volume or 0):>14,.0f}"
                    )
                return "\n".join(lines)
            return "No breakout candidates matched the filters."
        
        elif scan_type == "breadth":
            top_n = int(args[1]) if len(args) > 1 else 150
            result = await self._handle_breadth(top_n)
            return result
        
        elif scan_type == "momentum":
            limit = int(args[1]) if len(args) > 1 else 15
            result = await self._handle_momentum(limit)
            return result
        
        elif scan_type in ("sectors", "sector"):
            top_n = int(args[1]) if len(args) > 1 else 12
            return await self._handle_sectors(top_n)
        
        elif scan_type in ("newpairs", "new", "pools"):
            network = args[1] if len(args) > 1 else "eth"
            limit = int(args[2]) if len(args) > 2 else 15
            return await self._handle_newpairs(network, limit)
        
        return (
            f"Unknown scan type: {scan_type}\n"
            "Use: top, accumulation, breakout, breadth, momentum, sectors, newpairs"
        )
    
    # ------------------------------------------------------------------
    # Advanced skill commands
    # ------------------------------------------------------------------
    
    async def _ohlcv_payload(self, symbol: str, days: int = 200, timeframe: str = "1d") -> Optional[Dict]:
        """Fetch OHLCV and return the plain dict expected by advanced tools."""
        market = await get_market_data_provider()
        ohlcv = await market.get_historical_ohlcv(symbol, timeframe, days)
        if not ohlcv or len(ohlcv.closes) < 10:
            return None
        return {
            "timestamps": ohlcv.timestamps,
            "opens": ohlcv.opens,
            "highs": ohlcv.highs,
            "lows": ohlcv.lows,
            "closes": ohlcv.closes,
            "volumes": ohlcv.volumes,
        }
    
    async def _handle_breadth(self, top_n: int = 150) -> str:
        from tools.advanced_tools import get_market_breadth
        r = await get_market_breadth(top_n)
        if not r["success"]:
            return f"Market breadth failed: {r['error']}"
        d = r["data"]
        lines = [
            "MARKET BREADTH", "-" * 70,
            f"Universe            : {d['universe_size']} coins",
            f"Regime              : {d['regime'].upper()}  (score {d['breadth_score']}/100)",
            f"Advance / Decline   : {d['advance_decline']['advancing']} / {d['advance_decline']['declining']}  (ratio {d['advance_decline']['ratio']:.2f})",
            f"% Positive 24h/7d/30d: {d['pct_above_24h']:.1f}%  {d['pct_above_7d']:.1f}%  {d['pct_above_30d']:.1f}%",
            f"Median change       : {d['median_change']['24h']:+.2f}%  {d['median_change']['7d']:+.2f}%  {d['median_change']['30d']:+.2f}%",
            f"Interpretation      : {d['interpretation']}",
            "",
            "Leaders : " + ", ".join(f"{x['symbol']} {x['change_24h']:+.1f}%" for x in d["leaders"] if x["change_24h"] is not None),
            "Laggards: " + ", ".join(f"{x['symbol']} {x['change_24h']:+.1f}%" for x in d["laggards"] if x["change_24h"] is not None),
        ]
        return "\n".join(lines)
    
    async def _handle_momentum(self, limit: int = 15) -> str:
        from tools.advanced_tools import scan_momentum
        r = await scan_momentum(limit)
        if not r["success"]:
            return f"Momentum scan failed: {r['error']}"
        d = r["data"]
        universe = r.get("metadata", {}).get("universe", "n/a")
        lines = [f"MOMENTUM SCANNER (universe {universe})", "-" * 78]
        lines.append(f"{'#':>2}  {'SYMBOL':<10} {'PRICE':>12} {'24h':>8} {'7d':>8} {'30d':>8} {'SCORE':>8} {'ACCEL':>8}")
        for i, c in enumerate(d["candidates"], 1):
            lines.append(
                f"{i:>2}. {c['symbol']:<10} {c['price']:>12,.6f} "
                f"{c['change_24h']:>+7.2f}% {c['change_7d']:>+7.2f}% {c['change_30d']:>+7.2f}% "
                f"{c['momentum_score']:>8.3f} {c['acceleration']:>+8.2f}"
            )
        return "\n".join(lines)
    
    async def _handle_sectors(self, top_n: int = 12) -> str:
        from tools.advanced_tools import get_sector_performance
        r = await get_sector_performance(top_n)
        if not r["success"]:
            return f"Sector analysis failed: {r['error']}"
        d = r["data"]
        lines = [
            f"SECTOR ROTATION  [{d['market_regime'].upper()}]", "-" * 70,
            d["rotation_signal"], "",
            "LEADING SECTORS",
        ]
        for s in d["leaders"]:
            lines.append(f"  {s['sector'][:34]:<34} {s['market_cap_change_24h']:>+7.2f}%   MC ${s['market_cap']:>15,.0f}")
        lines.append("")
        lines.append("LAGGING SECTORS")
        for s in d["laggards"]:
            lines.append(f"  {s['sector'][:34]:<34} {s['market_cap_change_24h']:>+7.2f}%   MC ${s['market_cap']:>15,.0f}")
        return "\n".join(lines)
    
    async def _handle_derivs(self, symbol: str) -> str:
        from tools.advanced_tools import get_derivatives_analysis
        r = await get_derivatives_analysis(symbol)
        if not r["success"]:
            return f"Derivatives analysis failed: {r['error']}"
        d = r["data"]
        f = d["funding"]
        lines = [
            f"DERIVATIVES — {d['symbol']}", "-" * 70,
            f"Stance              : {d['stance'].replace('_', ' ').upper()}  (score {d['sentiment_score']:+.2f})",
            f"Funding (current)   : {f['current_rate_pct']:+.4f}%   annualized {f['annualized_pct']:+.1f}%",
            f"Mark / Index price  : {f['mark_price']} / {f['index_price']}",
            f"Open interest       : {d['open_interest']['current']:,.2f}   change {d['open_interest']['change_pct_period']:+.1f}%",
            f"Long/Short ratio    : {d['long_short']['latest_ratio']}",
            "",
            "Signals:",
        ]
        lines += [f"  • {s}" for s in d["signals"]] or ["  • No notable crowding signals"]
        return "\n".join(lines)
    
    async def _handle_correlation(self, symbols: List[str]) -> str:
        from tools.advanced_tools import calculate_correlation_matrix
        r = await calculate_correlation_matrix(symbols, days=90)
        if not r["success"]:
            return f"Correlation analysis failed: {r['error']}"
        d = r["data"]
        names = d["symbols"]
        header = "CORRELATION MATRIX (90d daily returns)"
        lines = [header, "-" * (14 + 8 * len(names)), "        " + "".join(f"{n:>8}" for n in names)]
        for n in names:
            row = d["matrix"][n]
            lines.append(f"{n:<8}" + "".join(f"{row[m]:>8.2f}" for m in names))
        lines += [
            "",
            f"Average correlation : {d['average_correlation']:.3f}  ({d['diversification']} diversification)",
            "Beta to BTC         : " + "  ".join(f"{k} {v:+.2f}" for k, v in d["beta_to_btc"].items()),
            "Most correlated     : " + ", ".join(f"{p['pair']} {p['correlation']:.2f}" for p in d["most_correlated"]),
            "Least correlated    : " + ", ".join(f"{p['pair']} {p['correlation']:.2f}" for p in d["least_correlated"]),
        ]
        return "\n".join(lines)
    
    async def _handle_orderbook(self, symbol: str) -> str:
        from tools.advanced_tools import analyze_order_book
        r = await analyze_order_book(symbol, 100)
        if not r["success"]:
            return f"Order book analysis failed: {r['error']}"
        d = r["data"]
        lines = [
            f"ORDER BOOK — {d['symbol']}", "-" * 70,
            f"Mid price        : {d['mid_price']:,.6f}",
            f"Spread           : {d['spread']:.6f} ({d['spread_pct']:.4f}%)  [{d['liquidity_quality']}]",
            f"Bid / Ask volume : {d['bid_volume']:,.2f} / {d['ask_volume']:,.2f}",
            f"Imbalance        : {d['imbalance_pct']:+.1f}%   pressure {d['pressure'].upper()}",
            f"Interpretation   : {d['interpretation']}",
            "",
            "Bid walls:",
        ]
        lines += [f"  {w['price']:,.6f}  size {w['quantity']:,.2f} ({w['multiple']}x avg)" for w in d["bid_walls"]] or ["  none"]
        lines.append("Ask walls:")
        lines += [f"  {w['price']:,.6f}  size {w['quantity']:,.2f} ({w['multiple']}x avg)" for w in d["ask_walls"]] or ["  none"]
        return "\n".join(lines)
    
    async def _handle_fib(self, symbol: str) -> str:
        from tools.advanced_tools import calculate_fibonacci
        data = await self._ohlcv_payload(symbol, 200)
        if not data:
            return f"No OHLCV data for {symbol.upper()}."
        r = await calculate_fibonacci(symbol=symbol, ohlcv=data)
        if not r["success"]:
            return f"Fibonacci failed: {r['error']}"
        d = r["data"]
        lines = [
            f"FIBONACCI — {symbol.upper()}  (trend {d['trend']}, range position {d['range_position_pct']}%)", "-" * 70,
            f"Swing high: {d['swing_high']:,.6f}    Swing low: {d['swing_low']:,.6f}",
            f"Current   : {d['current_price']:,.6f}    Golden zone: {'YES' if d['golden_zone'] else 'no'}",
            "",
            "Retracements:",
        ]
        for k, v in d["retracement_levels"].items():
            mark = "  <-- price" if abs(v - d["current_price"]) / d["current_price"] < 0.01 else ""
            lines.append(f"  {float(k)*100:>5.1f}%  {v:>14,.6f}{mark}")
        lines.append("Extensions:")
        for k, v in d["extension_levels"].items():
            lines.append(f"  {float(k)*100:>5.1f}%  {v:>14,.6f}")
        n = d["nearest_level"]
        lines.append(f"\nNearest level: {n['name']} at {n['price']:,.6f} ({n['distance_pct']:.2f}% away)")
        return "\n".join(lines)
    
    async def _handle_profile(self, symbol: str) -> str:
        from tools.advanced_tools import calculate_volume_profile
        data = await self._ohlcv_payload(symbol, 200)
        if not data:
            return f"No OHLCV data for {symbol.upper()}."
        r = await calculate_volume_profile(symbol=symbol, ohlcv=data)
        if not r["success"]:
            return f"Volume profile failed: {r['error']}"
        d = r["data"]
        lines = [
            f"VOLUME PROFILE — {symbol.upper()}", "-" * 70,
            f"POC             : {d['poc']:,.6f}",
            f"Value area      : {d['value_area_low']:,.6f} — {d['value_area_high']:,.6f}",
            f"Current price   : {d['current_price']:,.6f}  ({d['price_location'].replace('_', ' ')})",
            f"Bias            : {d['bias'].upper()}",
            "",
            "High volume nodes:",
        ]
        for h in d["high_volume_nodes"]:
            lines.append(f"  {h['price']:>14,.6f}   volume share {h['share_pct']:.2f}%")
        return "\n".join(lines)
    
    async def _handle_volatility(self, symbol: str) -> str:
        from tools.advanced_tools import analyze_volatility
        data = await self._ohlcv_payload(symbol, 200)
        if not data:
            return f"No OHLCV data for {symbol.upper()}."
        r = await analyze_volatility(symbol=symbol, ohlcv=data)
        if not r["success"]:
            return f"Volatility analysis failed: {r['error']}"
        d = r["data"]
        return "\n".join([
            f"VOLATILITY — {symbol.upper()}", "-" * 70,
            f"Realized vol 7d / 30d : {d['realized_vol_7d_pct']:.2f}% / {d['realized_vol_30d_pct']:.2f}%",
            f"Regime                : {d['regime'].upper()}   state: {d['volatility_state']}",
            f"ATR                   : {d['atr']:,.6f}  ({d['atr_pct']:.2f}% of price)",
            f"Max drawdown          : {d['max_drawdown_pct']:.2f}%",
            f"Note                  : {d['note']}",
        ])
    
    async def _handle_reversion(self, symbol: str) -> str:
        from tools.advanced_tools import calculate_mean_reversion
        data = await self._ohlcv_payload(symbol, 200)
        if not data:
            return f"No OHLCV data for {symbol.upper()}."
        r = await calculate_mean_reversion(symbol=symbol, ohlcv=data)
        if not r["success"]:
            return f"Mean reversion failed: {r['error']}"
        d = r["data"]
        b = d["bollinger"]
        return "\n".join([
            f"MEAN REVERSION — {symbol.upper()}", "-" * 70,
            f"Price        : {d['price']:,.6f}",
            f"SMA20 / SMA50: {d['sma20']:,.6f} / {d['sma50']:,.6f}  ({d['trend_context'].replace('_', ' ')})",
            f"Z-score      : {d['z_score']:+.3f}",
            f"Bollinger    : lower {b['lower']:,.6f}  mid {b['middle']:,.6f}  upper {b['upper']:,.6f}  (%B {b['percent_b']:.3f})",
            f"RSI(14)      : {d['rsi_14']:.2f}",
            f"Signal       : {d['signal'].replace('_', ' ').upper()}  (strength {d['strength']})",
            f"Distance SMA20: {d['distance_from_sma20_pct']:+.2f}%",
        ])
    
    async def _handle_ichimoku(self, symbol: str) -> str:
        from tools.advanced_tools import calculate_ichimoku
        data = await self._ohlcv_payload(symbol, 200)
        if not data:
            return f"No OHLCV data for {symbol.upper()}."
        r = await calculate_ichimoku(symbol=symbol, ohlcv=data)
        if not r["success"]:
            return f"Ichimoku failed: {r['error']}"
        d = r["data"]
        lines = [
            f"ICHIMOKU — {symbol.upper()}", "-" * 70,
            f"Tenkan / Kijun  : {d['tenkan_sen']:,.6f} / {d['kijun_sen']:,.6f}",
            f"Senkou A / B    : {d['senkou_span_a']:,.6f} / {d['senkou_span_b']:,.6f}",
            f"Cloud top/bottom: {d['cloud_top']:,.6f} / {d['cloud_bottom']:,.6f}  ({d['cloud_color']})",
            f"Price position  : {d['price_position'].replace('_', ' ').upper()}",
            f"Bias            : {d['bias'].upper()}",
            "",
        ]
        lines += [f"  • {s}" for s in d["signals"]]
        return "\n".join(lines)
    
    async def _handle_wyckoff(self, symbol: str) -> str:
        from tools.advanced_tools import analyze_wyckoff
        data = await self._ohlcv_payload(symbol, 200)
        if not data:
            return f"No OHLCV data for {symbol.upper()}."
        r = await analyze_wyckoff(symbol=symbol, ohlcv=data)
        if not r["success"]:
            return f"Wyckoff analysis failed: {r['error']}"
        d = r["data"]
        returns = [
            f"WYCKOFF — {symbol.upper()}", "-" * 70,
            f"Structure       : {d['structure'].upper()}   phase {d['phase']}",
            f"Prior trend     : {d['prior_trend']}",
            f"Trading range   : {d['range_low']:,.6f} — {d['range_high']:,.6f}  (width {d['range_width_pct']:.1f}%)",
            f"In range        : {'YES' if d['in_trading_range'] else 'no'}",
            f"Spring / Upthrust: {d['spring_detected']} / {d['upthrust_detected']}",
            f"Sign of strength / weakness: {d['sign_of_strength']} / {d['sign_of_weakness']}",
            f"Volume trend    : {d['volume_trend']}",
            f"Confidence      : {d['confidence']:.0%}",
        ]
        return "\n".join(returns)
    
    async def _handle_newpairs(self, network: str = "eth", limit: int = 15) -> str:
        from tools.advanced_tools import scan_new_pairs
        r = await scan_new_pairs(network, limit)
        if not r["success"]:
            return f"New pair scan failed: {r['error']}"
        d = r["data"]
        lines = [f"NEW DEX PAIRS — {network.upper()}  ({d['count']} pools)", "-" * 78]
        lines.append(f"{'PAIR':<32} {'LIQUIDITY':>14} {'VOL 24H':>14} {'24H':>9}")
        for p in d["pairs"]:
            lines.append(
                f"{(p['name'] or '?')[:32]:<32} {p['liquidity_usd']:>14,.0f} "
                f"{p['volume_24h_usd']:>14,.0f} {p['change_24h_pct']:>+8.1f}%"
            )
        lines.append("\nHigh-risk early-stage pools — verify contract and liquidity locks before acting.")
        return "\n".join(lines)
    
    async def _handle_gas(self, args: List[str]) -> str:
        from tools.advanced_tools import get_gas_prices
        chains = [a.lower() for a in args] or None
        r = await get_gas_prices(chains)
        if not r["success"]:
            return f"Gas tracker failed: {r['error']}"
        d = r["data"]
        lines = ["GAS TRACKER", "-" * 60]
        for name, info in d["chains"].items():
            if "error" in info:
                lines.append(f"  {name:<12} unavailable ({str(info['error'])[:40]})")
            else:
                extra = f"  base {info['base_fee_gwei']:.3f}" if "base_fee_gwei" in info else ""
                lines.append(f"  {name:<12} {info['gas_price_gwei']:>10.4f} gwei{extra}")
        if d.get("cheapest_chain"):
            lines.append(f"\nCheapest chain: {d['cheapest_chain']}")
        return "\n".join(lines)
    
    async def _handle_journal(self, args: List[str]) -> str:
        from tools.journal_tools import (
            add_trade, close_trade, list_trades as list_journal, get_trade_stats
        )
        action = args[0].lower() if args else "list"
        
        if action == "add":
            if len(args) < 4:
                return "Usage: /journal add <SYMBOL> <long|short> <ENTRY> [QTY]"
            symbol, side, entry = args[1], args[2], float(args[3])
            qty = float(args[4]) if len(args) > 4 else 0.0
            r = await add_trade(symbol, side, entry, qty)
            if not r["success"]:
                return f"Failed to add trade: {r['error']}"
            t = r["data"]
            return f"Trade #{t['id']} opened: {t['side'].upper()} {t['symbol']} @ {t['entry_price']} (qty {t['quantity']})"
        
        elif action == "close":
            if len(args) < 3:
                return "Usage: /journal close <TRADE_ID> <EXIT_PRICE>"
            r = await close_trade(int(args[1]), float(args[2]))
            if not r["success"]:
                return f"Failed to close trade: {r['error']}"
            t = r["data"]
            return (
                f"Trade #{t['id']} closed: {t['symbol']} {t['side'].upper()} "
                f"{t['entry_price']} -> {t['exit_price']}   PnL {t['pnl_pct']:+.2f}%"
            )
        
        elif action == "stats":
            r = await get_trade_stats()
            if not r["success"]:
                return f"Stats failed: {r['error']}"
            s = r["data"]
            return "\n".join([
                "TRADE JOURNAL STATS", "-" * 50,
                f"Closed trades : {s['total_trades']}",
                f"Wins / Losses : {s['wins']} / {s['losses']}",
                f"Win rate      : {s['win_rate']:.1f}%",
                f"Total PnL     : {s['total_pnl']:+.2f}%",
                f"Average PnL   : {s['avg_pnl_pct']:+.2f}%",
                f"Best / Worst  : {s['best_trade_pct']:+.2f}% / {s['worst_trade_pct']:+.2f}%",
                f"Profit factor : {s['profit_factor']}",
            ])
        
        else:
            status = args[1].lower() if len(args) > 1 else None
            r = await list_journal(status=status, limit=50)
            if not r["success"]:
                return f"Failed to list trades: {r['error']}"
            trades = r["data"]
            if not trades:
                return "No trades in the journal."
            lines = [f"TRADE JOURNAL ({len(trades)} entries)", "-" * 78]
            for t in trades:
                pnl = f"{t['pnl_pct']:+.2f}%" if t["pnl_pct"] is not None else "  open "
                lines.append(
                    f"  #{t['id']:<4} {t['symbol']:<8} {t['side']:<5} {t['status']:<6} "
                    f"entry {t['entry_price']:>12,.4f}  exit {str(t['exit_price'] or '-'):>12}  PnL {pnl}"
                )
            return "\n".join(lines)
    

    
    async def _handle_paper(self, args: List[str]) -> str:
        """Handle paper trading commands."""
        from tools.paper_trading_tools import (
            create_paper_account, get_paper_account, list_paper_accounts,
            open_paper_position, close_paper_position, update_paper_positions,
            get_paper_account_stats, get_paper_trades
        )
        
        if not args:
            return "Usage: /paper create|list|open|close|update|stats|trades [args...]"
        
        action = args[0].lower()
        conversation = get_conversation_manager()
        session = conversation._current_session
        if not session:
            return "No active session. Start a conversation first."
        
        if action == "create":
            if len(args) < 2:
                return "Usage: /paper create <NAME> [INITIAL_BALANCE]"
            name = args[1]
            balance = float(args[2]) if len(args) > 2 else 10000.0
            r = await create_paper_account(session.id, name, balance)
            if not r["success"]:
                return f"Failed: {r['error']}"
            a = r["data"]
            return f"Created paper account #{a['id']}: {a['name']} with ${a['initial_balance']:,.2f}"
        
        elif action == "list":
            r = await list_paper_accounts(session.id)
            if not r["success"]:
                return f"Failed: {r['error']}"
            accounts = r["data"]
            if not accounts:
                return "No paper accounts. Create one with: /paper create <NAME>"
            lines = ["PAPER ACCOUNTS", "-" * 60]
            for a in accounts:
                lines.append(f"  #{a['id']}: {a['name']}  Balance: ${a['current_balance']:,.2f}  PnL: ${a.get('total_pnl',0):+,.2f} ({a.get('total_pnl_pct',0):+.2f}%)")
            return "\n".join(lines)
        
        elif action == "open":
            if len(args) < 6:
                return "Usage: /paper open <ACCOUNT_ID> <SYMBOL> <long|short> <QTY> <ENTRY> [SL] [TP]"
            account_id = int(args[1])
            symbol, side, qty, entry = args[2], args[3], float(args[4]), float(args[5])
            sl = float(args[6]) if len(args) > 6 else None
            tp = float(args[7]) if len(args) > 7 else None
            r = await open_paper_position(account_id, symbol, side, qty, entry, sl, tp)
            if not r["success"]:
                return f"Failed: {r['error']}"
            t = r["data"]["trade"]
            p = r["data"]["position"]
            return f"Opened #{p['id']}: {t['side'].upper()} {t['symbol']} x{t['quantity']} @ {t['price']:,.4f}" + (f"  SL:{sl}" if sl else "") + (f"  TP:{tp}" if tp else "")
        
        elif action == "close":
            if len(args) < 4:
                return "Usage: /paper close <ACCOUNT_ID> <POSITION_ID> <EXIT_PRICE> [QTY]"
            account_id = int(args[1])
            pos_id = int(args[2])
            exit_price = float(args[3])
            qty = float(args[4]) if len(args) > 4 else None
            r = await close_paper_position(account_id, pos_id, exit_price, qty)
            if not r["success"]:
                return f"Failed: {r['error']}"
            t = r["data"]["trade"]
            return f"Closed #{t['id']}: {t['symbol']} {t['side'].upper()} @ {t['price']:,.4f}  PnL {t.get('pnl_pct',0):+.2f}%"
        
        elif action == "update":
            if len(args) < 3:
                return "Usage: /paper update <ACCOUNT_ID> <SYMBOL=PRICE>..."
            account_id = int(args[1])
            prices = {}
            for arg in args[2:]:
                if "=" in arg:
                    sym, price = arg.split("=")
                    prices[sym.upper()] = float(price)
            if not prices:
                return "Usage: /paper update <ACCOUNT_ID> BTC=45000 ETH=3000..."
            r = await update_paper_positions(account_id, prices)
            if not r["success"]:
                return f"Failed: {r['error']}"
            lines = ["POSITIONS UPDATED", "-" * 50]
            for p in r["data"]:
                lines.append(f"  {p['symbol']}: ${p['current_price']:,.4f}  uPnL: ${p['unrealized_pnl']:+,.2f} ({p['unrealized_pnl_pct']:+.2f}%)")
            return "\n".join(lines)
        
        elif action == "stats":
            if len(args) < 2:
                return "Usage: /paper stats <ACCOUNT_ID>"
            r = await get_paper_account_stats(int(args[1]))
            if not r["success"]:
                return f"Failed: {r['error']}"
            d = r["data"]
            return "\n".join([
                f"PAPER ACCOUNT STATS — {d.get('account_name','')}", "-" * 60,
                f"Balance: ${d['current_balance']:,.2f}  (Avail: ${d['available_balance']:,.2f})",
                f"Total PnL: ${d['total_pnl']:+,.2f} ({d['total_pnl_pct']:+.2f}%)",
                f"Max DD: ${d['max_drawdown']:,.2f} ({d['max_drawdown_pct']:.2f}%)",
                f"Trades: {d['total_trades']}  Wins: {d['wins']}  Losses: {d['losses']}",
                f"Win Rate: {d['win_rate']:.1f}%  PF: {d['profit_factor']:.2f}  Sharpe: {d['sharpe_ratio']:.2f}",
                f"Avg Win: {d['avg_win']:+.2f}%  Avg Loss: {d['avg_loss']:+.2f}%  Expectancy: {d['expectancy']:+.2f}%",
            ])
        
        elif action == "trades":
            if len(args) < 2:
                return "Usage: /paper trades <ACCOUNT_ID> [SYMBOL] [LIMIT]"
            account_id = int(args[1])
            symbol = args[2].upper() if len(args) > 2 else None
            limit = int(args[3]) if len(args) > 3 else 20
            r = await get_paper_trades(account_id, symbol, limit)
            if not r["success"]:
                return f"Failed: {r['error']}"
            trades = r["data"]
            if not trades:
                return "No trades found."
            lines = [f"PAPER TRADES ({len(trades)})", "-" * 70]
            for t in trades:
                pnl = f"{t.get('pnl_pct',0):+.2f}%" if t.get('pnl_pct') is not None else " open"
                lines.append(f"  #{t['id']:<4} {t['symbol']:<8} {t['side']:<5} {t['action']:<6}  qty {t['quantity']:<10} @ {t['price']:>10,.4f}  PnL {pnl}")
            return "\n".join(lines)
        
        else:
            return f"Unknown paper action: {action}. Use: create, list, open, close, update, stats, trades"
    
    
    async def _handle_strategy(self, args: List[str]) -> str:
        """Handle strategy learning commands."""
        from tools.strategy_tools import (
            create_strategy, get_strategy, list_strategies,
            backtest_strategy, run_multi_symbol_backtest,
            optimize_strategy_parameters, discover_patterns,
            get_learning_patterns, get_backtest_results,
            get_strategy_performance
        )
        
        if not args:
            return "Usage: /strategy create|list|backtest|multi|optimize|learn|patterns|perf [args...]"
        
        action = args[0].lower()
        conversation = get_conversation_manager()
        session = conversation._current_session
        if not session:
            return "No active session."
        
        if action == "create":
            if len(args) < 4:
                return "Usage: /strategy create <NAME> <TYPE> <SYMBOLS...> [DESCRIPTION]"
            name = args[1]
            strat_type = args[2]
            symbols = [s.upper() for s in args[3:]]
            desc = "User-created strategy"
            defaults = {
                "trend_following": {
                    "parameters": {"ema_fast":12,"ema_slow":26,"rsi_period":14},
                    "entry_rules": {"rsi_filter":True,"rsi_max":70},
                    "exit_rules": {"rsi_exit":75,"trail_pct":0.02},
                    "risk_rules": {"risk_per_trade":0.02,"stop_loss_pct":0.05,"take_profit_pct":0.10}
                },
                "mean_reversion": {
                    "parameters": {"rsi_period":14,"bb_period":20},
                    "entry_rules": {"rsi_oversold":30},
                    "exit_rules": {"rsi_exit":50},
                    "risk_rules": {"risk_per_trade":0.02,"stop_loss_pct":0.05,"take_profit_pct":0.10}
                },
                "breakout": {
                    "parameters": {"lookback":20,"vol_mult":1.5},
                    "entry_rules": {"vol_mult":1.5},
                    "exit_rules": {"trail_pct":0.02},
                    "risk_rules": {"risk_per_trade":0.02,"stop_loss_pct":0.05,"take_profit_pct":0.10}
                }
            }
            d = defaults.get(strat_type, defaults["trend_following"])
            r = await create_strategy(
                session_id=session.id, name=name, description=desc,
                strategy_type=strat_type, symbols=symbols, timeframes=["1d","4h"],
                parameters=d["parameters"], entry_rules=d["entry_rules"],
                exit_rules=d["exit_rules"], risk_rules=d["risk_rules"]
            )
            if not r["success"]:
                return f"Failed: {r['error']}"
            return f"Created strategy #{r['data']['id']}: {name} ({strat_type}) for {', '.join(symbols)}"
        
        elif action == "list":
            type_filter = args[1] if len(args) > 1 else None
            r = await list_strategies(session.id, strategy_type=type_filter)
            if not r["success"]:
                return f"Failed: {r['error']}"
            strats = r["data"]
            if not strats:
                return "No strategies. Create one with: /strategy create <NAME> <TYPE> <SYMBOLS>"
            lines = ["STRATEGIES", "-" * 70]
            for s in strats:
                learned = " [LEARNED]" if s.get('is_learned') else ""
                lines.append(f"  #{s['id']}: {s['name']} ({s['strategy_type']})  {s['symbols']}{learned}")
            return "\n".join(lines)
        
        elif action == "backtest":
            if len(args) < 3:
                return "Usage: /strategy backtest <STRATEGY_ID> <SYMBOL> [TIMEFRAME] [START] [END]"
            strategy_id = int(args[1])
            symbol = args[2].upper()
            tf = args[3] if len(args) > 3 else "1d"
            start = args[4] if len(args) > 4 else None
            end = args[5] if len(args) > 5 else None
            r = await backtest_strategy(strategy_id, symbol, tf, start, end)
            if not r["success"]:
                return f"Failed: {r['error']}"
            d = r["data"]
            return "\n".join([
                f"BACKTEST — {symbol} ({tf})", "-" * 60,
                f"Trades: {d['total_trades']}  Wins: {d['wins']}  Losses: {d['losses']}",
                f"Win Rate: {d['win_rate']:.1f}%  PF: {d['profit_factor']:.2f}",
                f"Return: {d['total_return_pct']:+.2f}%  Annual: {d['annualized_return_pct']:+.2f}%",
                f"Sharpe: {d['sharpe_ratio']:.2f}  Sortino: {d['sortino_ratio']:.2f}  Calmar: {d['calmar_ratio']:.2f}",
                f"Max DD: {d['max_drawdown_pct']:.2f}%  Expectancy: {d['expectancy']:+.2f}%",
            ])
        
        elif action == "multi":
            if len(args) < 3:
                return "Usage: /strategy multi <STRATEGY_ID> <SYM1> <SYM2> ... [TF]"
            strategy_id = int(args[1])
            symbols = [s.upper() for s in args[2:]]
            tf = "1d" if symbols[-1] in ("1d","4h","1h") else "1d"
            if symbols[-1] in ("1d","4h","1h"):
                tf = symbols.pop()
            r = await run_multi_symbol_backtest(strategy_id, symbols, tf)
            if not r["success"]:
                return f"Failed: {r['error']}"
            d = r["data"]
            return "\n".join([
                f"MULTI-SYMBOL BACKTEST ({tf})", "-" * 60,
                f"Aggregate: {d['aggregate']['total_trades']} trades  WR: {d['aggregate']['win_rate']:.1f}%  PF: {d['aggregate']['profit_factor']:.2f}",
                f"Return: {d['aggregate']['avg_return_pct']:+.2f}%  Expectancy: {d['aggregate']['expectancy']:+.2f}%",
                "Per-symbol: " + ", ".join(f"{k}: {v['total_trades']}t/{v['win_rate']:.0f}%" for k,v in d['symbols'].items())
            ])
        
        elif action == "optimize":
            if len(args) < 3:
                return "Usage: /strategy optimize <STRATEGY_ID> <SYMBOL> <PARAM=VAL1,VAL2...>..."
            strategy_id = int(args[1])
            symbol = args[2].upper()
            param_grid = {}
            for arg in args[3:]:
                if "=" in arg:
                    key, vals = arg.split("=")
                    param_grid[key] = [float(v) if "." in v else int(v) for v in vals.split(",")]
            if not param_grid:
                return "Usage: /strategy optimize 1 BTC ema_fast=8,12,16 ema_slow=21,26,30"
            r = await optimize_strategy_parameters(strategy_id, symbol, param_grid)
            if not r["success"]:
                return f"Failed: {r['error']}"
            d = r["data"]
            return "\n".join([
                f"OPTIMIZATION RESULT — {symbol}", "-" * 60,
                f"Best {d['best_metric']}: {d['best_value']:.4f}",
                f"Parameters: {d['best_parameters']}",
                f"Trades: {d['backtest_result']['total_trades']}  WR: {d['backtest_result']['win_rate']:.1f}%  Sharpe: {d['backtest_result']['sharpe_ratio']:.2f}"
            ])
        
        elif action == "learn":
            if len(args) < 2:
                return "Usage: /strategy learn <SYMBOL> [DAYS] [MIN_WR]"
            symbol = args[1].upper()
            days = int(args[2]) if len(args) > 2 else 365
            min_wr = float(args[3]) if len(args) > 3 else 0.55
            r = await discover_patterns(session.id, symbol, "1d", days, 5, min_wr)
            if not r["success"]:
                return f"Failed: {r['error']}"
            patterns = r["data"]["discovered_patterns"]
            if not patterns:
                return f"No patterns found for {symbol} meeting criteria."
            lines = [f"DISCOVERED PATTERNS — {symbol}", "-" * 60]
            for p in patterns:
                lines.append(f"  {p['pattern_name']}: WR={p['confidence']:.0%}  N={p['times_observed']}  {p['description']}")
            return "\n".join(lines)
        
        elif action == "patterns":
            min_conf = float(args[1]) if len(args) > 1 else 0.5
            r = await get_learning_patterns(session.id, min_confidence=min_conf)
            if not r["success"]:
                return f"Failed: {r['error']}"
            patterns = r["data"]
            if not patterns:
                return "No patterns found."
            lines = [f"LEARNED PATTERNS (conf >= {min_conf:.0%})", "-" * 60]
            for p in patterns:
                lines.append(f"  {p['pattern_name']} ({p['pattern_type']}): conf={p['confidence']:.0%}  obs={p['times_observed']}  syms={p['symbols_tested']}")
            return "\n".join(lines)
        
        elif action == "perf":
            if len(args) < 2:
                return "Usage: /strategy perf <STRATEGY_ID>"
            r = await get_strategy_performance(int(args[1]))
            if not r["success"]:
                return f"Failed: {r['error']}"
            d = r["data"]
            s = d.get("strategy")
            hist = d.get("performance_history", [])
            lines = [f"STRATEGY PERFORMANCE — {s['name'] if s else '?'}", "-" * 60]
            if s:
                lines.append(f"Type: {s['strategy_type']}  Symbols: {s['symbols']}")
                lines.append(f"Total trades: {s['total_trades']}  WR: {s['win_rate']:.1f}%  Sharpe: {s['sharpe_ratio']:.2f}")
            if hist:
                lines.append("\nHistory:")
                for h in hist[:5]:
                    lines.append(f"  {h['period_start'].date()} to {h['period_end'].date()}: {h['total_trades']}t  WR={h['win_rate']:.1f}%  PnL={h['total_pnl_pct']:+.2f}%")
            return "\n".join(lines)
        
        else:
            return f"Unknown strategy action: {action}. Use: create, list, backtest, multi, optimize, learn, patterns, perf"


    async def _handle_analyze(self, symbol: str) -> str:
        """Handle analyze command with a real technical + market snapshot."""
        market = await get_market_data_provider()
        symbol = symbol.upper()

        coin = None
        for c in await market.get_coins_markets(order="market_cap_desc", per_page=250):
            if c.symbol == symbol:
                coin = c
                break

        from tools.technical_tools import (
            full_technical_analysis, detect_support_resistance,
        )

        ta = await full_technical_analysis(symbol)
        sr = await detect_support_resistance(symbol)

        if not ta.get("success") and not coin:
            return f"No data found for {symbol}."

        lines = [f"ANALYSIS — {symbol}", "=" * 70]
        if coin:
            lines += [
                f"Name         : {coin.name} ({coin.symbol})",
                f"Price        : ${(coin.current_price or 0):,.6f}",
                f"Market cap   : ${(coin.market_cap or 0):,.0f}  (rank {coin.market_cap_rank})",
                f"24h volume   : ${(coin.total_volume or 0):,.0f}",
                f"24h / 7d / 30d: {(coin.price_change_percentage_24h or 0):+.2f}% / "
                f"{(coin.price_change_percentage_7d or 0):+.2f}% / "
                f"{(coin.price_change_percentage_30d or 0):+.2f}%",
                f"Circulating  : {(coin.circulating_supply or 0):,.0f}"
                f"  / total {(coin.total_supply or 0):,.0f}"
                f"  / max {(coin.max_supply or 0):,.0f}",
                f"ATH          : ${(coin.ath or 0):,.6f}",
            ]

        if ta.get("success"):
            data = ta["data"]
            ind = data.get("indicators", {})
            structure = data.get("structure", {})
            summary = data.get("summary", {})
            atr_pct = ind.get("atr_pct")
            lines.append("")
            lines.append("Technical")
            rsi = ind.get("rsi")
            if isinstance(rsi, (int, float)):
                zone = "oversold" if rsi < 30 else "overbought" if rsi > 70 else "neutral"
                lines.append(f"  RSI(14)      : {rsi:.2f}  ({zone})")
            macd = ind.get("macd") or {}
            if isinstance(macd, dict) and macd.get("histogram") is not None:
                lines.append(f"  MACD hist    : {macd['histogram']:+.6f}  ({macd.get('trend', 'n/a')})")
            if atr_pct is not None:
                lines.append(f"  ATR          : {ind.get('atr', 0):,.6f}  ({atr_pct:.2f}% of price)")
            emas = ind.get("emas") or {}
            if emas:
                lines.append("  EMAs         : " + "  ".join(f"{k.replace('ema_', '')}={v:,.2f}" for k, v in emas.items()))
            trend = structure.get("trend") if isinstance(structure, dict) else None
            if trend:
                lines.append(f"  Trend        : {trend}  (structure: {structure.get('structure', 'n/a')})")
            if isinstance(summary, dict) and summary:
                lines.append(
                    f"  Bias         : {summary.get('bias', 'n/a')}  "
                    f"(bull {summary.get('bullish_signals', 0)} / bear {summary.get('bearish_signals', 0)}, "
                    f"confidence {summary.get('confidence', 0):.0%})"
                )

        if sr.get("success"):
            data = sr["data"]
            supports = data.get("support", [])[:3]
            resistances = data.get("resistance", [])[:3]
            lines.append("")
            lines.append("Levels")
            if supports:
                lines.append("  Support   : " + ", ".join(f"{s['price']:,.6f} ({s.get('touches', 0)} touches)" for s in supports))
            if resistances:
                lines.append("  Resistance: " + ", ".join(f"{r['price']:,.6f} ({r.get('touches', 0)} touches)" for r in resistances))
            if data.get("distance_to_support_pct") is not None:
                lines.append(
                    f"  Distance  : {data['distance_to_support_pct']:.2f}% to support, "
                    f"{data.get('distance_to_resistance_pct', 0):.2f}% to resistance"
                )

        return "\n".join(lines)
    
    async def _handle_compare(self, sym1: str, sym2: str) -> str:
        """Handle compare command using real market data."""
        from tools.research_tools import compare_coins

        r = await compare_coins(symbols=[sym1.upper(), sym2.upper()])
        if not r.get("success"):
            return f"Comparison failed: {r.get('error')}"

        d = r["data"]
        coins = d.get("coins", [])
        if not coins:
            return "No comparison data available."

        attrs = [
            ("current_price", "Price", "{:,.6f}"),
            ("market_cap", "Market cap", "{:,.0f}"),
            ("volume_24h", "24h volume", "{:,.0f}"),
            ("price_change_24h", "24h change", "{:+.2f}%"),
            ("price_change_7d", "7d change", "{:+.2f}%"),
            ("price_change_30d", "30d change", "{:+.2f}%"),
        ]
        best = d.get("best_by_metric", {})

        lines = [f"COMPARISON — {sym1.upper()} vs {sym2.upper()}", "-" * 70]
        header = f"{'METRIC':<14}" + "".join(f"{c.get('symbol', '?'):>22}" for c in coins)
        lines.append(header)
        for key, label, fmt in attrs:
            row = f"{label:<14}"
            for c in coins:
                value = c.get(key)
                cell = "n/a" if value is None else fmt.format(value)
                row += f"{cell:>22}"
            lines.append(row)

        lines.append("")
        wins = [f"{k}: {v}" for k, v in best.items()]
        if wins:
            lines.append("Best by metric: " + ", ".join(wins))
        return "\n".join(lines)
    
    async def _handle_whales(self, symbol: str) -> str:
        """Handle whales command."""
        return f"Tracking whales for {symbol.upper()}... (use natural language: 'Show whale activity for {symbol}')"
    
    async def _handle_wallet(self, chain: str, address: str) -> str:
        """Handle wallet command."""
        return f"Analyzing wallet {address} on {chain}... (use natural language: 'Analyze wallet {address} on {chain}')"
    
    async def _handle_watchlist(self, args: List[str]) -> str:
        """Handle watchlist command."""
        conversation = get_conversation_manager()
        db = await get_db_manager()
        
        if not conversation._current_session:
            return "No active session."
        
        if not args or args[0] == "list":
            items = await db.get_watchlist(conversation._current_session.id)
            if not items:
                return "Watchlist is empty."
            lines = ["Watchlist:"]
            for item in items:
                lines.append(f"  {item.symbol} ({item.name or 'Unknown'}) - Added at ${item.added_price or 'N/A'}")
            return "\n".join(lines)
        
        elif args[0] == "add" and len(args) > 1:
            symbol = args[1].upper()
            await db.add_to_watchlist(conversation._current_session.id, symbol)
            return f"Added {symbol} to watchlist."
        
        elif args[0] == "remove" and len(args) > 1:
            symbol = args[1].upper()
            await db.remove_from_watchlist(conversation._current_session.id, symbol)
            return f"Removed {symbol} from watchlist."
        
        return "Usage: /watchlist [add|remove|list] [SYMBOL]"
    
    async def _handle_skills(self, args: List[str]) -> str:
        """Handle skills command."""
        registry = get_skill_registry()
        
        if not args or args[0] == "list":
            skills = registry.list_skills()
            lines = ["Installed Skills:"]
            for skill in skills:
                status_icon = "🟢" if skill.status.value == "active" else ("🔴" if skill.status.value == "error" else "⚪")
                lines.append(f"  {status_icon} {skill.name} v{skill.version} - {skill.description[:60]}")
            return "\n".join(lines)
        
        elif args[0] == "active":
            skills = registry.get_active_skills()
            return "Active Skills:\n" + "\n".join(f"  - {s.name}" for s in skills)
        
        elif args[0] == "enable" and len(args) > 1:
            success = registry.activate_skill(args[1])
            return f"Skill {args[1]} {'activated' if success else 'not found'}."
        
        elif args[0] == "disable" and len(args) > 1:
            success = registry.deactivate_skill(args[1])
            return f"Skill {args[1]} {'deactivated' if success else 'not found'}."
        
        elif args[0] == "inspect" and len(args) > 1:
            skill = registry.get_skill(args[1])
            if skill:
                return f"""
Skill: {skill.name} v{skill.version}
Display: {skill.display_name}
Description: {skill.description}
Status: {skill.status.value}
Dependencies: {', '.join(skill.dependencies) or 'None'}
Required APIs: {', '.join(skill.required_apis) or 'None'}
Tools: {', '.join(skill.available_tools) or 'None'}
Priority: {skill.priority}
Core: {skill.is_core}
"""
            return f"Skill {args[1]} not found."
        
        return "Usage: /skills [list|active|enable|disable|inspect] [NAME]"
    
    async def _handle_memory(self, args: List[str]) -> str:
        """Handle memory command."""
        memory = await get_memory_manager()
        
        if not args or args[0] == "search":
            query = " ".join(args[1:]) if len(args) > 1 else ""
            if query:
                results = await memory.search(query)
                return f"Memory search results for '{query}':\n" + "\n".join(f"  - {r}" for r in results[:5])
            return "Usage: /memory search <QUERY>"
        
        elif args[0] == "export":
            data = await memory.export()
            return f"Memory exported: {len(data)} entries"
        
        elif args[0] == "clear":
            await memory.clear()
            return "Memory cleared."
        
        return "Usage: /memory [search|export|clear] [QUERY]"
    
    async def _handle_history(self, args: List[str]) -> str:
        """Handle history command."""
        conversation = get_conversation_manager()
        
        if not args:
            history = await conversation.get_conversation_history(20)
            lines = ["Recent Conversation:"]
            for msg in history[-10:]:
                prefix = "You" if msg["role"] == "user" else "Agent"
                lines.append(f"  {prefix}: {msg['content'][:100]}...")
            return "\n".join(lines)
        
        elif args[0] == "search" and len(args) > 1:
            query = " ".join(args[1:])
            results = await conversation.search_history(query)
            lines = [f"Search results for '{query}':"]
            for msg in results[:5]:
                lines.append(f"  [{msg['role']}] {msg['content'][:150]}...")
            return "\n".join(lines)
        
        return "Usage: /history [search <QUERY>]"
    
    async def _handle_report(self, args: List[str]) -> str:
        """Handle report command."""
        return "Report generation not yet implemented. Use natural language to request a report."
    
    async def _handle_config(self, args: List[str]) -> str:
        """Handle config command."""
        settings = get_settings()
        
        if not args or args[0] == "show":
            return f"""
Configuration:
  Kilo API: {settings.kilo_api.base_url}
  Default Model: {settings.kilo_api.default_model}
  Temperature: {settings.kilo_api.temperature}
  Max Tokens: {settings.kilo_api.max_tokens}
  Market Data: {settings.market_data.primary}
  Scanner Min Market Cap: ${settings.scanner.min_market_cap:,}
  Scanner Min Volume: ${settings.scanner.min_volume_24h:,}
  Database: {settings.database.path}
  Log Level: {settings.logging.level}
"""
        
        elif args[0] == "set" and len(args) >= 3:
            key = args[1]
            value = args[2]
            # Would need to implement config updating
            return f"Config setting '{key}' = '{value}' (not yet implemented)"
        
        return "Usage: /config [show|set <key> <value>]"
    
    def get_status(self) -> AgentStatus:
        """Get current agent status."""
        return self.status
    
    async def run_interactive(self) -> None:
        """Run interactive CLI loop."""
        self._running = True
        print(self._get_status_text())
        print("\nType /help for commands or ask me anything about crypto.\n")
        
        while self._running:
            try:
                user_input = input("crypto-agent > ").strip()
                
                if not user_input:
                    continue
                
                print()  # New line
                
                async for chunk in self.process_message(user_input):
                    print(chunk, end="", flush=True)
                
                print("\n")
                
            except KeyboardInterrupt:
                print("\nInterrupted. Type /exit to quit.")
            except EOFError:
                break
            except Exception as e:
                print(f"\nError: {e}\n")
        
        await self.shutdown()


# Global agent instance
_agent: Optional[CryptoIntelligenceAgent] = None


def get_agent() -> CryptoIntelligenceAgent:
    """Get the global agent instance."""
    global _agent
    if _agent is None:
        _agent = CryptoIntelligenceAgent()
    return _agent


async def main():
    """Main entry point."""
    agent = get_agent()
    
    if await agent.initialize():
        await agent.run_interactive()
    else:
        print("Failed to initialize agent.")


if __name__ == "__main__":
    asyncio.run(main())