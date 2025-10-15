"""
Core fuzzy matching components shared between FuzzyMatchExtractor and FuzzyMatchClassifier.

This module contains the common data structures and evaluation logic that both nodes use.
"""

from typing import Optional, Dict, Callable, List, Union, Literal, Tuple
from pydantic import BaseModel, Field, field_validator
from rapidfuzz import fuzz, process, utils
from plexus.CustomLogging import logging


class FuzzyTarget(BaseModel):
    """Configuration for a single fuzzy matching target."""
    target: str = Field(..., description="The string to search for.")
    threshold: int = Field(..., ge=0, le=100, description="Minimum fuzzy match score (0-100) required for this target.")
    scorer: Literal['ratio', 'partial_ratio', 'token_sort_ratio', 'token_set_ratio', 'WRatio', 'QRatio'] = \
        Field('ratio', description="Specifies which Rapidfuzz scoring algorithm to use.")
    preprocess: bool = Field(False, description=(
        "If True, applies Rapidfuzz default preprocessing (lowercase, remove non-alphanumeric) "
        "to both the target string and the input text before comparison."
    ))

    # Store scorer function for efficiency
    _scorer_func: Optional[Callable] = None

    def get_scorer_func(self):
        """Gets the Rapidfuzz scorer function based on the scorer name."""
        if self._scorer_func is None:
            scorer_map = {
                'ratio': fuzz.ratio,
                'partial_ratio': fuzz.partial_ratio,
                'token_sort_ratio': fuzz.token_sort_ratio,
                'token_set_ratio': fuzz.token_set_ratio,
                'WRatio': fuzz.WRatio,
                'QRatio': fuzz.QRatio
            }
            func = scorer_map.get(self.scorer)
            if func is None:
                raise ValueError(f"Invalid scorer specified: {self.scorer}")
            self._scorer_func = func
        return self._scorer_func


class FuzzyTargetGroup(BaseModel):
    """Configuration for a group of targets combined with a logical operator."""
    operator: Literal['and', 'or'] = Field(..., description="Logical operator ('and' or 'or') combining the items.")
    items: List[Union['FuzzyTargetGroup', FuzzyTarget]] = Field(
        ...,
        description="List of FuzzyTarget configurations or nested FuzzyTargetGroup configurations."
    )

    @field_validator('items')
    @classmethod
    def check_items_not_empty(cls, v):
        if not v:
            raise ValueError("Group 'items' list cannot be empty")
        return v


