"""
Memory management for the Crypto Intelligence Agent.
Handles persistent memory, preferences, and research findings.
"""

import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

from database.storage import get_db_manager
from database.models import UserPreference, ResearchFinding, Session, Analysis, Prediction
from core.conversation import get_conversation_manager


@dataclass
class MemoryEntry:
    """A memory entry."""
    key: str
    value: Any
    category: str
    created_at: datetime
    updated_at: datetime
    metadata: Dict = None


class MemoryManager:
    """Manages persistent memory."""
    
    def __init__(self):
        self._cache: Dict[str, Any] = {}
    
    async def initialize(self) -> None:
        """Initialize memory manager."""
        pass
    
    async def set_preference(self, key: str, value: str, category: str = "general", description: str = "") -> None:
        """Set a user preference."""
        db = await get_db_manager()
        await db.set_preference(key, value, category, description)
        self._cache[key] = value
    
    async def get_preference(self, key: str, default: str = "") -> str:
        """Get a user preference."""
        if key in self._cache:
            return self._cache[key]
        
        db = await get_db_manager()
        pref = await db.get_preference(key)
        if pref:
            self._cache[key] = pref.value
            return pref.value
        return default
    
    async def get_preferences(self, category: str = None) -> Dict[str, str]:
        """Get all preferences."""
        db = await get_db_manager()
        prefs = await db.get_preferences(category)
        return {p.key: p.value for p in prefs}
    
    async def save_finding(
        self,
        title: str,
        summary: str,
        symbols: List[str],
        finding_type: str,
        severity: str,
        data_sources: List[str],
        evidence: Dict,
        confidence: float,
        tags: List[str] = None
    ) -> ResearchFinding:
        """Save a research finding."""
        conversation = get_conversation_manager()
        
        if not conversation._current_session:
            raise ValueError("No active session")
        
        db = await get_db_manager()
        return await db.save_finding(
            session_id=conversation._current_session.id,
            title=title,
            summary=summary,
            symbols=symbols,
            finding_type=finding_type,
            severity=severity,
            data_sources=data_sources,
            evidence=evidence,
            confidence=confidence,
            tags=tags or []
        )
    
    async def get_findings(
        self,
        finding_type: str = None,
        severity: str = None,
        limit: int = 50
    ) -> List[ResearchFinding]:
        """Get research findings."""
        conversation = get_conversation_manager()
        
        if not conversation._current_session:
            return []
        
        db = await get_db_manager()
        return await db.get_findings(
            session_id=conversation._current_session.id,
            finding_type=finding_type,
            severity=severity,
            limit=limit
        )
    
    async def save_analysis(
        self,
        analysis_type: str,
        symbol: str,
        timeframe: str,
        input_data: Dict,
        result: Dict,
        confidence: float = None,
        tags: List[str] = None
    ) -> Analysis:
        """Save an analysis result."""
        conversation = get_conversation_manager()
        
        if not conversation._current_session:
            raise ValueError("No active session")
        
        db = await get_db_manager()
        return await db.save_analysis(
            session_id=conversation._current_session.id,
            analysis_type=analysis_type,
            symbol=symbol,
            timeframe=timeframe,
            input_data=input_data,
            result=result,
            confidence=confidence,
            tags=tags or []
        )
    
    async def get_analyses(
        self,
        symbol: str = None,
        analysis_type: str = None,
        limit: int = 50
    ) -> List[Analysis]:
        """Get previous analyses."""
        conversation = get_conversation_manager()
        
        if not conversation._current_session:
            return []
        
        db = await get_db_manager()
        return await db.get_analyses(
            session_id=conversation._current_session.id,
            symbol=symbol,
            analysis_type=analysis_type,
            limit=limit
        )
    
    async def save_prediction(
        self,
        symbol: str,
        prediction_type: str,
        timeframe: str,
        predicted_value: float = None,
        predicted_direction: str = None,
        confidence: float = 0.5,
        reasoning: str = "",
        metadata: Dict = None,
        expires_in_days: int = 30
    ) -> Prediction:
        """Save a prediction."""
        conversation = get_conversation_manager()
        
        if not conversation._current_session:
            raise ValueError("No active session")
        
        db = await get_db_manager()
        return await db.save_prediction(
            session_id=conversation._current_session.id,
            symbol=symbol,
            prediction_type=prediction_type,
            timeframe=timeframe,
            predicted_value=predicted_value,
            predicted_direction=predicted_direction,
            confidence=confidence,
            reasoning=reasoning,
            metadata=metadata or {},
            expires_in_days=expires_in_days
        )
    
    async def get_predictions(
        self,
        symbol: str = None,
        resolved: bool = None,
        limit: int = 50
    ) -> List[Prediction]:
        """Get predictions."""
        conversation = get_conversation_manager()
        
        if not conversation._current_session:
            return []
        
        db = await get_db_manager()
        return await db.get_predictions(
            session_id=conversation._current_session.id,
            symbol=symbol,
            resolved=resolved,
            limit=limit
        )
    
    async def resolve_prediction(
        self,
        prediction_id: int,
        actual_value: float = None,
        actual_direction: str = None,
        is_correct: bool = False,
        accuracy_score: float = None
    ) -> Optional[Prediction]:
        """Resolve a prediction."""
        db = await get_db_manager()
        return await db.resolve_prediction(
            prediction_id=prediction_id,
            actual_value=actual_value,
            actual_direction=actual_direction,
            is_correct=is_correct,
            accuracy_score=accuracy_score
        )
    
    async def search(self, query: str, limit: int = 10) -> List[str]:
        """Search memory for relevant information."""
        results = []
        query_lower = query.lower()
        
        # Search findings
        findings = await self.get_findings(limit=limit)
        for f in findings:
            if query_lower in f.title.lower() or query_lower in f.summary.lower() or any(query_lower in s.lower() for s in f.symbols):
                results.append(f"Finding: {f.title} - {f.summary[:100]}")
        
        # Search analyses
        conversation = get_conversation_manager()
        if conversation._current_session:
            db = await get_db_manager()
            analyses = await db.get_analyses(session_id=conversation._current_session.id, limit=limit)
            for a in analyses:
                if query_lower in a.symbol.lower() or query_lower in str(a.result).lower():
                    results.append(f"Analysis: {a.symbol} ({a.analysis_type.value}) - {str(a.result)[:100]}")
        
        return results[:limit]
    
    async def export(self) -> Dict:
        """Export all memory data."""
        conversation = get_conversation_manager()
        
        if not conversation._current_session:
            return {}
        
        db = await get_db_manager()
        
        findings = await self.get_findings(limit=1000)
        analyses = await db.get_analyses(session_id=conversation._current_session.id, limit=1000)
        predictions = await self.get_predictions(limit=1000)
        preferences = await self.get_preferences()
        
        return {
            "session_id": conversation._current_session.session_id,
            "exported_at": datetime.utcnow().isoformat(),
            "findings": [asdict(f) for f in findings],
            "analyses": [asdict(a) for a in analyses],
            "predictions": [asdict(p) for p in predictions],
            "preferences": preferences
        }
    
    async def clear(self) -> None:
        """Clear all memory for current session."""
        conversation = get_conversation_manager()
        
        if not conversation._current_session:
            return
        
        db = await get_db_manager()
        async with db.session() as session:
            await session.execute(f"DELETE FROM research_findings WHERE session_id = {conversation._current_session.id}")
            await session.execute(f"DELETE FROM analyses WHERE session_id = {conversation._current_session.id}")
            await session.execute(f"DELETE FROM predictions WHERE session_id = {conversation._current_session.id}")
            await session.execute(f"DELETE FROM user_preferences WHERE session_id = {conversation._current_session.id}")
        
        self._cache.clear()
    
    async def get_context_for_symbol(self, symbol: str) -> Dict:
        """Get all relevant memory context for a symbol."""
        conversation = get_conversation_manager()
        
        if not conversation._current_session:
            return {}
        
        db = await get_db_manager()
        
        # Get analyses for symbol
        analyses = await db.get_analyses(
            session_id=conversation._current_session.id,
            symbol=symbol,
            limit=10
        )
        
        # Get findings for symbol
        findings = await self.get_findings(limit=100)
        symbol_findings = [f for f in findings if symbol.upper() in [s.upper() for s in f.symbols]]
        
        # Get predictions for symbol
        predictions = await self.get_predictions(symbol=symbol, limit=10)
        
        # Get latest analysis
        latest_analysis = await db.get_latest_analysis(conversation._current_session.id, symbol)
        
        return {
            "symbol": symbol.upper(),
            "analyses_count": len(analyses),
            "recent_analyses": [{"type": a.analysis_type.value, "timeframe": a.timeframe, "confidence": a.confidence, "created": a.created_at.isoformat()} for a in analyses[:5]],
            "findings_count": len(symbol_findings),
            "recent_findings": [{"title": f.title, "type": f.finding_type, "severity": f.severity, "confidence": f.confidence} for f in symbol_findings[:5]],
            "predictions_count": len(predictions),
            "active_predictions": [{"type": p.prediction_type, "timeframe": p.timeframe, "confidence": p.confidence, "direction": p.predicted_direction} for p in predictions if p.resolved_at is None],
            "latest_analysis": latest_analysis.result if latest_analysis else None
        }


# Global memory manager instance
_memory_manager: Optional[MemoryManager] = None


async def get_memory_manager() -> MemoryManager:
    """Get the global memory manager instance."""
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
        await _memory_manager.initialize()
    return _memory_manager