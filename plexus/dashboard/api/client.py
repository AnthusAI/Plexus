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
from typing import Optional, Dict, Any, Tuple, List, TYPE_CHECKING
from dataclasses import dataclass
from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport
from gql.transport.exceptions import TransportQueryError
from queue import Queue, Empty
from threading import Thread, Event
import time
from datetime import datetime, timezone
import logging
from plexus.utils import truncate_dict_strings_inner
# Configure minimal logging for GraphQL operations
# Only show warnings and errors from external libraries
transport_logger = logging.getLogger('gql.transport')
transport_logger.setLevel(logging.WARNING)
transport_logger.propagate = False

requests_logger = logging.getLogger('urllib3')
requests_logger.setLevel(logging.WARNING)
requests_logger.propagate = False

gql_logger = logging.getLogger('gql')
gql_logger.setLevel(logging.WARNING)
gql_logger.propagate = False

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

        # Check environment variable for schema introspection setting
        # Default to True for backward compatibility, but allow disabling for Lambda/packaging scenarios
        fetch_schema_str = os.getenv('PLEXUS_FETCH_SCHEMA_FROM_TRANSPORT', 'true').lower()
        self._fetch_schema = fetch_schema_str in ('true', '1', 'yes')

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
            fetch_schema_from_transport=self._fetch_schema
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
        if not hasattr(self, '_stop_logging') or self._stop_logging is None or self._stop_logging.is_set():
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
                fetch_schema_from_transport=self._fetch_schema
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
    
    def load_score_configuration(self, scorecard_identifier: str, score_name: str, 
                                use_cache: bool = False, yaml_only: bool = False):
        """
        Load a score configuration using the standardized Score.load() method.
        
        This provides a convenient way for dashboard clients to load score configurations
        using the same DRY, tested logic used throughout the system.
        
        Args:
            scorecard_identifier: Scorecard identifier (ID, key, name, etc.)
            score_name: Name of the score to load
            use_cache: Whether to use cached YAML files (default: False for fresh API data)
            yaml_only: Whether to restrict to YAML-only loading (default: False)
            
        Returns:
            Score instance with loaded configuration
            
        Raises:
            ValueError: If the score cannot be loaded
        """
        from plexus.scores.Score import Score
        
        return Score.load(
            scorecard_identifier=scorecard_identifier,
            score_name=score_name,
            use_cache=use_cache,
            yaml_only=yaml_only
        )

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

        logging.info("=== BATCH SCORING JOB START ===")
        logging.info(f"itemId: {itemId}")
        logging.info(f"scorecardId: {scorecardId}")
        logging.info(f"accountId: {accountId}")
        logging.info(f"model_provider: {model_provider}")
        logging.info(f"model_name: {model_name}")
        logging.info(f"scoreId: {scoreId}")
        logging.info(f"status: {kwargs.get('status')}")
        
        logging.info("=== METADATA DUMP START ===")
        if metadata:
            for key, value in metadata.items():
                logging.info(f"metadata[{key}]: {str(value)[:200]}...")
        else:
            logging.info("No metadata provided")
        logging.info("=== METADATA DUMP END ===")
        
        logging.info("=== PARAMETERS DUMP START ===")
        if parameters:
            for key, value in parameters.items():
                logging.info(f"parameters[{key}]: {value}")
        else:
            logging.info("No parameters provided")
        logging.info("=== PARAMETERS DUMP END ===")

        logging.info("Starting batch_scoring_job with itemId={}, scorecardId={}, accountId={}".format(
            itemId, scorecardId, accountId
        ))
        logging.info(f"Received parameters: {parameters}")

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
                'parameters': parameters,
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
            parameters=parameters,
            metadata=metadata,
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
        if total_jobs >= max_batch_size and batch_job.status == 'OPEN':
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

    def generate_deep_link(self, url_pattern: str, params: Dict[str, str]) -> str:
        """
        Generate a deep link URL to a Plexus dashboard resource.
        
        Args:
            url_pattern: URL pattern with placeholders (e.g., "/reports/{reportId}")
            params: Dictionary of parameters to fill into the URL pattern
                   (e.g., {"reportId": "123"})
        
        Returns:
            Complete URL including protocol and hostname
        
        Example:
            client.generate_deep_link("/reports/{reportId}", {"reportId": "123"})
            # Returns: "https://app.plexus.domain/reports/123"
        """
        # Use environment variable for base URL, with fallback to a default
        base_url = os.environ.get('PLEXUS_DASHBOARD_URL', 'https://app.plexus.ai')
        
        # Remove trailing slash from base_url if present
        if base_url.endswith('/'):
            base_url = base_url[:-1]
        
        # Add leading slash to url_pattern if not present
        if not url_pattern.startswith('/'):
            url_pattern = '/' + url_pattern
            
        # Replace placeholders in the URL pattern
        for key, value in params.items():
            placeholder = f"{{{key}}}"
            url_pattern = url_pattern.replace(placeholder, value)
            
        # Combine the base URL with the filled pattern
        full_url = f"{base_url}{url_pattern}"
        
        return full_url

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
        
    # Context manager methods
    def __enter__(self):
        """Make the client usable as a context manager, returning the GQL client."""
        return self.client
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Handle cleanup when exiting the context manager."""
        return False  # Don't suppress exceptions
    
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
    
    # Chat-related methods for GraphQL chat system
    async def create_chat_session(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new chat session."""
        mutation = '''
        mutation CreateChatSession($input: CreateChatSessionInput!) {
            createChatSession(input: $input) {
                id
                accountId
                scorecardId
                scoreId
                procedureId
                name
                category
                status
                metadata
                createdAt
                updatedAt
            }
        }
        '''
        
        variables = {"input": session_data}
        result = await self._execute_query(mutation, variables)
        return result['createChatSession']
    
    async def create_chat_message(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new chat message."""
        mutation = '''
        mutation CreateChatMessage($input: CreateChatMessageInput!) {
            createChatMessage(input: $input) {
                id
                sessionId
                procedureId
                role
                content
                metadata
                createdAt
            }
        }
        '''
        
        variables = {"input": message_data}
        result = await self._execute_query(mutation, variables)
        return result['createChatMessage']
    
    async def update_chat_session(self, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing chat session."""
        mutation = '''
        mutation UpdateChatSession($input: UpdateChatSessionInput!) {
            updateChatSession(input: $input) {
                id
                accountId
                scorecardId
                scoreId
                procedureId
                status
                metadata
                createdAt
                updatedAt
            }
        }
        '''
        
        variables = {"input": update_data}
        result = await self._execute_query(mutation, variables)
        return result['updateChatSession']
    
    async def get_chat_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get a chat session by ID."""
        query = '''
        query GetChatSession($id: ID!) {
            getChatSession(id: $id) {
                id
                accountId
                scorecardId
                scoreId
                procedureId
                status
                metadata
                createdAt
                updatedAt
            }
        }
        '''
        
        variables = {"id": session_id}
        result = await self._execute_query(query, variables)
        return result.get('getChatSession')
    
    async def list_chat_messages(
        self, 
        session_id: str = None, 
        experiment_id: str = None, 
        limit: int = 50,
        sort_by: str = 'createdAt'
    ) -> List[Dict[str, Any]]:
        """List chat messages for a session or experiment."""
        if experiment_id:
            # Query by experiment GSI for chronological order
            query = '''
            query ListChatMessagesByExperiment($procedureId: String!, $limit: Int, $sortDirection: ModelSortDirection) {
                listChatMessages(
                    filter: { procedureId: { eq: $procedureId } }
                    limit: $limit
                    sortDirection: $sortDirection
                ) {
                    items {
                        id
                        sessionId
                        procedureId
                        role
                        content
                        metadata
                        createdAt
                    }
                }
            }
            '''
            variables = {
                "procedureId": experiment_id,
                "limit": limit,
                "sortDirection": "ASC" if sort_by == 'createdAt' else "DESC"
            }
        else:
            # Query by session
            query = '''
            query ListChatMessagesBySession($sessionId: String!, $limit: Int) {
                listChatMessages(
                    filter: { sessionId: { eq: $sessionId } }
                    limit: $limit
                    sortDirection: ASC
                ) {
                    items {
                        id
                        sessionId
                        procedureId
                        role
                        content
                        metadata
                        createdAt
                    }
                }
            }
            '''
            variables = {"sessionId": session_id, "limit": limit}
        
        result = await self._execute_query(query, variables)
        return result['listChatMessages']['items']
    
    async def list_chat_sessions(
        self, 
        account_id: str = None, 
        experiment_id: str = None, 
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """List chat sessions for an account or experiment."""
        if experiment_id:
            # Query by experiment GSI
            query = '''
            query ListChatSessionsByExperiment($procedureId: String!, $limit: Int) {
                listChatSessions(
                    filter: { procedureId: { eq: $procedureId } }
                    limit: $limit
                    sortDirection: DESC
                ) {
                    items {
                        id
                        accountId
                        scorecardId
                        scoreId
                        procedureId
                        status
                        metadata
                        createdAt
                        updatedAt
                    }
                }
            }
            '''
            variables = {"procedureId": experiment_id, "limit": limit}
        else:
            # Query by account
            query = '''
            query ListChatSessionsByAccount($accountId: String!, $limit: Int) {
                listChatSessions(
                    filter: { accountId: { eq: $accountId } }
                    limit: $limit
                    sortDirection: DESC
                ) {
                    items {
                        id
                        accountId
                        scorecardId
                        scoreId
                        procedureId
                        status
                        metadata
                        createdAt
                        updatedAt
                    }
                }
            }
            '''
            variables = {"accountId": account_id, "limit": limit}
        
        result = await self._execute_query(query, variables)
        return result['listChatSessions']['items']