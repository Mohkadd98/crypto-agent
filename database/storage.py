"""
Database storage layer for the Crypto Intelligence Agent.
Provides async CRUD operations for all models.
"""

import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, AsyncGenerator, Tuple
from pathlib import Path

from sqlalchemy import select, delete, update, func, and_, or_, desc
from sqlalchemy.ext.asyncio import (
    AsyncSession, AsyncEngine, create_async_engine, 
    async_sessionmaker, AsyncSession
)
from sqlalchemy.orm import selectinload

from database.models import (
    Base, Session, Message, Analysis, WatchlistItem, Skill,
    Prediction, UserPreference, ResearchFinding, ToolExecution, Trade,
    PaperAccount, PaperTrade, PaperPosition, Strategy,
    StrategyPerformance, LearningPattern, BacktestResult,
    ConversationRole, SkillStatus, AnalysisType
)
from core.config import get_settings, DatabaseSettings


class DatabaseManager:
    """Manages database connections and provides high-level operations."""
    
    def __init__(self, settings: Optional[DatabaseSettings] = None):
        self.settings = settings or get_settings().database
        self.engine: Optional[AsyncEngine] = None
        self.session_factory: Optional[async_sessionmaker[AsyncSession]] = None
    
    async def initialize(self) -> None:
        """Initialize the database engine and create tables."""
        # Ensure data directory exists
        db_path = Path(self.settings.path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create async engine
        database_url = f"sqlite+aiosqlite:///{db_path}"
        self.engine = create_async_engine(
            database_url,
            echo=self.settings.echo,
            pool_size=self.settings.pool_size,
            connect_args={"check_same_thread": False}
        )
        
        self.session_factory = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
        
        # Create tables
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    async def close(self) -> None:
        """Close the database engine."""
        if self.engine:
            await self.engine.dispose()
    
    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get a database session."""
        if not self.session_factory:
            await self.initialize()
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    
    # ===========================================
    # Session Management
    # ===========================================
    
    async def create_session(self, title: Optional[str] = None, metadata: Optional[Dict] = None) -> Session:
        """Create a new conversation session."""
        async with self.session() as db:
            session = Session(
                session_id=str(uuid.uuid4())[:8],
                title=title,
                extra_data=metadata or {}
            )
            db.add(session)
            await db.flush()
            await db.refresh(session)
            return session
    
    async def get_session(self, session_id: str) -> Optional[Session]:
        """Get a session by its session_id."""
        async with self.session() as db:
            result = await db.execute(
                select(Session).where(Session.session_id == session_id)
            )
            return result.scalar_one_or_none()
    
    async def get_latest_session(self) -> Optional[Session]:
        """Get the most recent session."""
        async with self.session() as db:
            result = await db.execute(
                select(Session).order_by(desc(Session.updated_at)).limit(1)
            )
            return result.scalar_one_or_none()
    
    async def update_session(self, session_id: str, **kwargs) -> Optional[Session]:
        """Update a session."""
        async with self.session() as db:
            # Query inside this session: calling get_session() would open a
            # second session and mutate a detached object, silently losing the
            # update.
            result = await db.execute(
                select(Session).where(Session.session_id == session_id)
            )
            session = result.scalar_one_or_none()
            if session:
                for key, value in kwargs.items():
                    if hasattr(session, key):
                        setattr(session, key, value)
                session.updated_at = datetime.utcnow()
                await db.flush()
                await db.refresh(session)
            return session
    
    async def list_sessions(self, limit: int = 20) -> List[Session]:
        """List recent sessions."""
        async with self.session() as db:
            result = await db.execute(
                select(Session).order_by(desc(Session.updated_at)).limit(limit)
            )
            return list(result.scalars().all())
    
    # ===========================================
    # Message Management
    # ===========================================
    
    async def add_message(
        self,
        session_id: int,
        role: ConversationRole,
        content: str,
        tool_calls: Optional[Dict] = None,
        tool_results: Optional[Dict] = None,
        model_used: Optional[str] = None,
        tokens_used: Optional[int] = None,
        cost_usd: Optional[float] = None
    ) -> Message:
        """Add a message to a session."""
        async with self.session() as db:
            message = Message(
                session_id=session_id,
                role=role,
                content=content,
                tool_calls=tool_calls,
                tool_results=tool_results,
                model_used=model_used,
                tokens_used=tokens_used,
                cost_usd=cost_usd
            )
            db.add(message)
            
            # Update session timestamp
            await db.execute(
                update(Session)
                .where(Session.id == session_id)
                .values(updated_at=datetime.utcnow())
            )
            
            await db.flush()
            await db.refresh(message)
            return message
    
    async def get_messages(
        self, 
        session_id: int, 
        limit: int = 100,
        offset: int = 0
    ) -> List[Message]:
        """Get messages for a session."""
        async with self.session() as db:
            result = await db.execute(
                select(Message)
                .where(Message.session_id == session_id)
                .order_by(Message.created_at)
                .offset(offset)
                .limit(limit)
            )
            return list(result.scalars().all())
    
    async def get_recent_messages(self, session_id: int, count: int = 20) -> List[Message]:
        """Get the most recent messages for a session."""
        async with self.session() as db:
            result = await db.execute(
                select(Message)
                .where(Message.session_id == session_id)
                .order_by(desc(Message.created_at))
                .limit(count)
            )
            messages = list(result.scalars().all())
            return list(reversed(messages))
    
    # ===========================================
    # Analysis Management
    # ===========================================
    
    async def save_analysis(
        self,
        session_id: int,
        analysis_type: AnalysisType,
        symbol: str,
        timeframe: Optional[str],
        input_data: Dict,
        result: Dict,
        confidence: Optional[float] = None,
        tags: Optional[List[str]] = None
    ) -> Analysis:
        """Save an analysis result."""
        async with self.session() as db:
            analysis = Analysis(
                session_id=session_id,
                analysis_type=analysis_type,
                symbol=symbol.upper(),
                timeframe=timeframe,
                input_data=input_data,
                result=result,
                confidence=confidence,
                tags=tags or []
            )
            db.add(analysis)
            await db.flush()
            await db.refresh(analysis)
            return analysis
    
    async def get_analyses(
        self,
        session_id: int,
        symbol: Optional[str] = None,
        analysis_type: Optional[AnalysisType] = None,
        limit: int = 50
    ) -> List[Analysis]:
        """Get analyses for a session."""
        async with self.session() as db:
            query = select(Analysis).where(Analysis.session_id == session_id)
            
            if symbol:
                query = query.where(Analysis.symbol == symbol.upper())
            if analysis_type:
                query = query.where(Analysis.analysis_type == analysis_type)
            
            query = query.order_by(desc(Analysis.created_at)).limit(limit)
            result = await db.execute(query)
            return list(result.scalars().all())
    
    async def get_latest_analysis(
        self,
        session_id: int,
        symbol: str,
        analysis_type: Optional[AnalysisType] = None
    ) -> Optional[Analysis]:
        """Get the latest analysis for a symbol."""
        async with self.session() as db:
            query = select(Analysis).where(
                and_(
                    Analysis.session_id == session_id,
                    Analysis.symbol == symbol.upper()
                )
            )
            if analysis_type:
                query = query.where(Analysis.analysis_type == analysis_type)
            
            query = query.order_by(desc(Analysis.created_at)).limit(1)
            result = await db.execute(query)
            return result.scalar_one_or_none()
    
    # ===========================================
    # Watchlist Management
    # ===========================================
    
    async def add_to_watchlist(
        self,
        session_id: int,
        symbol: str,
        name: Optional[str] = None,
        added_price: Optional[float] = None,
        notes: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> WatchlistItem:
        """Add a symbol to the watchlist."""
        async with self.session() as db:
            # Check if already exists
            existing = await db.execute(
                select(WatchlistItem).where(
                    and_(
                        WatchlistItem.session_id == session_id,
                        WatchlistItem.symbol == symbol.upper()
                    )
                )
            )
            item = existing.scalar_one_or_none()
            
            if item:
                # Update existing
                item.name = name or item.name
                item.added_price = added_price or item.added_price
                item.notes = notes or item.notes
                if tags:
                    item.tags = tags
                item.is_active = True
            else:
                item = WatchlistItem(
                    session_id=session_id,
                    symbol=symbol.upper(),
                    name=name,
                    added_price=added_price,
                    notes=notes,
                    tags=tags or []
                )
                db.add(item)
            
            await db.flush()
            await db.refresh(item)
            return item
    
    async def remove_from_watchlist(self, session_id: int, symbol: str) -> bool:
        """Remove a symbol from the watchlist."""
        async with self.session() as db:
            result = await db.execute(
                delete(WatchlistItem).where(
                    and_(
                        WatchlistItem.session_id == session_id,
                        WatchlistItem.symbol == symbol.upper()
                    )
                )
            )
            return result.rowcount > 0
    
    async def get_watchlist(self, session_id: int, active_only: bool = True) -> List[WatchlistItem]:
        """Get all watchlist items for a session."""
        async with self.session() as db:
            query = select(WatchlistItem).where(WatchlistItem.session_id == session_id)
            if active_only:
                query = query.where(WatchlistItem.is_active == True)
            query = query.order_by(WatchlistItem.added_at)
            result = await db.execute(query)
            return list(result.scalars().all())
    
    # ===========================================
    # Skill Management
    # ===========================================
    
    async def upsert_skill(self, skill_data: Dict) -> Skill:
        """Insert or update a skill."""
        async with self.session() as db:
            result = await db.execute(
                select(Skill).where(Skill.name == skill_data["name"])
            )
            skill = result.scalar_one_or_none()
            
            if skill:
                for key, value in skill_data.items():
                    if hasattr(skill, key) and key != "id":
                        setattr(skill, key, value)
                skill.updated_at = datetime.utcnow()
            else:
                skill = Skill(**skill_data)
                db.add(skill)
            
            await db.flush()
            await db.refresh(skill)
            return skill
    
    async def get_skill(self, name: str) -> Optional[Skill]:
        """Get a skill by name."""
        async with self.session() as db:
            result = await db.execute(select(Skill).where(Skill.name == name))
            return result.scalar_one_or_none()
    
    async def list_skills(self, status: Optional[SkillStatus] = None) -> List[Skill]:
        """List all skills."""
        async with self.session() as db:
            query = select(Skill).order_by(Skill.priority if hasattr(Skill, 'priority') else Skill.name)
            if status:
                query = query.where(Skill.status == status)
            result = await db.execute(query)
            return list(result.scalars().all())
    
    async def set_skill_status(self, name: str, status: SkillStatus, error: Optional[str] = None) -> Optional[Skill]:
        """Update a skill's status."""
        async with self.session() as db:
            skill = await self.get_skill(name)
            if skill:
                skill.status = status
                if error:
                    skill.last_error = error
                skill.updated_at = datetime.utcnow()
                await db.flush()
                await db.refresh(skill)
            return skill
    
    # ===========================================
    # Prediction Management
    # ===========================================
    
    async def save_prediction(
        self,
        session_id: int,
        symbol: str,
        prediction_type: str,
        timeframe: str,
        predicted_value: Optional[float],
        predicted_direction: Optional[str],
        confidence: float,
        reasoning: str,
        metadata: Optional[Dict] = None,
        expires_in_days: int = 30
    ) -> Prediction:
        """Save a prediction."""
        async with self.session() as db:
            prediction = Prediction(
                session_id=session_id,
                symbol=symbol.upper(),
                prediction_type=prediction_type,
                timeframe=timeframe,
                predicted_value=predicted_value,
                predicted_direction=predicted_direction,
                confidence=confidence,
                reasoning=reasoning,
                extra_data=metadata or {},
                expires_at=datetime.utcnow() + timedelta(days=expires_in_days)
            )
            db.add(prediction)
            await db.flush()
            await db.refresh(prediction)
            return prediction
    
    async def get_predictions(
        self,
        session_id: int,
        symbol: Optional[str] = None,
        resolved: Optional[bool] = None,
        limit: int = 50
    ) -> List[Prediction]:
        """Get predictions."""
        async with self.session() as db:
            query = select(Prediction).where(Prediction.session_id == session_id)
            
            if symbol:
                query = query.where(Prediction.symbol == symbol.upper())
            if resolved is not None:
                if resolved:
                    query = query.where(Prediction.resolved_at.isnot(None))
                else:
                    query = query.where(Prediction.resolved_at.is_(None))
            
            query = query.order_by(desc(Prediction.created_at)).limit(limit)
            result = await db.execute(query)
            return list(result.scalars().all())
    
    async def resolve_prediction(
        self,
        prediction_id: int,
        actual_value: Optional[float],
        actual_direction: Optional[str],
        is_correct: bool,
        accuracy_score: Optional[float] = None
    ) -> Optional[Prediction]:
        """Resolve a prediction with actual results."""
        async with self.session() as db:
            result = await db.execute(select(Prediction).where(Prediction.id == prediction_id))
            prediction = result.scalar_one_or_none()
            
            if prediction:
                prediction.resolved_at = datetime.utcnow()
                prediction.actual_value = actual_value
                prediction.actual_direction = actual_direction
                prediction.is_correct = is_correct
                prediction.accuracy_score = accuracy_score
                await db.flush()
                await db.refresh(prediction)
            return prediction
    
    # ===========================================
    # User Preferences
    # ===========================================
    
    async def set_preference(self, key: str, value: str, category: str, description: Optional[str] = None) -> UserPreference:
        """Set a user preference."""
        async with self.session() as db:
            result = await db.execute(select(UserPreference).where(UserPreference.key == key))
            pref = result.scalar_one_or_none()
            
            if pref:
                pref.value = value
                pref.category = category
                if description:
                    pref.description = description
            else:
                pref = UserPreference(key=key, value=value, category=category, description=description)
                db.add(pref)
            
            await db.flush()
            await db.refresh(pref)
            return pref
    
    async def get_preference(self, key: str) -> Optional[UserPreference]:
        """Get a user preference."""
        async with self.session() as db:
            result = await db.execute(select(UserPreference).where(UserPreference.key == key))
            return result.scalar_one_or_none()
    
    async def get_preferences(self, category: Optional[str] = None) -> List[UserPreference]:
        """Get all preferences, optionally filtered by category."""
        async with self.session() as db:
            query = select(UserPreference)
            if category:
                query = query.where(UserPreference.category == category)
            result = await db.execute(query)
            return list(result.scalars().all())
    
    # ===========================================
    # Research Findings
    # ===========================================
    
    async def save_finding(
        self,
        session_id: int,
        title: str,
        summary: str,
        symbols: List[str],
        finding_type: str,
        severity: str,
        data_sources: List[str],
        evidence: Dict,
        confidence: float,
        tags: Optional[List[str]] = None
    ) -> ResearchFinding:
        """Save a research finding."""
        async with self.session() as db:
            finding = ResearchFinding(
                session_id=session_id,
                title=title,
                summary=summary,
                symbols=[s.upper() for s in symbols],
                finding_type=finding_type,
                severity=severity,
                data_sources=data_sources,
                evidence=evidence,
                confidence=confidence,
                tags=tags or []
            )
            db.add(finding)
            await db.flush()
            await db.refresh(finding)
            return finding
    
    async def get_findings(
        self,
        session_id: int,
        finding_type: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50
    ) -> List[ResearchFinding]:
        """Get research findings."""
        async with self.session() as db:
            query = select(ResearchFinding).where(ResearchFinding.session_id == session_id)
            
            if finding_type:
                query = query.where(ResearchFinding.finding_type == finding_type)
            if severity:
                query = query.where(ResearchFinding.severity == severity)
            
            query = query.order_by(desc(ResearchFinding.created_at)).limit(limit)
            result = await db.execute(query)
            return list(result.scalars().all())
    
    # ===========================================
    # Trade Journal
    # ===========================================
    
    async def add_trade(
        self,
        session_id: int,
        symbol: str,
        side: str,
        entry_price: float,
        quantity: float = 0.0,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        notes: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> Trade:
        """Add a trade to the journal."""
        async with self.session() as db:
            trade = Trade(
                session_id=session_id,
                symbol=symbol.upper(),
                side=side.lower(),
                entry_price=entry_price,
                quantity=quantity,
                stop_loss=stop_loss,
                take_profit=take_profit,
                notes=notes,
                tags=tags or [],
                status="open"
            )
            db.add(trade)
            await db.flush()
            await db.refresh(trade)
            return trade
    
    async def close_trade(
        self,
        trade_id: int,
        exit_price: float,
        notes: Optional[str] = None
    ) -> Optional[Trade]:
        """Close an open trade and compute PnL."""
        async with self.session() as db:
            result = await db.execute(select(Trade).where(Trade.id == trade_id))
            trade = result.scalar_one_or_none()
            if not trade:
                return None
            
            trade.exit_price = exit_price
            trade.status = "closed"
            trade.closed_at = datetime.utcnow()
            if notes:
                trade.notes = (trade.notes or "") + "\n" + notes
            
            direction = 1 if trade.side == "long" else -1
            trade.pnl_pct = ((exit_price - trade.entry_price) / trade.entry_price) * 100 * direction
            trade.pnl = trade.pnl_pct / 100 * trade.entry_price * trade.quantity if trade.quantity else None
            
            await db.flush()
            await db.refresh(trade)
            return trade
    
    async def list_trades(
        self,
        session_id: int,
        status: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 100
    ) -> List[Trade]:
        """List trades."""
        async with self.session() as db:
            query = select(Trade).where(Trade.session_id == session_id)
            if status:
                query = query.where(Trade.status == status)
            if symbol:
                query = query.where(Trade.symbol == symbol.upper())
            query = query.order_by(desc(Trade.opened_at)).limit(limit)
            result = await db.execute(query)
            return list(result.scalars().all())
    
    async def get_trade_stats(self, session_id: int) -> Dict:
        """Compute aggregate trade journal statistics."""
        async with self.session() as db:
            result = await db.execute(
                select(Trade).where(
                    and_(Trade.session_id == session_id, Trade.status == "closed")
                )
            )
            trades = list(result.scalars().all())
        
        if not trades:
            return {
                "total_trades": 0, "wins": 0, "losses": 0, "win_rate": 0.0,
                "total_pnl": 0.0, "avg_pnl_pct": 0.0, "best_trade_pct": 0.0,
                "worst_trade_pct": 0.0, "profit_factor": 0.0,
            }
        
        pnls = [t.pnl_pct for t in trades if t.pnl_pct is not None]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        
        return {
            "total_trades": len(trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": len(wins) / len(trades) * 100 if trades else 0.0,
            "total_pnl": sum(pnls),
            "avg_pnl_pct": sum(pnls) / len(pnls) if pnls else 0.0,
            "best_trade_pct": max(pnls) if pnls else 0.0,
            "worst_trade_pct": min(pnls) if pnls else 0.0,
            "profit_factor": (gross_profit / gross_loss) if gross_loss > 0 else float("inf") if gross_profit > 0 else 0.0,
        }
    
    # ===========================================
    # Tool Execution Logging
    # ===========================================
    
    async def log_tool_execution(
        self,
        session_id: int,
        tool_name: str,
        skill_name: Optional[str],
        input_params: Dict,
        output_data: Dict,
        success: bool,
        error_message: Optional[str],
        execution_time_ms: int
    ) -> ToolExecution:
        """Log a tool execution."""
        async with self.session() as db:
            execution = ToolExecution(
                session_id=session_id,
                tool_name=tool_name,
                skill_name=skill_name,
                input_params=input_params,
                output_data=output_data,
                success=success,
                error_message=error_message,
                execution_time_ms=execution_time_ms
            )
            db.add(execution)
            await db.flush()
            await db.refresh(execution)
            return execution
    
    async def get_tool_executions(
        self,
        session_id: int,
        tool_name: Optional[str] = None,
        limit: int = 100
    ) -> List[ToolExecution]:
        """Get tool execution logs."""
        async with self.session() as db:
            query = select(ToolExecution).where(ToolExecution.session_id == session_id)
            if tool_name:
                query = query.where(ToolExecution.tool_name == tool_name)
            query = query.order_by(desc(ToolExecution.created_at)).limit(limit)
            result = await db.execute(query)
            return list(result.scalars().all())

    # ===========================================
    # Paper Trading
    # ===========================================
    
    async def create_paper_account(
        self,
        session_id: int,
        name: str,
        initial_balance: float = 10000.0
    ) -> PaperAccount:
        """Create a new paper trading account."""
        async with self.session() as db:
            account = PaperAccount(
                session_id=session_id,
                name=name,
                initial_balance=initial_balance,
                current_balance=initial_balance,
                available_balance=initial_balance,
                peak_balance=initial_balance
            )
            db.add(account)
            await db.flush()
            await db.refresh(account)
            return account
    
    async def get_paper_account(self, account_id: int) -> Optional[PaperAccount]:
        """Get a paper account by ID."""
        async with self.session() as db:
            result = await db.execute(
                select(PaperAccount)
                .options(selectinload(PaperAccount.trades), selectinload(PaperAccount.positions))
                .where(PaperAccount.id == account_id)
            )
            return result.scalar_one_or_none()
    
    async def get_paper_accounts(self, session_id: int) -> List[PaperAccount]:
        """Get all paper accounts for a session."""
        async with self.session() as db:
            result = await db.execute(
                select(PaperAccount)
                .where(PaperAccount.session_id == session_id)
                .order_by(desc(PaperAccount.created_at))
            )
            return list(result.scalars().all())
    
    async def update_paper_account_balance(self, account_id: int) -> PaperAccount:
        """Recalculate and update account balance from positions."""
        async with self.session() as db:
            account = await self.get_paper_account(account_id)
            if not account:
                return None
            
            # Calculate position values
            total_position_value = 0.0
            total_unrealized = 0.0
            for pos in account.positions:
                if pos.side == "long":
                    unrealized = (pos.current_price - pos.entry_price) * pos.quantity
                else:
                    unrealized = (pos.entry_price - pos.current_price) * pos.quantity
                pos.unrealized_pnl = unrealized
                pos.unrealized_pnl_pct = (unrealized / (pos.entry_price * pos.quantity)) * 100 if pos.quantity else 0
                total_position_value += pos.current_price * pos.quantity
                total_unrealized += unrealized
            
            # Update account
            account.current_balance = account.available_balance + total_position_value + total_unrealized
            account.total_pnl = account.current_balance - account.initial_balance
            account.total_pnl_pct = (account.total_pnl / account.initial_balance) * 100 if account.initial_balance else 0
            
            # Update drawdown
            if account.current_balance > account.peak_balance:
                account.peak_balance = account.current_balance
            drawdown = account.peak_balance - account.current_balance
            if drawdown > account.max_drawdown:
                account.max_drawdown = drawdown
                account.max_drawdown_pct = (drawdown / account.peak_balance) * 100 if account.peak_balance else 0
            
            account.updated_at = datetime.utcnow()
            await db.flush()
            await db.refresh(account)
            return account
    
    async def open_paper_position(
        self,
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
    ) -> Tuple[PaperTrade, PaperPosition]:
        """Open a new paper trading position."""
        async with self.session() as db:
            account = await self.get_paper_account(account_id)
            if not account:
                raise ValueError("Account not found")
            
            cost = quantity * entry_price
            fee = cost * 0.001  # 0.1% fee
            total_cost = cost + fee
            
            if account.available_balance < total_cost:
                raise ValueError(f"Insufficient balance: {account.available_balance} < {total_cost}")
            
            # Create trade record
            trade = PaperTrade(
                account_id=account_id,
                symbol=symbol.upper(),
                side=side.lower(),
                action="open",
                status="executed",
                quantity=quantity,
                price=entry_price,
                fee=fee,
                strategy_id=strategy_id,
                signal_data=signal_data or {},
                market_context=market_context or {},
            )
            
            # Create position
            position = PaperPosition(
                account_id=account_id,
                symbol=symbol.upper(),
                side=side.lower(),
                quantity=quantity,
                entry_price=entry_price,
                current_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                strategy_id=strategy_id,
            )
            
            # Update account balance
            account.available_balance -= total_cost
            
            db.add(trade)
            db.add(position)
            await db.flush()
            await db.refresh(trade)
            await db.refresh(position)
            
            return trade, position
    
    async def close_paper_position(
        self,
        account_id: int,
        position_id: int,
        exit_price: float,
        quantity: Optional[float] = None,
        reason: str = "manual"
    ) -> Tuple[PaperTrade, Optional[PaperPosition]]:
        """Close a paper trading position (fully or partially)."""
        async with self.session() as db:
            result = await db.execute(
                select(PaperPosition).where(
                    and_(PaperPosition.id == position_id, PaperPosition.account_id == account_id)
                )
            )
            position = result.scalar_one_or_none()
            if not position:
                raise ValueError("Position not found")
            
            close_qty = quantity or position.quantity
            if close_qty > position.quantity:
                raise ValueError("Cannot close more than position size")
            
            # Calculate PnL
            if position.side == "long":
                pnl = (exit_price - position.entry_price) * close_qty
            else:
                pnl = (position.entry_price - exit_price) * close_qty
            
            fee = close_qty * exit_price * 0.001
            net_pnl = pnl - fee
            pnl_pct = (net_pnl / (position.entry_price * close_qty)) * 100 if close_qty else 0
            
            # Create closing trade record
            trade = PaperTrade(
                account_id=account_id,
                symbol=position.symbol,
                side=position.side,
                action="close",
                status="executed",
                quantity=close_qty,
                price=exit_price,
                fee=fee,
                pnl=net_pnl,
                pnl_pct=pnl_pct,
                strategy_id=position.strategy_id,
                signal_data={"close_reason": reason},
                market_context={},
            )
            
            # Update position
            if close_qty >= position.quantity:
                # Full close
                await db.delete(position)
                position = None
            else:
                # Partial close
                position.quantity -= close_qty
            
            # Update account balance
            account = await self.get_paper_account(account_id)
            proceeds = close_qty * exit_price - fee
            account.available_balance += proceeds
            
            db.add(trade)
            await db.flush()
            await db.refresh(trade)
            
            return trade, position
    
    async def update_paper_positions_prices(self, account_id: int, prices: Dict[str, float]) -> List[PaperPosition]:
        """Update current prices for all open positions."""
        async with self.session() as db:
            result = await db.execute(
                select(PaperPosition).where(PaperPosition.account_id == account_id)
            )
            positions = list(result.scalars().all())
            
            for pos in positions:
                if pos.symbol in prices:
                    pos.current_price = prices[pos.symbol]
                    if pos.side == "long":
                        pos.unrealized_pnl = (pos.current_price - pos.entry_price) * pos.quantity
                    else:
                        pos.unrealized_pnl = (pos.entry_price - pos.current_price) * pos.quantity
                    pos.unrealized_pnl_pct = (pos.unrealized_pnl / (pos.entry_price * pos.quantity)) * 100 if pos.quantity else 0
                    pos.updated_at = datetime.utcnow()
                    
                    # Check stop loss / take profit
                    if pos.stop_loss and pos.side == "long" and pos.current_price <= pos.stop_loss:
                        await self.close_paper_position(account_id, pos.id, pos.stop_loss, reason="stop_loss")
                    elif pos.stop_loss and pos.side == "short" and pos.current_price >= pos.stop_loss:
                        await self.close_paper_position(account_id, pos.id, pos.stop_loss, reason="stop_loss")
                    elif pos.take_profit and pos.side == "long" and pos.current_price >= pos.take_profit:
                        await self.close_paper_position(account_id, pos.id, pos.take_profit, reason="take_profit")
                    elif pos.take_profit and pos.side == "short" and pos.current_price <= pos.take_profit:
                        await self.close_paper_position(account_id, pos.id, pos.take_profit, reason="take_profit")
            
            await db.commit()
            return positions
    
    async def get_paper_trades(
        self,
        account_id: int,
        symbol: Optional[str] = None,
        limit: int = 100
    ) -> List[PaperTrade]:
        """Get paper trades for an account."""
        async with self.session() as db:
            query = select(PaperTrade).where(PaperTrade.account_id == account_id)
            if symbol:
                query = query.where(PaperTrade.symbol == symbol.upper())
            query = query.order_by(desc(PaperTrade.executed_at)).limit(limit)
            result = await db.execute(query)
            return list(result.scalars().all())
    
    async def get_paper_account_stats(self, account_id: int) -> Dict:
        """Get comprehensive paper account statistics."""
        async with self.session() as db:
            account = await self.get_paper_account(account_id)
            if not account:
                return {}
            
            # Get all closed trades
            result = await db.execute(
                select(PaperTrade).where(
                    and_(
                        PaperTrade.account_id == account_id,
                        PaperTrade.action == "close"
                    )
                )
            )
            trades = list(result.scalars().all())
            
            if not trades:
                return {
                    "account_name": account.name,
                    "initial_balance": account.initial_balance,
                    "current_balance": account.current_balance,
                    "available_balance": account.available_balance,
                    "total_pnl": account.total_pnl,
                    "total_pnl_pct": account.total_pnl_pct,
                    "max_drawdown": account.max_drawdown,
                    "max_drawdown_pct": account.max_drawdown_pct,
                    "total_trades": 0,
                    "wins": 0,
                    "losses": 0,
                    "win_rate": 0.0,
                    "profit_factor": 0.0,
                    "sharpe_ratio": 0.0,
                    "avg_win": 0.0,
                    "avg_loss": 0.0,
                    "expectancy": 0.0,
                }
            
            pnls = [t.pnl for t in trades if t.pnl is not None]
            pnls_pct = [t.pnl_pct for t in trades if t.pnl_pct is not None]
            wins = [p for p in pnls if p > 0]
            losses = [p for p in pnls if p <= 0]
            wins_pct = [p for p in pnls_pct if p > 0]
            losses_pct = [p for p in pnls_pct if p <= 0]
            
            gross_profit = sum(wins)
            gross_loss = abs(sum(losses))
            
            # Sharpe ratio (simplified)
            returns = pnls_pct
            sharpe = 0.0
            if len(returns) > 1:
                import statistics
                mean_ret = statistics.mean(returns)
                std_ret = statistics.stdev(returns) if len(returns) > 1 else 0
                sharpe = (mean_ret / std_ret) * (252 ** 0.5) if std_ret > 0 else 0  # Annualized
            
            return {
                "account_name": account.name,
                "initial_balance": account.initial_balance,
                "current_balance": account.current_balance,
                "available_balance": account.available_balance,
                "total_pnl": account.total_pnl,
                "total_pnl_pct": account.total_pnl_pct,
                "max_drawdown": account.max_drawdown,
                "max_drawdown_pct": account.max_drawdown_pct,
                "total_trades": len(trades),
                "wins": len(wins),
                "losses": len(losses),
                "win_rate": len(wins) / len(trades) * 100 if trades else 0.0,
                "profit_factor": (gross_profit / gross_loss) if gross_loss > 0 else float("inf") if gross_profit > 0 else 0.0,
                "sharpe_ratio": sharpe,
                "avg_win": statistics.mean(wins_pct) if wins_pct else 0.0,
                "avg_loss": statistics.mean(losses_pct) if losses_pct else 0.0,
                "expectancy": (sum(pnls_pct) / len(pnls_pct)) if pnls_pct else 0.0,
                "best_trade_pct": max(pnls_pct) if pnls_pct else 0.0,
                "worst_trade_pct": min(pnls_pct) if pnls_pct else 0.0,
            }

    # ===========================================
    # Strategy Management
    # ===========================================
    
    async def create_strategy(
        self,
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
    ) -> Strategy:
        """Create a new trading strategy."""
        async with self.session() as db:
            strategy = Strategy(
                session_id=session_id,
                name=name,
                description=description,
                strategy_type=strategy_type,
                parameters=parameters,
                entry_rules=entry_rules,
                exit_rules=exit_rules,
                risk_rules=risk_rules,
                symbols=[s.upper() for s in symbols],
                timeframes=timeframes,
                is_learned=is_learned,
                parent_strategy_id=parent_strategy_id,
            )
            db.add(strategy)
            await db.flush()
            await db.refresh(strategy)
            return strategy
    
    async def get_strategy(self, strategy_id: int) -> Optional[Strategy]:
        """Get a strategy by ID."""
        async with self.session() as db:
            result = await db.execute(select(Strategy).where(Strategy.id == strategy_id))
            return result.scalar_one_or_none()
    
    async def get_strategies(
        self,
        session_id: int,
        strategy_type: Optional[str] = None,
        is_active: Optional[bool] = None,
        is_learned: Optional[bool] = None
    ) -> List[Strategy]:
        """Get strategies for a session."""
        async with self.session() as db:
            query = select(Strategy).where(Strategy.session_id == session_id)
            if strategy_type:
                query = query.where(Strategy.strategy_type == strategy_type)
            if is_active is not None:
                query = query.where(Strategy.is_active == is_active)
            if is_learned is not None:
                query = query.where(Strategy.is_learned == is_learned)
            query = query.order_by(desc(Strategy.created_at))
            result = await db.execute(query)
            return list(result.scalars().all())
    
    async def update_strategy_performance(
        self,
        strategy_id: int,
        total_trades: int,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        profit_factor: float,
        sharpe_ratio: float,
        max_drawdown: float,
        expectancy: float
    ) -> Optional[Strategy]:
        """Update strategy performance metrics."""
        async with self.session() as db:
            result = await db.execute(select(Strategy).where(Strategy.id == strategy_id))
            strategy = result.scalar_one_or_none()
            if strategy:
                strategy.total_trades = total_trades
                strategy.win_rate = win_rate
                strategy.avg_win = avg_win
                strategy.avg_loss = avg_loss
                strategy.profit_factor = profit_factor
                strategy.sharpe_ratio = sharpe_ratio
                strategy.max_drawdown = max_drawdown
                strategy.expectancy = expectancy
                strategy.updated_at = datetime.utcnow()
                await db.flush()
                await db.refresh(strategy)
            return strategy
    
    async def save_strategy_performance(
        self,
        strategy_id: int,
        period_start: datetime,
        period_end: datetime,
        total_trades: int,
        wins: int,
        losses: int,
        win_rate: float,
        total_pnl: float,
        total_pnl_pct: float,
        max_drawdown: float,
        sharpe_ratio: float,
        profit_factor: float,
        expectancy: float,
        avg_holding_time_hours: float,
        best_trade_pct: float,
        worst_trade_pct: float,
        data_source: str
    ) -> StrategyPerformance:
        """Save a strategy performance snapshot."""
        async with self.session() as db:
            perf = StrategyPerformance(
                strategy_id=strategy_id,
                period_start=period_start,
                period_end=period_end,
                total_trades=total_trades,
                wins=wins,
                losses=losses,
                win_rate=win_rate,
                total_pnl=total_pnl,
                total_pnl_pct=total_pnl_pct,
                max_drawdown=max_drawdown,
                sharpe_ratio=sharpe_ratio,
                profit_factor=profit_factor,
                expectancy=expectancy,
                avg_holding_time_hours=avg_holding_time_hours,
                best_trade_pct=best_trade_pct,
                worst_trade_pct=worst_trade_pct,
                data_source=data_source,
            )
            db.add(perf)
            await db.flush()
            await db.refresh(perf)
            return perf
    
    async def get_strategy_performance_history(
        self,
        strategy_id: int,
        limit: int = 50
    ) -> List[StrategyPerformance]:
        """Get performance history for a strategy."""
        async with self.session() as db:
            result = await db.execute(
                select(StrategyPerformance)
                .where(StrategyPerformance.strategy_id == strategy_id)
                .order_by(desc(StrategyPerformance.period_end))
                .limit(limit)
            )
            return list(result.scalars().all())

    # ===========================================
    # Learning Patterns
    # ===========================================
    
    async def save_learning_pattern(
        self,
        session_id: int,
        pattern_type: str,
        pattern_name: str,
        description: str,
        conditions: Dict,
        action: Dict,
        supporting_evidence: Dict,
        confidence: float = 0.5,
        symbols_tested: Optional[List[str]] = None
    ) -> LearningPattern:
        """Save or update a learned pattern."""
        async with self.session() as db:
            # Check if similar pattern exists
            result = await db.execute(
                select(LearningPattern).where(
                    and_(
                        LearningPattern.session_id == session_id,
                        LearningPattern.pattern_type == pattern_type,
                        LearningPattern.pattern_name == pattern_name
                    )
                )
            )
            pattern = result.scalar_one_or_none()
            
            if pattern:
                pattern.times_observed += 1
                pattern.confidence = max(pattern.confidence, confidence)
                pattern.supporting_evidence = supporting_evidence
                pattern.updated_at = datetime.utcnow()
                if symbols_tested:
                    existing = set(pattern.symbols_tested or [])
                    existing.update(s.upper() for s in symbols_tested)
                    pattern.symbols_tested = list(existing)
            else:
                pattern = LearningPattern(
                    session_id=session_id,
                    pattern_type=pattern_type,
                    pattern_name=pattern_name,
                    description=description,
                    conditions=conditions,
                    action=action,
                    supporting_evidence=supporting_evidence,
                    confidence=confidence,
                    symbols_tested=[s.upper() for s in symbols_tested] if symbols_tested else [],
                )
                db.add(pattern)
            
            await db.flush()
            await db.refresh(pattern)
            return pattern
    
    async def update_learning_pattern_outcome(
        self,
        pattern_id: int,
        success: bool
    ) -> Optional[LearningPattern]:
        """Update pattern success/failure count."""
        async with self.session() as db:
            result = await db.execute(select(LearningPattern).where(LearningPattern.id == pattern_id))
            pattern = result.scalar_one_or_none()
            if pattern:
                if success:
                    pattern.times_successful += 1
                else:
                    pattern.times_failed += 1
                # Update confidence based on success rate
                total = pattern.times_successful + pattern.times_failed
                if total > 0:
                    pattern.confidence = pattern.times_successful / total
                pattern.last_validated_at = datetime.utcnow()
                pattern.updated_at = datetime.utcnow()
                await db.flush()
                await db.refresh(pattern)
            return pattern
    
    async def get_learning_patterns(
        self,
        session_id: int,
        pattern_type: Optional[str] = None,
        min_confidence: float = 0.0,
        active_only: bool = True
    ) -> List[LearningPattern]:
        """Get learned patterns."""
        async with self.session() as db:
            query = select(LearningPattern).where(LearningPattern.session_id == session_id)
            if pattern_type:
                query = query.where(LearningPattern.pattern_type == pattern_type)
            if active_only:
                query = query.where(LearningPattern.is_active == True)
            if min_confidence > 0:
                query = query.where(LearningPattern.confidence >= min_confidence)
            query = query.order_by(desc(LearningPattern.confidence), desc(LearningPattern.times_observed))
            result = await db.execute(query)
            return list(result.scalars().all())
    
    async def get_learning_pattern(self, pattern_id: int) -> Optional[LearningPattern]:
        """Get a learning pattern by ID."""
        async with self.session() as db:
            result = await db.execute(select(LearningPattern).where(LearningPattern.id == pattern_id))
            return result.scalar_one_or_none()

    # ===========================================
    # Backtesting
    # ===========================================
    
    async def save_backtest_result(
        self,
        strategy_id: int,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        initial_balance: float,
        final_balance: float,
        total_return_pct: float,
        annualized_return_pct: float,
        total_trades: int,
        wins: int,
        losses: int,
        win_rate: float,
        profit_factor: float,
        sharpe_ratio: float,
        sortino_ratio: float,
        max_drawdown_pct: float,
        avg_holding_hours: float,
        expectancy: float,
        calmar_ratio: float,
        trades_detail: List[Dict],
        equity_curve: List[Dict],
        parameters_used: Dict
    ) -> BacktestResult:
        """Save a backtest result."""
        async with self.session() as db:
            result = BacktestResult(
                strategy_id=strategy_id,
                symbol=symbol.upper(),
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date,
                initial_balance=initial_balance,
                final_balance=final_balance,
                total_return_pct=total_return_pct,
                annualized_return_pct=annualized_return_pct,
                total_trades=total_trades,
                wins=wins,
                losses=losses,
                win_rate=win_rate,
                profit_factor=profit_factor,
                sharpe_ratio=sharpe_ratio,
                sortino_ratio=sortino_ratio,
                max_drawdown_pct=max_drawdown_pct,
                avg_holding_hours=avg_holding_hours,
                expectancy=expectancy,
                calmar_ratio=calmar_ratio,
                trades_detail=trades_detail,
                equity_curve=equity_curve,
                parameters_used=parameters_used,
            )
            db.add(result)
            await db.flush()
            await db.refresh(result)
            return result
    
    async def get_backtest_results(
        self,
        strategy_id: int,
        symbol: Optional[str] = None,
        limit: int = 20
    ) -> List[BacktestResult]:
        """Get backtest results for a strategy."""
        async with self.session() as db:
            query = select(BacktestResult).where(BacktestResult.strategy_id == strategy_id)
            if symbol:
                query = query.where(BacktestResult.symbol == symbol.upper())
            query = query.order_by(desc(BacktestResult.created_at)).limit(limit)
            result = await db.execute(query)
            return list(result.scalars().all())


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


async def get_db_manager() -> DatabaseManager:
    """Get the global database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
        await _db_manager.initialize()
    return _db_manager


async def close_db_manager() -> None:
    """Close the global database manager."""
    global _db_manager
    if _db_manager:
        await _db_manager.close()
        _db_manager = None