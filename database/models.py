"""
Database models for the Crypto Intelligence Agent.
Uses SQLAlchemy 2.0 with async support.
"""

from datetime import datetime
from typing import Optional, List
from enum import Enum as PyEnum

from sqlalchemy import (
    String, Text, Integer, Float, Boolean, DateTime, ForeignKey, 
    Index, JSON, LargeBinary, Enum as SQLEnum
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON


class Base(DeclarativeBase):
    pass


class ConversationRole(PyEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class SkillStatus(PyEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    INSTALLED = "installed"
    ERROR = "error"


class AnalysisType(PyEnum):
    MARKET_SCAN = "market_scan"
    TECHNICAL = "technical"
    FUNDAMENTAL = "fundamental"
    ONCHAIN = "onchain"
    SENTIMENT = "sentiment"
    RISK = "risk"
    PATTERN = "pattern"
    COMPARISON = "comparison"
    PORTFOLIO = "portfolio"


class Session(Base):
    __tablename__ = "sessions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    title: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    extra_data: Mapped[dict] = mapped_column("metadata", SQLiteJSON, default=dict)
    
    messages: Mapped[List["Message"]] = relationship("Message", back_populates="session", cascade="all, delete-orphan")
    analyses: Mapped[List["Analysis"]] = relationship("Analysis", back_populates="session", cascade="all, delete-orphan")
    watchlist_items: Mapped[List["WatchlistItem"]] = relationship("WatchlistItem", back_populates="session", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    role: Mapped[ConversationRole] = mapped_column(SQLEnum(ConversationRole), index=True)
    content: Mapped[str] = mapped_column(Text)
    tool_calls: Mapped[Optional[dict]] = mapped_column(SQLiteJSON, nullable=True)
    tool_results: Mapped[Optional[dict]] = mapped_column(SQLiteJSON, nullable=True)
    model_used: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    
    session: Mapped["Session"] = relationship("Session", back_populates="messages")


class Analysis(Base):
    __tablename__ = "analyses"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    analysis_type: Mapped[AnalysisType] = mapped_column(SQLEnum(AnalysisType), index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    timeframe: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    input_data: Mapped[dict] = mapped_column(SQLiteJSON, default=dict)
    result: Mapped[dict] = mapped_column(SQLiteJSON, default=dict)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tags: Mapped[List[str]] = mapped_column(SQLiteJSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    
    session: Mapped["Session"] = relationship("Session", back_populates="analyses")


class WatchlistItem(Base):
    __tablename__ = "watchlist"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    added_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[List[str]] = mapped_column(SQLiteJSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    session: Mapped["Session"] = relationship("Session", back_populates="watchlist_items")
    
    __table_args__ = (
        Index("ix_watchlist_session_symbol", "session_id", "symbol", unique=True),
    )


class Skill(Base):
    __tablename__ = "skills"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text)
    version: Mapped[str] = mapped_column(String(32))
    status: Mapped[SkillStatus] = mapped_column(SQLEnum(SkillStatus), default=SkillStatus.INSTALLED, index=True)
    dependencies: Mapped[List[str]] = mapped_column(SQLiteJSON, default=list)
    required_apis: Mapped[List[str]] = mapped_column(SQLiteJSON, default=list)
    available_tools: Mapped[List[str]] = mapped_column(SQLiteJSON, default=list)
    instructions: Mapped[str] = mapped_column(Text)
    config: Mapped[dict] = mapped_column(SQLiteJSON, default=dict)
    is_core: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class Prediction(Base):
    __tablename__ = "predictions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    prediction_type: Mapped[str] = mapped_column(String(64))  # price_target, breakout, accumulation, etc.
    timeframe: Mapped[str] = mapped_column(String(32))  # 1d, 7d, 30d, etc.
    predicted_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    predicted_direction: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)  # up, down, sideways
    confidence: Mapped[float] = mapped_column(Float)
    reasoning: Mapped[str] = mapped_column(Text)
    extra_data: Mapped[dict] = mapped_column("metadata", SQLiteJSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    actual_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    actual_direction: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    is_correct: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    accuracy_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class UserPreference(Base):
    __tablename__ = "user_preferences"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    value: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(64), index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ResearchFinding(Base):
    __tablename__ = "research_findings"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(256))
    summary: Mapped[str] = mapped_column(Text)
    symbols: Mapped[List[str]] = mapped_column(SQLiteJSON, default=list)
    finding_type: Mapped[str] = mapped_column(String(64), index=True)  # opportunity, risk, pattern, anomaly
    severity: Mapped[str] = mapped_column(String(16))  # low, medium, high, critical
    data_sources: Mapped[List[str]] = mapped_column(SQLiteJSON, default=list)
    evidence: Mapped[dict] = mapped_column(SQLiteJSON, default=dict)
    confidence: Mapped[float] = mapped_column(Float)
    tags: Mapped[List[str]] = mapped_column(SQLiteJSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    session: Mapped["Session"] = relationship("Session")


class Trade(Base):
    __tablename__ = "trades"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    side: Mapped[str] = mapped_column(String(8))  # long / short
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)  # open / closed
    entry_price: Mapped[float] = mapped_column(Float)
    exit_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    quantity: Mapped[float] = mapped_column(Float, default=0.0)
    stop_loss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    take_profit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pnl: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pnl_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[List[str]] = mapped_column(SQLiteJSON, default=list)


class ToolExecution(Base):
    __tablename__ = "tool_executions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    tool_name: Mapped[str] = mapped_column(String(128), index=True)
    skill_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    input_params: Mapped[dict] = mapped_column(SQLiteJSON, default=dict)
    output_data: Mapped[dict] = mapped_column(SQLiteJSON, default=dict)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    execution_time_ms: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


# ===========================================
# Paper Trading & Strategy Learning Models
# ===========================================

class PaperAccount(Base):
    """Virtual trading account for paper trading."""
    __tablename__ = "paper_accounts"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    initial_balance: Mapped[float] = mapped_column(Float, default=10000.0)  # USDT
    current_balance: Mapped[float] = mapped_column(Float, default=10000.0)
    available_balance: Mapped[float] = mapped_column(Float, default=10000.0)
    total_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    total_pnl_pct: Mapped[float] = mapped_column(Float, default=0.0)
    max_drawdown: Mapped[float] = mapped_column(Float, default=0.0)
    max_drawdown_pct: Mapped[float] = mapped_column(Float, default=0.0)
    peak_balance: Mapped[float] = mapped_column(Float, default=10000.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    trades: Mapped[List["PaperTrade"]] = relationship("PaperTrade", back_populates="account", cascade="all, delete-orphan")
    positions: Mapped[List["PaperPosition"]] = relationship("PaperPosition", back_populates="account", cascade="all, delete-orphan")


class PaperTrade(Base):
    """Individual paper trade execution."""
    __tablename__ = "paper_trades"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("paper_accounts.id", ondelete="CASCADE"), index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    side: Mapped[str] = mapped_column(String(8))  # long / short
    action: Mapped[str] = mapped_column(String(16))  # open / close / partial_close
    status: Mapped[str] = mapped_column(String(16), default="executed", index=True)  # executed / cancelled / rejected
    quantity: Mapped[float] = mapped_column(Float)
    price: Mapped[float] = mapped_column(Float)
    fee: Mapped[float] = mapped_column(Float, default=0.0)
    pnl: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # Realized PnL on close
    pnl_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    strategy_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("strategies.id", ondelete="SET NULL"), nullable=True, index=True)
    signal_data: Mapped[dict] = mapped_column(SQLiteJSON, default=dict)  # Technical signals that triggered trade
    market_context: Mapped[dict] = mapped_column(SQLiteJSON, default=dict)  # Market regime, breadth, etc.
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    executed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    
    account: Mapped["PaperAccount"] = relationship("PaperAccount", back_populates="trades")


class PaperPosition(Base):
    """Open paper trading position."""
    __tablename__ = "paper_positions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("paper_accounts.id", ondelete="CASCADE"), index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    side: Mapped[str] = mapped_column(String(8))  # long / short
    quantity: Mapped[float] = mapped_column(Float)
    entry_price: Mapped[float] = mapped_column(Float)
    current_price: Mapped[float] = mapped_column(Float)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    unrealized_pnl_pct: Mapped[float] = mapped_column(Float, default=0.0)
    stop_loss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    take_profit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    strategy_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("strategies.id", ondelete="SET NULL"), nullable=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    account: Mapped["PaperAccount"] = relationship("PaperAccount", back_populates="positions")


class Strategy(Base):
    """Trading strategy definition with parameters."""
    __tablename__ = "strategies"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    description: Mapped[str] = mapped_column(Text)
    strategy_type: Mapped[str] = mapped_column(String(64), index=True)  # trend_following, mean_reversion, breakout, etc.
    parameters: Mapped[dict] = mapped_column(SQLiteJSON, default=dict)  # Configurable params
    entry_rules: Mapped[dict] = mapped_column(SQLiteJSON, default=dict)  # Conditions for entry
    exit_rules: Mapped[dict] = mapped_column(SQLiteJSON, default=dict)   # Conditions for exit
    risk_rules: Mapped[dict] = mapped_column(SQLiteJSON, default=dict)   # Position sizing, stop loss, etc.
    symbols: Mapped[List[str]] = mapped_column(SQLiteJSON, default=list)  # Applicable symbols
    timeframes: Mapped[List[str]] = mapped_column(SQLiteJSON, default=list)  # Applicable timeframes
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_learned: Mapped[bool] = mapped_column(Boolean, default=False)  # Discovered via learning vs manual
    parent_strategy_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("strategies.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Performance metrics (updated after backtests/paper trades)
    total_trades: Mapped[int] = mapped_column(Integer, default=0)
    win_rate: Mapped[float] = mapped_column(Float, default=0.0)
    avg_win: Mapped[float] = mapped_column(Float, default=0.0)
    avg_loss: Mapped[float] = mapped_column(Float, default=0.0)
    profit_factor: Mapped[float] = mapped_column(Float, default=0.0)
    sharpe_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    max_drawdown: Mapped[float] = mapped_column(Float, default=0.0)
    expectancy: Mapped[float] = mapped_column(Float, default=0.0)
    last_backtest_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_paper_trade_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class StrategyPerformance(Base):
    """Historical performance snapshots for strategies."""
    __tablename__ = "strategy_performance"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy_id: Mapped[int] = mapped_column(Integer, ForeignKey("strategies.id", ondelete="CASCADE"), index=True)
    period_start: Mapped[datetime] = mapped_column(DateTime, index=True)
    period_end: Mapped[datetime] = mapped_column(DateTime)
    total_trades: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    win_rate: Mapped[float] = mapped_column(Float, default=0.0)
    total_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    total_pnl_pct: Mapped[float] = mapped_column(Float, default=0.0)
    max_drawdown: Mapped[float] = mapped_column(Float, default=0.0)
    sharpe_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    profit_factor: Mapped[float] = mapped_column(Float, default=0.0)
    expectancy: Mapped[float] = mapped_column(Float, default=0.0)
    avg_holding_time_hours: Mapped[float] = mapped_column(Float, default=0.0)
    best_trade_pct: Mapped[float] = mapped_column(Float, default=0.0)
    worst_trade_pct: Mapped[float] = mapped_column(Float, default=0.0)
    data_source: Mapped[str] = mapped_column(String(32))  # backtest / paper_trading / live
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class LearningPattern(Base):
    """Discovered patterns from self-learning."""
    __tablename__ = "learning_patterns"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    pattern_type: Mapped[str] = mapped_column(String(64), index=True)  # entry_signal, exit_signal, regime_filter, risk_rule
    pattern_name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text)
    conditions: Mapped[dict] = mapped_column(SQLiteJSON, default=dict)  # IF conditions
    action: Mapped[dict] = mapped_column(SQLiteJSON, default=dict)      # THEN action
    supporting_evidence: Mapped[dict] = mapped_column(SQLiteJSON, default=dict)  # Historical examples
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    times_observed: Mapped[int] = mapped_column(Integer, default=1)
    times_successful: Mapped[int] = mapped_column(Integer, default=0)
    times_failed: Mapped[int] = mapped_column(Integer, default=0)
    symbols_tested: Mapped[List[str]] = mapped_column(SQLiteJSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_validated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class BacktestResult(Base):
    """Stored backtest results for strategies."""
    __tablename__ = "backtest_results"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy_id: Mapped[int] = mapped_column(Integer, ForeignKey("strategies.id", ondelete="CASCADE"), index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    timeframe: Mapped[str] = mapped_column(String(16))
    start_date: Mapped[datetime] = mapped_column(DateTime)
    end_date: Mapped[datetime] = mapped_column(DateTime)
    initial_balance: Mapped[float] = mapped_column(Float)
    final_balance: Mapped[float] = mapped_column(Float)
    total_return_pct: Mapped[float] = mapped_column(Float)
    annualized_return_pct: Mapped[float] = mapped_column(Float)
    total_trades: Mapped[int] = mapped_column(Integer)
    wins: Mapped[int] = mapped_column(Integer)
    losses: Mapped[int] = mapped_column(Integer)
    win_rate: Mapped[float] = mapped_column(Float)
    profit_factor: Mapped[float] = mapped_column(Float)
    sharpe_ratio: Mapped[float] = mapped_column(Float)
    sortino_ratio: Mapped[float] = mapped_column(Float)
    max_drawdown_pct: Mapped[float] = mapped_column(Float)
    avg_holding_hours: Mapped[float] = mapped_column(Float)
    expectancy: Mapped[float] = mapped_column(Float)
    calmar_ratio: Mapped[float] = mapped_column(Float)
    trades_detail: Mapped[List[dict]] = mapped_column(SQLiteJSON, default=list)  # Individual trade records
    equity_curve: Mapped[List[dict]] = mapped_column(SQLiteJSON, default=list)   # [{timestamp, balance}, ...]
    parameters_used: Mapped[dict] = mapped_column(SQLiteJSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)