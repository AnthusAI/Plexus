"""
GraphQL API Client - Handles authentication, API communication, and background logging.

This client provides three main functionalities:
1. GraphQL API communication with authentication
2. Fire-and-forget score logging with configurable batching
3. Background thread management for async operations

Authentication:
    Uses API key authentication configured through environment variables:
    - PLEXUS_API_URL: The AppSync API endpoint
    - PLEXUS_API_KEY: The API key for authentication

Background Logging:
    The client maintains a background thread for efficient score logging with these features:
    - Configurable batch sizes (default: 10 items)
    - Configurable timeouts (default: 1 second)
    - Immediate logging option for urgent data
    - Automatic batch flushing on shutdown
    - Error resilience (errors are logged but don't affect main thread)

    Example usage:
        # Standard batched logging
        client.log_score(0.95, "item-123", 
                        accountId="acc-123",
                        scoringJobId="job-123",
                        scorecardId="card-123")

        # Immediate logging (no batching)
        client.log_score(0.95, "item-123",
                        immediate=True,
                        accountId="acc-123",
                        scoringJobId="job-123",
                        scorecardId="card-123")

        # Custom batch configuration
        client.log_score(0.95, "item-123",
                        batch_size=50,
                        batch_timeout=5.0,
                        accountId="acc-123",
                        scoringJobId="job-123",
                        scorecardId="card-123")

Implementation Details:
    - Uses a Queue for thread-safe communication
    - Maintains separate batches for different batch_size/timeout configurations
    - Daemon thread ensures cleanup on program exit
    - Graceful shutdown with flush() method
    - Automatic JSON serialization of metadata fields

Error Handling:
    - API errors are caught and logged (fire-and-forget)
    - Background thread errors don't affect main application
    - GraphQL query errors are propagated for direct API calls
"""

import os
from typing import Optional, Dict, Any, Tuple, TYPE_CHECKING
from dataclasses import dataclass
from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport
from gql.transport.exceptions import TransportQueryError
from queue import Queue, Empty
from threading import Thread, Event
import time
from datetime import datetime, timezone

if TYPE_CHECKING:
    from .models.scoring_job import ScoringJob
    from .models.batch_job import BatchJob
    from .models.account import Account
    from .models.scorecard import Scorecard
    from .models.score import Score

@dataclass
class ClientContext:
    account_key: Optional[str] = None
    account_id: Optional[str] = None
    scorecard_key: Optional[str] = None
    scorecard_id: Optional[str] = None
    score_name: Optional[str] = None
    score_id: Optional[str] = None

