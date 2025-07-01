from typing import Optional, Dict, Any, Callable
from pydantic import Field, BaseModel
from langgraph.graph import StateGraph, END
from plexus.scores.nodes.BaseNode import BaseNode
from plexus.CustomLogging import logging
from plexus.dashboard.api.models.score_result import ScoreResult
from plexus.scores.Score import Score
from plexus.LangChainUser import LangChainUser
import pydantic
import sys
from io import StringIO

class LogicalClassifier(BaseNode):
    """
    A node that performs programmatic classification using a provided function.
    Returns None to allow flow to continue to subsequent nodes if no match is found.
    """
    
    class Parameters(BaseNode.Parameters):
        code: str = Field(description="Python code string defining the score function")
        # Make conditions optional with a default of None
        conditions: Optional[list] = Field(default=None, description="List of conditions for routing results")

    class GraphState(BaseNode.GraphState):
        classification: Optional[str]
        explanation: Optional[str]
        criteria_met: Optional[Any] = None  # Allow any type for criteria_met

    def __init__(self, **parameters):
        LangChainUser.__init__(self, **parameters)
        # We intentionally override super().__init__() to allow for a carefully-crafted Pydantic model here.
        combined_parameters_model = pydantic.create_model(
            "CombinedParameters",
            __base__=(LogicalClassifier.Parameters, LangChainUser.Parameters))
        self.parameters = combined_parameters_model(**parameters)
        
        # Create a custom print function that logs instead of printing to stdout
        def log_print(*args, **kwargs):
            """Custom print function that logs messages instead of printing to stdout."""
            # Convert print arguments to a string like normal print would
            sep = kwargs.get('sep', ' ')
            message = sep.join(str(arg) for arg in args)
            # Log at INFO level so it gets captured by the log capture system
            logging.info(f"[LogicalClassifier] {message}")
        
        # Create a logging function for explicit logging in embedded code
        def log_info(message):
            """Logging function available in embedded code."""
            logging.info(f"[LogicalClassifier] {message}")
        
        def log_debug(message):
            """Debug logging function available in embedded code."""
            logging.debug(f"[LogicalClassifier] {message}")
        
        def log_warning(message):
            """Warning logging function available in embedded code."""
            logging.warning(f"[LogicalClassifier] {message}")
        
        def log_error(message):
            """Error logging function available in embedded code."""
            logging.error(f"[LogicalClassifier] {message}")
        
        # Compile the code string into a function with enhanced namespace
        namespace = {
            'Score': Score,
            'print': log_print,  # Replace print with our logging version
            'log': log_info,     # Provide explicit logging functions
            'log_info': log_info,
            'log_debug': log_debug,
            'log_warning': log_warning,
            'log_error': log_error,
            'logging': logging   # Also provide the full logging module
        }
        exec(self.parameters.code, namespace)
        self.score_function = namespace.get('score')
        if not self.score_function:
            raise ValueError("Code must define a 'score' function")

    def get_score_node(self):
        """Node that executes the programmatic scoring function."""
        score_function = self.score_function
        parameters = Score.Parameters(**self.parameters.model_dump())  # Convert to Score.Parameters

        def execute_score(state):
            logging.info(f"→ {self.node_name}: Executing logical score")
            if isinstance(state, dict):
                state = self.GraphState(**state)

            # Create a merged metadata dictionary that includes both the existing metadata
            # and all state attributes (excluding 'metadata' itself to avoid recursion)
            state_dict = state.model_dump()

            # logging.info(f"LogicalClassifier state_dict: {state_dict}")

            merged_metadata = state_dict.get('metadata', {}).copy()

            # Add all state attributes directly to metadata
            for key, value in state_dict.items():
                if key != 'metadata' and key != 'text':
                    merged_metadata[key] = value
            
            # Create Score.Input from state with enhanced metadata
            score_input = Score.Input(
                text=state.text,
                metadata=merged_metadata
            )

            # logging.info(f"LogicalClassifier parameters: {parameters}")
            # logging.info(f"LogicalClassifier score_input: {score_input}")

            # Execute the score function with both parameters and input
            result = score_function(parameters, score_input)
            
            if result is None:
                # Continue to next node
                return state
            
            # Create the initial result state
            state_update = {
                **state.model_dump(),
                "classification": result.value,  # Critical for conditions
                "value": result.value,
                "explanation": result.metadata.get('explanation')
            }
            
            # Add all metadata fields as direct state attributes for output aliasing
            if result.metadata:
                for key, value in result.metadata.items():
                    if key != 'explanation':  # explanation is already handled above
                        state_update[key] = value
            
            result_state = self.GraphState(**state_update)
            
            # Prepare output state for logging
            output_state = {
                "classification": result.value,
                "value": result.value,
                "explanation": result.metadata.get('explanation')
            }
            
            # Add all metadata fields to output state for logging
            if result.metadata:
                for key, value in result.metadata.items():
                    if key != 'explanation':  # explanation is already handled above
                        output_state[key] = value
            
            logging.info(f"  ✓ {self.node_name}: {result.value}")
            
            # Log the state and get a new state object with updated node_results
            updated_state = self.log_state(result_state, None, output_state)
            
            return updated_state

        return execute_score

    def add_core_nodes(self, workflow: StateGraph) -> StateGraph:
        """Add core nodes to the workflow."""
        workflow.add_node(self.node_name, self.get_score_node())
        return workflow