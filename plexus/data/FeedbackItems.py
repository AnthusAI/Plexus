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
    """
    
    class Parameters(DataCache.Parameters):
        """Parameters for FeedbackItems data cache."""
        
        scorecard: Union[str, int] = Field(..., description="Scorecard identifier (name, key, ID, or external ID)")
        score: Optional[Union[str, int]] = Field(None, description="Single score identifier (deprecated, use scores)")
        scores: Optional[List[Union[str, int]]] = Field(None, description="List of score identifiers to include as columns (name, key, ID, or external ID)")
        days: int = Field(..., description="Number of days back to search for feedback items")
        limit: Optional[int] = Field(None, description="Maximum total number of items in the dataset")
        limit_per_cell: Optional[int] = Field(None, description="Maximum number of items to sample from each confusion matrix cell")
        initial_value: Optional[str] = Field(None, description="Filter by original AI prediction value")
        final_value: Optional[str] = Field(None, description="Filter by corrected human value")
        feedback_id: Optional[str] = Field(None, description="Specific feedback item ID to create dataset for (if specified, only this item will be included)")
        identifier_extractor: Optional[str] = Field(None, description="Optional client-specific identifier extractor class (e.g., 'CallCriteriaIdentifierExtractor')")
        column_mappings: Optional[Dict[str, str]] = Field(None, description="Optional mapping of original score names to new column names (e.g., {'Agent Misrepresentation': 'Agent Misrepresentation - With Confidence'})")
        cache_file: str = Field(default="feedback_items_cache.parquet", description="Cache file name")
        local_cache_directory: str = Field(default='./.plexus_training_data_cache/', description="Local cache directory")
        
        @validator('scores', always=True)
        def validate_scores(cls, v, values):
            """Ensure either 'score' or 'scores' is provided, not both. Convert single score to list."""
            score = values.get('score')
            if score and v:
                raise ValueError("Cannot specify both 'score' and 'scores'. Use 'scores' for multiple scores.")
            if not score and not v:
                raise ValueError("Must specify either 'score' or 'scores'")
            # Convert single score to list for uniform handling
            if score and not v:
                return [score]
            return v
        
        @validator('days')
        def days_must_be_positive(cls, v):
            if v <= 0:
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
            logger.info(f"Initializing [magenta1][b]FeedbackItems[/b][/magenta1] for specific feedback_id='{self.parameters.feedback_id}' in scorecard='{self.parameters.scorecard}', scores={self.parameters.scores}'")
        else:
            logger.info(f"Initializing [magenta1][b]FeedbackItems[/b][/magenta1] for scorecard='{self.parameters.scorecard}', scores={self.parameters.scores}, days={self.parameters.days}")

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

    def _resolve_identifiers(self) -> Tuple[str, str, List[Tuple[str, str]]]:
        """
        Resolve scorecard and score identifiers to their IDs and names.
        
        Returns:
            Tuple of (scorecard_id, scorecard_name, [(score_id, score_name), ...])
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
            scorecard_name = str(self.parameters.scorecard)
        
        # Resolve all scores
        resolved_scores = []
        for score_identifier in self.parameters.scores:
            score_id = resolve_score_identifier(self.client, scorecard_id, str(score_identifier))
            if not score_id:
                raise ValueError(f"Could not resolve score identifier '{score_identifier}' within scorecard '{scorecard_id}'")
            
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
                score_name = result.get('getScore', {}).get('name', score_identifier)
            except Exception:
                score_name = str(score_identifier)
            
            resolved_scores.append((score_id, score_name))
            logger.info(f"Resolved score '{score_identifier}' to ID: {score_id}, name: {score_name}")
        
        return scorecard_id, scorecard_name, resolved_scores

    def _generate_cache_identifier(self, scorecard_id: str, resolved_scores: List[Tuple[str, str]]) -> str:
        """Generate a unique cache identifier for the given parameters."""
        # Sort score IDs for consistent cache keys regardless of order
        score_ids = sorted([score_id for score_id, _ in resolved_scores])
        score_ids_str = '_'.join(score_ids[:3])  # Use first 3 score IDs in filename
        
        params = {
            'scorecard_id': scorecard_id,
            'score_ids': score_ids,  # Include all score IDs in hash
            'days': self.parameters.days,
            'limit': self.parameters.limit,
            'limit_per_cell': self.parameters.limit_per_cell,
            'initial_value': self.normalized_initial_value,
            'final_value': self.normalized_final_value,
            'feedback_id': self.parameters.feedback_id
        }
        params_str = json.dumps(params, sort_keys=True)
        params_hash = hashlib.md5(params_str.encode()).hexdigest()[:8]
        
        # If a specific feedback_id is provided, include it in the identifier
        if self.parameters.feedback_id:
            return f"feedback_items_{scorecard_id}_single_{self.parameters.feedback_id[:8]}_{params_hash}"
        else:
            return f"feedback_items_{scorecard_id}_{len(score_ids)}scores_{self.parameters.days}d_{params_hash}"

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
        Load a dataframe with feedback items and score results for multiple scores.
        
        Args:
            data: Not used - parameters come from class initialization
            fresh: If True, bypass cache and fetch fresh data (generates new parquet)
            reload: If True, reload existing cache with current values (NOT SUPPORTED for multi-score)
            
        Returns:
            DataFrame with items and columns for each score
        """
        # Resolve identifiers
        scorecard_id, scorecard_name, resolved_scores = self._resolve_identifiers()
        
        # Generate cache identifier
        cache_identifier = self._generate_cache_identifier(scorecard_id, resolved_scores)
        
        # Handle reload mode - NOT SUPPORTED for multi-score yet
        if reload:
            logger.warning("Reload mode is not yet supported for multi-score datasets. Performing fresh load instead.")
            fresh = True
        
        # Check cache
        if not fresh and self._cache_exists(cache_identifier):
            logger.info(f"Loading from cache: {cache_identifier}")
            return self._load_from_cache(cache_identifier)
        
        logger.info(f"Fetching fresh data for {scorecard_name} with {len(resolved_scores)} scores (last {self.parameters.days} days)")
        
        # Fetch feedback items for all scores
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        lambda: asyncio.run(self._fetch_feedback_items_for_scores(scorecard_id, resolved_scores))
                    )
                    feedback_by_score = future.result()
            else:
                feedback_by_score = asyncio.run(self._fetch_feedback_items_for_scores(
                    scorecard_id, resolved_scores
                ))
        except RuntimeError:
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                feedback_by_score = new_loop.run_until_complete(self._fetch_feedback_items_for_scores(
                    scorecard_id, resolved_scores
                ))
            finally:
                new_loop.close()
        
        if not feedback_by_score:
            logger.warning("No feedback items found for any score")
            return pd.DataFrame()
        
        # Log feedback counts per score
        for score_id, score_name in resolved_scores:
            count = len(feedback_by_score.get(score_id, []))
            logger.info(f"Score '{score_name}': {count} feedback items")
        
        # Sample items from confusion matrix if needed (only for first score for now)
        # TODO: Implement proper multi-score sampling strategy
        if not self.parameters.feedback_id and len(resolved_scores) > 0:
            first_score_id, first_score_name = resolved_scores[0]
            if first_score_id in feedback_by_score:
                logger.info(f"Sampling based on confusion matrix for score '{first_score_name}'")
                sampled_items = self._sample_items_from_confusion_matrix(feedback_by_score[first_score_id])
                
                # Update the feedback_by_score with sampled items for the first score
                feedback_by_score[first_score_id] = sampled_items
                logger.info(f"Sampled {len(sampled_items)} items from confusion matrix")
        
        # Collect all unique item IDs
        all_item_ids = set()
        for feedback_items in feedback_by_score.values():
            for feedback_item in feedback_items:
                all_item_ids.add(feedback_item.itemId)
        
        logger.info(f"Total unique items across all scores: {len(all_item_ids)}")
        
        # Fetch ScoreResults as fallback for items without FeedbackItems
        logger.info("Fetching ScoreResults as fallback for missing feedback items")
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        lambda: asyncio.run(self._fetch_score_results_for_items(list(all_item_ids), resolved_scores))
                    )
                    score_results_map = future.result()
            else:
                score_results_map = asyncio.run(self._fetch_score_results_for_items(
                    list(all_item_ids), resolved_scores
                ))
        except RuntimeError:
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                score_results_map = new_loop.run_until_complete(self._fetch_score_results_for_items(
                    list(all_item_ids), resolved_scores
                ))
            finally:
                new_loop.close()
        
        # Create dataset rows with fallback logic
        df = self._create_dataset_rows(feedback_by_score, resolved_scores, score_results_map)
        
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
                        $itemId: ID!
                        $scoreId: ID!
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
        
        # If a specific feedback_id is provided, fetch only that item
        if self.parameters.feedback_id:
            logger.info(f"Fetching specific feedback item: {self.parameters.feedback_id}")
            specific_items = await self._fetch_specific_feedback_items([self.parameters.feedback_id])
            
            if not specific_items:
                logger.warning(f"Feedback item {self.parameters.feedback_id} not found")
                return {}
            
            # Validate that the item belongs to the correct scorecard
            item = specific_items[0]
            if item.scorecardId != scorecard_id:
                logger.error(f"Feedback item {self.parameters.feedback_id} belongs to scorecard {item.scorecardId}, "
                           f"but expected scorecard {scorecard_id}")
                return {}
            
            # Add the item to the appropriate score's list
            score_id = item.scoreId
            if score_id not in feedback_by_score:
                feedback_by_score[score_id] = []
            feedback_by_score[score_id].append(item)
            
            logger.info(f"Successfully fetched specific feedback item {self.parameters.feedback_id} for score {score_id}")
            return feedback_by_score
        
        # Otherwise, fetch items for each score using the normal FeedbackService approach
        for score_id, score_name in resolved_scores:
            logger.info(f"Fetching feedback items for score '{score_name}' ({score_id})")
            
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
            logger.info(f"Received {len(all_items)} feedback items for score '{score_name}'")
            
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
                
                logger.info(f"After case-insensitive filtering for score '{score_name}': {len(filtered_items)} items (from {len(all_items)} total)")
                feedback_by_score[score_id] = filtered_items
            else:
                feedback_by_score[score_id] = all_items
        
        return feedback_by_score

    def _sample_items_from_confusion_matrix(self, feedback_items: List[FeedbackItem]) -> List[FeedbackItem]:
        """
        Sample items from each confusion matrix cell, prioritizing items with edit comments.
        
        Args:
            feedback_items: All feedback items
            
        Returns:
            Sampled items respecting limit_per_cell and overall limit
        """
        # Group items by confusion matrix cell (initial_value, final_value)
        matrix_cells = defaultdict(list)
        
        for item in feedback_items:
            if item.initialAnswerValue is not None and item.finalAnswerValue is not None:
                cell_key = (str(item.initialAnswerValue), str(item.finalAnswerValue))
                matrix_cells[cell_key].append(item)
        
        logger.info(f"Found {len(matrix_cells)} confusion matrix cells")
        for cell_key, cell_items in matrix_cells.items():
            logger.info(f"  Cell {cell_key}: {len(cell_items)} items")
        
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

    def _create_dataset_rows(
        self, 
        feedback_by_score: Dict[str, List[FeedbackItem]],
        resolved_scores: List[Tuple[str, str]],
        score_results_map: Dict[str, Dict[str, Any]]
    ) -> pd.DataFrame:
        """
        Create dataset rows from feedback items for multiple scores with ScoreResult fallback.
        
        Expected columns:
        - content_id: DynamoDB item ID
        - feedback_item_id: Feedback item ID (comma-separated if multiple)
        - text: Item.text content
        - metadata: JSON string of metadata structure
        - IDs: Hash of identifiers with name/value/URL structure
        - call_date: Extracted call date from metadata
        - {score_name}: Score value (from FeedbackItem or ScoreResult fallback)
        - {score_name} comment: Explanation/comment
        - {score_name} edit comment: Edit comment from feedback item
        
        Args:
            feedback_by_score: Dict mapping score_id -> List[FeedbackItem]
            resolved_scores: List of (score_id, score_name) tuples
            score_results_map: Dict mapping item_id -> score_id -> ScoreResult data
            
        Returns:
            DataFrame with properly formatted rows
        """
        logger.info(f"Creating dataset with {len(resolved_scores)} scores")
        
        # Collect all unique item IDs across all scores
        all_item_ids = set()
        for feedback_items in feedback_by_score.values():
            for feedback_item in feedback_items:
                all_item_ids.add(feedback_item.itemId)
        
        logger.info(f"Found {len(all_item_ids)} unique items across all scores")
        
        # Create rows indexed by item_id
        rows_by_item = {}
        
        for item_id in all_item_ids:
            # Initialize row with base columns (will be populated from first feedback item we encounter)
            rows_by_item[item_id] = {
                'content_id': item_id,
                'feedback_item_ids': [],  # Collect all feedback item IDs for this item
                'text': None,
                'metadata': None,
                'IDs': None,
                'call_date': None
            }
        
        # Process each score and add columns
        for score_id, score_name in resolved_scores:
            logger.info(f"Processing score '{score_name}' ({score_id})")
            
            # Apply column mapping if specified
            mapped_score_name = score_name
            if self.parameters.column_mappings and score_name in self.parameters.column_mappings:
                mapped_score_name = self.parameters.column_mappings[score_name]
                logger.info(f"Column mapping applied: '{score_name}' -> '{mapped_score_name}'")
            
            # Get feedback items for this score
            feedback_items = feedback_by_score.get(score_id, [])
            
            # Create a map of item_id -> FeedbackItem for quick lookup
            feedback_by_item = {fi.itemId: fi for fi in feedback_items}
            
            # Process each item
            for item_id in all_item_ids:
                row = rows_by_item[item_id]
                
                # Check if we have a FeedbackItem for this item/score combination
                feedback_item = feedback_by_item.get(item_id)
                
                if feedback_item:
                    # Populate base columns if not already done
                    if row['text'] is None:
                        if feedback_item.item:
                            text = feedback_item.item.text or ""
                            row['text'] = text
                        else:
                            row['text'] = ""
                        
                        row['metadata'] = self._create_metadata_structure(feedback_item)
                        row['IDs'] = self._create_ids_hash(feedback_item)
                        
                        # Extract call_date
                        try:
                            metadata_dict = json.loads(row['metadata']) if isinstance(row['metadata'], str) else row['metadata']
                            row['call_date'] = metadata_dict.get('call_date')
                        except:
                            pass
                    
                    # Add feedback item ID to the list
                    row['feedback_item_ids'].append(feedback_item.id)
                    
                    # Use FeedbackItem values (priority)
                    row[mapped_score_name] = feedback_item.finalAnswerValue
                    row[f"{mapped_score_name} comment"] = self._determine_score_comment(feedback_item)
                    row[f"{mapped_score_name} edit comment"] = getattr(feedback_item, 'editCommentValue', None) or ""
                    
                    logger.debug(f"Item {item_id}: Using FeedbackItem value for score '{score_name}': {feedback_item.finalAnswerValue}")
                
                else:
                    # Fallback to ScoreResult if available
                    score_result = score_results_map.get(item_id, {}).get(score_id)
                    
                    if score_result:
                        row[mapped_score_name] = score_result.get('value')
                        row[f"{mapped_score_name} comment"] = score_result.get('explanation', '')
                        row[f"{mapped_score_name} edit comment"] = ""  # No edit comment for ScoreResults
                        
                        logger.debug(f"Item {item_id}: Using ScoreResult fallback for score '{score_name}': {score_result.get('value')}")
                    else:
                        # No data available for this item/score combination
                        row[mapped_score_name] = None
                        row[f"{mapped_score_name} comment"] = ""
                        row[f"{mapped_score_name} edit comment"] = ""
                        
                        logger.debug(f"Item {item_id}: No data available for score '{score_name}'")
        
        # Convert to list of rows and join feedback_item_ids
        rows = []
        for item_id, row in rows_by_item.items():
            # Join feedback item IDs with commas
            row['feedback_item_id'] = ','.join(row.pop('feedback_item_ids', []))
            rows.append(row)
        
        # Create DataFrame
        if not rows:
            # Create empty DataFrame with expected columns
            columns = ['content_id', 'feedback_item_id', 'IDs', 'metadata', 'text', 'call_date']
            for score_id, score_name in resolved_scores:
                mapped_score_name = self.parameters.column_mappings.get(score_name, score_name) if self.parameters.column_mappings else score_name
                columns.extend([mapped_score_name, f"{mapped_score_name} comment", f"{mapped_score_name} edit comment"])
            df = pd.DataFrame(columns=columns)
        else:
            df = pd.DataFrame(rows)
        
        logger.info(f"Created dataset with {len(df)} rows and {len(df.columns)} columns: {list(df.columns)}")
        
        # Use the comprehensive debug utility from base class
        self.debug_dataframe(df, "FEEDBACK_ITEMS_DATASET", logger)
        
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