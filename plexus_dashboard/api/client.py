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
from typing import Optional, Dict, Any
from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport
from gql.transport.exceptions import TransportQueryError
from queue import Queue, Empty
from threading import Thread, Event
import time
from datetime import datetime, timezone

class _BaseAPIClient:
    """Base API client with GraphQL functionality"""
    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.api_url = api_url or os.environ.get('PLEXUS_API_URL')
        self.api_key = api_key or os.environ.get('PLEXUS_API_KEY')
        
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
        self.ScoreResult = ScoreResultNamespace(self)
        self.Scorecard = ScorecardNamespace(self)
        self.Account = AccountNamespace(self)
        
        # Background logging setup
        self._log_queue = Queue()
        self._stop_logging = Event()
        self._log_thread = Thread(target=self._process_logs, daemon=True)
        self._log_thread.start()
    
    def execute(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        try:
            return self.client.execute(gql(query), variable_values=variables)
        except TransportQueryError as e:
            raise Exception(f"GraphQL query failed: {str(e)}")
    
    def log_score(
        self, 
        value: float, 
        item_id: str, 
        *,  # Force keyword arguments
        immediate: bool = False,
        batch_size: Optional[int] = 10,
        batch_timeout: Optional[float] = 1.0,
        **kwargs
    ) -> None:
        """Fire-and-forget score logging with configurable batching.
        
        This method provides flexible logging options:
        1. Standard batched logging (default)
        2. Immediate logging (immediate=True)
        3. Custom batch configurations (batch_size, batch_timeout)
        
        The method is non-blocking and thread-safe. Errors during logging
        are caught and logged but don't affect the calling code.
        
        Args:
            value: Score value to log (required)
            item_id: ID of the item being scored (required)
            immediate: If True, log immediately in a new thread (no batching)
            batch_size: Max items per batch (None for no limit), default 10
            batch_timeout: Max seconds before flushing batch (None for no timeout), default 1s
            **kwargs: Additional score result fields (accountId, etc.)
        
        Thread Safety:
            This method is thread-safe and can be called from multiple threads.
            The background processing ensures proper batching and API communication.
        
        Error Handling:
            Errors during logging are caught and logged but not propagated.
            This ensures the main application continues running even if logging fails.
        """
        if immediate:
            thread = Thread(
                target=self._log_single_score,
                args=(value, item_id),
                kwargs=kwargs,
                daemon=True
            )
            thread.start()
        else:
            self._log_queue.put({
                'value': value,
                'itemId': item_id,
                'batch_size': batch_size,
                'batch_timeout': batch_timeout,
                **kwargs
            })
    
    def _log_single_score(self, value: float, item_id: str, **kwargs):
        try:
            from .models.score_result import ScoreResult
            ScoreResult.create(
                client=self,
                value=value,
                itemId=item_id,
                **kwargs
            )
        except Exception as e:
            # Log error but don't raise - this is fire-and-forget
            print(f"Error logging score: {e}")
    
    def _process_logs(self):
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
    
    def _flush_logs(self, items):
        try:
            from .models.score_result import ScoreResult
            ScoreResult.batch_create(self, items)
        except Exception as e:
            # Log error but don't raise - this is fire-and-forget
            print(f"Error flushing logs: {e}")
    
    def flush(self) -> None:
        """Flush any pending log items immediately.
        
        This method:
        1. Stops the background logging thread
        2. Collects any remaining items from the queue
        3. Sends them to the API in a final batch
        4. Waits for the thread to finish (with timeout)
        
        This is automatically called during shutdown but can also be
        called manually to ensure all logs are sent.
        
        Thread Safety:
            Safe to call from any thread, but should typically be called
            only during shutdown or when immediate flushing is required.
        """
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

class ScoreResultNamespace:
    def __init__(self, client: _BaseAPIClient):
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
        # ... implementation ...

class ScorecardNamespace:
    def __init__(self, client: _BaseAPIClient):
        self._client = client
        
    def get_by_key(self, key: str):
        from .models.scorecard import Scorecard
        return Scorecard.get_by_key(key, self._client)
        
    def get_by_id(self, id: str):
        from .models.scorecard import Scorecard
        return Scorecard.get_by_id(id, self._client)

class AccountNamespace:
    def __init__(self, client: _BaseAPIClient):
        self._client = client
        
    def get_by_key(self, key: str):
        from .models.account import Account
        return Account.get_by_key(key, self._client)
        
    def get_by_id(self, id: str):
        from .models.account import Account
        return Account.get_by_id(id, self._client)

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
    """
    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        context: Optional[Dict[str, str]] = None
    ):
        super().__init__(api_url, api_key)
        self.context = context or {}
        
        # Initialize model namespaces
        self.ScoreResult = ScoreResultNamespace(self)
        self.Scorecard = ScorecardNamespace(self)
        self.Account = AccountNamespace(self)

    def updateExperiment(self, id: str, **kwargs) -> None:
        """Update experiment fields."""
        try:
            # Always update the updatedAt timestamp
            kwargs['updatedAt'] = datetime.now(timezone.utc).isoformat().replace(
                '+00:00', 'Z'
            )
            
            mutation = """
            mutation UpdateExperiment($input: UpdateExperimentInput!) {
                updateExperiment(input: $input) {
                    id
                    type
                    accountId
                    status
                    createdAt
                    updatedAt
                    parameters
                    metrics
                    metricsExplanation
                    inferences
                    cost
                    startedAt
                    elapsedSeconds
                    estimatedRemainingSeconds
                    totalItems
                    processedItems
                    errorMessage
                    errorDetails
                    scorecardId
                    scoreId
                    confusionMatrix
                    scoreGoal
                    datasetClassDistribution
                    isDatasetClassDistributionBalanced
                    predictedClassDistribution
                    isPredictedClassDistributionBalanced
                }
            }
            """
            
            variables = {
                'input': {
                    'id': id,
                    **kwargs
                }
            }
            
            self.execute(mutation, variables)
            
        except Exception as e:
            logger.error(f"Error updating experiment: {e}")
            raise