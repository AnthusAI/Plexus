"""
Core metrics calculation logic for items and score results.
This module provides reusable functions for calculating metrics that can be used
by both Lambda functions and CLI commands.
"""

import os
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional, Tuple
import requests
from dotenv import load_dotenv
import sqlite3
import atexit

# Load environment variables from .env file
load_dotenv('.env', override=True)

logger = logging.getLogger(__name__)

class SQLiteCache:
    """A simple SQLite-based cache for storing metric counts."""
    def __init__(self, db_name='plexus-record-count-cache.db'):
        # Check if /tmp exists and is writable, common for Lambda environments
        if os.path.exists('/tmp') and os.access('/tmp', os.W_OK):
            self.db_path = os.path.join('/tmp', db_name)
        else:
            # Fallback to a local tmp directory for local development
            local_tmp_dir = 'tmp'
            if not os.path.exists(local_tmp_dir):
                os.makedirs(local_tmp_dir)
            self.db_path = os.path.join(local_tmp_dir, db_name)

        # Use an absolute path to avoid ambiguity
        abs_db_path = os.path.abspath(self.db_path)
        logger.debug(f"Initializing SQLite cache at {abs_db_path}")
        self.conn = sqlite3.connect(abs_db_path)
        self.create_table()

    def create_table(self):
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value INTEGER,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def get(self, key: str) -> Optional[int]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT value FROM cache WHERE key = ?", (key,))
        result = cursor.fetchone()
        if result:
            logger.debug(f"Cache GET - HIT: key='{key}', value={result[0]}")
            return result[0]
        else:
            logger.debug(f"Cache GET - MISS: key='{key}'")
            return None

    def set(self, key: str, value: int):
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO cache (key, value) VALUES (?, ?)",
                (key, value)
            )
        self.conn.commit()  # Explicitly commit the transaction
        logger.debug(f"Cache SET: key='{key}', value={value}")

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("SQLite cache connection closed.")

# Instantiate the cache once at the module level
cache = SQLiteCache()

# Ensure the cache connection is closed gracefully on exit
atexit.register(cache.close)

