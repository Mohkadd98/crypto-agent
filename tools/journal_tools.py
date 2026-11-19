"""
Trade journal tools for the Crypto Intelligence Agent.
Database-backed trade recording and performance statistics.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any

from database.storage import get_db_manager
from core.conversation import get_conversation_manager


def _ok(data: Any, metadata: Optional[Dict] = None) -> Dict:
    return {
        "success": True, "data": data, "source": "trade_journal",
        "timestamp": datetime.utcnow().isoformat(), "error": None,
        "metadata": metadata or {},
    }


def _fail(error: str) -> Dict:
    return {
        "success": False, "data": None, "source": "trade_journal",
        "timestamp": datetime.utcnow().isoformat(), "error": str(error),
        "metadata": {},
    }


async def _session_id() -> Optional[int]:
    conv = get_conversation_manager()
    return conv._current_session.id if conv._current_session else None


async def add_trade(
    symbol: str,
    side: str,
    entry_price: float,
    quantity: float = 0.0,
    stop_loss: Optional[float] = None,
    take_profit: Optional[float] = None,
    notes: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> Dict:
    """Open a new trade in the journal."""
    try:
        sid = await _session_id()
        if sid is None:
            return _fail("No active session")
        db = await get_db_manager()
        trade = await db.add_trade(
            session_id=sid, symbol=symbol, side=side, entry_price=entry_price,
            quantity=quantity, stop_loss=stop_loss, take_profit=take_profit,
            notes=notes, tags=tags,
        )
        return _ok({
            "id": trade.id, "symbol": trade.symbol, "side": trade.side,
            "entry_price": trade.entry_price, "quantity": trade.quantity,
            "stop_loss": trade.stop_loss, "take_profit": trade.take_profit,
            "status": trade.status,
        })
    except Exception as e:
        return _fail(e)


async def close_trade(trade_id: int, exit_price: float, notes: Optional[str] = None) -> Dict:
    """Close an open trade and compute PnL."""
    try:
        db = await get_db_manager()
        trade = await db.close_trade(trade_id, exit_price, notes)
        if not trade:
            return _fail(f"Trade {trade_id} not found")
        return _ok({
            "id": trade.id, "symbol": trade.symbol, "side": trade.side,
            "entry_price": trade.entry_price, "exit_price": trade.exit_price,
            "pnl_pct": trade.pnl_pct, "pnl": trade.pnl, "status": trade.status,
        })
    except Exception as e:
        return _fail(e)


async def list_trades(status: Optional[str] = None, symbol: Optional[str] = None, limit: int = 50) -> Dict:
    """List trades from the journal."""
    try:
        sid = await _session_id()
        if sid is None:
            return _fail("No active session")
        db = await get_db_manager()
        trades = await db.list_trades(sid, status=status, symbol=symbol, limit=limit)
        return _ok([
            {
                "id": t.id, "symbol": t.symbol, "side": t.side, "status": t.status,
                "entry_price": t.entry_price, "exit_price": t.exit_price,
                "quantity": t.quantity, "pnl_pct": t.pnl_pct, "pnl": t.pnl,
                "opened_at": t.opened_at.isoformat(),
                "closed_at": t.closed_at.isoformat() if t.closed_at else None,
                "notes": t.notes, "tags": t.tags,
            }
            for t in trades
        ], {"count": len(trades)})
    except Exception as e:
        return _fail(e)


async def get_trade_stats() -> Dict:
    """Get aggregate trade journal statistics."""
    try:
        sid = await _session_id()
        if sid is None:
            return _fail("No active session")
        db = await get_db_manager()
        stats = await db.get_trade_stats(sid)
        return _ok(stats)
    except Exception as e:
        return _fail(e)


TRADE_JOURNAL_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "add_trade",
            "description": "Open a new trade in the journal (records entry price, size, stops)",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "side": {"type": "string", "enum": ["long", "short"]},
                    "entry_price": {"type": "number"},
                    "quantity": {"type": "number", "default": 0},
                    "stop_loss": {"type": "number"},
                    "take_profit": {"type": "number"},
                    "notes": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["symbol", "side", "entry_price"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "close_trade",
            "description": "Close an open trade and compute PnL",
            "parameters": {
                "type": "object",
                "properties": {
                    "trade_id": {"type": "integer"},
                    "exit_price": {"type": "number"},
                    "notes": {"type": "string"},
                },
                "required": ["trade_id", "exit_price"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_trades",
            "description": "List trades from the journal with optional filters",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": ["open", "closed"]},
                    "symbol": {"type": "string"},
                    "limit": {"type": "integer", "default": 50},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_trade_stats",
            "description": "Get aggregate trade statistics: win rate, total PnL, profit factor",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]
