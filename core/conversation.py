"""
Conversation management for the Crypto Intelligence Agent.
Handles multi-turn conversations, context management, and message history.
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum

from database.storage import get_db_manager
from database.models import ConversationRole, Message, Session


@dataclass
class ConversationContext:
    """Current conversation context."""
    session_id: str
    current_topic: Optional[str] = None
    current_symbol: Optional[str] = None
    referenced_symbols: List[str] = field(default_factory=list)
    last_analysis: Optional[Dict] = None
    active_skills: List[str] = field(default_factory=list)
    user_preferences: Dict = field(default_factory=dict)
    metadata: Dict = field(default_factory=dict)


class ConversationManager:
    """Manages conversation state and history."""
    
    def __init__(self):
        self._current_session: Optional[Session] = None
        self._context = ConversationContext(session_id="")
        self._max_history_tokens = 8000
        self._summarization_threshold = 6000
    
    async def initialize(self, session_id: Optional[str] = None) -> Session:
        """Initialize or resume a conversation session."""
        db = await get_db_manager()
        
        if session_id:
            session = await db.get_session(session_id)
            if session:
                self._current_session = session
                self._context.session_id = session.session_id
                await self._load_context()
                return session
        
        # Create new session
        session = await db.create_session()
        self._current_session = session
        self._context.session_id = session.session_id
        return session
    
    async def _load_context(self) -> None:
        """Load conversation context from recent messages."""
        if not self._current_session:
            return
        
        db = await get_db_manager()
        messages = await db.get_recent_messages(self._current_session.id, count=20)
        
        # Extract context from recent messages
        symbols = []
        for msg in messages:
            if msg.role == ConversationRole.USER:
                # Simple symbol extraction
                content = msg.content.upper()
                for word in content.split():
                    if word.isalpha() and 2 <= len(word) <= 6 and word.isupper():
                        symbols.append(word)
        
        # Deduplicate and keep recent
        seen = set()
        unique_symbols = []
        for s in reversed(symbols):
            if s not in seen:
                seen.add(s)
                unique_symbols.append(s)
        
        self._context.referenced_symbols = unique_symbols[:10]
        self._context.current_symbol = unique_symbols[0] if unique_symbols else None
        
        # Load user preferences
        prefs = await db.get_preferences()
        self._context.user_preferences = {p.key: p.value for p in prefs}
    
    def get_context(self) -> ConversationContext:
        """Get current conversation context."""
        return self._context
    
    def update_context(self, **kwargs) -> None:
        """Update conversation context."""
        for key, value in kwargs.items():
            if hasattr(self._context, key):
                setattr(self._context, key, value)
        
        # Track referenced symbols
        if "current_symbol" in kwargs and kwargs["current_symbol"]:
            symbol = kwargs["current_symbol"].upper()
            if symbol not in self._context.referenced_symbols:
                self._context.referenced_symbols.insert(0, symbol)
            self._context.referenced_symbols = self._context.referenced_symbols[:10]
    
    async def add_message(
        self,
        role: ConversationRole,
        content: str,
        tool_calls: Optional[Dict] = None,
        tool_results: Optional[Dict] = None,
        model_used: Optional[str] = None,
        tokens_used: Optional[int] = None,
        cost_usd: Optional[float] = None
    ) -> Message:
        """Add a message to the conversation."""
        if not self._current_session:
            await self.initialize()
        
        db = await get_db_manager()
        message = await db.add_message(
            session_id=self._current_session.id,
            role=role,
            content=content,
            tool_calls=tool_calls,
            tool_results=tool_results,
            model_used=model_used,
            tokens_used=tokens_used,
            cost_usd=cost_usd
        )
        
        # Update context based on message
        if role == ConversationRole.USER:
            self._extract_symbols_from_message(content)
        
        return message
    
    def _extract_symbols_from_message(self, content: str) -> None:
        """Extract coin symbols from user message."""
        import re
        
        # Common patterns for coin references
        symbols = set()
        
        # Direct symbol mentions ($BTC, BTC, etc.)
        for match in re.finditer(r'\$?([A-Z]{2,6})\b', content.upper()):
            symbol = match.group(1)
            if symbol not in ('THE', 'AND', 'FOR', 'ARE', 'BUT', 'NOT', 'YOU', 'ALL', 'CAN', 'HOW', 'WHAT', 'WHY', 'WHEN', 'WHERE', 'WHO', 'WHICH', 'THIS', 'THAT', 'WITH', 'FROM', 'HAVE', 'BEEN', 'WERE', 'THEY', 'THEIR', 'THERE', 'ABOUT', 'WOULD', 'COULD', 'SHOULD', 'WANT', 'NEED', 'LIKE', 'JUST', 'MORE', 'THAN', 'VERY', 'MUCH', 'MANY', 'SOME', 'ANY', 'EACH', 'OTHER', 'ANOTHER', 'SUCH', 'ONLY', 'OWN', 'SAME', 'DIFFERENT', 'NEW', 'OLD', 'GOOD', 'BAD', 'BIG', 'SMALL', 'LONG', 'SHORT', 'HIGH', 'LOW', 'FAST', 'SLOW', 'EARLY', 'LATE', 'NEXT', 'LAST', 'FIRST', 'SECOND', 'THIRD'):
                symbols.add(symbol)
        
        # Add to referenced symbols
        for symbol in symbols:
            if symbol not in self._context.referenced_symbols:
                self._context.referenced_symbols.insert(0, symbol)
        
        self._context.referenced_symbols = self._context.referenced_symbols[:10]
        if self._context.referenced_symbols:
            self._context.current_symbol = self._context.referenced_symbols[0]
    
    async def get_recent_messages(self, count: int = 20) -> List[Message]:
        """Get recent messages for context."""
        if not self._current_session:
            return []
        
        db = await get_db_manager()
        return await db.get_recent_messages(self._current_session.id, count)
    
    async def get_conversation_history(self, limit: int = 100) -> List[Dict]:
        """Get formatted conversation history for AI context."""
        if not self._current_session:
            return []
        
        db = await get_db_manager()
        messages = await db.get_messages(self._current_session.id, limit=limit)
        
        return [
            {
                "role": msg.role.value,
                "content": msg.content,
                "tool_calls": msg.tool_calls,
                "tool_results": msg.tool_results,
                "timestamp": msg.created_at.isoformat()
            }
            for msg in messages
        ]
    
    async def build_ai_context(
        self,
        include_history: bool = True,
        history_limit: int = 20,
        system_prompt: Optional[str] = None
    ) -> List[Dict]:
        """Build message context for AI completion."""
        messages = []
        
        # System prompt
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # Add context summary
        context_summary = self._build_context_summary()
        if context_summary:
            messages.append({"role": "system", "content": f"Conversation Context:\n{context_summary}"})
        
        # Add recent history
        if include_history:
            history = await self.get_conversation_history(history_limit)
            for msg in history:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
        
        return messages
    
    def _build_context_summary(self) -> str:
        """Build a summary of current conversation context."""
        parts = []
        
        if self._context.current_symbol:
            parts.append(f"Current focus: {self._context.current_symbol}")
        
        if self._context.referenced_symbols:
            parts.append(f"Referenced symbols: {', '.join(self._context.referenced_symbols[:5])}")
        
        if self._context.current_topic:
            parts.append(f"Current topic: {self._context.current_topic}")
        
        if self._context.active_skills:
            parts.append(f"Active skills: {', '.join(self._context.active_skills)}")
        
        if self._context.last_analysis:
            parts.append(f"Last analysis: {self._context.last_analysis.get('type', 'unknown')} on {self._context.last_analysis.get('symbol', 'unknown')}")
        
        return "\n".join(parts) if parts else ""
    
    async def search_history(self, query: str, limit: int = 10) -> List[Dict]:
        """Search conversation history."""
        if not self._current_session:
            return []
        
        db = await get_db_manager()
        messages = await db.get_messages(self._current_session.id, limit=200)
        
        query_lower = query.lower()
        results = []
        
        for msg in messages:
            if query_lower in msg.content.lower():
                results.append({
                    "role": msg.role.value,
                    "content": msg.content[:500],
                    "timestamp": msg.created_at.isoformat()
                })
                if len(results) >= limit:
                    break
        
        return results
    
    async def clear_history(self) -> bool:
        """Clear conversation history (keep session)."""
        if not self._current_session:
            return False
        
        db = await get_db_manager()
        async with db.session() as session:
            await session.execute(
                f"DELETE FROM messages WHERE session_id = {self._current_session.id}"
            )
        return True
    
    def get_session_info(self) -> Optional[Dict]:
        """Get current session info."""
        if not self._current_session:
            return None
        
        return {
            "session_id": self._current_session.session_id,
            "title": self._current_session.title,
            "created_at": self._current_session.created_at.isoformat(),
            "updated_at": self._current_session.updated_at.isoformat(),
            "metadata": self._current_session.extra_data
        }


# Global conversation manager instance
_conversation_manager: Optional[ConversationManager] = None


def get_conversation_manager() -> ConversationManager:
    """Get the global conversation manager instance."""
    global _conversation_manager
    if _conversation_manager is None:
        _conversation_manager = ConversationManager()
    return _conversation_manager