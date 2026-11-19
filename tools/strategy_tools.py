"""
Strategy learning and backtesting tools for the Crypto Intelligence Agent.
Strategy management, backtesting engine, pattern discovery, and performance analytics.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import numpy as np
import pandas as pd

from database.storage import get_db_manager
from tools.market_tools import ToolResult
from providers.market_data import get_market_data_provider, OHLCVData



def _model_to_dict(obj) -> Dict:
    """Convert SQLAlchemy model to dict."""
    if obj is None:
        return None
    result = {}
    for col in obj.__table__.columns:
        value = getattr(obj, col.name)
        if isinstance(value, datetime):
            value = value.isoformat()
        result[col.name] = value
    return result


# Tool function wrappers

async def create_strategy(
    session_id: int,
    name: str,
    description: str,
    strategy_type: str,
    parameters: Dict,
    entry_rules: Dict,
    exit_rules: Dict,
    risk_rules: Dict,
    symbols: List[str],
    timeframes: List[str],
    is_learned: bool = False,
    parent_strategy_id: Optional[int] = None
) -> Dict:
    """Create a new trading strategy."""
    try:
        db = await get_db_manager()
        strategy = await db.create_strategy(
            session_id=session_id,
            name=name,
            description=description,
            strategy_type=strategy_type,
            parameters=parameters,
            entry_rules=entry_rules,
            exit_rules=exit_rules,
            risk_rules=risk_rules,
            symbols=symbols,
            timeframes=timeframes,
            is_learned=is_learned,
            parent_strategy_id=parent_strategy_id
        )
        return ToolResult(
            success=True,
            data=_model_to_dict(strategy),
            source="strategy_learning",
            timestamp=datetime.utcnow()
        ).to_dict()
    except Exception as e:
        return ToolResult(
            success=False,
            data=None,
            source="strategy_learning",
            timestamp=datetime.utcnow(),
            error=str(e)
        ).to_dict()


async def get_strategy(strategy_id: int) -> Dict:
    """Get a strategy by ID."""
    try:
        db = await get_db_manager()
        strategy = await db.get_strategy(strategy_id)
        if not strategy:
            return ToolResult(
                success=False,
                data=None,
                source="strategy_learning",
                timestamp=datetime.utcnow(),
                error="Strategy not found"
            ).to_dict()
        return ToolResult(
            success=True,
            data=_model_to_dict(strategy),
            source="strategy_learning",
            timestamp=datetime.utcnow()
        ).to_dict()
    except Exception as e:
        return ToolResult(
            success=False,
            data=None,
            source="strategy_learning",
            timestamp=datetime.utcnow(),
            error=str(e)
        ).to_dict()


async def list_strategies(
    session_id: int,
    strategy_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    is_learned: Optional[bool] = None
) -> Dict:
    """List strategies for a session."""
    try:
        db = await get_db_manager()
        strategies = await db.get_strategies(session_id, strategy_type, is_active, is_learned)
        return ToolResult(
            success=True,
            data=[_model_to_dict(s) for s in strategies],
            source="strategy_learning",
            timestamp=datetime.utcnow()
        ).to_dict()
    except Exception as e:
        return ToolResult(
            success=False,
            data=None,
            source="strategy_learning",
            timestamp=datetime.utcnow(),
            error=str(e)
        ).to_dict()


async def backtest_strategy(
    strategy_id: int,
    symbol: str,
    timeframe: str = "1d",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    initial_balance: float = 10000.0,
    parameters_override: Optional[Dict] = None
) -> Dict:
    """Run a backtest for a strategy on historical data."""
    try:
        db = await get_db_manager()
        strategy = await db.get_strategy(strategy_id)
        if not strategy:
            return ToolResult(
                success=False,
                data=None,
                source="strategy_learning",
                timestamp=datetime.utcnow(),
                error="Strategy not found"
            ).to_dict()
        
        # Extract strategy data before session closes
        strategy_data = {
            "strategy_type": strategy.strategy_type,
            "parameters": dict(strategy.parameters),
            "entry_rules": dict(strategy.entry_rules),
            "exit_rules": dict(strategy.exit_rules),
            "risk_rules": dict(strategy.risk_rules),
        }
        
        # Get market data
        provider = await get_market_data_provider()
        
        # Parse dates
        end = datetime.fromisoformat(end_date) if end_date else datetime.utcnow()
        start = datetime.fromisoformat(start_date) if start_date else end - timedelta(days=365)
        
        # Fetch OHLCV data
        ohlcv = await provider.get_historical_ohlcv(symbol, timeframe, (end - start).days)
        if not ohlcv or len(ohlcv.closes) < 50:
            return ToolResult(
                success=False,
                data=None,
                source="strategy_learning",
                timestamp=datetime.utcnow(),
                error=f"Insufficient data for {symbol}"
            ).to_dict()
        
        # Run backtest
        result = _run_backtest(
            strategy=strategy_data,
            ohlcv=ohlcv,
            initial_balance=initial_balance,
            parameters_override=parameters_override
        )
        
        # Save result
        # Filter result to match save_backtest_result signature
        bt_fields = {
            "final_balance": result.get("final_balance", initial_balance * (1 + result.get("total_return_pct", 0) / 100)),
            "total_return_pct": result.get("total_return_pct", 0),
            "annualized_return_pct": result.get("annualized_return_pct", 0),
            "total_trades": result.get("total_trades", 0),
            "wins": result.get("wins", 0),
            "losses": result.get("losses", 0),
            "win_rate": result.get("win_rate", 0),
            "profit_factor": result.get("profit_factor", 0),
            "sharpe_ratio": result.get("sharpe_ratio", 0),
            "sortino_ratio": result.get("sortino_ratio", 0),
            "max_drawdown_pct": result.get("max_drawdown_pct", 0),
            "avg_holding_hours": result.get("avg_holding_hours", 0),
            "expectancy": result.get("expectancy", 0),
            "calmar_ratio": result.get("calmar_ratio", 0),
            "trades_detail": result.get("trades_detail", []),
            "equity_curve": result.get("equity_curve", []),
            "parameters_used": result.get("parameters_used", {}),
        }
        
        await db.save_backtest_result(
            strategy_id=strategy_id,
            symbol=symbol.upper(),
            timeframe=timeframe,
            start_date=start,
            end_date=end,
            initial_balance=initial_balance,
            **bt_fields
        )
        
        # Update strategy performance
        await db.update_strategy_performance(
            strategy_id=strategy_id,
            total_trades=result["total_trades"],
            win_rate=result["win_rate"],
            avg_win=result.get("avg_win_pct", 0),
            avg_loss=result.get("avg_loss_pct", 0),
            profit_factor=result["profit_factor"],
            sharpe_ratio=result["sharpe_ratio"],
            max_drawdown=result["max_drawdown_pct"],
            expectancy=result["expectancy"]
        )
        
        return ToolResult(
            success=True,
            data=result,
            source="strategy_learning",
            timestamp=datetime.utcnow()
        ).to_dict()
    except Exception as e:
        return ToolResult(
            success=False,
            data=None,
            source="strategy_learning",
            timestamp=datetime.utcnow(),
            error=str(e)
        ).to_dict()


async def run_multi_symbol_backtest(
    strategy_id: int,
    symbols: List[str],
    timeframe: str = "1d",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    initial_balance: float = 10000.0
) -> Dict:
    """Run backtest across multiple symbols."""
    try:
        results = {}
        for symbol in symbols:
            r = await backtest_strategy(strategy_id, symbol, timeframe, start_date, end_date, initial_balance)
            if r["success"]:
                results[symbol] = r["data"]
        
        # Aggregate
        all_trades = []
        for sym_data in results.values():
            all_trades.extend(sym_data.get("trades_detail", []))
        
        if not all_trades:
            return ToolResult(
                success=False,
                data=None,
                source="strategy_learning",
                timestamp=datetime.utcnow(),
                error="No trades generated"
            ).to_dict()
        
        pnls = [t["pnl_pct"] for t in all_trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        
        return ToolResult(
            success=True,
            data={
                "symbols": results,
                "aggregate": {
                    "total_trades": len(all_trades),
                    "wins": len(wins),
                    "losses": len(losses),
                    "win_rate": len(wins) / len(all_trades) * 100,
                    "avg_return_pct": np.mean(pnls) if pnls else 0,
                    "profit_factor": (sum(wins) / abs(sum(losses))) if losses else float("inf"),
                    "expectancy": np.mean(pnls) if pnls else 0,
                }
            },
            source="strategy_learning",
            timestamp=datetime.utcnow()
        ).to_dict()
    except Exception as e:
        return ToolResult(
            success=False,
            data=None,
            source="strategy_learning",
            timestamp=datetime.utcnow(),
            error=str(e)
        ).to_dict()


async def optimize_strategy_parameters(
    strategy_id: int,
    symbol: str,
    timeframe: str = "1d",
    param_grid: Dict[str, List] = None,
    metric: str = "sharpe_ratio"
) -> Dict:
    """Optimize strategy parameters via grid search."""
    try:
        if not param_grid:
            return ToolResult(
                success=False,
                data=None,
                source="strategy_learning",
                timestamp=datetime.utcnow(),
                error="Parameter grid required"
            ).to_dict()
        
        best_result = None
        best_params = None
        best_metric = -float("inf")
        
        # Generate parameter combinations
        import itertools
        keys = list(param_grid.keys())
        values = list(param_grid.values())
        
        for combo in itertools.product(*values):
            params = dict(zip(keys, combo))
            r = await backtest_strategy(strategy_id, symbol, timeframe, parameters_override=params)
            if r["success"]:
                metric_val = r["data"].get(metric, -float("inf"))
                if metric_val > best_metric:
                    best_metric = metric_val
                    best_result = r["data"]
                    best_params = params
        
        if best_result is None:
            return ToolResult(
                success=False,
                data=None,
                source="strategy_learning",
                timestamp=datetime.utcnow(),
                error="No valid parameter combinations"
            ).to_dict()
        
        return ToolResult(
            success=True,
            data={
                "best_parameters": best_params,
                "best_metric": metric,
                "best_value": best_metric,
                "backtest_result": best_result
            },
            source="strategy_learning",
            timestamp=datetime.utcnow()
        ).to_dict()
    except Exception as e:
        return ToolResult(
            success=False,
            data=None,
            source="strategy_learning",
            timestamp=datetime.utcnow(),
            error=str(e)
        ).to_dict()


async def discover_patterns(
    session_id: int,
    symbol: str,
    timeframe: str = "1d",
    lookback_days: int = 365,
    min_occurrences: int = 5,
    min_win_rate: float = 0.55
) -> Dict:
    """Discover recurring patterns from historical data (self-learning)."""
    try:
        db = await get_db_manager()
        provider = await get_market_data_provider()
        
        # Fetch data
        ohlcv = await provider.get_historical_ohlcv(symbol, timeframe, lookback_days)
        if not ohlcv or len(ohlcv.closes) < 100:
            return ToolResult(
                success=False,
                data=None,
                source="strategy_learning",
                timestamp=datetime.utcnow(),
                error="Insufficient data"
            ).to_dict()
        
        # Convert to DataFrame
        df = pd.DataFrame({
            'timestamp': pd.to_datetime(ohlcv.timestamps, unit='ms'),
            'open': ohlcv.opens,
            'high': ohlcv.highs,
            'low': ohlcv.lows,
            'close': ohlcv.closes,
            'volume': ohlcv.volumes
        })
        df.set_index('timestamp', inplace=True)
        
        # Calculate indicators
        df['rsi'] = _calc_rsi(df['close'])
        df['macd'], df['macd_signal'], _ = _calc_macd(df['close'])
        df['ema_20'] = df['close'].ewm(span=20).mean()
        df['ema_50'] = df['close'].ewm(span=50).mean()
        df['atr'] = _calc_atr(df)
        df['bb_upper'], df['bb_middle'], df['bb_lower'] = _calc_bbands(df['close'])
        df['returns'] = df['close'].pct_change()
        df['future_return_1d'] = df['returns'].shift(-1)
        df['future_return_3d'] = df['close'].pct_change(3).shift(-3)
        
        patterns = []
        
        # Pattern 1: RSI oversold + price above EMA20
        mask = (df['rsi'] < 30) & (df['close'] > df['ema_20'])
        if mask.sum() >= min_occurrences:
            future_rets = df.loc[mask, 'future_return_1d'].dropna()
            win_rate = (future_rets > 0).mean()
            if win_rate >= min_win_rate:
                patterns.append({
                    "pattern_type": "entry_signal",
                    "pattern_name": "RSI_Oversold_Above_EMA20",
                    "description": "RSI < 30 with price above EMA20 - mean reversion bounce",
                    "conditions": {"rsi": "< 30", "close": "> ema_20"},
                    "action": {"side": "long", "hold_days": 1},
                    "confidence": float(win_rate),
                    "times_observed": int(mask.sum()),
                    "supporting_evidence": {
                        "avg_return_1d": float(future_rets.mean()),
                        "win_rate": float(win_rate),
                        "sample_size": int(mask.sum())
                    }
                })
        
        # Pattern 2: MACD bullish crossover
        df['macd_cross'] = (df['macd'] > df['macd_signal']) & (df['macd'].shift(1) <= df['macd_signal'].shift(1))
        mask = df['macd_cross']
        if mask.sum() >= min_occurrences:
            future_rets = df.loc[mask, 'future_return_3d'].dropna()
            win_rate = (future_rets > 0).mean()
            if win_rate >= min_win_rate:
                patterns.append({
                    "pattern_type": "entry_signal",
                    "pattern_name": "MACD_Bullish_Crossover",
                    "description": "MACD crosses above signal line - momentum entry",
                    "conditions": {"macd": "> macd_signal", "prev_macd": "<= prev_macd_signal"},
                    "action": {"side": "long", "hold_days": 3},
                    "confidence": float(win_rate),
                    "times_observed": int(mask.sum()),
                    "supporting_evidence": {
                        "avg_return_3d": float(future_rets.mean()),
                        "win_rate": float(win_rate),
                        "sample_size": int(mask.sum())
                    }
                })
        
        # Pattern 3: Bollinger Band squeeze + breakout
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
        df['bb_squeeze'] = df['bb_width'] < df['bb_width'].rolling(20).quantile(0.2)
        df['bb_breakout_up'] = df['bb_squeeze'].shift(1) & (df['close'] > df['bb_upper'])
        mask = df['bb_breakout_up']
        if mask.sum() >= min_occurrences:
            future_rets = df.loc[mask, 'future_return_3d'].dropna()
            win_rate = (future_rets > 0).mean()
            if win_rate >= min_win_rate:
                patterns.append({
                    "pattern_type": "entry_signal",
                    "pattern_name": "BB_Squeeze_Breakout",
                    "description": "Bollinger Band squeeze followed by upper band breakout",
                    "conditions": {"bb_width": "< 20th percentile", "close": "> bb_upper"},
                    "action": {"side": "long", "hold_days": 3},
                    "confidence": float(win_rate),
                    "times_observed": int(mask.sum()),
                    "supporting_evidence": {
                        "avg_return_3d": float(future_rets.mean()),
                        "win_rate": float(win_rate),
                        "sample_size": int(mask.sum())
                    }
                })
        
        # Pattern 4: Volume spike on support
        df['vol_avg'] = df['volume'].rolling(20).mean()
        df['vol_spike'] = df['volume'] > df['vol_avg'] * 2
        df['near_support'] = abs(df['close'] - df['low'].rolling(20).min()) / df['close'] < 0.02
        mask = df['vol_spike'] & df['near_support']
        if mask.sum() >= min_occurrences:
            future_rets = df.loc[mask, 'future_return_3d'].dropna()
            win_rate = (future_rets > 0).mean()
            if win_rate >= min_win_rate:
                patterns.append({
                    "pattern_type": "entry_signal",
                    "pattern_name": "Volume_Spike_On_Support",
                    "description": "High volume near recent low - accumulation signal",
                    "conditions": {"volume": "> 2x avg", "close": "near 20d low"},
                    "action": {"side": "long", "hold_days": 3},
                    "confidence": float(win_rate),
                    "times_observed": int(mask.sum()),
                    "supporting_evidence": {
                        "avg_return_3d": float(future_rets.mean()),
                        "win_rate": float(win_rate),
                        "sample_size": int(mask.sum())
                    }
                })
        
        # Pattern 5: EMA trend filter for exits
        df['trend_up'] = df['ema_20'] > df['ema_50']
        df['trend_down'] = df['ema_20'] < df['ema_50']
        
        # Save patterns to DB
        saved = []
        for p in patterns:
            saved_pattern = await db.save_learning_pattern(
                session_id=session_id,
                pattern_type=p["pattern_type"],
                pattern_name=p["pattern_name"],
                description=p["description"],
                conditions=p["conditions"],
                action=p["action"],
                supporting_evidence=p["supporting_evidence"],
                confidence=p["confidence"],
                symbols_tested=[symbol.upper()]
            )
            saved.append(_model_to_dict(saved_pattern))
        
        return ToolResult(
            success=True,
            data={"discovered_patterns": saved},
            source="strategy_learning",
            timestamp=datetime.utcnow()
        ).to_dict()
    except Exception as e:
        return ToolResult(
            success=False,
            data=None,
            source="strategy_learning",
            timestamp=datetime.utcnow(),
            error=str(e)
        ).to_dict()


async def get_learning_patterns(
    session_id: int,
    pattern_type: Optional[str] = None,
    min_confidence: float = 0.5,
    active_only: bool = True
) -> Dict:
    """Get discovered learning patterns."""
    try:
        db = await get_db_manager()
        patterns = await db.get_learning_patterns(session_id, pattern_type, min_confidence, active_only)
        return ToolResult(
            success=True,
            data=[_model_to_dict(p) for p in patterns],
            source="strategy_learning",
            timestamp=datetime.utcnow()
        ).to_dict()
    except Exception as e:
        return ToolResult(
            success=False,
            data=None,
            source="strategy_learning",
            timestamp=datetime.utcnow(),
            error=str(e)
        ).to_dict()


async def validate_pattern(
    pattern_id: int,
    symbol: str,
    timeframe: str = "1d",
    test_days: int = 90
) -> Dict:
    """Validate a learned pattern on out-of-sample data."""
    try:
        db = await get_db_manager()
        pattern = await db.get_learning_pattern(pattern_id)  # Need to add this method
        if not pattern:
            return ToolResult(
                success=False,
                data=None,
                source="strategy_learning",
                timestamp=datetime.utcnow(),
                error="Pattern not found"
            ).to_dict()
        
        provider = await get_market_data_provider()
        end = datetime.utcnow()
        start = end - timedelta(days=test_days)
        
        ohlcv = await provider.get_historical_ohlcv(symbol, timeframe, test_days)
        if not ohlcv:
            return ToolResult(
                success=False,
                data=None,
                source="strategy_learning",
                timestamp=datetime.utcnow(),
                error="No data for validation"
            ).to_dict()
        
        # Simple validation - check if pattern conditions hold
        # For now return mock validation
        return ToolResult(
            success=True,
            data={
                "pattern_id": pattern_id,
                "validation_period": f"{start.date()} to {end.date()}",
                "status": "pending_implementation",
                "note": "Full validation requires pattern condition parser"
            },
            source="strategy_learning",
            timestamp=datetime.utcnow()
        ).to_dict()
    except Exception as e:
        return ToolResult(
            success=False,
            data=None,
            source="strategy_learning",
            timestamp=datetime.utcnow(),
            error=str(e)
        ).to_dict()


async def get_backtest_results(
    strategy_id: int,
    symbol: Optional[str] = None,
    limit: int = 20
) -> Dict:
    """Get backtest results for a strategy."""
    try:
        db = await get_db_manager()
        results = await db.get_backtest_results(strategy_id, symbol, limit)
        return ToolResult(
            success=True,
            data=[_model_to_dict(r) for r in results],
            source="strategy_learning",
            timestamp=datetime.utcnow()
        ).to_dict()
    except Exception as e:
        return ToolResult(
            success=False,
            data=None,
            source="strategy_learning",
            timestamp=datetime.utcnow(),
            error=str(e)
        ).to_dict()


async def get_strategy_performance(strategy_id: int) -> Dict:
    """Get strategy performance history."""
    try:
        db = await get_db_manager()
        history = await db.get_strategy_performance_history(strategy_id)
        strategy = await db.get_strategy(strategy_id)
        return ToolResult(
            success=True,
            data={
                "strategy": _model_to_dict(strategy) if strategy else None,
                "performance_history": [_model_to_dict(h) for h in history]
            },
            source="strategy_learning",
            timestamp=datetime.utcnow()
        ).to_dict()
    except Exception as e:
        return ToolResult(
            success=False,
            data=None,
            source="strategy_learning",
            timestamp=datetime.utcnow(),
            error=str(e)
        ).to_dict()


# Internal backtest engine

def _serialize(obj):
    """Convert numpy/pandas types to JSON-serializable Python types."""
    if isinstance(obj, (np.integer, np.floating)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_serialize(v) for v in obj]
    else:
        return obj


def _run_backtest(
    strategy: Any,
    ohlcv: OHLCVData,
    initial_balance: float,
    parameters_override: Optional[Dict] = None
) -> Dict:
    """Run vectorized backtest for a strategy."""
    df = pd.DataFrame({
        'timestamp': pd.to_datetime(ohlcv.timestamps, unit='ms'),
        'open': ohlcv.opens,
        'high': ohlcv.highs,
        'low': ohlcv.lows,
        'close': ohlcv.closes,
        'volume': ohlcv.volumes
    })
    df.set_index('timestamp', inplace=True)
    
    # Merge parameters
    params = {**strategy.get("parameters", {})}
    if parameters_override:
        params.update(parameters_override)
    
    # Calculate indicators needed
    df['rsi'] = _calc_rsi(df['close'], params.get('rsi_period', 14))
    df['ema_fast'] = df['close'].ewm(span=params.get('ema_fast', 12)).mean()
    df['ema_slow'] = df['close'].ewm(span=params.get('ema_slow', 26)).mean()
    df['macd'], df['macd_signal'], df['macd_hist'] = _calc_macd(df['close'])
    df['atr'] = _calc_atr(df, params.get('atr_period', 14))
    df['bb_upper'], df['bb_middle'], df['bb_lower'] = _calc_bbands(df['close'], params.get('bb_period', 20))
    
    # Generate signals based on strategy type
    signals = _generate_signals(df, strategy, params)
    
    # Simulate trades
    trades = _simulate_trades(df, signals, initial_balance, params)
    
    # Calculate metrics
    if not trades:
        return _serialize({
            "total_trades": 0, "wins": 0, "losses": 0, "win_rate": 0,
            "total_return_pct": 0, "annualized_return_pct": 0,
            "profit_factor": 0, "sharpe_ratio": 0, "sortino_ratio": 0,
            "max_drawdown_pct": 0, "avg_holding_hours": 0,
            "expectancy": 0, "calmar_ratio": 0,
            "trades_detail": [], "equity_curve": []
        })
    
    pnls = [t["pnl_pct"] for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    
    equity_curve = _build_equity_curve(trades, initial_balance)
    final_balance = equity_curve[-1]["balance"] if equity_curve else initial_balance
    total_return = (final_balance / initial_balance - 1) * 100
    
    # Annualized return
    days = (df.index[-1] - df.index[0]).days
    annualized = ((final_balance / initial_balance) ** (365 / max(days, 1)) - 1) * 100 if days > 0 else 0
    
    # Sharpe
    sharpe = 0
    if len(pnls) > 1:
        import statistics
        mean_ret = statistics.mean(pnls)
        std_ret = statistics.stdev(pnls) if len(pnls) > 1 else 0
        sharpe = (mean_ret / std_ret) * (252 ** 0.5) if std_ret > 0 else 0
    
    # Sortino
    sortino = 0
    downside = [p for p in pnls if p < 0]
    if downside:
        import statistics
        downside_std = statistics.stdev(downside) if len(downside) > 1 else 0
        sortino = (statistics.mean(pnls) / downside_std) * (252 ** 0.5) if downside_std > 0 else 0
    
    # Max drawdown
    peak = initial_balance
    max_dd = 0
    for point in equity_curve:
        if point["balance"] > peak:
            peak = point["balance"]
        dd = (peak - point["balance"]) / peak * 100
        max_dd = max(max_dd, dd)
    
    # Calmar
    calmar = annualized / max_dd if max_dd > 0 else 0
    
    # Expectancy
    expectancy = np.mean(pnls) if pnls else 0
    
    # Avg holding time
    holding_times = [(t["exit_time"] - t["entry_time"]).total_seconds() / 3600 for t in trades]
    avg_holding = np.mean(holding_times) if holding_times else 0
    
    return _serialize({
        "total_trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": len(wins) / len(trades) * 100 if trades else 0,
        "total_return_pct": total_return,
        "annualized_return_pct": annualized,
        "profit_factor": (gross_profit / gross_loss) if gross_loss > 0 else float("inf") if gross_profit > 0 else 0,
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "max_drawdown_pct": max_dd,
        "avg_holding_hours": avg_holding,
        "expectancy": expectancy,
        "calmar_ratio": calmar,
        "trades_detail": trades,
        "equity_curve": equity_curve,
        "avg_win_pct": np.mean(wins) if wins else 0,
        "avg_loss_pct": np.mean(losses) if losses else 0,
    })


def _generate_signals(df: pd.DataFrame, strategy: Dict, params: Dict) -> pd.Series:
    """Generate entry/exit signals based on strategy rules."""
    signals = pd.Series(0, index=df.index)  # 1 = long, -1 = short, 0 = flat
    
    strategy_type = strategy.get("strategy_type", "trend_following")
    entry_rules = strategy.get("entry_rules", {})
    exit_rules = strategy.get("exit_rules", {})
    
    if strategy_type == "trend_following":
        # EMA crossover + RSI filter
        long_entry = (df['ema_fast'] > df['ema_slow']) & (df['ema_fast'].shift(1) <= df['ema_slow'].shift(1))
        if entry_rules.get('rsi_filter'):
            long_entry &= (df['rsi'] < entry_rules.get('rsi_max', 70))
        signals[long_entry] = 1
        
        # Exit on opposite crossover or RSI overbought
        long_exit = (df['ema_fast'] < df['ema_slow']) | (df['rsi'] > exit_rules.get('rsi_exit', 75))
        signals[long_exit & (signals.shift(1) == 1)] = 0
        
    elif strategy_type == "mean_reversion":
        # RSI oversold + price near lower BB
        long_entry = (df['rsi'] < entry_rules.get('rsi_oversold', 30)) & (df['close'] <= df['bb_lower'] * 1.01)
        signals[long_entry] = 1
        
        # Exit on RSI recovery or BB middle touch
        long_exit = (df['rsi'] > exit_rules.get('rsi_exit', 50)) | (df['close'] >= df['bb_middle'] * 0.99)
        signals[long_exit & (signals.shift(1) == 1)] = 0
        
    elif strategy_type == "breakout":
        # Price breaks above 20-day high with volume
        df['high_20'] = df['high'].rolling(20).max()
        df['vol_avg'] = df['volume'].rolling(20).mean()
        long_entry = (df['close'] > df['high_20'].shift(1)) & (df['volume'] > df['vol_avg'] * entry_rules.get('vol_mult', 1.5))
        signals[long_entry] = 1
        
        # Exit on trailing stop or time
        long_exit = (df['close'] < df['close'].shift(1) * (1 - exit_rules.get('trail_pct', 0.02)))
        signals[long_exit & (signals.shift(1) == 1)] = 0
    
    else:
        # Default: simple EMA crossover
        long_entry = (df['ema_fast'] > df['ema_slow']) & (df['ema_fast'].shift(1) <= df['ema_slow'].shift(1))
        long_exit = (df['ema_fast'] < df['ema_slow'])
        signals[long_entry] = 1
        signals[long_exit & (signals.shift(1) == 1)] = 0
    
    return signals


def _simulate_trades(df: pd.DataFrame, signals: pd.Series, initial_balance: float, params: Dict) -> List[Dict]:
    """Simulate trades from signals."""
    trades = []
    position = 0
    entry_price = 0
    entry_time = None
    balance = initial_balance
    
    stop_loss_pct = params.get('stop_loss_pct', 0.05)
    take_profit_pct = params.get('take_profit_pct', 0.10)
    risk_per_trade = params.get('risk_per_trade', 0.02)
    
    for i in range(1, len(df)):
        current_signal = signals.iloc[i]
        prev_signal = signals.iloc[i-1]
        price = df['close'].iloc[i]
        timestamp = df.index[i]
        
        # Entry
        if prev_signal == 0 and current_signal == 1:
            position = 1
            entry_price = price
            entry_time = timestamp
            # Position sizing based on risk
            risk_amount = balance * risk_per_trade
            stop_distance = entry_price * stop_loss_pct
            qty = risk_amount / stop_distance if stop_distance > 0 else 0
            
        # Exit conditions
        elif position == 1:
            pnl_pct = (price - entry_price) / entry_price
            
            # Stop loss
            if pnl_pct <= -stop_loss_pct:
                exit_price = entry_price * (1 - stop_loss_pct)
                trades.append({
                    "entry_time": entry_time,
                    "exit_time": timestamp,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "quantity": qty,
                    "pnl": (exit_price - entry_price) * qty,
                    "pnl_pct": -stop_loss_pct * 100,
                    "exit_reason": "stop_loss"
                })
                balance += (exit_price - entry_price) * qty
                position = 0
                
            # Take profit
            elif pnl_pct >= take_profit_pct:
                exit_price = entry_price * (1 + take_profit_pct)
                trades.append({
                    "entry_time": entry_time,
                    "exit_time": timestamp,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "quantity": qty,
                    "pnl": (exit_price - entry_price) * qty,
                    "pnl_pct": take_profit_pct * 100,
                    "exit_reason": "take_profit"
                })
                balance += (exit_price - entry_price) * qty
                position = 0
                
            # Signal exit
            elif current_signal == 0:
                trades.append({
                    "entry_time": entry_time,
                    "exit_time": timestamp,
                    "entry_price": entry_price,
                    "exit_price": price,
                    "quantity": qty,
                    "pnl": (price - entry_price) * qty,
                    "pnl_pct": pnl_pct * 100,
                    "exit_reason": "signal_exit"
                })
                balance += (price - entry_price) * qty
                position = 0
    
    # Close any open position at end
    if position == 1:
        price = df['close'].iloc[-1]
        pnl_pct = (price - entry_price) / entry_price
        trades.append({
            "entry_time": entry_time,
            "exit_time": df.index[-1],
            "entry_price": entry_price,
            "exit_price": price,
            "quantity": qty,
            "pnl": (price - entry_price) * qty,
            "pnl_pct": pnl_pct * 100,
            "exit_reason": "end_of_data"
        })
    
    return trades


def _build_equity_curve(trades: List[Dict], initial_balance: float) -> List[Dict]:
    """Build equity curve from trades."""
    curve = [{"timestamp": trades[0]["entry_time"].isoformat() if trades else datetime.utcnow().isoformat(), "balance": initial_balance}]
    balance = initial_balance
    for t in trades:
        balance += t["pnl"]
        curve.append({"timestamp": t["exit_time"].isoformat(), "balance": round(balance, 2)})
    return curve


# Indicator calculations

def _calc_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def _calc_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple:
    ema_fast = close.ewm(span=fast).mean()
    ema_slow = close.ewm(span=slow).mean()
    macd = ema_fast - ema_slow
    macd_signal = macd.ewm(span=signal).mean()
    macd_hist = macd - macd_signal
    return macd, macd_signal, macd_hist


def _calc_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def _calc_bbands(close: pd.Series, period: int = 20, std: float = 2.0) -> tuple:
    middle = close.rolling(period).mean()
    std_dev = close.rolling(period).std()
    upper = middle + std_dev * std
    lower = middle - std_dev * std
    return upper, middle, lower


# Tool definitions for AI function calling

STRATEGY_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "create_strategy",
            "description": "Create a new trading strategy with entry/exit/risk rules",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "integer"},
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "strategy_type": {"type": "string", "description": "trend_following, mean_reversion, breakout, etc."},
                    "parameters": {"type": "object", "description": "Strategy parameters"},
                    "entry_rules": {"type": "object", "description": "Entry conditions"},
                    "exit_rules": {"type": "object", "description": "Exit conditions"},
                    "risk_rules": {"type": "object", "description": "Risk management rules"},
                    "symbols": {"type": "array", "items": {"type": "string"}},
                    "timeframes": {"type": "array", "items": {"type": "string"}},
                    "is_learned": {"type": "boolean", "default": False},
                    "parent_strategy_id": {"type": "integer"}
                },
                "required": ["session_id", "name", "description", "strategy_type", "parameters", "entry_rules", "exit_rules", "risk_rules", "symbols", "timeframes"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_strategy",
            "description": "Get a strategy by ID",
            "parameters": {
                "type": "object",
                "properties": {"strategy_id": {"type": "integer"}},
                "required": ["strategy_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_strategies",
            "description": "List strategies for a session",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "integer"},
                    "strategy_type": {"type": "string"},
                    "is_active": {"type": "boolean"},
                    "is_learned": {"type": "boolean"}
                },
                "required": ["session_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "backtest_strategy",
            "description": "Run backtest for a strategy on historical data",
            "parameters": {
                "type": "object",
                "properties": {
                    "strategy_id": {"type": "integer"},
                    "symbol": {"type": "string"},
                    "timeframe": {"type": "string", "default": "1d"},
                    "start_date": {"type": "string", "description": "ISO format date"},
                    "end_date": {"type": "string", "description": "ISO format date"},
                    "initial_balance": {"type": "number", "default": 10000.0},
                    "parameters_override": {"type": "object"}
                },
                "required": ["strategy_id", "symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_multi_symbol_backtest",
            "description": "Run backtest across multiple symbols",
            "parameters": {
                "type": "object",
                "properties": {
                    "strategy_id": {"type": "integer"},
                    "symbols": {"type": "array", "items": {"type": "string"}},
                    "timeframe": {"type": "string", "default": "1d"},
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                    "initial_balance": {"type": "number", "default": 10000.0}
                },
                "required": ["strategy_id", "symbols"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "optimize_strategy_parameters",
            "description": "Optimize strategy parameters via grid search",
            "parameters": {
                "type": "object",
                "properties": {
                    "strategy_id": {"type": "integer"},
                    "symbol": {"type": "string"},
                    "timeframe": {"type": "string", "default": "1d"},
                    "param_grid": {"type": "object", "description": "Parameter name -> list of values to test"},
                    "metric": {"type": "string", "default": "sharpe_ratio", "description": "Metric to optimize"}
                },
                "required": ["strategy_id", "symbol", "param_grid"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "discover_patterns",
            "description": "Discover recurring patterns from historical data (self-learning)",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "integer"},
                    "symbol": {"type": "string"},
                    "timeframe": {"type": "string", "default": "1d"},
                    "lookback_days": {"type": "integer", "default": 365},
                    "min_occurrences": {"type": "integer", "default": 5},
                    "min_win_rate": {"type": "number", "default": 0.55}
                },
                "required": ["session_id", "symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_learning_patterns",
            "description": "Get discovered learning patterns",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "integer"},
                    "pattern_type": {"type": "string"},
                    "min_confidence": {"type": "number", "default": 0.5},
                    "active_only": {"type": "boolean", "default": True}
                },
                "required": ["session_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "validate_pattern",
            "description": "Validate a learned pattern on out-of-sample data",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern_id": {"type": "integer"},
                    "symbol": {"type": "string"},
                    "timeframe": {"type": "string", "default": "1d"},
                    "test_days": {"type": "integer", "default": 90}
                },
                "required": ["pattern_id", "symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_backtest_results",
            "description": "Get backtest results for a strategy",
            "parameters": {
                "type": "object",
                "properties": {
                    "strategy_id": {"type": "integer"},
                    "symbol": {"type": "string"},
                    "limit": {"type": "integer", "default": 20}
                },
                "required": ["strategy_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_strategy_performance",
            "description": "Get strategy performance history",
            "parameters": {
                "type": "object",
                "properties": {"strategy_id": {"type": "integer"}},
                "required": ["strategy_id"]
            }
        }
    }
]