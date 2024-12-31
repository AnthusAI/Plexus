"""Model namespaces for the Plexus Dashboard API client."""

from typing import Optional, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from .client import _BaseAPIClient

class ScoreResultNamespace:
    def __init__(self, client: '_BaseAPIClient'):
        self._client = client
        
    def create(
        self,
        value: float,
        item_id: str,
        *,
        immediate: bool = False,
        batch_size: Optional[int] = 10,
        batch_timeout: Optional[float] = 1.0,
        **kwargs
    ) -> None:
        """Create a new score result, optionally in background"""
        from .models.score_result import ScoreResult
        return ScoreResult.create(
            client=self._client,
            value=value,
            itemId=item_id,
            **kwargs
        )

    def batch_create(self, items: list[Dict]) -> None:
        """Create multiple score results in a batch."""
        from .models.score_result import ScoreResult
        return ScoreResult.batch_create(self._client, items)

class ScorecardNamespace:
    def __init__(self, client: '_BaseAPIClient'):
        self._client = client
        
    def get_by_key(self, key: str):
        from .models.scorecard import Scorecard
        return Scorecard.get_by_key(key, self._client)
        
    def get_by_id(self, id: str):
        from .models.scorecard import Scorecard
        return Scorecard.get_by_id(id, self._client)

class AccountNamespace:
    def __init__(self, client: '_BaseAPIClient'):
        self._client = client
        
    def get_by_key(self, key: str):
        from .models.account import Account
        return Account.get_by_key(key, self._client)
        
    def get_by_id(self, id: str):
        from .models.account import Account
        return Account.get_by_id(id, self._client) 