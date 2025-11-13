"""
Score enrichment module for datasets.

This module provides functionality to enrich datasets with score values from the Plexus API,
regardless of the original data source (CallCriteriaDBCache, FeedbackItems, etc.).

The enrichment follows a 4-tier fallback strategy for each item/score combination:
1. Most recent FeedbackItem for that Item and Score
2. Most recent ScoreResult (non-evaluation) for that Item and Score
3. Most recent ScoreResult (any source) for that Item and Score
4. Generate a new prediction on-demand (if enabled)
"""

import logging
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import datetime
from collections import defaultdict

from plexus.cli.shared.client_utils import create_client
from plexus.cli.shared.identifier_resolution import resolve_scorecard_identifier, resolve_score_identifier
from plexus.cli.shared.fetch_scorecard_structure import fetch_scorecard_structure

logger = logging.getLogger(__name__)


class ScoreEnrichment:
    """
    Enriches datasets with score values from the Plexus API.
    
    This class adds score columns to datasets by fetching values from FeedbackItems
    and ScoreResults, following a prioritized fallback strategy with optional prediction.
    """
    
    def __init__(self, client=None, enable_predictions=False):
        """
        Initialize the score enrichment service.
        
        Args:
            client: Optional PlexusDashboardClient instance. If not provided, creates one.
            enable_predictions: If True, generate predictions for items with no existing score data.
        """
        self.client = client or create_client()
        self.enable_predictions = enable_predictions
    
    async def enrich_dataframe(
        self,
        df: pd.DataFrame,
        scorecard_identifier: Union[str, int],
        score_identifiers: List[Union[str, int]],
        account_id: str,
        text_column: str = 'text'
    ) -> pd.DataFrame:
        """
        Enrich a dataframe with score values from the Plexus API.
        
        Args:
            df: The dataframe to enrich. Must have 'content_id' column.
            scorecard_identifier: Scorecard identifier (name, key, ID, or external ID)
            score_identifiers: List of score identifiers to add as columns
            account_id: Account ID for API queries
            text_column: Name of the column containing text for predictions (default: 'text')
            
        Returns:
            Enriched dataframe with additional score columns
            
        Raises:
            ValueError: If dataframe is missing required columns
        """
        if df.empty:
            logger.warning("Empty dataframe provided for enrichment")
            return df
            
        if 'content_id' not in df.columns:
            raise ValueError("Dataframe must have 'content_id' column for score enrichment")
        
        # Resolve scorecard (synchronous function)
        scorecard_structure = fetch_scorecard_structure(self.client, scorecard_identifier)
        if not scorecard_structure:
            raise ValueError(f"Could not resolve scorecard: {scorecard_identifier}")
        
        scorecard_id = scorecard_structure['id']
        scorecard_name = scorecard_structure['name']
        
        logger.info(f"Enriching dataset with scores from scorecard '{scorecard_name}' (ID: {scorecard_id})")
        
        # Resolve all scores (synchronous function)
        # Build a map of score names/keys/ids from the scorecard structure for faster lookup
        score_map = {}
        for section in scorecard_structure.get('sections', {}).get('items', []):
            for score in section.get('scores', {}).get('items', []):
                score_map[score['id']] = score
                score_map[score['name']] = score
                if score.get('key'):
                    score_map[score['key']] = score
                if score.get('externalId'):
                    score_map[score['externalId']] = score
        
        score_info = []
        for score_identifier in score_identifiers:
            # Try to find the score in our map
            score_data = score_map.get(str(score_identifier))
            if score_data:
                score_info.append((score_data['id'], score_data['name']))
                logger.info(f"  - Will enrich with score '{score_data['name']}' (ID: {score_data['id']})")
            else:
                logger.warning(f"Could not resolve score: {score_identifier}. Skipping.")
                continue
        
        if not score_info:
            logger.warning("No valid scores to enrich. Returning original dataframe.")
            return df
        
        # Get all unique content IDs (items) from the dataframe
        content_ids = df['content_id'].unique().tolist()
        # Convert to strings to ensure consistency
        content_ids = [str(cid) for cid in content_ids]
        logger.info(f"Fetching score values for {len(content_ids)} items and {len(score_info)} scores")
        
        # Fetch score values for all items and scores
        score_values = await self._fetch_score_values_for_items(
            content_ids, score_info, account_id
        )
        
        # Tier 4: Generate predictions for items with no data (if enabled)
        if self.enable_predictions:
            items_needing_predictions = self._identify_items_needing_predictions(
                content_ids, score_info, score_values
            )
            
            if items_needing_predictions:
                logger.info(f"Generating predictions for {len(items_needing_predictions)} item/score combinations")
                predictions = await self._generate_predictions(
                    df, items_needing_predictions, scorecard_id, text_column
                )
                
                # Merge predictions into score_values
                for (content_id, score_id, score_name), prediction_data in predictions.items():
                    if content_id not in score_values:
                        score_values[content_id] = {}
                    score_values[content_id][score_name] = prediction_data
        
        # Add score columns to dataframe
        df_enriched = self._add_score_columns(df, score_values, score_info)
        
        return df_enriched
    
    async def _fetch_score_values_for_items(
        self,
        content_ids: List[str],
        score_info: List[Tuple[str, str]],
        account_id: str
    ) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """
        Fetch score values for all items and scores using the 3-tier fallback strategy.
        
        Args:
            content_ids: List of item IDs (content_ids)
            score_info: List of (score_id, score_name) tuples
            account_id: Account ID for API queries
            
        Returns:
            Nested dict: {content_id: {score_name: {value, comment, edit_comment, source}}}
        """
        # Initialize result structure
        score_values = defaultdict(lambda: defaultdict(dict))
        
        # For each score, fetch values for all items
        for score_id, score_name in score_info:
            logger.info(f"Fetching values for score '{score_name}' (ID: {score_id})")
            
            # Tier 1: Fetch FeedbackItems
            feedback_items = await self._fetch_feedback_items(
                content_ids, score_id, account_id
            )
            logger.info(f"  Found {len(feedback_items)} FeedbackItems for '{score_name}'")
            
            # Tier 2 & 3: Fetch ScoreResults (both non-eval and all)
            score_results = await self._fetch_score_results(
                content_ids, score_id
            )
            logger.info(f"  Found {len(score_results)} ScoreResults for '{score_name}'")
            
            # Apply fallback logic for each item
            for content_id in content_ids:
                value_data = self._apply_fallback_logic(
                    content_id,
                    score_id,
                    feedback_items.get(content_id),
                    score_results.get(content_id, [])
                )
                
                if value_data:
                    score_values[content_id][score_name] = value_data
        
        return score_values
    
    async def _fetch_feedback_items(
        self,
        content_ids: List[str],
        score_id: str,
        account_id: str
    ) -> Dict[str, Any]:
        """
        Fetch the most recent FeedbackItem for each item/score combination.
        
        Args:
            content_ids: List of item IDs
            score_id: Score ID
            account_id: Account ID
            
        Returns:
            Dict mapping content_id to FeedbackItem data
        """
        feedback_map = {}
        
        # Query for feedback items
        # Note: We need to query by itemId and scoreId
        query = """
        query ListFeedbackItems(
            $filter: ModelFeedbackItemFilterInput
            $limit: Int
        ) {
            listFeedbackItems(filter: $filter, limit: $limit) {
                items {
                    id
                    itemId
                    scoreId
                    initialAnswerValue
                    finalAnswerValue
                    initialCommentValue
                    finalCommentValue
                    editCommentValue
                    createdAt
                    updatedAt
                }
            }
        }
        """
        
        # Batch query in chunks to avoid overwhelming the API
        batch_size = 100
        for i in range(0, len(content_ids), batch_size):
            batch_ids = content_ids[i:i + batch_size]
            
            # GraphQL doesn't support IN queries easily, so we query for each item
            # In a real implementation, we'd use a GSI or optimize this
            for content_id in batch_ids:
                try:
                    result = self.client.execute(
                        query,
                        {
                            "filter": {
                                "and": [
                                    {"itemId": {"eq": content_id}},
                                    {"scoreId": {"eq": score_id}}
                                ]
                            },
                            "limit": 1000  # Get all feedback items for this item/score
                        }
                    )
                    
                    if result and result.get('listFeedbackItems'):
                        items = result['listFeedbackItems'].get('items', [])
                        if items:
                            # Get the most recent one
                            most_recent = max(items, key=lambda x: x.get('updatedAt', x.get('createdAt', '')))
                            feedback_map[content_id] = most_recent
                            
                except Exception as e:
                    logger.warning(f"Error fetching feedback items for item {content_id}: {e}")
                    continue
        
        return feedback_map
    
    async def _fetch_score_results(
        self,
        content_ids: List[str],
        score_id: str
    ) -> Dict[str, List[Any]]:
        """
        Fetch ScoreResults for each item/score combination.
        
        Args:
            content_ids: List of item IDs
            score_id: Score ID
            
        Returns:
            Dict mapping content_id to list of ScoreResult data (sorted by date, newest first)
        """
        score_results_map = defaultdict(list)
        
        query = """
        query ListScoreResults(
            $filter: ModelScoreResultFilterInput
            $limit: Int
        ) {
            listScoreResults(filter: $filter, limit: $limit) {
                items {
                    id
                    itemId
                    scoreId
                    value
                    explanation
                    evaluationId
                    createdAt
                }
            }
        }
        """
        
        # Batch query
        batch_size = 100
        for i in range(0, len(content_ids), batch_size):
            batch_ids = content_ids[i:i + batch_size]
            
            for content_id in batch_ids:
                try:
                    result = self.client.execute(
                        query,
                        {
                            "filter": {
                                "and": [
                                    {"itemId": {"eq": content_id}},
                                    {"scoreId": {"eq": score_id}}
                                ]
                            },
                            "limit": 1000
                        }
                    )
                    
                    if result and result.get('listScoreResults'):
                        items = result['listScoreResults'].get('items', [])
                        if items:
                            # Sort by createdAt (newest first)
                            sorted_items = sorted(
                                items,
                                key=lambda x: x.get('createdAt', ''),
                                reverse=True
                            )
                            score_results_map[content_id] = sorted_items
                            
                except Exception as e:
                    logger.warning(f"Error fetching score results for item {content_id}: {e}")
                    continue
        
        return score_results_map
    
    def _apply_fallback_logic(
        self,
        content_id: str,
        score_id: str,
        feedback_item: Optional[Dict[str, Any]],
        score_results: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Apply 3-tier fallback logic to get the best available score value.
        
        Priority:
        1. Most recent FeedbackItem
        2. Most recent ScoreResult (non-evaluation)
        3. Most recent ScoreResult (any source)
        
        Args:
            content_id: Item ID
            score_id: Score ID
            feedback_item: FeedbackItem data (if exists)
            score_results: List of ScoreResult data (sorted newest first)
            
        Returns:
            Dict with keys: value, comment, edit_comment, source
            None if no data available
        """
        # Tier 1: FeedbackItem
        if feedback_item:
            return {
                'value': feedback_item.get('finalAnswerValue') or feedback_item.get('initialAnswerValue'),
                'comment': feedback_item.get('finalCommentValue') or feedback_item.get('initialCommentValue', ''),
                'edit_comment': feedback_item.get('editCommentValue', ''),
                'source': 'FeedbackItem'
            }
        
        # Tier 2: ScoreResult (non-evaluation)
        for score_result in score_results:
            if not score_result.get('evaluationId'):
                return {
                    'value': score_result.get('value'),
                    'comment': score_result.get('explanation', ''),
                    'edit_comment': '',
                    'source': 'ScoreResult (production)'
                }
        
        # Tier 3: ScoreResult (any source)
        if score_results:
            score_result = score_results[0]  # Already sorted newest first
            return {
                'value': score_result.get('value'),
                'comment': score_result.get('explanation', ''),
                'edit_comment': '',
                'source': f"ScoreResult (evaluation: {score_result.get('evaluationId', 'unknown')})"
            }
        
        # No data available
        return None
    
    def _identify_items_needing_predictions(
        self,
        content_ids: List[str],
        score_info: List[Tuple[str, str]],
        score_values: Dict[str, Dict[str, Dict[str, Any]]]
    ) -> List[Tuple[str, str, str]]:
        """
        Identify which item/score combinations need predictions.
        
        Args:
            content_ids: List of all content IDs in the dataset
            score_info: List of (score_id, score_name) tuples
            score_values: Current score values dict
            
        Returns:
            List of (content_id, score_id, score_name) tuples that need predictions
        """
        items_needing_predictions = []
        
        for content_id in content_ids:
            for score_id, score_name in score_info:
                # Check if we have any data for this item/score combination
                has_data = (
                    content_id in score_values and
                    score_name in score_values[content_id] and
                    score_values[content_id][score_name].get('value') is not None
                )
                
                if not has_data:
                    items_needing_predictions.append((content_id, score_id, score_name))
        
        return items_needing_predictions
    
    async def _generate_predictions(
        self,
        df: pd.DataFrame,
        items_needing_predictions: List[Tuple[str, str, str]],
        scorecard_id: str,
        text_column: str
    ) -> Dict[Tuple[str, str, str], Dict[str, Any]]:
        """
        Generate predictions for items that have no existing score data.
        
        Args:
            df: The dataframe containing item data
            items_needing_predictions: List of (content_id, score_id, score_name) tuples
            scorecard_id: Scorecard ID
            text_column: Name of column containing text for predictions
            
        Returns:
            Dict mapping (content_id, score_id, score_name) to prediction data
        """
        predictions = {}
        
        if text_column not in df.columns:
            logger.warning(f"Text column '{text_column}' not found in dataframe. Cannot generate predictions.")
            return predictions
        
        # Group by score to batch predictions
        items_by_score = defaultdict(list)
        for content_id, score_id, score_name in items_needing_predictions:
            items_by_score[(score_id, score_name)].append(content_id)
        
        # Generate predictions for each score
        for (score_id, score_name), content_ids_for_score in items_by_score.items():
            logger.info(f"Generating {len(content_ids_for_score)} predictions for score '{score_name}'")
            
            try:
                # Load the score configuration
                from plexus.scores.Score import Score
                
                score_instance = Score.load(
                    scorecard_identifier=scorecard_id,
                    score_name=score_name,
                    use_cache=True,
                    yaml_only=False
                )
                
                # Get text for each item
                for content_id in content_ids_for_score:
                    # Find the row for this content_id
                    row = df[df['content_id'] == content_id]
                    if row.empty:
                        logger.warning(f"Could not find row for content_id {content_id}")
                        continue
                    
                    text = row[text_column].iloc[0]
                    if not text or pd.isna(text):
                        logger.warning(f"No text found for content_id {content_id}")
                        continue
                    
                    # Generate prediction
                    try:
                        result = score_instance.predict(text)
                        
                        predictions[(content_id, score_id, score_name)] = {
                            'value': result.get('value'),
                            'comment': result.get('explanation', ''),
                            'edit_comment': '',
                            'source': 'Generated prediction (Tier 4)'
                        }
                        
                        logger.debug(f"Generated prediction for {content_id}/{score_name}: {result.get('value')}")
                        
                    except Exception as e:
                        logger.error(f"Error generating prediction for {content_id}/{score_name}: {e}")
                        continue
                
            except Exception as e:
                logger.error(f"Error loading score '{score_name}' for predictions: {e}")
                continue
        
        logger.info(f"Successfully generated {len(predictions)} predictions")
        return predictions
    
    def _add_score_columns(
        self,
        df: pd.DataFrame,
        score_values: Dict[str, Dict[str, Dict[str, Any]]],
        score_info: List[Tuple[str, str]]
    ) -> pd.DataFrame:
        """
        Add score columns to the dataframe.
        
        For each score, adds 3 columns:
        - {score_name}: The score value
        - {score_name} comment: The comment/explanation
        - {score_name} edit comment: The edit comment (only from FeedbackItems)
        
        Args:
            df: Original dataframe
            score_values: Nested dict of score values
            score_info: List of (score_id, score_name) tuples
            
        Returns:
            Dataframe with added score columns
        """
        df_copy = df.copy()
        
        for score_id, score_name in score_info:
            # Initialize columns
            values = []
            comments = []
            edit_comments = []
            
            for content_id in df_copy['content_id']:
                score_data = score_values.get(content_id, {}).get(score_name, {})
                
                values.append(score_data.get('value'))
                comments.append(score_data.get('comment', ''))
                edit_comments.append(score_data.get('edit_comment', ''))
            
            # Add columns (only if they don't already exist)
            if score_name not in df_copy.columns:
                df_copy[score_name] = values
                logger.info(f"Added column '{score_name}' with {sum(v is not None for v in values)} non-null values")
            else:
                logger.info(f"Column '{score_name}' already exists, skipping")
            
            if f"{score_name} comment" not in df_copy.columns:
                df_copy[f"{score_name} comment"] = comments
            
            if f"{score_name} edit comment" not in df_copy.columns:
                df_copy[f"{score_name} edit comment"] = edit_comments
        
        return df_copy


def enrich_dataframe_with_scores(
    df: pd.DataFrame,
    scorecard_identifier: Union[str, int],
    score_identifiers: List[Union[str, int]],
    account_id: str,
    client=None,
    enable_predictions=False,
    text_column='text'
) -> pd.DataFrame:
    """
    Convenience function to enrich a dataframe with score values.
    
    This is a synchronous wrapper around ScoreEnrichment.enrich_dataframe().
    
    Args:
        df: The dataframe to enrich
        scorecard_identifier: Scorecard identifier
        score_identifiers: List of score identifiers
        account_id: Account ID
        client: Optional PlexusDashboardClient instance
        enable_predictions: If True, generate predictions for items with no existing data
        text_column: Name of column containing text for predictions (default: 'text')
        
    Returns:
        Enriched dataframe
    """
    import asyncio
    
    enrichment = ScoreEnrichment(client=client, enable_predictions=enable_predictions)
    
    # Run the async function
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        # No event loop in current thread, create a new one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    if loop.is_running():
        # If we're already in an async context, create a new loop in a thread
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(
                asyncio.run,
                enrichment.enrich_dataframe(df, scorecard_identifier, score_identifiers, account_id, text_column)
            )
            return future.result()
    else:
        return loop.run_until_complete(
            enrichment.enrich_dataframe(df, scorecard_identifier, score_identifiers, account_id, text_column)
        )

