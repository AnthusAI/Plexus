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
        score: Union[str, int] = Field(..., description="Score identifier (name, key, ID, or external ID)")  
        days: int = Field(..., description="Number of days back to search for feedback items")
        limit: Optional[int] = Field(None, description="Maximum total number of items in the dataset")
        limit_per_cell: Optional[int] = Field(None, description="Maximum number of items to sample from each confusion matrix cell")
        initial_value: Optional[str] = Field(None, description="Filter by original AI prediction value")
        final_value: Optional[str] = Field(None, description="Filter by corrected human value")
        identifier_extractor: Optional[str] = Field(None, description="Optional client-specific identifier extractor class (e.g., 'CallCriteriaIdentifierExtractor')")
        cache_file: str = Field(default="feedback_items_cache.parquet", description="Cache file name")
        local_cache_directory: str = Field(default='./.plexus_training_data_cache/', description="Local cache directory")
        
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
        
        logger.info(f"Initializing [magenta1][b]FeedbackItems[/b][/magenta1] for scorecard='{self.parameters.scorecard}', score='{self.parameters.score}', days={self.parameters.days}")

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
            'final_value': self.normalized_final_value
        }
        params_str = json.dumps(params, sort_keys=True)
        params_hash = hashlib.md5(params_str.encode()).hexdigest()[:8]
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

    def load_dataframe(self, *, data=None, fresh=False) -> pd.DataFrame:
        """
        Load a dataframe of feedback items sampled from confusion matrix cells.
        
        Args:
            data: Not used - parameters come from class initialization
            fresh: If True, bypass cache and fetch fresh data
            
        Returns:
            DataFrame with sampled feedback items
        """
        # Resolve identifiers
        scorecard_id, scorecard_name, score_id, score_name = self._resolve_identifiers()
        
        # Generate cache identifier
        cache_identifier = self._generate_cache_identifier(scorecard_id, score_id)
        
        # For dataset generation, we should always generate fresh data
        # The cache is only used for internal optimization during the same run
        # TODO: Remove caching entirely for dataset generation commands
        if not fresh and self._cache_exists(cache_identifier):
            return self._load_from_cache(cache_identifier)
        
        logger.info(f"Fetching fresh feedback data for {scorecard_name} / {score_name} (last {self.parameters.days} days)")
        
        # Fetch feedback items
        try:
            # Try to get the current event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're in a running loop, create a task
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        lambda: asyncio.run(self._fetch_feedback_items(scorecard_id, score_id, scorecard_name, score_name))
                    )
                    feedback_items = future.result()
            else:
                # If no running loop, use asyncio.run
                feedback_items = asyncio.run(self._fetch_feedback_items(
                    scorecard_id, score_id, scorecard_name, score_name
                ))
        except RuntimeError:
            # Fallback: create new event loop
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                feedback_items = new_loop.run_until_complete(self._fetch_feedback_items(
                    scorecard_id, score_id, scorecard_name, score_name
                ))
            finally:
                new_loop.close()
        
        if not feedback_items:
            logger.warning("No feedback items found")
            return pd.DataFrame()
        
        logger.info(f"Found {len(feedback_items)} feedback items")
        
        # Build confusion matrix and sample items
        sampled_items = self._sample_items_from_confusion_matrix(feedback_items)
        
        if not sampled_items:
            logger.warning("No items after sampling")
            return pd.DataFrame()
        
        logger.info(f"Sampled {len(sampled_items)} items from confusion matrix")
        
        # Create dataset rows
        df = self._create_dataset_rows(sampled_items, score_name)
        
        # Save to cache
        self._save_to_cache(df, cache_identifier)
        
        return df

    async def _fetch_feedback_items(self, scorecard_id: str, score_id: str, 
                                   scorecard_name: str, score_name: str) -> List[FeedbackItem]:
        """Fetch feedback items using the FeedbackService."""
        # First, get all items without value filtering (since FeedbackService is case-sensitive)
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
            return filtered_items
        
        return all_items

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
            
            # Build the row with ONLY the specified columns (IDs first, then metadata, then text)
            row = {
                'content_id': content_id,
                'feedback_item_id': feedback_item_id,
                'IDs': ids_hash,
                'metadata': metadata,
                'text': text,
                score_name: score_value,
                f"{score_name} comment": score_comment,
                f"{score_name} edit comment": edit_comment
            }
            
            rows.append(row)
            
            # Only debug first few items to avoid too much output
            # Processing feedback items for dataset creation
        
        # Create DataFrame with proper column structure even when empty
        if not rows:
            # Create empty DataFrame with expected columns (IDs first, then metadata, then text)
            columns = ['content_id', 'feedback_item_id', 'IDs', 'metadata', 'text', score_name, f"{score_name} comment", f"{score_name} edit comment"]
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
        required_columns = ['content_id', 'feedback_item_id', 'text', 'metadata', 'IDs', score_name, f"{score_name} comment", f"{score_name} edit comment"]
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
        metadata = {
            'feedback_item_id': feedback_item.id,
            'scorecard_id': feedback_item.scorecardId,
            'score_id': feedback_item.scoreId,
            'account_id': feedback_item.accountId,
            'created_at': feedback_item.createdAt,
            'updated_at': feedback_item.updatedAt,
            'edited_at': feedback_item.editedAt,
            'editor_name': feedback_item.editorName,
            'is_agreement': feedback_item.isAgreement,
            'cache_key': feedback_item.cacheKey,
            'initial_answer_value': feedback_item.initialAnswerValue,
            'initial_comment_value': feedback_item.initialCommentValue
        }
        
        # Add item metadata if available
        if feedback_item.item:
            item_metadata = {
                'item_id': feedback_item.item.id,
                'external_id': getattr(feedback_item.item, 'externalId', None),
                'item_created_at': getattr(feedback_item.item, 'createdAt', None),
                'item_updated_at': getattr(feedback_item.item, 'updatedAt', None),
                'item_metadata': getattr(feedback_item.item, 'metadata', None)
            }
            metadata['item'] = item_metadata
        
        return json.dumps(metadata, default=str)
    
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