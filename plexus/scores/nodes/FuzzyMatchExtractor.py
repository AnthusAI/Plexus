from typing import Dict, Any, Callable, List, Union, Tuple
import pydantic
from pydantic import Field
from langgraph.graph import StateGraph, END
from plexus.scores.nodes.BaseNode import BaseNode
from plexus.CustomLogging import logging
from plexus.LangChainUser import LangChainUser # Although not used for LLM, might inherit base params
from plexus.scores.shared.fuzzy_matching import FuzzyTarget, FuzzyTargetGroup, FuzzyMatchingEngine

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
        FuzzyMatchingEngine.validate_targets_structure(self.parameters.targets)

    def _evaluate(self, item: Union[FuzzyTargetGroup, FuzzyTarget], text: str) -> Tuple[bool, List[Dict]]:
        """Recursively evaluates a target or group against the text."""
        return FuzzyMatchingEngine.evaluate_single_text(item, text)

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