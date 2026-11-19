"""
Paper trading tools for the Crypto Intelligence Agent.
Virtual trading account management, position tracking, and performance analytics.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

from database.storage import get_db_manager
from tools.market_tools import ToolResult
from datetime import datetime


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

async def create_paper_account(
    session_id: int,
    name: str,
    initial_balance: float = 10000.0
) -> Dict:
    """Create a new paper trading account."""
    try:
        db = await get_db_manager()
        account = await db.create_paper_account(session_id, name, initial_balance)
        return ToolResult(
            success=True,
            data=_model_to_dict(account),
            source="paper_trading",
            timestamp=datetime.utcnow()
        ).to_dict()
    except Exception as e:
        return ToolResult(
            success=False,
            data=None,
            source="paper_trading",
            timestamp=datetime.utcnow(),
            error=str(e)
        ).to_dict()


async def get_paper_account(account_id: int) -> Dict:
    """Get paper account details with positions."""
    try:
        db = await get_db_manager()
        account = await db.get_paper_account(account_id)
        if not account:
            return ToolResult(
                success=False,
                data=None,
                source="paper_trading",
                timestamp=datetime.utcnow(),
                error="Account not found"
            ).to_dict()
        
        # Include positions and recent trades
        data = _model_to_dict(account)
        data["positions"] = [_model_to_dict(p) for p in account.positions]
        data["recent_trades"] = [_model_to_dict(t) for t in account.trades[-10:]]
        
        return ToolResult(
            success=True,
            data=data,
            source="paper_trading",
            timestamp=datetime.utcnow()
        ).to_dict()
    except Exception as e:
        return ToolResult(
            success=False,
            data=None,
            source="paper_trading",
            timestamp=datetime.utcnow(),
            error=str(e)
        ).to_dict()


async def list_paper_accounts(session_id: int) -> Dict:
    """List all paper accounts for a session."""
    try:
        db = await get_db_manager()
        accounts = await db.get_paper_accounts(session_id)
        return ToolResult(
            success=True,
            data=[_model_to_dict(a) for a in accounts],
            source="paper_trading",
            timestamp=datetime.utcnow()
        ).to_dict()
    except Exception as e:
        return ToolResult(
            success=False,
            data=None,
            source="paper_trading",
            timestamp=datetime.utcnow(),
            error=str(e)
        ).to_dict()


async def open_paper_position(
    account_id: int,
    symbol: str,
    side: str,
    quantity: float,
    entry_price: float,
    stop_loss: Optional[float] = None,
    take_profit: Optional[float] = None,
    strategy_id: Optional[int] = None,
    signal_data: Optional[Dict] = None,
    market_context: Optional[Dict] = None
) -> Dict:
    """Open a new paper trading position."""
    try:
        db = await get_db_manager()
        trade, position = await db.open_paper_position(
            account_id=account_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            strategy_id=strategy_id,
            signal_data=signal_data,
            market_context=market_context
        )
        return ToolResult(
            success=True,
            data={"trade": _model_to_dict(trade), "position": _model_to_dict(position)},
            source="paper_trading",
            timestamp=datetime.utcnow()
        ).to_dict()
    except Exception as e:
        return ToolResult(
            success=False,
            data=None,
            source="paper_trading",
            timestamp=datetime.utcnow(),
            error=str(e)
        ).to_dict()


async def close_paper_position(
    account_id: int,
    position_id: int,
    exit_price: float,
    quantity: Optional[float] = None,
    reason: str = "manual"
) -> Dict:
    """Close a paper trading position (fully or partially)."""
    try:
        db = await get_db_manager()
        trade, position = await db.close_paper_position(
            account_id=account_id,
            position_id=position_id,
            exit_price=exit_price,
            quantity=quantity,
            reason=reason
        )
        return ToolResult(
            success=True,
            data={"trade": _model_to_dict(trade), "position": _model_to_dict(position) if position else None},
            source="paper_trading",
            timestamp=datetime.utcnow()
        ).to_dict()
    except Exception as e:
        return ToolResult(
            success=False,
            data=None,
            source="paper_trading",
            timestamp=datetime.utcnow(),
            error=str(e)
        ).to_dict()


async def update_paper_positions(account_id: int, prices: Dict[str, float]) -> Dict:
    """Update current prices for all open positions and check SL/TP."""
    try:
        db = await get_db_manager()
        positions = await db.update_paper_positions_prices(account_id, prices)
        return ToolResult(
            success=True,
            data=[_model_to_dict(p) for p in positions],
            source="paper_trading",
            timestamp=datetime.utcnow()
        ).to_dict()
    except Exception as e:
        return ToolResult(
            success=False,
            data=None,
            source="paper_trading",
            timestamp=datetime.utcnow(),
            error=str(e)
        ).to_dict()


async def get_paper_account_stats(account_id: int) -> Dict:
    """Get comprehensive paper account statistics."""
    try:
        db = await get_db_manager()
        stats = await db.get_paper_account_stats(account_id)
        return ToolResult(
            success=True,
            data=stats,
            source="paper_trading",
            timestamp=datetime.utcnow()
        ).to_dict()
    except Exception as e:
        return ToolResult(
            success=False,
            data=None,
            source="paper_trading",
            timestamp=datetime.utcnow(),
            error=str(e)
        ).to_dict()


async def get_paper_trades(
    account_id: int,
    symbol: Optional[str] = None,
    limit: int = 100
) -> Dict:
    """Get paper trades for an account."""
    try:
        db = await get_db_manager()
        trades = await db.get_paper_trades(account_id, symbol, limit)
        return ToolResult(
            success=True,
            data=[_model_to_dict(t) for t in trades],
            source="paper_trading",
            timestamp=datetime.utcnow()
        ).to_dict()
    except Exception as e:
        return ToolResult(
            success=False,
            data=None,
            source="paper_trading",
            timestamp=datetime.utcnow(),
            error=str(e)
        ).to_dict()


# Tool definitions for AI function calling

PAPER_TRADING_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "create_paper_account",
            "description": "Create a new virtual paper trading account",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "integer", "description": "Session ID"},
                    "name": {"type": "string", "description": "Account name"},
                    "initial_balance": {"type": "number", "description": "Starting balance in USDT", "default": 10000.0}
                },
                "required": ["session_id", "name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_paper_account",
            "description": "Get paper account details including open positions and recent trades",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {"type": "integer", "description": "Paper account ID"}
                },
                "required": ["account_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_paper_accounts",
            "description": "List all paper trading accounts for a session",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "integer", "description": "Session ID"}
                },
                "required": ["session_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_paper_position",
            "description": "Open a new paper trading position",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {"type": "integer", "description": "Paper account ID"},
                    "symbol": {"type": "string", "description": "Trading symbol (e.g. BTC, SOL)"},
                    "side": {"type": "string", "description": "Position side: long or short"},
                    "quantity": {"type": "number", "description": "Position size"},
                    "entry_price": {"type": "number", "description": "Entry price"},
                    "stop_loss": {"type": "number", "description": "Stop loss price (optional)"},
                    "take_profit": {"type": "number", "description": "Take profit price (optional)"},
                    "strategy_id": {"type": "integer", "description": "Associated strategy ID (optional)"},
                    "signal_data": {"type": "object", "description": "Technical signals that triggered the trade (optional)"},
                    "market_context": {"type": "object", "description": "Market regime/context at entry (optional)"}
                },
                "required": ["account_id", "symbol", "side", "quantity", "entry_price"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "close_paper_position",
            "description": "Close a paper trading position (fully or partially)",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {"type": "integer", "description": "Paper account ID"},
                    "position_id": {"type": "integer", "description": "Position ID to close"},
                    "exit_price": {"type": "number", "description": "Exit price"},
                    "quantity": {"type": "number", "description": "Quantity to close (optional, defaults to full position)"},
                    "reason": {"type": "string", "description": "Close reason: manual, stop_loss, take_profit, strategy_exit", "default": "manual"}
                },
                "required": ["account_id", "position_id", "exit_price"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_paper_positions",
            "description": "Update current prices for all open positions and check stop loss/take profit",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {"type": "integer", "description": "Paper account ID"},
                    "prices": {"type": "object", "description": "Symbol -> current price mapping", "additionalProperties": {"type": "number"}}
                },
                "required": ["account_id", "prices"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_paper_account_stats",
            "description": "Get comprehensive paper account performance statistics",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {"type": "integer", "description": "Paper account ID"}
                },
                "required": ["account_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_paper_trades",
            "description": "Get paper trade history for an account",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {"type": "integer", "description": "Paper account ID"},
                    "symbol": {"type": "string", "description": "Filter by symbol (optional)"},
                    "limit": {"type": "integer", "description": "Maximum number of trades", "default": 100}
                },
                "required": ["account_id"]
            }
        }
    }
]