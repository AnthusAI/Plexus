"""
ClientManager - High-level client for managing API operations with context.

This client maintains context and provides a simpler interface for API operations. It handles:
- ID resolution (looking up IDs from keys/names)
- Context maintenance (account, scorecard, score)
- Efficient background logging
- Caching of resolved IDs

Example usage:
    # Initialize with account
    manager = ClientManager.for_account("call-criteria")
    
    # Initialize with full context
    manager = ClientManager.for_scorecard(
        account_key="call-criteria",
        scorecard_key="agent-performance",
        score_name="accuracy"
    )
    
    # Log results using maintained context
    manager.log_score(0.95, "call-123", confidence=0.87)
    
    # Override context for specific logs
    manager.log_score(0.95, "call-123", 
                    scorecard_key="different-scorecard",
                    score_name="different-score")
"""

from typing import Optional, Dict, Any
from dataclasses import dataclass
from .client import PlexusDashboardClient
from .models.account import Account
from .models.scorecard import Scorecard
from .models.score import Score

@dataclass
class ClientContext:
    """Maintains resolved IDs and original identifiers"""
    account_key: Optional[str] = None
    account_id: Optional[str] = None
    scorecard_key: Optional[str] = None
    scorecard_id: Optional[str] = None
    score_name: Optional[str] = None
    score_id: Optional[str] = None

class ClientManager:
    def __init__(
        self,
        api_client: Optional[PlexusDashboardClient] = None,
        context: Optional[ClientContext] = None
    ):
        self.api_client = api_client or PlexusDashboardClient()
        self.context = context or ClientContext()
        self._cache = {}  # Cache for resolved IDs
        
    @classmethod
    def for_account(cls, account_key: str) -> 'ClientManager':
        """Create a manager initialized with account context"""
        return cls(context=ClientContext(account_key=account_key))
        
    @classmethod
    def for_scorecard(
        cls,
        account_key: str,
        scorecard_key: str,
        score_name: Optional[str] = None
    ) -> 'ClientManager':
        """Create a manager initialized with full scoring context"""
        return cls(context=ClientContext(
            account_key=account_key,
            scorecard_key=scorecard_key,
            score_name=score_name
        ))
    
    def _resolve_account_id(self) -> str:
        """Get account ID, resolving from key if needed"""
        if self.context.account_id:
            return self.context.account_id
            
        cache_key = f"account:{self.context.account_key}"
        if cache_key in self._cache:
            return self._cache[cache_key]
            
        account = Account.get_by_key(self.context.account_key, self.api_client)
        self._cache[cache_key] = account.id
        self.context.account_id = account.id
        return account.id
    
    def _resolve_scorecard_id(self, override_key: Optional[str] = None) -> Optional[str]:
        """Get scorecard ID, resolving from key if needed"""
        key = override_key or self.context.scorecard_key
        if not key:
            return None
            
        cache_key = f"scorecard:{key}"
        if cache_key in self._cache:
            return self._cache[cache_key]
            
        scorecard = Scorecard.get_by_key(key, self.api_client)
        self._cache[cache_key] = scorecard.id
        if not override_key:
            self.context.scorecard_id = scorecard.id
        return scorecard.id
    
    def log_score(
        self,
        value: float,
        item_id: str,
        *,
        confidence: Optional[float] = None,
        metadata: Optional[Dict] = None,
        scorecard_key: Optional[str] = None,
        score_name: Optional[str] = None,
        immediate: bool = False,
        batch_size: Optional[int] = 10,
        batch_timeout: Optional[float] = 1.0
    ) -> None:
        """Log a score using the current context."""
        # Resolve IDs (using cache when possible)
        account_id = self._resolve_account_id()
        scorecard_id = self._resolve_scorecard_id(scorecard_key)
        
        # Build score data
        score_data = {
            'accountId': account_id,
            'itemId': item_id
        }
        
        if scorecard_id:
            score_data['scorecardId'] = scorecard_id
        if confidence is not None:
            score_data['confidence'] = confidence
        if metadata:
            score_data['metadata'] = metadata
            
        # Log through API client
        self.api_client.log_score(
            value=value,
            immediate=immediate,
            batch_size=batch_size,
            batch_timeout=batch_timeout,
            **score_data
        ) 