from typing import Optional, Dict, Any, Callable
from pydantic import Field, BaseModel
from langgraph.graph import StateGraph, END
from plexus.scores.nodes.BaseNode import BaseNode
from plexus.CustomLogging import logging
from plexus.dashboard.api.models.score_result import ScoreResult
from plexus.scores.Score import Score
from plexus.LangChainUser import LangChainUser
import pydantic

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

    def __init__(self, **parameters):
        LangChainUser.__init__(self, **parameters)
        # We intentionally override super().__init__() to allow for a carefully-crafted Pydantic model here.
        combined_parameters_model = pydantic.create_model(
            "CombinedParameters",
            __base__=(LogicalClassifier.Parameters, LangChainUser.Parameters))
        self.parameters = combined_parameters_model(**parameters)
        
        # Compile the code string into a function
        namespace = {
            'Score': Score
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
            logging.info("<*> Entering execute_score node")
            if isinstance(state, dict):
                state = self.GraphState(**state)

            # Create a merged metadata dictionary that includes both the existing metadata
            # and all state attributes (excluding 'metadata' itself to avoid recursion)
            state_dict = state.model_dump()

            logging.info(f"LogicalClassifier state_dict: {state_dict}")

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

            logging.info(f"LogicalClassifier parameters: {parameters}")
            logging.info(f"LogicalClassifier score_input: {score_input}")

            # Execute the score function with both parameters and input
            result = score_function(parameters, score_input)
            
            if result is None:
                # Continue to next node
                return state
            
            # Return dict to merge with state, like YesOrNoClassifier does
            state_update = {
                **state.model_dump(),
                "classification": result.value,  # Critical for conditions
                "value": result.value,
                "explanation": result.metadata.get('explanation')
            }
            logging.info(f"LogicalClassifier result value: {result.value}")
            logging.info(f"LogicalClassifier result explanation: {result.metadata.get('explanation')}")
            graph_state = self.GraphState(**state_update)

            # Input state that contains everything except metadata.
            input_metadata = graph_state.model_dump()
            
            # Safely remove 'scores' from metadata if metadata exists
            if 'metadata' in input_metadata and isinstance(input_metadata['metadata'], dict):
                input_metadata['metadata'].pop('scores', None)
                input_metadata['metadata'].pop('trace', None)
            
            input_metadata.pop('messages', None)
            input_metadata.pop('text', None)
            
            input_state = {
                "state_input": {
                    **input_metadata
                }
            }

            output_state = {
                "classification": result.value,
                "explanation": result.metadata.get('explanation')
            }

            # Log the state and get a new state object with updated node_results
            updated_state = self.log_state(graph_state, input_state, output_state)

            return updated_state

        return execute_score

    def add_core_nodes(self, workflow: StateGraph) -> StateGraph:
        """Add core nodes to the workflow."""
        workflow.add_node(self.node_name, self.get_score_node())
        return workflow