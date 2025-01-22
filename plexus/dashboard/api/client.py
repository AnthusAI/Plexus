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
import logging

# Configure GQL loggers to not propagate to root
gql_logger = logging.getLogger('gql')
gql_logger.setLevel(logging.INFO)
gql_logger.propagate = False
if not gql_logger.handlers:
    null_handler = logging.NullHandler()
    gql_logger.addHandler(null_handler)

transport_logger = logging.getLogger('gql.transport')
transport_logger.setLevel(logging.INFO)
transport_logger.propagate = False
if not transport_logger.handlers:
    null_handler = logging.NullHandler()
    transport_logger.addHandler(null_handler)

requests_logger = logging.getLogger('urllib3')
requests_logger.setLevel(logging.INFO)
requests_logger.propagate = False
if not requests_logger.handlers:
    null_handler = logging.NullHandler()
    requests_logger.addHandler(null_handler)

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
        self.api_url = api_url or os.getenv('PLEXUS_API_URL')
        self.api_key = api_key or os.getenv('PLEXUS_API_KEY')
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
            fetch_schema_from_transport=True
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
                try:
                    item = self._log_queue.get(timeout=1.0)
                except Empty:
                    # This is expected when queue is empty - just flush existing batches
                    current_time = time.time()
                    for items in batches.values():
                        if items:
                            self._flush_logs(items)
                    batches.clear()
                    last_flush = current_time
                    continue
                
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
                    
            except Exception as e:
                # Log any unexpected errors but keep the thread running
                logging.error(f"Error in log processing thread: {e}")
                time.sleep(1.0)  # Avoid tight loop if there's a persistent error

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
            transport = RequestsHTTPTransport(
                url=self.api_url,
                headers={
                    'x-api-key': self.api_key,
                    'Content-Type': 'application/json',
                },
                verify=True,
                retries=3,
            )
            client = Client(
                transport=transport,
                fetch_schema_from_transport=True
            )
            with client as session:
                return session.execute(gql(query), variable_values=variables)
        except TransportQueryError as e:
            # The error object contains a list of error dictionaries
            if hasattr(e, 'errors') and e.errors:
                error_message = e.errors[0]['message']
            else:
                error_message = str(e)
            raise Exception(f"GraphQL query failed: {error_message}")

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
        """Get scorecard ID, trying key, external ID, and name lookup"""
        identifier = override_key or self.context.scorecard_key
        if not identifier:
            return None
        
        # Check cache first
        cache_key = f"scorecard:{identifier}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        from .models.scorecard import Scorecard
        
        # Try each lookup method in sequence
        for lookup_method in [
            lambda: Scorecard.get_by_key(identifier, self),
            lambda: Scorecard.get_by_external_id(identifier, self),
            lambda: Scorecard.get_by_name(identifier, self)
        ]:
            try:
                scorecard = lookup_method()
                self._cache[cache_key] = scorecard.id
                if not override_key:
                    self.context.scorecard_id = scorecard.id
                return scorecard.id
            except (ValueError, Exception):
                continue
            
        raise ValueError(f"Could not find scorecard in the API with identifier: {identifier}")
    
    def _resolve_score_id(self) -> Optional[str]:
        """Get score ID, resolving from key, external ID, or name if needed"""
        if self.context.score_id:
            return self.context.score_id
        
        identifier = self.context.score_name
        if not identifier:
            return None
        
        scorecard_id = self._resolve_scorecard_id()
        if not scorecard_id:
            return None
        
        # Check cache first
        cache_key = f"score:{identifier}:{self.context.scorecard_key}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        from .models.score import Score
        
        # Try each lookup method in sequence
        for lookup_method in [
            lambda: Score.get_by_key(identifier, scorecard_id, self),
            lambda: Score.get_by_external_id(identifier, scorecard_id, self),
            lambda: Score.get_by_name(identifier, scorecard_id, self)
        ]:
            try:
                score = lookup_method()
                if score:
                    self._cache[cache_key] = score.id
                    self.context.score_id = score.id
                    return score.id
            except Exception:
                continue
            
        return None

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

    def _get_batch_job_count(self, batch_job_id: str, max_retries: int = 3) -> int:
        """
        Get accurate count of scoring jobs for a batch with retries and consistency check.
        """
        count_jobs_query = """
        query CountBatchJobLinks(
            $batchJobId: String!
            $limit: Int
            $nextToken: String
        ) {
            listBatchJobScoringJobs(
                filter: { batchJobId: { eq: $batchJobId } }
                limit: $limit
                nextToken: $nextToken
            ) {
                items {
                    scoringJobId
                }
                nextToken
            }
        }
        """
        
        all_items = []
        next_token = None
        retries = 0
        
        while retries < max_retries:
            try:
                # Fetch items with pagination
                variables = {
                    'batchJobId': str(batch_job_id),
                    'limit': 1000  # Adjust based on your needs
                }
                if next_token:
                    variables['nextToken'] = next_token
                    
                result = self.execute(count_jobs_query, variables)
                page_items = result.get('listBatchJobScoringJobs', {}).get('items', [])
                all_items.extend(page_items)
                
                next_token = result.get('listBatchJobScoringJobs', {}).get('nextToken')
                if not next_token:  # No more pages
                    break
                    
            except Exception as e:
                logging.warning(f"Error counting batch jobs (attempt {retries + 1}): {e}")
                retries += 1
                time.sleep(0.5)  # Add small delay between retries
                continue
                
        total_jobs = len(all_items)
        logging.info(f"Found {total_jobs} total scoring jobs for batch {batch_job_id}")
        return total_jobs

    def batch_scoring_job(
        self,
        itemId: str,
        scorecardId: str,
        accountId: str,
        model_provider: str,
        model_name: str,
        scoreId: Optional[str] = None,
        parameters: Optional[Dict] = None,
        metadata: Optional[Dict] = None,
        max_batch_size: int = 20,
        **kwargs
    ) -> Tuple['ScoringJob', 'BatchJob']:
        """Finds or creates a scoring job and assigns it to an appropriate batch job.
        
        If a scoring job exists for the item, returns it with its associated batch job.
        If no scoring job exists, creates one and either:
        - Assigns it to an existing open batch job with matching criteria, or
        - Creates a new batch job if no suitable open batch exists."""
        from .models.scoring_job import ScoringJob
        from .models.batch_job import BatchJob

        logging.info(f"Starting batch_scoring_job with itemId={itemId}, scorecardId={scorecardId}, accountId={accountId}")
        if parameters:
            logging.info(f"Received parameters: {parameters}")
        if metadata:
            logging.info(f"Received metadata: {metadata}")

        # First check if a scoring job already exists for this item
        existing_job = ScoringJob.find_by_item_id(itemId, self)
        if existing_job:
            logging.info(f"Found existing scoring job {existing_job.id} for item {itemId}")
            batch_job = ScoringJob.get_batch_job(existing_job.id, self)
            if not batch_job:
                logging.warning(f"Scoring job {existing_job.id} has no associated batch job")
            return existing_job, batch_job

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
                    totalRequests
                    status
                    modelProvider
                    modelName
                    scoringJobCountCache
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

        # Find existing batch or create new one
        batch_job = None
        open_batches = result.get('listBatchJobs', {}).get('items', [])
        
        for batch in open_batches:
            total_requests = batch.get('totalRequests')
            # If totalRequests is None or less than max_batch_size, use this batch
            if total_requests is None or total_requests < max_batch_size:
                batch_job = BatchJob.get_by_id(batch['id'], self)
                break

        if not batch_job:
            logging.info("No usable open batch found, creating new one")
            create_params = {
                'accountId': accountId,
                'type': 'MultiStepScore',
                'modelProvider': model_provider,
                'modelName': model_name,
                'parameters': parameters or {},
                'scorecardId': scorecardId,
                'scoreId': scoreId,
                'scoringJobCountCache': 0,  # Initialize cache to 0
            }
            # Don't include status in kwargs since we set it explicitly
            kwargs_without_status = {k: v for k, v in kwargs.items() if k != 'status'}
            create_params.update(kwargs_without_status)
            create_params['status'] = 'OPEN'  # Always set status to OPEN for new batch jobs
            
            batch_job = BatchJob.create(
                client=self,
                **create_params
            )
            logging.info(f"Created new batch job: {batch_job.id}")

        # Create new scoring job with batch ID
        logging.info(f"Creating scoring job for batch {batch_job.id}")
        
        # Create scoring job with metadata
        scoring_job = ScoringJob.create(
            client=self,
            accountId=accountId,
            scorecardId=scorecardId,
            itemId=itemId,
            scoreId=scoreId,
            batchId=batch_job.id,
            parameters=parameters or {},
            metadata=metadata,  # Pass metadata directly
            status='PENDING'
        )
        logging.info(f"Created scoring job: {scoring_job.id}")

        # Create the link between batch job and scoring job
        link_mutation = """
        mutation CreateBatchJobScoringJob($input: CreateBatchJobScoringJobInput!) {
            createBatchJobScoringJob(input: $input) {
                batchJobId
                scoringJobId
            }
        }
        """
        link_result = self.execute(
            link_mutation,
            {
                'input': {
                    'batchJobId': batch_job.id,
                    'scoringJobId': scoring_job.id
                }
            }
        )
        logging.info(f"Created batch-scoring link: {link_result}")

        # Count actual scoring jobs for this batch using BatchJobScoringJob
        total_jobs = self._get_batch_job_count(batch_job.id)
        logging.info(f"Total scoring jobs in batch: {total_jobs}")
        logging.info(f"Max batch size: {max_batch_size}")

        # Get current batch status
        batch_query = """
        query GetBatchStatus($batchId: ID!) {
            getBatchJob(id: $batchId) {
                id
                status
                totalRequests
                scoringJobCountCache
            }
        }
        """
        batch_status_result = self.execute(batch_query, {'batchId': batch_job.id})
        current_status = batch_status_result.get('getBatchJob', {}).get('status')
        logging.info(f"Current batch status: {current_status}")

        # Update batch job count and cache
        update_count_mutation = """
        mutation UpdateBatchJobCount($input: UpdateBatchJobInput!) {
            updateBatchJob(input: $input) {
                id
                scoringJobCountCache
                status
            }
        }
        """
        update_result = self.execute(
            update_count_mutation,
            {
                'input': {
                    'id': batch_job.id,
                    'accountId': batch_job.accountId,
                    'status': batch_job.status,
                    'type': batch_job.type,
                    'batchId': batch_job.batchId,
                    'modelProvider': batch_job.modelProvider,
                    'modelName': batch_job.modelName,
                    'scoringJobCountCache': total_jobs
                }
            }
        )
        logging.info(f"Updated batch job count: {update_result}")
        
        # If we've reached or exceeded max_batch_size and batch is still open, close it
        if total_jobs >= max_batch_size and current_status == 'OPEN':
            logging.info(
                f"Batch job {batch_job.id} has reached max size "
                f"({total_jobs}/{max_batch_size}). Closing batch."
            )
            close_mutation = """
            mutation CloseBatchJob($input: UpdateBatchJobInput!) {
                updateBatchJob(input: $input) {
                    id
                    status
                    scoringJobCountCache
                }
            }
            """
            close_result = self.execute(
                close_mutation, 
                {
                    'input': {
                        'id': batch_job.id,
                        'accountId': batch_job.accountId,
                        'status': 'CLOSED',
                        'type': batch_job.type,
                        'batchId': batch_job.batchId,
                        'modelProvider': batch_job.modelProvider,
                        'modelName': batch_job.modelName,
                        'scoringJobCountCache': total_jobs
                    }
                }
            )
            logging.info(f"Batch job closed: {close_result}")

        return scoring_job, batch_job

    def updateEvaluation(self, id: str, **kwargs) -> None:
        """Update evaluation fields."""
        try:
            # Always update the updatedAt timestamp
            kwargs['updatedAt'] = datetime.now(timezone.utc).isoformat().replace(
                '+00:00', 'Z'
            )
            
            mutation = """
            mutation UpdateEvaluation($input: UpdateEvaluationInput!) {
                updateEvaluation(input: $input) {
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
                    accuracy
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
            
            return self.execute(mutation, variables)
            
        except Exception as e:
            logging.error(f"Error updating evaluation: {e}")
            raise

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