class FuzzyMatchingEngine:
    """
    Shared fuzzy matching evaluation engine.

    Provides static methods for evaluating FuzzyTarget and FuzzyTargetGroup configurations
    against text or lists of values.
    """

    @staticmethod
    def evaluate_single_text(item: Union[FuzzyTargetGroup, FuzzyTarget], text: str) -> Tuple[bool, List[Dict]]:
        """
        Evaluates a target or group against a single text string.
        Used by FuzzyMatchExtractor.

        Returns:
            Tuple of (success: bool, matches: List[Dict])
        """
        if isinstance(item, FuzzyTarget):
            # Base Case: Evaluate a single FuzzyTarget
            target_str = item.target
            text_to_search = text
            scorer_func = item.get_scorer_func()
            processor = utils.default_process if item.preprocess else None

            # Use process.extractOne for efficiency
            result = process.extractOne(
                target_str,
                [text_to_search],
                scorer=scorer_func,
                processor=processor,
                score_cutoff=item.threshold
            )

            if result:
                score = result[1]
                choice = result[0]
                matched_substring = choice
                matched_indices = None

                # Attempt to find the actual substring and indices using alignment functions
                try:
                    alignment = None
                    if item.scorer == 'partial_ratio':
                        alignment = fuzz.partial_ratio_alignment(target_str, text_to_search, processor=processor)
                    elif item.scorer == 'token_sort_ratio':
                        alignment = fuzz.token_sort_ratio_alignment(target_str, text_to_search, processor=processor)
                    elif item.scorer == 'token_set_ratio':
                        alignment = fuzz.token_set_ratio_alignment(target_str, text_to_search, processor=processor)

                    if alignment:
                        matched_substring = text_to_search[alignment.dest_start:alignment.dest_end]
                        matched_indices = (alignment.dest_start, alignment.dest_end)
                        logging.debug(f"Alignment successful for '{item.target}'. Matched: '{matched_substring}' Indices: {matched_indices}")
                    elif item.scorer not in ['ratio', 'WRatio', 'QRatio']:
                        logging.warning(f"Alignment failed or not supported for scorer '{item.scorer}' on target '{item.target}'. Using full text as matched_text.")
                    else:
                        logging.debug(f"Alignment not available for scorer '{item.scorer}' on target '{item.target}'. Using full text as matched_text.")

                except Exception as e:
                    logging.warning(f"Error during alignment calculation for target '{item.target}' with scorer '{item.scorer}': {e}. Using full text.", exc_info=True)

                match_details = {
                    "target": item.target,
                    "threshold": item.threshold,
                    "score": score,
                    "matched_text": matched_substring,
                    "matched_indices": matched_indices
                }
                logging.debug(f"Match found for '{item.target}': Score={score} >= Threshold={item.threshold}")
                return True, [match_details]
            else:
                logging.debug(f"No match found for '{item.target}' (Threshold: {item.threshold})")
                return False, []

        elif isinstance(item, FuzzyTargetGroup):
            # Recursive Step: Evaluate a FuzzyTargetGroup
            collected_matches = []
            overall_result = False

            if item.operator == 'or':
                overall_result = False
                for sub_item in item.items:
                    item_result, item_matches = FuzzyMatchingEngine.evaluate_single_text(sub_item, text)
                    collected_matches.extend(item_matches)
                    if item_result:
                        overall_result = True
                        logging.debug(f"OR group: Short-circuiting after True result.")
                        break  # Short-circuit OR

            elif item.operator == 'and':
                overall_result = True
                temp_matches = []
                for sub_item in item.items:
                    item_result, item_matches = FuzzyMatchingEngine.evaluate_single_text(sub_item, text)
                    if not item_result:
                        overall_result = False
                        temp_matches = []
                        logging.debug(f"AND group: Short-circuiting after False result.")
                        break  # Short-circuit AND
                    else:
                        temp_matches.extend(item_matches)
                if overall_result:
                    collected_matches = temp_matches

            logging.debug(f"{item.operator.upper()} group result: {overall_result}")
            return overall_result, collected_matches

    @staticmethod
    def evaluate_multiple_values(item: Union[FuzzyTargetGroup, FuzzyTarget], values: List[str]) -> Tuple[bool, List[Dict]]:
        """
        Evaluates a target or group against a list of values.
        Used by FuzzyMatchClassifier.

        Returns:
            Tuple of (success: bool, matches: List[Dict])
        """
        if isinstance(item, FuzzyTarget):
            # Base Case: Evaluate a single FuzzyTarget against all values
            target_str = item.target
            scorer_func = item.get_scorer_func()
            processor = utils.default_process if item.preprocess else None

            best_match = None
            best_score = 0

            # Try fuzzy matching against all values
            for value in values:
                if not value or not isinstance(value, str):
                    continue

                result = process.extractOne(
                    target_str,
                    [value],
                    scorer=scorer_func,
                    processor=processor,
                    score_cutoff=item.threshold
                )

                if result and result[1] > best_score:
                    best_match = result
                    best_score = result[1]

            if best_match:
                score = best_match[1]
                matched_text = best_match[0]

                match_details = {
                    "target": item.target,
                    "threshold": item.threshold,
                    "score": score,
                    "matched_text": matched_text,
                    "matched_indices": None  # Could be enhanced later
                }
                logging.debug(f"Match found for '{item.target}': Score={score} >= Threshold={item.threshold}")
                return True, [match_details]
            else:
                logging.debug(f"No match found for '{item.target}' (Threshold: {item.threshold})")
                return False, []

        elif isinstance(item, FuzzyTargetGroup):
            # Recursive Step: Evaluate a FuzzyTargetGroup
            collected_matches = []
            overall_result = False

            if item.operator == 'or':
                overall_result = False
                for sub_item in item.items:
                    item_result, item_matches = FuzzyMatchingEngine.evaluate_multiple_values(sub_item, values)
                    collected_matches.extend(item_matches)
                    if item_result:
                        overall_result = True
                        logging.debug(f"OR group: Short-circuiting after True result.")
                        break  # Short-circuit OR

            elif item.operator == 'and':
                overall_result = True
                temp_matches = []
                for sub_item in item.items:
                    item_result, item_matches = FuzzyMatchingEngine.evaluate_multiple_values(sub_item, values)
                    if not item_result:
                        overall_result = False
                        temp_matches = []
                        logging.debug(f"AND group: Short-circuiting after False result.")
                        break  # Short-circuit AND
                    else:
                        temp_matches.extend(item_matches)
                if overall_result:
                    collected_matches = temp_matches

            logging.debug(f"{item.operator.upper()} group result: {overall_result}")
            return overall_result, collected_matches

    @staticmethod
    def validate_targets_structure(target_config: Union[FuzzyTargetGroup, FuzzyTarget]):
        """
        Validates the targets structure recursively.
        """
        if isinstance(target_config, FuzzyTargetGroup):
            for item in target_config.items:
                FuzzyMatchingEngine.validate_targets_structure(item)
        # Pydantic handles most structural validation