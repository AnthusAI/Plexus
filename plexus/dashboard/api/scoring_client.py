"""
ScoringClient - High-level client for evaluation scoring and logging.

This client maintains scoring context and provides a simpler interface for logging
results. It handles:
- ID resolution (looking up IDs from keys/names)
- Context maintenance (account, scorecard, score)
- Efficient background logging
- Caching of resolved IDs

Example usage:
    # Initialize with account
    client = ScoringClient.for_account("call-criteria")
    
    # Initialize with full context
    client = ScoringClient.for_scorecard(
        account_key="call-criteria",
        scorecard_key="agent-performance",
        score_name="accuracy"
    )
    
    # Log results using maintained context
    client.log_score(0.95, "call-123", confidence=0.87)
    
    # Override context for specific logs
    client.log_score(0.95, "call-123", 
                    scorecard_key="different-scorecard",
                    score_name="different-score")

Implementation Notes:
    - IDs are resolved lazily and cached
    - Background logging uses configurable batching
    - Thread-safe for concurrent scoring
    - Handles ID resolution errors gracefully
"""

from typing import Optional, Dict, Any, Union
from dataclasses import dataclass
from .client import PlexusAPIClient
from .models.account import Account
from .models.scorecard import Scorecard
from .models.score import Score
from plexus.utils.dict_utils import truncate_dict_strings_inner
import logging

@dataclass
class ScoringContext:
    """Maintains resolved IDs and original identifiers"""
    account_key: Optional[str] = None
    account_id: Optional[str] = None
    scorecard_key: Optional[str] = None
    scorecard_id: Optional[str] = None
    score_name: Optional[str] = None
    score_id: Optional[str] = None

class ScoringClient:
    def __init__(
        self,
        api_client: Optional[PlexusAPIClient] = None,
        context: Optional[ScoringContext] = None
    ):
        self.api_client = api_client or PlexusAPIClient()
        self.context = context or ScoringContext()
        self._cache = {}  # Cache for resolved IDs
        
    @classmethod
    def for_account(cls, account_key: str) -> 'ScoringClient':
        """Create a client initialized with account context"""
        return cls(context=ScoringContext(account_key=account_key))
        
    @classmethod
    def for_scorecard(
        cls,
        account_key: str,
        scorecard_key: str,
        score_name: Optional[str] = None
    ) -> 'ScoringClient':
        """Create a client initialized with full scoring context"""
        return cls(context=ScoringContext(
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
        """Log a score using the current context.
        
        Args:
            value: Score value to log
            item_id: ID of the item being scored
            confidence: Optional confidence score
            metadata: Optional metadata dict
            scorecard_key: Override default scorecard
            score_name: Override default score
            immediate: If True, log immediately (no batching)
            batch_size: Max items per batch
            batch_timeout: Max seconds before flushing batch
            
        The method uses the client's context for account/scorecard/score IDs,
        but allows overriding specific parts of the context per call.
        
        Example:
            # Use context
            client.log_score(0.95, "item-123", confidence=0.87)
            
            # Override scorecard
            client.log_score(0.95, "item-123", 
                           scorecard_key="different-scorecard")
        """
        # Build score data
        score_data = {
            'value': value,
            'itemId': item_id,
            'accountId': self._resolve_account_id()
        }
        
        if scorecard_key:
            score_data['scorecardId'] = self._resolve_scorecard_id(scorecard_key)
        if confidence is not None:
            score_data['confidence'] = confidence
        if metadata:
            score_data['metadata'] = metadata
            
        logging.debug(f"Logging score with data: {truncate_dict_strings_inner(score_data)}")
        
        # Log through API client
        self.api_client.log_score(
            value=value,
            item_id=item_id,
            immediate=immediate,
            batch_size=batch_size,
            batch_timeout=batch_timeout,
            **score_data
        ) 