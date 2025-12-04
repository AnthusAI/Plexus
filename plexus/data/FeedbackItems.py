"""
FeedbackItems data cache for loading datasets from feedback items.

This data cache loads feedback items for a specific scorecard and score,
builds a confusion matrix, and samples items from each cell to create
a balanced training dataset.
"""

import os
import json
import hashlib
import logging
import asyncio
import random
from typing import Optional, List, Dict, Any, Tuple, Union
from datetime import datetime, timezone, timedelta
from collections import defaultdict

import pandas as pd
from pydantic import Field, validator

from plexus.data.DataCache import DataCache
from plexus.cli.feedback.feedback_service import FeedbackService
from plexus.cli.shared.identifier_resolution import resolve_scorecard_identifier, resolve_score_identifier
from plexus.cli.shared.client_utils import create_client
from plexus.cli.report.utils import resolve_account_id_for_command
from plexus.dashboard.api.models.feedback_item import FeedbackItem

logger = logging.getLogger(__name__)


class FeedbackItems(DataCache):
    """
    Data cache that loads datasets from feedback items.

    This class fetches feedback items for a given scorecard and score,
    analyzes the confusion matrix, and samples items from each matrix cell
    to create a balanced dataset for training/evaluation.

    Confusion Matrix Sampling:
    --------------------------
    Items are grouped by (initial_value, final_value) pairs, forming confusion matrix cells:
    - (No→No): AI predicted No, human kept No (agreement)
    - (No→Yes): AI predicted No, human changed to Yes (false negative)
    - (Yes→No): AI predicted Yes, human changed to No (false positive)
    - (Yes→Yes): AI predicted Yes, human kept Yes (agreement)

    Sampling behavior with limit_per_cell:
    - Samples up to limit_per_cell items from EACH cell independently
    - This creates balanced training across prediction patterns, not raw frequency
    - Example: With limit_per_cell=50 and raw data [2,592 No→Yes, 315 No→No, 5 Yes→Yes]:
      Result: 50 No→Yes + 50 No→No + 5 Yes→Yes = 105 items (52% Yes, 48% No final values)
      Instead of raw 89% Yes, 11% No distribution

    This balancing helps models learn from both agreements and corrections across
    different prediction types, rather than being dominated by the most common pattern.
    """
    
    class Parameters(DataCache.Parameters):
        """Parameters for FeedbackItems data cache."""
        
        scorecard: Union[str, int] = Field(..., description="Scorecard identifier (name, key, ID, or external ID)")
        score: Union[str, int] = Field(..., description="Score identifier (name, key, ID, or external ID)")  
        days: Optional[int] = Field(None, description="Number of days back to search for feedback items (None = all time)")
        limit: Optional[int] = Field(None, description="Maximum total number of items in the dataset")
        limit_per_cell: Optional[int] = Field(None, description="Maximum number of items to sample from each confusion matrix cell")
        initial_value: Optional[str] = Field(None, description="Filter by original AI prediction value")
        final_value: Optional[str] = Field(None, description="Filter by corrected human value")
        feedback_id: Optional[str] = Field(None, description="Specific feedback item ID to create dataset for (if specified, only this item will be included)")
        backfill_cells: Optional[bool] = Field(False, description="If True, backfill confusion matrix cells to limit_per_cell using older data outside the time window when cells have insufficient items")
        identifier_extractor: Optional[str] = Field(None, description="Optional client-specific identifier extractor class (e.g., 'CallCriteriaIdentifierExtractor')")
        column_mappings: Optional[Dict[str, str]] = Field(None, description="Optional mapping of original score names to new column names (e.g., {'Agent Misrepresentation': 'Agent Misrepresentation - With Confidence'})")
        cache_file: str = Field(default="feedback_items_cache.parquet", description="Cache file name")
        local_cache_directory: str = Field(default='./.plexus_training_data_cache/', description="Local cache directory")
        
        @validator('days')
        def days_must_be_positive(cls, v):
            if v is not None and v <= 0:
                raise ValueError('days must be positive')
            return v
            
        @validator('limit')
        def limit_must_be_positive(cls, v):
            if v is not None and v <= 0:
                raise ValueError('limit must be positive')
            return v
            
        @validator('limit_per_cell')
        def limit_per_cell_must_be_positive(cls, v):
            if v is not None and v <= 0:
                raise ValueError('limit_per_cell must be positive')
            return v

    def __init__(self, **parameters):
        super().__init__(**parameters)
        self.local_cache_directory = self.parameters.local_cache_directory
        os.makedirs(self.local_cache_directory, exist_ok=True)
        self.cache_file = self.parameters.cache_file
        
        # Initialize client and resolve IDs
        self.client = create_client()
        self.account_id = resolve_account_id_for_command(self.client, None)
        
        # Normalize filter values for case-insensitive comparison
        self.normalized_initial_value = self._normalize_value(self.parameters.initial_value)
        self.normalized_final_value = self._normalize_value(self.parameters.final_value)
        
        # Load identifier extractor if specified
        self.identifier_extractor = None
        if self.parameters.identifier_extractor:
            self.identifier_extractor = self._load_identifier_extractor(self.parameters.identifier_extractor)
        
        if self.parameters.feedback_id:
            logger.info(f"Initializing [magenta1][b]FeedbackItems[/b][/magenta1] for specific feedback_id='{self.parameters.feedback_id}' in scorecard='{self.parameters.scorecard}', score='{self.parameters.score}'")
        else:
            days_str = f"days={self.parameters.days}" if self.parameters.days is not None else "all time"
            logger.info(f"Initializing [magenta1][b]FeedbackItems[/b][/magenta1] for scorecard='{self.parameters.scorecard}', score='{self.parameters.score}', {days_str}")

    def _perform_reload(self, cache_identifier: str, scorecard_id: str, score_id: str, 
                        scorecard_name: str, score_name: str) -> pd.DataFrame:
        """
        Perform a reload operation by fetching current values for existing cached records.
        
        This method:
        1. Loads the existing cached dataframe
        2. Extracts the feedback_item_ids from the cache
        3. Fetches ONLY those specific feedback items from the API (with current values)
        4. Updates the values in the cached dataframe
        5. Preserves all IDs and the exact same set of records
        
        Args:
            cache_identifier: Cache file identifier
            scorecard_id: ID of the scorecard
            score_id: ID of the score
            scorecard_name: Name of the scorecard
            score_name: Name of the score
            
        Returns:
            Updated DataFrame with refreshed values for existing records only
        """
        # Load existing data
        existing_df = self._load_from_cache(cache_identifier)
        logger.info(f"Loaded {len(existing_df)} existing rows from cache for reload")
        
        # Extract feedback_item_ids from existing data
        if 'feedback_item_id' not in existing_df.columns:
            logger.error("Cannot perform reload: 'feedback_item_id' column not found in cached data")
            return existing_df
        
        feedback_item_ids = existing_df['feedback_item_id'].tolist()
        logger.info(f"Will fetch updates for {len(feedback_item_ids)} feedback items")
        
        # Fetch only the specific feedback items by their IDs
        logger.info(f"Fetching current values for existing feedback items...")
        try:
            # Try to get the current event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're in a running loop, create a task
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        lambda: asyncio.run(self._fetch_specific_feedback_items(feedback_item_ids))
                    )
                    feedback_items = future.result()
            else:
                # If no running loop, use asyncio.run
                feedback_items = asyncio.run(self._fetch_specific_feedback_items(feedback_item_ids))
        except RuntimeError:
            # Fallback: create new event loop
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                feedback_items = new_loop.run_until_complete(
                    self._fetch_specific_feedback_items(feedback_item_ids)
                )
            finally:
                new_loop.close()
        
        if not feedback_items:
            logger.warning("Could not fetch feedback items for reload, returning existing data")
            return existing_df
        
        logger.info(f"Fetched {len(feedback_items)} feedback items for reload")
        
        # Create a mapping of feedback_item_id to FeedbackItem for efficient lookup
        feedback_items_map = {item.id: item for item in feedback_items}
        
        # Update the dataframe with new values
        updated_count = 0
        for idx, row in existing_df.iterrows():
            feedback_item_id = row['feedback_item_id']
            
            if feedback_item_id in feedback_items_map:
                feedback_item = feedback_items_map[feedback_item_id]
                
                # Update the answer values and comments
                existing_df.at[idx, score_name] = feedback_item.finalAnswerValue
                
                # Update the comment using the same logic as in _determine_score_comment
                score_comment = self._determine_score_comment(feedback_item)
                existing_df.at[idx, f"{score_name} comment"] = score_comment
                
                # Update edit comment
                edit_comment = getattr(feedback_item, 'editCommentValue', None) or ""
                existing_df.at[idx, f"{score_name} edit comment"] = edit_comment
                
                # Update metadata with latest values
                metadata = self._create_metadata_structure(feedback_item)
                existing_df.at[idx, 'metadata'] = metadata
                
                updated_count += 1
            else:
                logger.warning(f"Feedback item {feedback_item_id} not found in API response, keeping existing values")
        
        logger.info(f"Updated {updated_count} out of {len(existing_df)} records")
        
        # Save the updated cache
        self._save_to_cache(existing_df, cache_identifier)
        
        return existing_df
    
    def _normalize_value(self, value: Optional[str]) -> Optional[str]:
        """
        Normalize a value for case-insensitive comparison.
        
        Args:
            value: The value to normalize
            
        Returns:
            Normalized value (lowercase, stripped) or None
        """
        if value is None:
            return None
        return str(value).lower().strip()
    
    def _normalize_item_value(self, value: Optional[str]) -> Optional[str]:
        """
        Normalize an item value for case-insensitive comparison.
        This method is provided for consistency with the test expectations.
        
        Args:
            value: The value to normalize
            
        Returns:
            Normalized value (lowercase, stripped) or None
        """
        return self._normalize_value(value)

    def _load_identifier_extractor(self, extractor_class_name: str):
        """
        Load the identifier extractor class following Plexus extension loading pattern.
        
        Args:
            extractor_class_name: Name of the extractor class (e.g., 'CallCriteriaIdentifierExtractor')
            
        Returns:
            Instance of the identifier extractor class, or None if loading fails
        """
        import importlib
        
        try:
            # Try to load from plexus_extensions module (same pattern as CallCriteriaDBCache)
            module_path = f"plexus_extensions.{extractor_class_name}"
            module = importlib.import_module(module_path)
            extractor_class = getattr(module, extractor_class_name)
            
            # Initialize the extractor with basic parameters
            # The extractor should handle its own database connections and config
            extractor = extractor_class()
            
            logger.info(f"Successfully loaded identifier extractor: {extractor_class_name}")
            return extractor
            
        except Exception as e:
            logger.warning(f"Failed to load identifier extractor '{extractor_class_name}': {e}")
            return None

    def _resolve_identifiers(self) -> Tuple[str, str, str, str]:
        """
        Resolve scorecard and score identifiers to their IDs and names.
        
        Returns:
            Tuple of (scorecard_id, scorecard_name, score_id, score_name)
        """
        # Resolve scorecard
        scorecard_id = resolve_scorecard_identifier(self.client, str(self.parameters.scorecard))
        if not scorecard_id:
            raise ValueError(f"Could not resolve scorecard identifier: {self.parameters.scorecard}")
        
        # Get scorecard name for display
        try:
            query = f"""
            query GetScorecard {{
                getScorecard(id: "{scorecard_id}") {{
                    id
                    name
                }}
            }}
            """
            result = self.client.execute(query)
            scorecard_name = result.get('getScorecard', {}).get('name', self.parameters.scorecard)
        except Exception:
            scorecard_name = self.parameters.scorecard
        
        # Resolve score within the scorecard
        score_id = resolve_score_identifier(self.client, scorecard_id, str(self.parameters.score))
        if not score_id:
            raise ValueError(f"Could not resolve score identifier '{self.parameters.score}' within scorecard '{scorecard_id}'")
        
        # Get score name for display
        try:
            query = f"""
            query GetScore {{
                getScore(id: "{score_id}") {{
                    id
                    name
                }}
            }}
            """
            result = self.client.execute(query)
            score_name = result.get('getScore', {}).get('name', self.parameters.score)
        except Exception:
            score_name = self.parameters.score
        
        return scorecard_id, scorecard_name, score_id, score_name

    def _generate_cache_identifier(self, scorecard_id: str, score_id: str) -> str:
        """Generate a unique cache identifier for the given parameters."""
        params = {
            'scorecard_id': scorecard_id,
            'score_id': score_id,
            'days': self.parameters.days,
            'limit': self.parameters.limit,
            'limit_per_cell': self.parameters.limit_per_cell,
            'initial_value': self.normalized_initial_value,
            'final_value': self.normalized_final_value,
            'feedback_id': self.parameters.feedback_id,
            'backfill_cells': self.parameters.backfill_cells
        }
        params_str = json.dumps(params, sort_keys=True)
        params_hash = hashlib.md5(params_str.encode()).hexdigest()[:8]

        # If a specific feedback_id is provided, include it in the identifier
        if self.parameters.feedback_id:
            return f"feedback_items_{scorecard_id}_{score_id}_single_{self.parameters.feedback_id[:8]}_{params_hash}"
        else:
            return f"feedback_items_{scorecard_id}_{score_id}_{self.parameters.days}d_{params_hash}"

    def _get_cache_file_path(self, identifier: str) -> str:
        """Get the full path to the cache file."""
        cache_dir = os.path.join(self.local_cache_directory, 'dataframes')
        os.makedirs(cache_dir, exist_ok=True)
        cache_filename = f"{identifier}.parquet"
        return os.path.join(cache_dir, cache_filename)

    def _cache_exists(self, identifier: str) -> bool:
        """Check if cache file exists."""
        cache_file = self._get_cache_file_path(identifier)
        return os.path.exists(cache_file)

    def _save_to_cache(self, df: pd.DataFrame, identifier: str):
        """Save dataframe to cache."""
        cache_file = self._get_cache_file_path(identifier)
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        df.to_parquet(cache_file, index=False)
        logger.info(f"Saved {len(df)} rows to cache: {cache_file}")

    def _load_from_cache(self, identifier: str) -> pd.DataFrame:
        """Load dataframe from cache."""
        cache_file = self._get_cache_file_path(identifier)
        df = pd.read_parquet(cache_file)
        logger.info(f"Loaded {len(df)} rows from cache: {cache_file}")
        return df

    def load_dataframe(self, *, data=None, fresh=False, reload=False) -> pd.DataFrame:
        """
        Load a dataframe of feedback items sampled from confusion matrix cells.
        
        Args:
            data: Not used - parameters come from class initialization
            fresh: If True, bypass cache and fetch fresh data (generates new parquet)
            reload: If True, reload existing cache with current values, preserving form IDs
            
        Returns:
            DataFrame with sampled feedback items
        """
        # Resolve identifiers
        scorecard_id, scorecard_name, score_id, score_name = self._resolve_identifiers()
        
        # Generate cache identifier
        cache_identifier = self._generate_cache_identifier(scorecard_id, score_id)
        
        # Handle reload mode - reload existing cache with current values
        if reload:
            logger.error(f"🔍 RELOAD DEBUG: reload=True, checking cache existence")
            if not self._cache_exists(cache_identifier):
                logger.error(f"🔍 RELOAD DEBUG: No existing cache found, falling through to fresh load")
                logger.warning("No existing cache found for reload mode. Performing fresh load instead.")
                # Fall through to fresh load
            else:
                logger.error(f"🔍 RELOAD DEBUG: Cache exists, calling _perform_reload")
                logger.info(f"Reload mode: Loading existing cache and fetching current data for {scorecard_name} / {score_name}")
                return self._perform_reload(cache_identifier, scorecard_id, score_id, scorecard_name, score_name)
        
        # For dataset generation, we should always generate fresh data
        # The cache is only used for internal optimization during the same run
        # TODO: Remove caching entirely for dataset generation commands  
        if not fresh and not reload and self._cache_exists(cache_identifier):
            return self._load_from_cache(cache_identifier)
        
        days_str = f"last {self.parameters.days} days" if self.parameters.days is not None else "all time"
        logger.error(f"🔍 FRESH LOAD DEBUG: Fetching fresh feedback data for {scorecard_name} / {score_name} ({days_str})")
        logger.info(f"Fetching fresh feedback data for {scorecard_name} / {score_name} ({days_str})")
        
        # Fetch feedback items
        try:
            # Try to get the current event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're in a running loop, create a task
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        lambda: asyncio.run(self._fetch_feedback_items_for_scores(scorecard_id, [(score_id, score_name)]))
                    )
                    result = future.result()
                    feedback_items = result.get(score_id, [])
            else:
                # If no running loop, use asyncio.run
                result = asyncio.run(self._fetch_feedback_items_for_scores(
                    scorecard_id, [(score_id, score_name)]
                ))
                feedback_items = result.get(score_id, [])
        except RuntimeError:
            # Fallback: create new event loop
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                result = new_loop.run_until_complete(self._fetch_feedback_items_for_scores(
                    scorecard_id, [(score_id, score_name)]
                ))
                feedback_items = result.get(score_id, [])
            finally:
                new_loop.close()
        
        if not feedback_items:
            logger.warning("No feedback items found")
            return pd.DataFrame()
        
        logger.info(f"Found {len(feedback_items)} feedback items")

        # If a specific feedback_id was provided, skip sampling and use the single item
        if self.parameters.feedback_id:
            sampled_items = feedback_items
            logger.info(f"Using single feedback item {self.parameters.feedback_id} without sampling")
        else:
            # Build confusion matrix
            matrix_cells = self._build_confusion_matrix(feedback_items)

            # Backfill cells if enabled
            if self.parameters.backfill_cells:
                logger.info("Backfill enabled: filling sparse cells with older data")
                matrix_cells = self._backfill_matrix_cells(matrix_cells, scorecard_id, score_id)

            # Flatten matrix back to list for sampling
            all_items = []
            for cell_items in matrix_cells.values():
                all_items.extend(cell_items)

            logger.info(f"After backfill: {len(all_items)} total items")

            # Sample from confusion matrix
            sampled_items = self._sample_items_from_confusion_matrix(all_items)

            if not sampled_items:
                logger.warning("No items after sampling")
                return pd.DataFrame()

            logger.info(f"Sampled {len(sampled_items)} items from confusion matrix")
        
        # Create dataset rows
        df = self._create_dataset_rows(sampled_items, score_name)
        
        # Save to cache
        self._save_to_cache(df, cache_identifier)
        
        return df

    async def _fetch_specific_feedback_items(self, feedback_item_ids: List[str]) -> List[FeedbackItem]:
        """
        Fetch specific feedback items by their IDs.
        
        Args:
            feedback_item_ids: List of feedback item IDs to fetch
            
        Returns:
            List of FeedbackItem objects
        """
        if not feedback_item_ids:
            return []
        
        all_items = []
        errors = 0
        
        # Fetch each feedback item individually using getFeedbackItem
        for idx, feedback_item_id in enumerate(feedback_item_ids, 1):
            try:
                # Query for a specific feedback item by ID
                query = """
                query GetFeedbackItem($id: ID!) {
                    getFeedbackItem(id: $id) {
                        id
                        accountId
                        scorecardId
                        scoreId
                        itemId
                        cacheKey
                        initialAnswerValue
                        initialCommentValue
                        finalAnswerValue
                        finalCommentValue
                        editCommentValue
                        isAgreement
                        editedAt
                        editorName
                        createdAt
                        updatedAt
                        item {
                            id
                            externalId
                            text
                            metadata
                            identifiers
                            createdAt
                            updatedAt
                        }
                    }
                }
                """
                
                result = self.client.execute(query, {"id": feedback_item_id})
                
                # DEBUG: Log the raw GraphQL response - using ERROR level to ensure visibility
                logger.error(f"🔍 GRAPHQL DEBUG: Processing feedback_item_id={feedback_item_id}")
                logger.error(f"🔍 GRAPHQL DEBUG: Raw result keys: {list(result.keys()) if result else 'None'}")
                if result and 'getFeedbackItem' in result and result['getFeedbackItem']:
                    feedback_data = result['getFeedbackItem']
                    logger.error(f"🔍 GRAPHQL DEBUG: FeedbackItem keys: {list(feedback_data.keys())}")
                    if 'item' in feedback_data and feedback_data['item']:
                        item_raw_data = feedback_data['item']
                        logger.error(f"🔍 GRAPHQL DEBUG: Item raw data keys: {list(item_raw_data.keys())}")
                        logger.error(f"🔍 GRAPHQL DEBUG: Item metadata from GraphQL: {item_raw_data.get('metadata')}")
                        logger.error(f"🔍 GRAPHQL DEBUG: Item metadata type: {type(item_raw_data.get('metadata'))}")
                    else:
                        logger.error(f"🔍 GRAPHQL DEBUG: No item data in feedback response")
                else:
                    logger.error(f"🔍 GRAPHQL DEBUG: No feedback item data in GraphQL response")
                
                if result and 'getFeedbackItem' in result and result['getFeedbackItem']:
                    item_data = result['getFeedbackItem']
                    feedback_item = FeedbackItem.from_dict(item_data, self.client)
                    all_items.append(feedback_item)
                    
                    # Log progress every 10 items
                    if idx % 10 == 0:
                        logger.info(f"Fetched {idx}/{len(feedback_item_ids)} feedback items")
                else:
                    logger.warning(f"Feedback item {feedback_item_id} not found in API")
                    errors += 1
                
            except Exception as e:
                logger.error(f"Error fetching feedback item {feedback_item_id}: {e}")
                errors += 1
                # Continue with other items even if one fails
        
        logger.info(f"Fetched {len(all_items)} out of {len(feedback_item_ids)} feedback items ({errors} errors)")
        return all_items

    async def _fetch_score_results_for_items(
        self, 
        item_ids: List[str], 
        resolved_scores: List[Tuple[str, str]]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Fetch the most recent ScoreResult for each item/score combination as fallback.
        
        Args:
            item_ids: List of item IDs to fetch ScoreResults for
            resolved_scores: List of (score_id, score_name) tuples
            
        Returns:
            Dict mapping item_id -> score_id -> ScoreResult data
            Example: {
                "item-123": {
                    "score-456": {"value": "yes", "explanation": "...", "confidence": 0.95, ...},
                    "score-789": {"value": "no", "explanation": "...", "confidence": 0.88, ...}
                }
            }
        """
        logger.info(f"Fetching ScoreResults for {len(item_ids)} items across {len(resolved_scores)} scores")
        score_results_map = {}
        
        for item_id in item_ids:
            score_results_map[item_id] = {}
            
            for score_id, score_name in resolved_scores:
                try:
                    # Query for the most recent ScoreResult for this item/score combination
                    # Filter out evaluation-type results (we only want production ScoreResults)
                    query = """
                    query ListScoreResultsByItemAndScore(
                        $itemId: String!
                        $scoreId: String!
                    ) {
                        listScoreResults(
                            filter: {
                                itemId: { eq: $itemId }
                                scoreId: { eq: $scoreId }
                                type: { ne: "evaluation" }
                            }
                            limit: 1
                        ) {
                            items {
                                id
                                itemId
                                scoreId
                                value
                                explanation
                                confidence
                                metadata
                                updatedAt
                                createdAt
                            }
                        }
                    }
                    """
                    
                    result = self.client.execute(query, {
                        "itemId": item_id,
                        "scoreId": score_id
                    })
                    
                    if result and result.get('listScoreResults', {}).get('items'):
                        score_result = result['listScoreResults']['items'][0]
                        score_results_map[item_id][score_id] = score_result
                        logger.debug(f"Found ScoreResult for item {item_id}, score {score_name}: {score_result.get('value')}")
                    else:
                        logger.debug(f"No ScoreResult found for item {item_id}, score {score_name}")
                
                except Exception as e:
                    logger.warning(f"Error fetching ScoreResult for item {item_id}, score {score_name}: {e}")
                    # Continue with other items/scores even if one fails
        
        # Count how many items have at least one ScoreResult
        items_with_results = sum(1 for item_results in score_results_map.values() if item_results)
        logger.info(f"Found ScoreResults for {items_with_results}/{len(item_ids)} items")
        
        return score_results_map
    
    async def _fetch_feedback_items_for_scores(
        self, 
        scorecard_id: str, 
        resolved_scores: List[Tuple[str, str]]
    ) -> Dict[str, List[FeedbackItem]]:
        """
        Fetch feedback items for multiple scores.
        
        Args:
            scorecard_id: ID of the scorecard
            resolved_scores: List of (score_id, score_name) tuples
            
        Returns:
            Dict mapping score_id -> List[FeedbackItem]
        """
        feedback_by_score = {}
        
        # Process each score
        for score_id, score_name in resolved_scores:
            # If a specific feedback_id is provided, fetch only that item
            if self.parameters.feedback_id:
                logger.info(f"Fetching specific feedback item: {self.parameters.feedback_id}")
                specific_items = await self._fetch_specific_feedback_items([self.parameters.feedback_id])
                
                if not specific_items:
                    logger.warning(f"Feedback item {self.parameters.feedback_id} not found")
                    feedback_by_score[score_id] = []
                    continue
                
                # Validate that the item belongs to the correct scorecard and score
                item = specific_items[0]
                if item.scorecardId != scorecard_id or item.scoreId != score_id:
                    logger.error(f"Feedback item {self.parameters.feedback_id} belongs to scorecard {item.scorecardId}/score {item.scoreId}, "
                               f"but expected scorecard {scorecard_id}/score {score_id}")
                    feedback_by_score[score_id] = []
                    continue
                
                logger.info(f"Successfully fetched specific feedback item {self.parameters.feedback_id}")
                feedback_by_score[score_id] = specific_items
                continue
            
            # Otherwise, fetch items using the normal FeedbackService approach
            logger.error(f"🔍 FEEDBACK SERVICE DEBUG: About to call FeedbackService.find_feedback_items for score {score_name}")
            all_items = await FeedbackService.find_feedback_items(
                client=self.client,
                scorecard_id=scorecard_id,
                score_id=score_id,
                account_id=self.account_id,
                days=self.parameters.days,
                initial_value=None,  # Don't filter at service level
                final_value=None,    # Don't filter at service level
                limit=None,  # We'll apply limits after sampling
                prioritize_edit_comments=False
            )
            logger.error(f"🔍 FEEDBACK SERVICE DEBUG: Received {len(all_items)} items from FeedbackService for score {score_name}")
            
            # Debug the first item to see what metadata structure we get
            if all_items:
                first_item = all_items[0]
                logger.error(f"🔍 FEEDBACK SERVICE DEBUG: First item ID: {first_item.id}")
                logger.error(f"🔍 FEEDBACK SERVICE DEBUG: First item has .item: {hasattr(first_item, 'item')}")
                if hasattr(first_item, 'item') and first_item.item:
                    logger.error(f"🔍 FEEDBACK SERVICE DEBUG: First item.item.id: {first_item.item.id}")
                    logger.error(f"🔍 FEEDBACK SERVICE DEBUG: First item.item.metadata: {getattr(first_item.item, 'metadata', 'NOT_FOUND')}")
                else:
                    logger.error(f"🔍 FEEDBACK SERVICE DEBUG: First item has no .item or .item is None")
            
            # Apply case-insensitive filtering locally if needed
            if self.parameters.initial_value or self.parameters.final_value:
                filtered_items = []
                for item in all_items:
                    matches = True
                    
                    # Case-insensitive initial_value filtering
                    if self.parameters.initial_value:
                        item_initial = self._normalize_item_value(item.initialAnswerValue)
                        if item_initial != self.normalized_initial_value:
                            matches = False
                    
                    # Case-insensitive final_value filtering  
                    if self.parameters.final_value:
                        item_final = self._normalize_item_value(item.finalAnswerValue)
                        if item_final != self.normalized_final_value:
                            matches = False
                    
                    if matches:
                        filtered_items.append(item)
                
                logger.info(f"After case-insensitive filtering: {len(filtered_items)} items (from {len(all_items)} total)")
                feedback_by_score[score_id] = filtered_items
            else:
                feedback_by_score[score_id] = all_items
        
        return feedback_by_score

    def _build_confusion_matrix(self, feedback_items: List[FeedbackItem]) -> Dict[Tuple[str, str], List[FeedbackItem]]:
        """
        Build confusion matrix by grouping items into cells based on (initial_value, final_value) pairs.

        Args:
            feedback_items: List of feedback items to group

        Returns:
            Dict mapping (initial_value, final_value) -> List[FeedbackItem]
        """
        matrix_cells = defaultdict(list)

        for item in feedback_items:
            if item.initialAnswerValue is not None and item.finalAnswerValue is not None:
                cell_key = (str(item.initialAnswerValue), str(item.finalAnswerValue))
                matrix_cells[cell_key].append(item)

        logger.info(f"Built confusion matrix with {len(matrix_cells)} cells")
        for cell_key, cell_items in matrix_cells.items():
            logger.info(f"  Cell {cell_key}: {len(cell_items)} items")

        return dict(matrix_cells)

    async def _fetch_backfill_items_for_cell(
        self,
        scorecard_id: str,
        score_id: str,
        initial_value: str,
        final_value: str,
        before_date: datetime,
        limit: int,
        existing_ids: set
    ) -> List[FeedbackItem]:
        """
        Fetch additional feedback items for a specific confusion matrix cell from before a given date.

        Args:
            scorecard_id: ID of the scorecard
            score_id: ID of the score
            initial_value: Initial answer value to filter by
            final_value: Final answer value to filter by
            before_date: Only fetch items edited before this date
            limit: Maximum number of items to fetch
            existing_ids: Set of feedback item IDs already in the dataset (to avoid duplicates)

        Returns:
            List of FeedbackItem objects for backfilling
        """
        logger.info(f"Backfilling cell ({initial_value}→{final_value}): fetching up to {limit} items before {before_date.isoformat()}")

        # Use FeedbackService to find items with a very large lookback window
        # We use days=3650 (10 years) instead of None to ensure we use the efficient GSI query
        # which properly paginates and retrieves all items
        all_items = await FeedbackService.find_feedback_items(
            client=self.client,
            scorecard_id=scorecard_id,
            score_id=score_id,
            account_id=self.account_id,
            days=3650,  # 10 years - effectively "all time" using the efficient GSI query
            initial_value=None,
            final_value=None,
            limit=None,
            prioritize_edit_comments=False
        )

        # Filter items manually
        backfill_items = []
        for item in all_items:
            # Skip if already in existing dataset
            if item.id in existing_ids:
                continue

            # Filter by initial and final values (case-insensitive)
            if self._normalize_item_value(item.initialAnswerValue) != self._normalize_value(initial_value):
                continue
            if self._normalize_item_value(item.finalAnswerValue) != self._normalize_value(final_value):
                continue

            # Filter by date
            item_date = item.editedAt or item.createdAt
            if item_date and item_date < before_date:
                backfill_items.append(item)

        # Sort by date descending (most recent first) and take up to limit
        backfill_items.sort(key=lambda x: x.editedAt or x.createdAt, reverse=True)
        backfill_items = backfill_items[:limit]

        logger.info(f"Found {len(backfill_items)} backfill items for cell ({initial_value}→{final_value})")
        return backfill_items

    def _backfill_matrix_cells(
        self,
        matrix_cells: Dict[Tuple[str, str], List[FeedbackItem]],
        scorecard_id: str,
        score_id: str
    ) -> Dict[Tuple[str, str], List[FeedbackItem]]:
        """
        Backfill confusion matrix cells to limit_per_cell using older data when cells have insufficient items.

        For each cell with fewer than limit_per_cell items, this method fetches additional items
        from before the time window, prioritizing more recent data, until reaching limit_per_cell.

        Args:
            matrix_cells: Dict mapping (initial, final) -> List[FeedbackItem]
            scorecard_id: ID of the scorecard
            score_id: ID of the score

        Returns:
            Updated matrix_cells dict with backfilled items
        """
        if not self.parameters.limit_per_cell:
            logger.info("No limit_per_cell set, skipping backfill")
            return matrix_cells

        # Track all existing feedback item IDs to avoid duplicates
        existing_ids = set()
        for cell_items in matrix_cells.values():
            for item in cell_items:
                existing_ids.add(item.id)

        logger.info(f"Backfilling matrix cells (current total: {len(existing_ids)} items)")

        # Check each cell and backfill if needed
        for cell_key, cell_items in matrix_cells.items():
            initial_value, final_value = cell_key
            current_count = len(cell_items)

            if current_count >= self.parameters.limit_per_cell:
                logger.info(f"Cell {cell_key} already at capacity ({current_count}/{self.parameters.limit_per_cell})")
                continue

            needed = self.parameters.limit_per_cell - current_count
            logger.info(f"Cell {cell_key} needs {needed} more items ({current_count}/{self.parameters.limit_per_cell})")

            # Find the oldest item in this cell to know where to start searching
            if cell_items:
                oldest_date = min(item.editedAt or item.createdAt for item in cell_items)
            else:
                # If somehow we have an empty cell, use current time as boundary
                oldest_date = datetime.now(timezone.utc)

            # Fetch backfill items
            try:
                # Try to get the current event loop
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If we're in a running loop, create a task
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            lambda: asyncio.run(self._fetch_backfill_items_for_cell(
                                scorecard_id, score_id, initial_value, final_value,
                                oldest_date, needed, existing_ids
                            ))
                        )
                        backfill_items = future.result()
                else:
                    # If no running loop, use asyncio.run
                    backfill_items = asyncio.run(self._fetch_backfill_items_for_cell(
                        scorecard_id, score_id, initial_value, final_value,
                        oldest_date, needed, existing_ids
                    ))
            except RuntimeError:
                # Fallback: create new event loop
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    backfill_items = new_loop.run_until_complete(
                        self._fetch_backfill_items_for_cell(
                            scorecard_id, score_id, initial_value, final_value,
                            oldest_date, needed, existing_ids
                        )
                    )
                finally:
                    new_loop.close()

            # Add backfill items to the cell
            if backfill_items:
                matrix_cells[cell_key].extend(backfill_items)
                for item in backfill_items:
                    existing_ids.add(item.id)
                logger.info(f"Added {len(backfill_items)} backfill items to cell {cell_key} (now {len(matrix_cells[cell_key])} total)")

        total_items = sum(len(items) for items in matrix_cells.values())
        logger.info(f"Backfill complete: {total_items} total items across {len(matrix_cells)} cells")

        return matrix_cells

    def _sample_items_from_confusion_matrix(self, feedback_items: List[FeedbackItem]) -> List[FeedbackItem]:
        """
        Sample items from each confusion matrix cell, prioritizing items with edit comments.

        Args:
            feedback_items: All feedback items

        Returns:
            Sampled items respecting limit_per_cell and overall limit
        """
        # Build confusion matrix
        matrix_cells = self._build_confusion_matrix(feedback_items)
        
        # Sample from each cell with priority for edit comments
        sampled_items = []
        for cell_key, cell_items in matrix_cells.items():
            # Determine how many items to sample from this cell
            if self.parameters.limit_per_cell is not None:
                sample_size = min(len(cell_items), self.parameters.limit_per_cell)
            else:
                sample_size = len(cell_items)
            
            # Apply prioritized sampling within the cell
            cell_sample = self._prioritize_items_with_edit_comments(cell_items, sample_size)
            
            sampled_items.extend(cell_sample)
            logger.info(f"  Sampled {len(cell_sample)} items from cell {cell_key}")
        
        # Apply overall limit if specified, with prioritization
        if self.parameters.limit is not None and len(sampled_items) > self.parameters.limit:
            sampled_items = self._prioritize_items_with_edit_comments(sampled_items, self.parameters.limit)
            logger.info(f"Applied overall limit: reduced to {len(sampled_items)} items")
        
        return sampled_items

    def _prioritize_items_with_edit_comments(self, items: List[FeedbackItem], limit: int) -> List[FeedbackItem]:
        """
        Prioritize items with edit comments when applying a limit.
        
        Rules:
        1. If there are fewer items than the limit, take them all
        2. If there are more than the limit, prioritize ones with edit comments
        3. If still more than limit after including all with edit comments, 
           randomly sample from the items with edit comments
        
        Args:
            items: List of FeedbackItem objects
            limit: Maximum number of items to return
            
        Returns:
            List of prioritized and limited feedback items
        """
        # Rule 1: If fewer items than limit, take them all
        if len(items) <= limit:
            return items
        
        # Separate items with and without edit comments
        items_with_comments = [item for item in items if item.editCommentValue]
        items_without_comments = [item for item in items if not item.editCommentValue]
        
        # Rule 2: Prioritize items with edit comments
        if len(items_with_comments) <= limit:
            # We can fit all items with comments, plus some without comments
            result = items_with_comments.copy()
            remaining_slots = limit - len(items_with_comments)
            
            if remaining_slots > 0 and items_without_comments:
                # Randomly sample from items without comments to fill remaining slots
                random.shuffle(items_without_comments)
                result.extend(items_without_comments[:remaining_slots])
            
            return result
        else:
            # Rule 3: More items with comments than limit - randomly sample from them
            random.shuffle(items_with_comments)
            return items_with_comments[:limit]

    def _create_dataset_rows(self, feedback_items: List[FeedbackItem], score_name: str) -> pd.DataFrame:
        """
        Create dataset rows from feedback items in CallCriteriaDBCache format.
        
        Expected columns (EXACTLY these, no extras):
        - content_id: DynamoDB item ID
        - feedback_item_id: Feedback item ID
        - text: Item.text content
        - metadata: JSON string of metadata structure
        - IDs: Hash of identifiers with name/value/URL structure
        - {score_name}: Final answer value (ground truth)
        - {score_name} comment: Final explanation/comment with complex logic
        - {score_name} edit comment: Edit comment from feedback item
        
        Args:
            feedback_items: Sampled feedback items
            score_name: Name of the score for column naming
            
        Returns:
            DataFrame with properly formatted rows matching CallCriteriaDBCache format
        """
        logger.debug(f"FeedbackItems: Creating dataset with {len(feedback_items)} items for score: {score_name}")
        
        # Apply column mapping if specified
        mapped_score_name = score_name
        if self.parameters.column_mappings and score_name in self.parameters.column_mappings:
            mapped_score_name = self.parameters.column_mappings[score_name]
            logger.info(f"Column mapping applied: '{score_name}' -> '{mapped_score_name}'")
        
        # Create properly formatted dataset rows
        rows = []
        
        for i, feedback_item in enumerate(feedback_items):
            # content_id: Use DynamoDB item ID
            content_id = feedback_item.itemId
            
            # feedback_item_id: Use feedback item ID
            feedback_item_id = feedback_item.id
            
            # text: Get the text content from Item.text (the transcript)
            text = ""
            if feedback_item.item:
                # First try the direct text field
                text = feedback_item.item.text
                
                # If text is None, try to reload the item with full data
                if text is None and hasattr(feedback_item.item, 'get_by_id'):
                    try:
                        full_item = feedback_item.item.get_by_id(feedback_item.item.id)
                        if full_item and full_item.text:
                            text = full_item.text
                            print(f"DEBUG: Loaded text from full item: {len(text)} characters")
                        else:
                            print(f"DEBUG: Full item still has no text")
                    except Exception as e:
                        print(f"DEBUG: Error loading full item: {e}")
                
                # Convert None to empty string
                text = text or ""
                
                # Text content retrieved for processing
            
            # metadata: Create JSON string of metadata structure
            metadata = self._create_metadata_structure(feedback_item)
            
            # IDs: Create hash of identifiers from Item
            ids_hash = self._create_ids_hash(feedback_item)
            
            # Score value: Final answer value (ground truth)
            score_value = feedback_item.finalAnswerValue
            
            # Score comment: Complex logic for determining the comment
            score_comment = self._determine_score_comment(feedback_item)
            
            # Edit comment: Direct edit comment from feedback item
            edit_comment = getattr(feedback_item, 'editCommentValue', None) or ""
            
            # Extract call_date from metadata for separate column
            call_date = None
            try:
                metadata_dict = json.loads(metadata) if isinstance(metadata, str) else metadata
                call_date = metadata_dict.get('call_date')
            except:
                pass
            
            # Build the row with ONLY the specified columns (IDs first, then metadata, then text)
            row = {
                'content_id': content_id,
                'feedback_item_id': feedback_item_id,
                'IDs': ids_hash,
                'metadata': metadata,
                'text': text,
                'call_date': call_date,
                mapped_score_name: score_value,
                f"{mapped_score_name} comment": score_comment,
                f"{mapped_score_name} edit comment": edit_comment
            }
            
            rows.append(row)
            
            # Only debug first few items to avoid too much output
            # Processing feedback items for dataset creation
        
        # Create DataFrame with proper column structure even when empty
        if not rows:
            # Create empty DataFrame with expected columns (IDs first, then metadata, then text)
            columns = ['content_id', 'feedback_item_id', 'IDs', 'metadata', 'text', 'call_date', mapped_score_name, f"{mapped_score_name} comment", f"{mapped_score_name} edit comment"]
            df = pd.DataFrame(columns=columns)
        else:
            df = pd.DataFrame(rows)
            
        logger.info(f"Created dataset with {len(df)} rows and {len(df.columns)} columns: {list(df.columns)}")
        logger.debug(f"Sample row data: {rows[0] if rows else 'No rows'}")
        
        # Use the comprehensive debug utility from base class
        self.debug_dataframe(df, "FEEDBACK_ITEMS_DATASET", logger)
        
        # Additional FeedbackItems-specific debugging
        logger.info("FEEDBACK_ITEMS_SPECIFIC_CHECKS:")
        
        # Check for missing required columns specific to FeedbackItems format
        required_columns = ['content_id', 'feedback_item_id', 'text', 'metadata', 'IDs', mapped_score_name, f"{mapped_score_name} comment", f"{mapped_score_name} edit comment"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            logger.error(f"Missing required FeedbackItems columns: {missing_columns}")
        else:
            logger.info("All required FeedbackItems columns present")
        
        # Special debugging for IDs column structure
        if 'IDs' in df.columns and len(df) > 0:
            logger.info("FEEDBACK_ITEMS_IDS_DEBUG: Analyzing IDs column structure...")
            sample_ids = df.iloc[0]['IDs']
            logger.info(f"Sample IDs value type: {type(sample_ids)}")
            logger.info(f"Sample IDs value: {sample_ids}")
            try:
                if isinstance(sample_ids, str):
                    ids_parsed = json.loads(sample_ids)
                    logger.info(f"Successfully parsed {len(ids_parsed)} identifiers")
                    for idx, identifier in enumerate(ids_parsed):
                        logger.info(f"Identifier {idx}: {identifier}")
                else:
                    logger.warning(f"IDs is not a JSON string, type: {type(sample_ids)}")
            except Exception as e:
                logger.warning(f"Could not parse IDs JSON: {e}")
        
        return df
    
    def _create_metadata_structure(self, feedback_item: FeedbackItem) -> str:
        """
        Create metadata JSON string from feedback item and associated item.

        Args:
            feedback_item: The feedback item with associated item data

        Returns:
            JSON string containing relevant metadata
        """
        import json  # Move import to top of function
        from datetime import datetime

        # Helper function to convert datetime to ISO string
        def serialize_datetime(value):
            if isinstance(value, datetime):
                return value.isoformat()
            return value

        metadata = {
            'feedback_item_id': feedback_item.id,
            'scorecard_id': feedback_item.scorecardId,
            'score_id': feedback_item.scoreId,
            'account_id': feedback_item.accountId,
            'created_at': serialize_datetime(feedback_item.createdAt),
            'updated_at': serialize_datetime(feedback_item.updatedAt),
            'edited_at': serialize_datetime(feedback_item.editedAt),
            'editor_name': feedback_item.editorName,
            'is_agreement': feedback_item.isAgreement,
            'cache_key': feedback_item.cacheKey,
            'initial_answer_value': feedback_item.initialAnswerValue,
            'initial_comment_value': feedback_item.initialCommentValue
        }

        # Add item metadata if available - use the cached metadata directly from API
        if feedback_item.item:
            logger.info(f"Adding item metadata for feedback_item_id={feedback_item.id}, item_id={feedback_item.item.id}")
            item_metadata = {
                'item_id': feedback_item.item.id,
                'external_id': getattr(feedback_item.item, 'externalId', None),
                'item_created_at': serialize_datetime(getattr(feedback_item.item, 'createdAt', None)),
                'item_updated_at': serialize_datetime(getattr(feedback_item.item, 'updatedAt', None)),
                'item_metadata': getattr(feedback_item.item, 'metadata', None)
            }
            metadata['item'] = item_metadata
            logger.info(f"Item metadata added: {item_metadata}")
            
            # Use the Item's cached metadata directly (it should already have the API structure)
            original_item_metadata = getattr(feedback_item.item, 'metadata', None)
            logger.info(f"DEBUG: Checking item metadata for item_id={feedback_item.item.id}")
            logger.info(f"DEBUG: feedback_item.item type: {type(feedback_item.item)}")
            logger.info(f"DEBUG: feedback_item.item attributes: {dir(feedback_item.item)}")
            logger.info(f"DEBUG: original_item_metadata: {original_item_metadata}")
            logger.info(f"DEBUG: original_item_metadata type: {type(original_item_metadata)}")
            if original_item_metadata:
                logger.info(f"Found original item metadata for item_id={feedback_item.item.id}: type={type(original_item_metadata)}")
                try:
                    # Parse the original item metadata if it's a JSON string
                    if isinstance(original_item_metadata, str):
                        parsed_metadata = json.loads(original_item_metadata)
                        logger.info(f"Parsed item metadata from JSON string for item_id={feedback_item.item.id}")
                    else:
                        parsed_metadata = original_item_metadata
                        logger.info(f"Using item metadata as object for item_id={feedback_item.item.id}")
                    
                    # Merge the API-cached metadata directly (should already have other_data, etc.)
                    if isinstance(parsed_metadata, dict):
                        metadata.update(parsed_metadata)
                        logger.info(f"Merged {len(parsed_metadata)} fields from cached item metadata for item_id={feedback_item.item.id}")
                    else:
                        logger.info(f"Parsed item metadata is not a dict for item_id={feedback_item.item.id}, type={type(parsed_metadata)}")
                except Exception as e:
                    logger.warning(f"Could not parse cached item metadata for item_id={feedback_item.item.id}: {e}")
                    # Continue without the cached metadata
        
        # Parse other_data if it's a JSON string (fix the root cause)
        if 'other_data' in metadata and isinstance(metadata['other_data'], str):
            try:
                metadata['other_data'] = json.loads(metadata['other_data'])
                logger.info(f"Parsed other_data from JSON string to dict for item_id={feedback_item.item.id}")
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Could not parse other_data JSON string for item_id={feedback_item.item.id}: {e}")
                # Keep as string if parsing fails

        # Check for non-serializable objects before attempting JSON serialization
        try:
            return json.dumps(metadata)
        except TypeError as e:
            # Log which key has the problematic value
            logger.error(f"Failed to serialize metadata to JSON: {e}")
            for key, value in metadata.items():
                logger.error(f"  metadata['{key}'] = {value} (type: {type(value)})")
            raise
    
    def _create_ids_hash(self, feedback_item: FeedbackItem) -> str:
        """
        Create IDs hash from Item identifiers, using identifier extractor if available.
        
        Expected format: List of objects with name, value, and optional URL.
        
        Args:
            feedback_item: The feedback item with associated item data
            
        Returns:
            JSON string containing identifier hash
        """
        ids = []
        
        if not feedback_item.item:
            return json.dumps(ids)
        
        item = feedback_item.item
        
        # Use identifier extractor if available to get client-specific identifiers
        if self.identifier_extractor:
            try:
                client_identifiers = self.identifier_extractor.extract_identifiers(feedback_item)
                if client_identifiers:
                    ids.extend(client_identifiers)
                    logger.info(f"IDENTIFIERS_DEBUG: Added {len(client_identifiers)} client identifiers to IDs: {client_identifiers}")
                    
                    # Convert to the format expected by Item.upsert_by_identifiers
                    identifiers_dict = {}
                    for identifier in client_identifiers:
                        if isinstance(identifier, dict) and 'name' in identifier and 'value' in identifier:
                            name = str(identifier['name']).lower().replace(' ', '_')
                            identifiers_dict[name] = str(identifier['value'])
                    
                    # Upsert the Item with extracted identifiers to ensure it has proper Identifier records
                    if identifiers_dict:
                        logger.info(f"IDENTIFIERS_DEBUG: Upserting Item {item.id} with identifiers: {identifiers_dict}")
                        try:
                            # Create a dashboard client for Item operations
                            dashboard_client = create_client()
                            # Get the resolved score ID for associating Items with scores
                            _, _, score_id, _ = self._resolve_identifiers()
                            # Use the centralized Item upsert method from base DataCache class
                            item_id, was_created, error_msg = self.upsert_item_for_dataset_row(
                                dashboard_client=dashboard_client,
                                account_id=feedback_item.accountId,
                                item_data=item,
                                identifiers_dict=identifiers_dict,
                                external_id=item.externalId or item.id,
                                score_id=score_id  # Associate Item with the score being evaluated
                            )
                            if error_msg:
                                logger.warning(f"IDENTIFIERS_DEBUG: Error upserting Item with identifiers: {error_msg}")
                            else:
                                logger.info(f"IDENTIFIERS_DEBUG: Successfully upserted Item {item_id} (was_created: {was_created})")
                        except Exception as upsert_error:
                            logger.warning(f"IDENTIFIERS_DEBUG: Failed to upsert Item with identifiers: {upsert_error}")
                else:
                    logger.info(f"IDENTIFIERS_DEBUG: No client identifiers returned from extractor")
            except Exception as e:
                logger.warning(f"IDENTIFIERS_DEBUG: Failed to extract client identifiers: {e}")
        
        # Add external ID if available (fallback/additional identifier)
        external_id = getattr(item, 'externalId', None)
        if external_id:
            ids.append({
                'name': 'External ID',
                'value': external_id,
                'url': None
            })
        
        # Process legacy JSON identifiers field (fallback for backward compatibility)
        identifiers_json = getattr(item, 'identifiers', None)
        if identifiers_json:
            try:
                if isinstance(identifiers_json, str):
                    identifiers_data = json.loads(identifiers_json)
                else:
                    identifiers_data = identifiers_json
                
                if isinstance(identifiers_data, list):
                    for identifier in identifiers_data:
                        if isinstance(identifier, dict):
                            # Handle legacy format where 'id' is used instead of 'value'
                            value = identifier.get('value') or identifier.get('id')
                            if value:
                                ids.append({
                                    'name': identifier.get('name', 'Identifier'),
                                    'value': str(value),
                                    'url': identifier.get('url')
                                })
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Error parsing identifiers JSON: {e}")
        
        # Add item ID as fallback identifier
        ids.append({
            'name': 'Item ID',
            'value': item.id,
            'url': None
        })
        
        return json.dumps(ids)
    
    def _determine_score_comment(self, feedback_item: FeedbackItem) -> str:
        """
        Determine the score comment using complex logic.
        
        Logic:
        1. If edit comment is 'agree' and there's no new final comment, use original comment
        2. If final comment/explanation is 'agree', use original comment  
        3. Otherwise, favor edit comment over final comment/explanation
        4. Fallback to original comment if nothing else available
        
        Args:
            feedback_item: The feedback item
            
        Returns:
            The determined comment string
        """
        # Get comment values - prioritize the "Value" fields which are the primary ones
        edit_comment = getattr(feedback_item, 'editCommentValue', None) or ""
        final_comment = getattr(feedback_item, 'finalCommentValue', None) or ""
        initial_comment = getattr(feedback_item, 'initialCommentValue', None) or ""
        
        # Debug logging to see what we're working with
        logger.debug(f"Comment values - edit: '{edit_comment}', final: '{final_comment}', initial: '{initial_comment}'")
        
        # Normalize agreement text (case insensitive)
        edit_comment_lower = str(edit_comment).lower().strip()
        final_comment_lower = str(final_comment).lower().strip()
        
        # Case 1: Edit comment is 'agree' and no new final comment
        if edit_comment_lower == 'agree' and not final_comment:
            logger.debug(f"Using initial comment (edit=agree, no final): '{initial_comment}'")
            return initial_comment
        
        # Case 2: Final comment is 'agree'
        if final_comment_lower == 'agree':
            logger.debug(f"Using initial comment (final=agree): '{initial_comment}'")
            return initial_comment
        
        # Case 3: Favor edit comment if available and meaningful
        if edit_comment and edit_comment_lower != 'agree':
            logger.debug(f"Using edit comment: '{edit_comment}'")
            return edit_comment
        
        # Case 4: Use final comment if available and meaningful  
        if final_comment and final_comment_lower != 'agree':
            logger.debug(f"Using final comment: '{final_comment}'")
            return final_comment
        
        # Case 5: Fallback to initial comment
        logger.debug(f"Using initial comment (fallback): '{initial_comment}'")
        return initial_comment