class MetricsCalculator:
    """
    A utility class for calculating items and score results metrics over time periods.
    
    Uses API key authentication to connect to the Plexus GraphQL API and provides
    methods to count items and score results within specific timeframes, 
    generate time buckets, and calculate hourly rates and statistics.
    """
    
    def __init__(self, graphql_endpoint: str, api_key: str, cache_bucket_minutes: int = 5):
        """
        Initialize the MetricsCalculator.
        
        Args:
            graphql_endpoint: The GraphQL API endpoint URL
            api_key: The API key for authentication
            cache_bucket_minutes: The width of the cache buckets in minutes.
        """
        self.graphql_endpoint = graphql_endpoint
        self.api_key = api_key
        self.cache = cache
        self.cache_bucket_minutes = cache_bucket_minutes
        
    def make_graphql_request(self, query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make a GraphQL request to the API using API key authentication.
        
        Args:
            query: The GraphQL query string
            variables: Variables for the GraphQL query
            
        Returns:
            The response data from the API
            
        Raises:
            Exception: If the request fails or returns errors
        """
        payload = {
            'query': query,
            'variables': variables
        }
        
        # Log the request with a brief description
        query_type = "unknown"
        if "listItemByAccountIdAndCreatedAt" in query:
            query_type = "items"
        elif "listScoreResultByAccountIdAndCreatedAt" in query:
            query_type = "score_results"
        elif "listScoreResultByAccountIdAndUpdatedAt" in query:
            query_type = "score_results"
        elif "listItems" in query:
            query_type = "items"
        elif "listScoreResults" in query:
            query_type = "score_results"
        
        page_info = ""
        if variables.get('nextToken'):
            page_info = f" (page {variables.get('_page_number', '?')})"
        
        logger.info(f"GraphQL request: {query_type}{page_info}")
        logger.debug(f"Making GraphQL request to {self.graphql_endpoint}")
        logger.debug(f"Query: {query}")
        logger.debug(f"Variables: {variables}")
        
        headers = {
            'x-api-key': self.api_key,
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.post(
                self.graphql_endpoint,
                json=payload,
                headers=headers,
                timeout=60  # Increased timeout to 60 seconds
            )
        except requests.exceptions.Timeout:
            raise Exception(f"GraphQL request timed out after 60 seconds")
        except requests.exceptions.RequestException as e:
            raise Exception(f"GraphQL request failed: {str(e)}")
        
        if response.status_code != 200:
            raise Exception(f"GraphQL request failed with status {response.status_code}: {response.text}")
        
        data = response.json()
        
        if 'errors' in data:
            errors = data['errors']
            error_messages = [error.get('message', str(error)) for error in errors]
            raise Exception(f"GraphQL errors: {', '.join(error_messages)}")
        
        return data.get('data', {})
    
    def count_items_in_timeframe(self, account_id: str, start_time: datetime, end_time: datetime) -> int:
        """
        Count items created within a specific timeframe using the GSI.
        
        Args:
            account_id: The account ID to filter by
            start_time: Start of the time range
            end_time: End of the time range
            
        Returns:
            Total count of items in the timeframe
        """
        query = """
        query ListItemByAccountIdAndCreatedAt($accountId: String!, $startTime: String!, $endTime: String!, $nextToken: String, $limit: Int) {
            listItemByAccountIdAndCreatedAt(
                accountId: $accountId, 
                createdAt: { between: [$startTime, $endTime] },
                nextToken: $nextToken,
                limit: $limit
            ) {
                items {
                    id
                }
                nextToken
            }
        }
        """
        
        variables = {
            'accountId': account_id,
            'startTime': start_time.isoformat(),
            'endTime': end_time.isoformat(),
            'limit': 1000
        }
        
        total_count = 0
        next_token = None
        page_count = 0
        max_pages = 500  # Increased page limit
        
        logger.info(f"Counting items for account {account_id} between {start_time} and {end_time}")
        
        while True:
            if page_count >= max_pages:
                logger.warning(f"Reached maximum page limit ({max_pages}) while counting items. Partial count: {total_count}")
                break
                
            if next_token:
                variables['nextToken'] = next_token
            
            # Add page number to variables for logging
            variables['_page_number'] = page_count + 1
            
            logger.debug(f"Fetching items page {page_count + 1}")
            
            try:
                data = self.make_graphql_request(query, variables)
            except Exception as e:
                logger.error(f"Failed to fetch items page {page_count + 1}: {str(e)}")
                break
                
            items = data.get('listItemByAccountIdAndCreatedAt', {}).get('items', [])
            item_count = len(items)
            total_count += item_count
            page_count += 1
            
            logger.debug(f"Fetched {item_count} items on page {page_count}, total so far: {total_count}")
            
            next_token = data.get('listItemByAccountIdAndCreatedAt', {}).get('nextToken')
            if not next_token:
                break
        
        logger.info(f"Found {total_count} items between {start_time} and {end_time} (processed {page_count} pages)")
        return total_count
    
    def count_score_results_in_timeframe(self, account_id: str, start_time: datetime, end_time: datetime) -> int:
        """
        Count score results updated within a specific timeframe using the GSI.
        
        Args:
            account_id: The account ID to filter by
            start_time: Start of the time range
            end_time: End of the time range
            
        Returns:
            Total count of score results in the timeframe
        """
        query = """
        query ListScoreResultByAccountIdAndUpdatedAt($accountId: String!, $startTime: String!, $endTime: String!, $nextToken: String, $limit: Int) {
            listScoreResultByAccountIdAndUpdatedAt(
                accountId: $accountId, 
                updatedAt: { between: [$startTime, $endTime] },
                nextToken: $nextToken,
                limit: $limit
            ) {
                items {
                    id
                }
                nextToken
            }
        }
        """
        
        variables = {
            'accountId': account_id,
            'startTime': start_time.isoformat(),
            'endTime': end_time.isoformat(),
            'limit': 1000
        }
        
        total_count = 0
        next_token = None
        page_count = 0
        max_pages = 500  # Increased page limit
        
        logger.info(f"Counting score results for account {account_id} between {start_time} and {end_time}")
        
        while True:
            if page_count >= max_pages:
                logger.warning(f"Reached maximum page limit ({max_pages}) while counting score results. Partial count: {total_count}")
                break
                
            if next_token:
                variables['nextToken'] = next_token
            
            # Add page number to variables for logging
            variables['_page_number'] = page_count + 1
            
            logger.debug(f"Fetching score results page {page_count + 1}")
            
            try:
                data = self.make_graphql_request(query, variables)
            except Exception as e:
                logger.error(f"Failed to fetch score results page {page_count + 1}: {str(e)}")
                break
                
            items = data.get('listScoreResultByAccountIdAndUpdatedAt', {}).get('items', [])
            item_count = len(items)
            total_count += item_count
            page_count += 1
            
            logger.debug(f"Fetched {item_count} score results on page {page_count}, total so far: {total_count}")
            
            next_token = data.get('listScoreResultByAccountIdAndUpdatedAt', {}).get('nextToken')
            if not next_token:
                break
        
        logger.info(f"Found {total_count} score results between {start_time} and {end_time} (processed {page_count} pages)")
        return total_count
    
    def get_time_buckets(self, start_time: datetime, end_time: datetime, bucket_size_minutes: int) -> List[Tuple[datetime, datetime]]:
        """
        Generate time buckets of a specific size between a start and end time.
        """
        buckets = []
        current_time = start_time
        while current_time < end_time:
            bucket_end_time = current_time + timedelta(minutes=bucket_size_minutes)
            buckets.append((current_time, min(bucket_end_time, end_time)))
            current_time = bucket_end_time
        return buckets

    def get_clock_aligned_buckets(self, start_time: datetime, end_time: datetime, bucket_size_minutes: int) -> List[Tuple[datetime, datetime]]:
        """
        Calculates the clock-aligned buckets that are fully contained within the given time range.
        """
        buckets = []
        
        # Find the start of the first full bucket
        first_bucket_start = start_time
        if start_time.minute % bucket_size_minutes != 0 or start_time.second != 0 or start_time.microsecond != 0:
            minutes_to_add = bucket_size_minutes - (start_time.minute % bucket_size_minutes)
            first_bucket_start = (start_time + timedelta(minutes=minutes_to_add)).replace(minute=(start_time.minute + minutes_to_add) % 60, second=0, microsecond=0)

        # Iterate through buckets and add the ones that are fully contained
        current_time = first_bucket_start
        while current_time + timedelta(minutes=bucket_size_minutes) <= end_time:
            buckets.append((current_time, current_time + timedelta(minutes=bucket_size_minutes)))
            current_time += timedelta(minutes=bucket_size_minutes)
            
        return buckets

    def get_count_with_caching(self, account_id: str, start_time: datetime, end_time: datetime, count_function) -> int:
        """
        Get count for a time range, using clock-aligned cache buckets.
        """
        cache_key_prefix = count_function.__name__
        total_count = 0
        
        # Get the clock-aligned buckets that are fully contained in the time range
        aligned_buckets = self.get_clock_aligned_buckets(start_time, end_time, self.cache_bucket_minutes)

        if not aligned_buckets:
            # If no full buckets, just query the whole range
            return count_function(account_id, start_time, end_time)

        # 1. Count items in the first partial bucket (if any)
        first_bucket_start = aligned_buckets[0][0]
        if start_time < first_bucket_start:
            total_count += count_function(account_id, start_time, first_bucket_start)

        # 2. Count items in the full buckets (using cache)
        for bucket_start, bucket_end in aligned_buckets:
            cache_key = f"{cache_key_prefix}:{account_id}:{bucket_start.isoformat()}"
            cached_value = self.cache.get(cache_key)
            if cached_value is not None:
                count = cached_value
                logger.debug(f"Cache hit for {cache_key}: {count} items")
            else:
                count = count_function(account_id, bucket_start, bucket_end)
                self.cache.set(cache_key, count)
                logger.debug(f"Cache miss for {cache_key}. Fetched and cached {count} items")
            total_count += count

        # 3. Count items in the last partial bucket (if any)
        last_bucket_end = aligned_buckets[-1][1]
        if end_time > last_bucket_end:
            total_count += count_function(account_id, last_bucket_end, end_time)

        return total_count
    
    def _get_count_for_window(self, account_id: str, start_time: datetime, end_time: datetime, count_function) -> int:
        """
        Gets the count for an arbitrary time window, using cached buckets and querying for margins.
        Implements the logic from the caching plan.
        """
        bucket_minutes = self.cache_bucket_minutes
        total_count = 0

        # 1. Calculate the boundaries of the fully cached portion of the window
        
        # Round start_time UP to the next bucket boundary
        # If start_time is already on a boundary, it will be moved to the next one, so we handle that.
        if start_time.minute % bucket_minutes == 0 and start_time.second == 0 and start_time.microsecond == 0:
            cache_period_start = start_time
        else:
            cache_period_start_minute = ((start_time.minute // bucket_minutes) + 1) * bucket_minutes
            cache_period_start = start_time.replace(second=0, microsecond=0)
            if cache_period_start_minute >= 60:
                cache_period_start = (cache_period_start + timedelta(hours=1)).replace(minute=0)
            else:
                cache_period_start = cache_period_start.replace(minute=cache_period_start_minute)

        # Round end_time DOWN to the previous bucket boundary
        cache_period_end_minute = (end_time.minute // bucket_minutes) * bucket_minutes
        cache_period_end = end_time.replace(minute=cache_period_end_minute, second=0, microsecond=0)

        # 2. Check if the window is too small to contain any full buckets
        if cache_period_start >= cache_period_end or cache_period_start > end_time or cache_period_end < start_time:
            # The entire window is a margin, query it directly
            logger.debug(f"Window {start_time.isoformat()} to {end_time.isoformat()} has no full cache buckets. Querying directly.")
            return count_function(account_id, start_time, end_time)

        # 3. Query the start margin (if it exists)
        start_margin_end = min(cache_period_start, end_time)
        if start_time < start_margin_end:
            logger.debug(f"Querying start margin: {start_time.isoformat()} to {start_margin_end.isoformat()}")
            total_count += count_function(account_id, start_time, start_margin_end)

        # 4. Get counts from the fully enclosed, cached buckets
        cached_buckets = self.get_clock_aligned_buckets(cache_period_start, cache_period_end, bucket_minutes)
        for sub_start, sub_end in cached_buckets:
            total_count += self.get_count_with_caching(account_id, sub_start, sub_end, count_function)

        # 5. Query the end margin (if it exists)
        if end_time > cache_period_end:
            logger.debug(f"Querying end margin: {cache_period_end.isoformat()} to {end_time.isoformat()}")
            total_count += count_function(account_id, cache_period_end, end_time)

        return total_count

    def get_score_results_summary(self, account_id: str, hours: int = 24) -> Dict[str, Any]:
        """
        Calculate key metrics for score results over the last N hours.
        
        Args:
            account_id: The account ID to filter by
            hours: The number of hours to look back from the current time
            
        Returns:
            A dictionary of calculated metrics for score results
        """
        end_time_utc = datetime.now(timezone.utc)
        logger.info(f"Calculating score results metrics for account {account_id} over {hours} hours")
        
        chart_data = []
        # Create ROLLING hourly buckets, going back from the current time
        for i in range(hours):
            bucket_end = end_time_utc - timedelta(hours=i)
            bucket_start = end_time_utc - timedelta(hours=i + 1)
            
            # This is the hourly window we want to analyze.
            # It is NOT clock-aligned.
            score_results_count = self._get_count_for_window(account_id, bucket_start, bucket_end, self.count_score_results_in_timeframe)
            
            # The label should reflect the clock hour it ends in.
            time_label = bucket_end.strftime('%I %p')
            
            chart_data.append({
                'time': time_label,
                'scoreResults': score_results_count,
                'bucketStart': bucket_start.isoformat(),
                'bucketEnd': bucket_end.isoformat()
            })
            
        # Reverse the data to be chronological
        chart_data.reverse()

        if not chart_data:
            return {
                'scoreResultsPerHour': 0, 'scoreResultsAveragePerHour': 0, 'scoreResultsPeakHourly': 0, 'scoreResultsTotal24h': 0,
                'chartData': []
            }
            
        total_score_results = sum(bucket['scoreResults'] for bucket in chart_data)
        current_hour_score_results = chart_data[-1]['scoreResults'] # The most recent hour
        average_score_results = total_score_results / len(chart_data) if chart_data else 0
        peak_score_results = max(bucket['scoreResults'] for bucket in chart_data) if chart_data else 0
        
        return {
            'scoreResultsPerHour': current_hour_score_results,
            'scoreResultsAveragePerHour': round(average_score_results),
            'scoreResultsPeakHourly': peak_score_results,
            'scoreResultsTotal24h': total_score_results,
            'chartData': chart_data
        }

    def get_items_summary(self, account_id: str, hours: int = 24) -> Dict[str, Any]:
        """
        Calculate key metrics for items over the last N hours.
        
        Args:
            account_id: The account ID to filter by
            hours: The number of hours to look back from the current time
            
        Returns:
            A dictionary of calculated metrics for items
        """
        end_time_utc = datetime.now(timezone.utc)
        logger.info(f"Calculating item metrics for account {account_id} over {hours} hours")
        
        chart_data = []
        # Create ROLLING hourly buckets, going back from the current time
        for i in range(hours):
            bucket_end = end_time_utc - timedelta(hours=i)
            bucket_start = end_time_utc - timedelta(hours=i + 1)
            
            items_count = self._get_count_for_window(account_id, bucket_start, bucket_end, self.count_items_in_timeframe)
            time_label = bucket_end.strftime('%I %p')
            
            chart_data.append({
                'time': time_label,
                'items': items_count,
                'bucketStart': bucket_start.isoformat(),
                'bucketEnd': bucket_end.isoformat()
            })
            
        # Reverse the data to be chronological
        chart_data.reverse()
            
        if not chart_data:
            return {
                'itemsPerHour': 0, 'itemsAveragePerHour': 0, 'itemsPeakHourly': 0, 'itemsTotal24h': 0,
                'chartData': []
            }
            
        total_items = sum(bucket['items'] for bucket in chart_data)
        current_hour_items = chart_data[-1]['items']
        average_items = total_items / len(chart_data) if chart_data else 0
        peak_items = max(bucket['items'] for bucket in chart_data) if chart_data else 0
        
        return {
            'itemsPerHour': current_hour_items,
            'itemsAveragePerHour': round(average_items),
            'itemsPeakHourly': peak_items,
            'itemsTotal24h': total_items,
            'chartData': chart_data
        }


def create_calculator_from_env(cache_bucket_minutes: int = 15) -> MetricsCalculator:
    """
    Create a MetricsCalculator instance from environment variables.
    
    Uses standard PLEXUS_API_URL and PLEXUS_API_KEY environment variables.
    """
    endpoint = os.getenv('PLEXUS_API_URL')
    api_key = os.getenv('PLEXUS_API_KEY')
    
    if not endpoint or not api_key:
        raise ValueError(
            "GraphQL endpoint and API key environment variables must be set. "
            "Set PLEXUS_API_URL and PLEXUS_API_KEY environment variables."
        )
        
    logger.info(f"Creating MetricsCalculator with endpoint: {endpoint}")
    logger.info(f"Using API key: ***{api_key[-4:]}")

    return MetricsCalculator(endpoint, api_key, cache_bucket_minutes=cache_bucket_minutes) 