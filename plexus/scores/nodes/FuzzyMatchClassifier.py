from typing import Optional, Dict, Any, List, Union, Tuple, Callable
import pydantic
from pydantic import Field
from langgraph.graph import StateGraph
from plexus.scores.nodes.BaseNode import BaseNode
from plexus.CustomLogging import logging
from plexus.LangChainUser import LangChainUser
from plexus.scores.shared.fuzzy_matching import FuzzyTarget, FuzzyTargetGroup, FuzzyMatchingEngine


# --- Main FuzzyMatchClassifier Node ---

class FuzzyMatchClassifier(BaseNode):
    """
    A node that performs fuzzy string matching on extracted data from state
    and returns classification results compatible with conditions/routing.

    Combines data extraction capabilities with fuzzy matching to provide
    flexible classification based on various state attributes.
    """

    class Parameters(BaseNode.Parameters):
        """Parameters for configuring the FuzzyMatchClassifier."""
        data_paths: List[str] = Field(
            ...,
            description="JSONPath-like expressions to extract values from state (e.g., 'metadata.schools[].school_id')"
        )
        targets: Union[FuzzyTargetGroup, FuzzyTarget] = Field(
            ...,
            description="The root target definition. Can be a single FuzzyTarget or a FuzzyTargetGroup."
        )
        classification_mapping: Dict[str, str] = Field(
            default_factory=dict,
            description="Maps matched target strings to classification values for output"
        )
        default_classification: Optional[str] = Field(
            default=None,
            description="Default classification value when no matches are found"
        )
        # Exclude LLM-specific params from BaseNode/LangChainUser if not needed
        model_config = pydantic.ConfigDict(
            ignored_types=(LangChainUser.Parameters,)
        )

    class GraphState(BaseNode.GraphState):
        """State specific to the FuzzyMatchClassifier node."""
        match_found: Optional[bool] = None
        matches: Optional[List[Dict[str, Any]]] = None
        # Inherits 'text', 'metadata', 'classification', 'explanation', etc. from BaseNode.GraphState

    def __init__(self, **parameters):
        # Initialize BaseNode part (handles name, etc.)
        super().__init__(**parameters)

        # Use Pydantic to parse and validate parameters
        self.parameters = self.Parameters(**parameters)

        # Validate the targets structure
        FuzzyMatchingEngine.validate_targets_structure(self.parameters.targets)

    def _extract_values_from_path(self, state_dict: Dict[str, Any], path: str) -> List[str]:
        """
        Extract values from state using JSONPath-like syntax.

        Supports patterns like:
        - 'text' -> state.text
        - 'metadata.field' -> state.metadata.field
        - 'metadata.schools[].school_id' -> [school.school_id for school in state.metadata.schools]
        """
        try:
            # Start with the full state dictionary
            current = state_dict

            # Split path by dots
            parts = path.split('.')

            for i, part in enumerate(parts):
                if not part:
                    continue

                # Handle array notation like 'schools[]'
                if part.endswith('[]'):
                    array_key = part[:-2]
                    if array_key in current and isinstance(current[array_key], list):
                        array_items = current[array_key]

                        # Check if there are more parts after the array notation
                        remaining_parts = parts[i + 1:]
                        if remaining_parts:
                            # Extract field from each array item
                            result = []
                            for item in array_items:
                                if isinstance(item, dict):
                                    # Navigate through remaining path parts for this item
                                    item_current = item
                                    for remaining_part in remaining_parts:
                                        if isinstance(item_current, dict) and remaining_part in item_current:
                                            item_current = item_current[remaining_part]
                                        else:
                                            item_current = None
                                            break

                                    if item_current is not None:
                                        result.append(str(item_current))
                            return result
                        else:
                            # No more parts, return the array items as strings
                            return [str(item) for item in array_items]
                    else:
                        logging.warning(f"Array key '{array_key}' not found or not a list in path '{path}'")
                        return []

                # Handle array index notation like 'schools[0]'
                elif '[' in part and part.endswith(']'):
                    array_key = part.split('[')[0]
                    index_str = part.split('[')[1][:-1]
                    try:
                        index = int(index_str)
                        if array_key in current and isinstance(current[array_key], list):
                            if 0 <= index < len(current[array_key]):
                                current = current[array_key][index]
                            else:
                                logging.warning(f"Array index {index} out of range for '{array_key}' in path '{path}'")
                                return []
                        else:
                            logging.warning(f"Array key '{array_key}' not found or not a list in path '{path}'")
                            return []
                    except ValueError:
                        logging.warning(f"Invalid array index '{index_str}' in path '{path}'")
                        return []

                # Handle regular field access
                else:
                    if isinstance(current, dict) and part in current:
                        current = current[part]
                    else:
                        logging.warning(f"Field '{part}' not found in path '{path}'")
                        return []

            # Convert result to list of strings (for non-array paths)
            if isinstance(current, list):
                return [str(item) for item in current]
            elif isinstance(current, str):
                return [current]
            elif current is not None:
                return [str(current)]
            else:
                return []

        except Exception as e:
            logging.error(f"Error extracting values from path '{path}': {e}")
            return []

    def _extract_all_values(self, state_dict: Dict[str, Any]) -> List[str]:
        """Extract all values from all configured data paths."""
        all_values = []
        for path in self.parameters.data_paths:
            values = self._extract_values_from_path(state_dict, path)
            all_values.extend(values)

        logging.debug(f"Extracted {len(all_values)} values from {len(self.parameters.data_paths)} paths")
        return all_values

    def _evaluate_fuzzy_targets(self, item: Union[FuzzyTargetGroup, FuzzyTarget], values: List[str]) -> Tuple[bool, List[Dict]]:
        """
        Recursively evaluates a target or group against the extracted values.
        Similar to FuzzyMatchExtractor's _evaluate method but works with a list of values.
        """
        return FuzzyMatchingEngine.evaluate_multiple_values(item, values)

    def _generate_classification(self, matches: List[Dict[str, Any]]) -> Tuple[Optional[str], Optional[str]]:
        """
        Generate classification and explanation based on matches.

        Returns:
            Tuple of (classification, explanation)
        """
        if not matches:
            classification = self.parameters.default_classification
            explanation = "No fuzzy matches found for any configured targets"
            return classification, explanation

        # Find the best match (highest score)
        best_match = max(matches, key=lambda m: m['score'])
        target = best_match['target']

        # Map target to classification using classification_mapping
        if self.parameters.classification_mapping:
            classification = self.parameters.classification_mapping.get(target, target)
        else:
            classification = target

        # Generate explanation
        matched_targets = [m['target'] for m in matches]
        explanation = f"Found fuzzy matches for: {', '.join(matched_targets)}. Best match: {target} (score: {best_match['score']:.1f})"

        return classification, explanation

    def get_classifier_node(self) -> Callable:
        """Returns the callable node function for the graph."""
        async def classifier_node(state: self.GraphState) -> self.GraphState:
            """The core logic node for fuzzy classification."""
            logging.info(f"→ {self.node_name}: Executing fuzzy classification")

            # Handle state conversion
            state_dict = None
            if isinstance(state, dict):
                state_dict = state
            elif hasattr(state, 'model_dump'):
                state_dict = state.model_dump()
            else:
                logging.error(f"Node {self.node_name}: Received unexpected state type: {type(state)}")
                return state

            # Try creating the correct state type from the dictionary
            try:
                self.GraphState(**state_dict)  # Validate state structure
            except Exception as e:
                logging.error(f"Failed to create {self.GraphState.__name__} from state dictionary: {e}")
                return state

            # Extract values from configured paths
            extracted_values = self._extract_all_values(state_dict)

            if not extracted_values:
                logging.warning(f"Node {self.node_name}: No values extracted from configured paths")
                classification = self.parameters.default_classification
                explanation = "No values found to match against"
                overall_success = False
                found_matches = []
            else:
                # Evaluate fuzzy targets against extracted values
                overall_success, found_matches = self._evaluate_fuzzy_targets(
                    self.parameters.targets,
                    extracted_values
                )

                # Generate classification and explanation
                classification, explanation = self._generate_classification(found_matches)

            # Create the updated state dictionary - same pattern as Extractor
            state_dict["classification"] = classification
            state_dict["explanation"] = explanation
            state_dict["match_found"] = overall_success
            state_dict["matches"] = found_matches

            # Create the new state object
            new_state = self.GraphState(**state_dict)

            # Log the input/output of this node (include match data in output_state for logging)
            # Handle both single FuzzyTarget and FuzzyTargetGroup cases
            if hasattr(self.parameters.targets, 'items'):
                # FuzzyTargetGroup case
                targets_list = [item.target for item in self.parameters.targets.items]
            else:
                # Single FuzzyTarget case
                targets_list = [self.parameters.targets.target]

            output_state = {
                "classification": classification,
                "explanation": explanation,
                "match_found": overall_success,
                "targets": targets_list,
                "matches": found_matches
            }

            final_state = self.log_state(
                new_state,
                input_state={'values_extracted': extracted_values},
                output_state=output_state
            )

            logging.info(f"  ✓ {self.node_name}: {final_state.classification or 'No classification'}")
            return final_state

        return classifier_node

    def add_core_nodes(self, workflow: StateGraph) -> StateGraph:
        """Adds the core classifier node to the workflow."""
        logging.info(f"Adding node '{self.node_name}' to workflow.")
        workflow.add_node(self.node_name, self.get_classifier_node())
        return workflow