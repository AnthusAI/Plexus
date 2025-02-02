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
        conditions: list = Field(description="List of conditions for routing results")

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

            # Create Score.Input from state
            score_input = Score.Input(
                text=state.text,
                metadata=state.metadata if hasattr(state, 'metadata') else {}
            )

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
            return self.GraphState(**state_update)

        return execute_score

    def add_core_nodes(self, workflow: StateGraph) -> StateGraph:
        """Add core nodes to the workflow."""
        workflow.add_node(self.node_name, self.get_score_node())
        return workflow