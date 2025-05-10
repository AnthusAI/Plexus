from typing import Optional, Dict, Any, Callable, List, Union, Literal, Tuple
import pydantic
from pydantic import BaseModel, Field, validator
from langgraph.graph import StateGraph, END
from plexus.scores.nodes.BaseNode import BaseNode
from plexus.CustomLogging import logging
from plexus.LangChainUser import LangChainUser # Although not used for LLM, might inherit base params
import rapidfuzz
from rapidfuzz import fuzz, process, utils

# --- Pydantic Models for Configuration ---

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
                # This should ideally not happen due to Pydantic validation
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

    @validator('items')
    def check_items_not_empty(cls, v):
        if not v:
            raise ValueError("Group 'items' list cannot be empty")
        return v

# --- Node Implementation ---

class FuzzyMatchExtractor(BaseNode):
    """
    A node that performs fuzzy string matching based on a configurable set of targets
    and logical operators (AND/OR), without using an LLM.

    It evaluates the input text against the configured `targets` structure.
    The result indicates overall success (`match_found`) and provides details
    of all individual successful matches (`matches`).
    """

    class Parameters(BaseNode.Parameters):
        """Parameters for configuring the FuzzyMatchExtractor."""
        targets: Union[FuzzyTargetGroup, FuzzyTarget] = Field(
            ...,
            description="The root target definition. Can be a single FuzzyTarget or a FuzzyTargetGroup."
        )
        # Inherits 'name' from BaseNode.Parameters
        # Exclude LLM-specific params from BaseNode/LangChainUser if not needed
        model_config = pydantic.ConfigDict(
            ignored_types=(LangChainUser.Parameters,)
        )

    class GraphState(BaseNode.GraphState):
        """State specific to the FuzzyMatchExtractor node."""
        match_found: bool = Field(False, description=(
            "Overall result indicating if the configured target logic was met."
        ))
        matches: List[Dict[str, Any]] = Field(
            default_factory=list,
            description=(
                "List containing details of each individual FuzzyTarget that met its threshold. "
                "Example entry: {'target': 'hello', 'threshold': 90, 'score': 95.5, "
                "'matched_text': 'Hello', 'matched_indices': (10, 15)}"
            )
        )
        # Inherits 'text', 'metadata', etc. from BaseNode.GraphState

    def __init__(self, **parameters):
        # Initialize BaseNode part (handles name, etc.)
        # Avoid full LangChainUser init if LLM params are truly unused
        super().__init__(**parameters)

        # Use Pydantic to parse and validate parameters
        self.parameters = self.Parameters(**parameters)

        # Pre-validate the structure recursively if needed (Pydantic does most of this)
        self._validate_targets_structure(self.parameters.targets)

    def _validate_targets_structure(self, target_config: Union[FuzzyTargetGroup, FuzzyTarget]):
        """Optional: Add deeper validation if needed beyond Pydantic."""
        if isinstance(target_config, FuzzyTargetGroup):
            for item in target_config.items:
                self._validate_targets_structure(item)
        # Pydantic handles most structural validation
        pass

    def _evaluate(self, item: Union[FuzzyTargetGroup, FuzzyTarget], text: str) -> Tuple[bool, List[Dict]]:
        """Recursively evaluates a target or group against the text."""
        if isinstance(item, FuzzyTarget):
            # Base Case: Evaluate a single FuzzyTarget
            target_str = item.target
            text_to_search = text
            scorer_func = item.get_scorer_func()
            processor = utils.default_process if item.preprocess else None

            # Use process.extractOne for efficiency. It handles preprocessing if processor is provided.
            # It finds the best match of target_str within text_to_search.
            result = process.extractOne(
                target_str,
                [text_to_search], # Must be a list/iterable of choices
                scorer=scorer_func,
                processor=processor,
                score_cutoff=item.threshold # Use score_cutoff for early exit
            )

            if result:
                # Result format: (choice, score, index) - choice is text_to_search here
                score = result[1]
                choice = result[0] # This is the full text_to_search
                matched_substring = choice # Default to full text
                matched_indices = None

                # Attempt to find the actual substring and indices using alignment functions
                alignment = None
                try:
                    if item.scorer == 'partial_ratio':
                        alignment = fuzz.partial_ratio_alignment(target_str, text_to_search, processor=processor)
                    elif item.scorer == 'token_sort_ratio':
                        alignment = fuzz.token_sort_ratio_alignment(target_str, text_to_search, processor=processor)
                    elif item.scorer == 'token_set_ratio':
                        alignment = fuzz.token_set_ratio_alignment(target_str, text_to_search, processor=processor)
                    # Add other alignment-supporting scorers here if needed

                    if alignment:
                        matched_substring = text_to_search[alignment.dest_start:alignment.dest_end]
                        matched_indices = (alignment.dest_start, alignment.dest_end)
                        # Optional: Re-verify score? Alignment score might differ slightly from extractOne score
                        # score = alignment.score # Uncomment if alignment score is preferred
                        logging.debug(f"Alignment successful for '{item.target}'. Matched: '{matched_substring}' Indices: {matched_indices}")
                    elif item.scorer not in ['ratio', 'WRatio', 'QRatio']:
                         # Log if alignment *should* have worked but didn't (unexpected)
                         logging.warning(f"Alignment failed or not supported for scorer '{item.scorer}' on target '{item.target}'. Using full text as matched_text.")
                    else:
                        # For scorers like ratio, WRatio, QRatio, no alignment is expected/available
                        logging.debug(f"Alignment not available for scorer '{item.scorer}' on target '{item.target}'. Using full text as matched_text.")

                except Exception as e:
                    logging.warning(f"Error during alignment calculation for target '{item.target}' with scorer '{item.scorer}': {e}. Using full text.", exc_info=True)

                match_details = {
                    "target": item.target,
                    "threshold": item.threshold,
                    "score": score, # Use score from extractOne or alignment? Sticking with extractOne for now.
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
                    item_result, item_matches = self._evaluate(sub_item, text)
                    collected_matches.extend(item_matches) # Collect matches even if we short-circuit
                    if item_result:
                        overall_result = True
                        logging.debug(f"OR group: Short-circuiting after True result.")
                        break # Short-circuit OR
            elif item.operator == 'and':
                overall_result = True
                temp_matches = [] # Store matches temporarily for AND
                for sub_item in item.items:
                    item_result, item_matches = self._evaluate(sub_item, text)
                    if not item_result:
                        overall_result = False
                        temp_matches = [] # Discard matches if one fails
                        logging.debug(f"AND group: Short-circuiting after False result.")
                        break # Short-circuit AND
                    else:
                        temp_matches.extend(item_matches)
                if overall_result:
                    collected_matches = temp_matches # Commit matches only if all passed

            logging.debug(f"{item.operator.upper()} group result: {overall_result}")
            return overall_result, collected_matches
        else:
            # Should not happen with Pydantic validation
            raise TypeError(f"Unexpected type in targets structure: {type(item)}")

    def get_matcher_node(self) -> Callable:
        """Returns the callable node function for the graph."""
        async def matcher_node(state: self.GraphState) -> self.GraphState:
            """The core logic node for fuzzy matching."""
            logging.info(f"<*> Entering {self.node_name} node")
            state_dict = None
            if isinstance(state, dict):
                state_dict = state
            elif hasattr(state, 'model_dump'): # Handle Pydantic models (like MockGraphState)
                state_dict = state.model_dump()
            else:
                logging.error(f"Node {self.node_name}: Received unexpected state type: {type(state)}")
                # Cannot proceed without a dict or model_dump-able object
                # Decide error handling: raise, return original state, return error state?
                # For now, return original state to avoid crashing the graph, though results will be wrong.
                return state

            # Try creating the correct state type from the dictionary
            try:
                current_state = self.GraphState(**state_dict)
            except Exception as e:
                logging.error(f"Failed to create {self.GraphState.__name__} from state dictionary: {e}")
                # Return original state if conversion fails
                return state

            input_text = current_state.text
            if not input_text:
                logging.warning(f"Node {self.node_name}: Input text is empty.")
                # Return current state, match_found=False, matches=[] (already default)
                # Log state before returning
                # Use current_state here as it's the correct type
                return self.log_state(current_state, input_state={'text': None}, output_state={'match_found': False, 'matches': []})

            # Evaluate the configured targets against the input text
            overall_success, found_matches = self._evaluate(self.parameters.targets, input_text)

            # Prepare the output state dictionary
            output_values = {
                "match_found": overall_success,
                "matches": found_matches
            }

            # Create the updated state dictionary, preserving existing fields
            # Use the dictionary we derived earlier
            updated_state_dict = state_dict.copy()
            updated_state_dict.update(output_values)

            # Create the new state object
            new_state = self.GraphState(**updated_state_dict)

            # Log the input/output of this node
            final_state = self.log_state(
                new_state,
                input_state={'text': input_text[:100] + ('...' if len(input_text) > 100 else '')}, # Log snippet
                output_state=output_values
            )

            logging.info(f"<*> Exiting {self.node_name} node. Match found: {final_state.match_found}")
            return final_state

        # Return the async function
        return matcher_node

    def add_core_nodes(self, workflow: StateGraph) -> StateGraph:
        """Adds the core matcher node to the workflow."""
        logging.info(f"Adding node '{self.node_name}' to workflow.")
        workflow.add_node(self.node_name, self.get_matcher_node())
        # Entry point and END edge are handled by BaseNode.build_compiled_workflow
        return workflow

    # Override build_compiled_workflow if custom entry/exit logic needed,
    # otherwise BaseNode's implementation should suffice.
    # def build_compiled_workflow(self, graph_state_class: Type[LangGraphScore.GraphState]) -> StateGraph:
    #     workflow = super().build_compiled_workflow(graph_state_class)
    #     # Add custom logic if needed
    #     return workflow 