class _BaseAPIClient:
    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        context: Optional[ClientContext] = None
    ):
        self.api_url = api_url or os.environ.get('PLEXUS_API_URL')
        self.api_key = api_key or os.environ.get('PLEXUS_API_KEY')
        self.context = context or ClientContext()
        self._cache = {}
        
        # Initialize background logging attributes
        self._log_queue = None
        self._stop_logging = None
        self._log_thread = None
        
        if not all([self.api_url, self.api_key]):
            raise ValueError("Missing required API URL or API key")
            
        # Set up GQL client with API key authentication
        transport = RequestsHTTPTransport(
            url=self.api_url,
            headers={
                'x-api-key': self.api_key,
                'Content-Type': 'application/json',
            },
            verify=True,
            retries=3,
        )
        
        self.client = Client(
            transport=transport,
            fetch_schema_from_transport=False
        )
        
        # Initialize model namespaces
        from .namespaces import (
            ScoreResultNamespace,
            ScorecardNamespace,
            AccountNamespace
        )
        self.ScoreResult = ScoreResultNamespace(self)
        self.Scorecard = ScorecardNamespace(self)
        self.Account = AccountNamespace(self)
        
        # Background logging setup
        self._log_queue = Queue()
        self._stop_logging = Event()
        self._log_thread = Thread(target=self._process_logs, daemon=True)
        self._log_thread.start()

    def _process_logs(self):
        """Process logs in background thread."""
        batches = {}  # Dict of batch_config -> items
        last_flush = time.time()
        
        while not self._stop_logging.is_set():
            try:
                # Wait up to 1 second for new items
                item = self._log_queue.get(timeout=1.0)
                
                # Extract batch config
                batch_size = item.pop('batch_size', 10)
                batch_timeout = item.pop('batch_timeout', 1.0)
                batch_key = (batch_size, batch_timeout)
                
                # Add to appropriate batch
                if batch_key not in batches:
                    batches[batch_key] = []
                batches[batch_key].append(item)
                
                # Check each batch
                current_time = time.time()
                for (size, timeout), items in list(batches.items()):
                    if (size and len(items) >= size) or \
                       (timeout and current_time - last_flush > timeout):
                        self._flush_logs(items)
                        batches[size, timeout] = []
                        last_flush = current_time
                    
            except Empty:
                # Flush any remaining items
                current_time = time.time()
                for items in batches.values():
                    if items:
                        self._flush_logs(items)
                batches.clear()
                last_flush = current_time

    def flush(self) -> None:
        """Flush any pending log items immediately."""
        if not self._stop_logging:
            return
            
        # Signal thread to stop
        self._stop_logging.set()
        
        # Get any remaining items from queue
        remaining = []
        while not self._log_queue.empty():
            try:
                remaining.append(self._log_queue.get_nowait())
            except Empty:
                break
        
        # Flush remaining items if any
        if remaining:
            self._flush_logs(remaining)
        
        # Wait for thread to finish
        if self._log_thread and self._log_thread.is_alive():
            self._log_thread.join(timeout=5.0)
    
    def __del__(self):
        self.flush()

    def execute(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        try:
            return self.client.execute(gql(query), variable_values=variables)
        except TransportQueryError as e:
            raise Exception(f"GraphQL query failed: {str(e)}")

    def _resolve_account_id(self) -> str:
        """Get account ID, resolving from key if needed"""
        if self.context.account_id:
            return self.context.account_id
            
        cache_key = f"account:{self.context.account_key}"
        if cache_key in self._cache:
            return self._cache[cache_key]
            
        from .models.account import Account
        account = Account.get_by_key(self.context.account_key, self)
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
            
        from .models.scorecard import Scorecard
        scorecard = Scorecard.get_by_key(key, self)
        self._cache[cache_key] = scorecard.id
        if not override_key:
            self.context.scorecard_id = scorecard.id
        return scorecard.id
    
    def _resolve_score_id(self) -> Optional[str]:
        """Get score ID, resolving from name if needed"""
        if self.context.score_id:
            return self.context.score_id
            
        if not self.context.score_name:
            return None
            
        cache_key = f"score:{self.context.score_name}:{self.context.scorecard_key}"
        if cache_key in self._cache:
            return self._cache[cache_key]
            
        scorecard_id = self._resolve_scorecard_id()
        if not scorecard_id:
            return None
            
        from .models.score import Score
        score = Score.get_by_name(self.context.score_name, scorecard_id, self)
        if not score:
            return None
            
        self._cache[cache_key] = score.id
        self.context.score_id = score.id
        return score.id

    def log_score(
        self, 
        value: float, 
        item_id: str, 
        *, 
        immediate: bool = False,
        batch_size: Optional[int] = 10,
        batch_timeout: Optional[float] = 1.0,
        confidence: Optional[float] = None,
        metadata: Optional[Dict] = None,
        scorecard_key: Optional[str] = None,
        score_name: Optional[str] = None,
        **kwargs
    ) -> None:
        score_data = {
            'value': value,
            'itemId': item_id,
            **kwargs
        }

        # Try to resolve IDs from context if not provided
        if 'accountId' not in score_data and self.context.account_key:
            score_data['accountId'] = self._resolve_account_id()
            
        if 'scorecardId' not in score_data and (scorecard_key or self.context.scorecard_key):
            scorecard_id = self._resolve_scorecard_id(scorecard_key)
            if scorecard_id:
                score_data['scorecardId'] = scorecard_id
        
        if confidence is not None:
            score_data['confidence'] = confidence
        if metadata:
            score_data['metadata'] = metadata
            
        if immediate:
            thread = Thread(
                target=self._log_single_score,
                args=(),
                kwargs=score_data,
                daemon=True
            )
            thread.start()
        else:
            self._log_queue.put({
                'batch_size': batch_size,
                'batch_timeout': batch_timeout,
                **score_data
            })

    def _log_single_score(self, **kwargs):
        try:
            from .models.score_result import ScoreResult
            ScoreResult.create(
                client=self,
                **kwargs
            )
        except Exception as e:
            print(f"Error logging score: {e}")
    
    def _flush_logs(self, items):
        try:
            from .models.score_result import ScoreResult
            ScoreResult.batch_create(self, items)
        except Exception as e:
            print(f"Error flushing logs: {e}")

    def batch_scoring_job(
        self,
        itemId: str,
        scorecardId: str,
        accountId: str,
        model_provider: str,
        model_name: str,
        provider: str,
        scoreId: Optional[str] = None,
        parameters: Optional[Dict] = None,
        max_batch_size: int = 100,
        **kwargs
    ) -> Tuple['ScoringJob', 'BatchJob']:
        """Create or add to a batch scoring job."""
        from .models.scoring_job import ScoringJob
        from .models.batch_job import BatchJob

        # Look for an existing open batch job
        query = """
        query GetOpenBatchJobs(
            $accountId: String!,
            $scorecardId: String!,
            $modelProvider: String!,
            $modelName: String!
        ) {
            listBatchJobs(
                filter: {
                    accountId: { eq: $accountId },
                    scorecardId: { eq: $scorecardId },
                    modelProvider: { eq: $modelProvider },
                    modelName: { eq: $modelName },
                    status: { eq: "OPEN" }
                }
            ) {
                items {
                    id
                    batchJobScoringJobs {
                        items {
                            scoringJobId
                        }
                    }
                }
            }
        }
        """

        result = self.execute(query, {
            'accountId': accountId,
            'scorecardId': scorecardId,
            'modelProvider': model_provider,
            'modelName': model_name
        })

        # Create new scoring job
        scoring_job = ScoringJob.create(
            client=self,
            accountId=accountId,
            scorecardId=scorecardId,
            itemId=itemId,
            scoreId=scoreId,
            parameters=parameters or {},
            **kwargs
        )

        # Find existing batch or create new one
        batch_job = None
        open_batches = result.get('listBatchJobs', {}).get('items', [])
        
        for batch in open_batches:
            scoring_job_count = len(batch.get('batchJobScoringJobs', {}).get('items', []))
            if scoring_job_count < max_batch_size:
                batch_job = BatchJob.get_by_id(batch['id'], self)
                break

        if not batch_job:
            batch_job = BatchJob.create(
                client=self,
                accountId=accountId,
                type='MODEL_INFERENCE',
                modelProvider=model_provider,
                modelName=model_name,
                provider=provider,
                parameters=parameters or {},
                scorecardId=scorecardId,
                scoreId=scoreId,
                **kwargs
            )

        # Link scoring job to batch job
        mutation = """
        mutation CreateBatchJobScoringJob(
            $batchJobId: String!, 
            $scoringJobId: String!
        ) {
            createBatchJobScoringJob(input: {
                batchJobId: $batchJobId
                scoringJobId: $scoringJobId
            }) {
                batchJobId
                scoringJobId
            }
        }
        """

        self.execute(mutation, {
            'batchJobId': batch_job.id,
            'scoringJobId': scoring_job.id
        })

        # Check if batch is now full
        count_query = """
        query GetBatchJobCount($batchJobId: String!) {
            getBatchJob(id: $batchJobId) {
                batchJobScoringJobs {
                    items {
                        scoringJobId
                    }
                }
            }
        }
        """

        count_result = self.execute(count_query, {'batchJobId': batch_job.id})
        current_count = len(count_result.get('getBatchJob', {})
                           .get('batchJobScoringJobs', {})
                           .get('items', []))

        if current_count >= max_batch_size:
            close_mutation = """
            mutation UpdateBatchJob($batchJobId: String!) {
                updateBatchJob(input: {
                    id: $batchJobId,
                    status: "CLOSED"
                }) {
                    id
                    status
                }
            }
            """
            self.execute(close_mutation, {'batchJobId': batch_job.id})

        return scoring_job, batch_job

class PlexusDashboardClient(_BaseAPIClient):
    """
    Client for the Plexus Dashboard API.
    
    Provides access to all API resources with schema-matching namespaces:
        client.ScoreResult.create(...)
        client.ScoreResult.batch_create(...)
        client.Scorecard.get_by_key(...)
        etc.
    
    Features:
    - Background processing with configurable batching
    - ID resolution and caching
    - Thread-safe operations
    - Context management for accounts, scorecards, and scores
    """
    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        context: Optional[ClientContext] = None
    ):
        super().__init__(api_url=api_url, api_key=api_key, context=context)

    @classmethod
    def for_account(cls, account_key: str) -> 'PlexusDashboardClient':
        """Create a client initialized with account context"""
        return cls(context=ClientContext(account_key=account_key))
        
    @classmethod
    def for_scorecard(
        cls,
        account_key: str,
        scorecard_key: str,
        score_name: Optional[str] = None
    ) -> 'PlexusDashboardClient':
        """Create a client initialized with full scoring context"""
        return cls(context=ClientContext(
            account_key=account_key,
            scorecard_key=scorecard_key,
            score_name=score_name
        ))