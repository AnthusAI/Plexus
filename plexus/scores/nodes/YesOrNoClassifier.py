from pydantic import Field
from langgraph.graph import StateGraph, END
from plexus.LangChainUser import LangChainUser
from plexus.scores.LangGraphScore import LangGraphScore
from plexus.scores.nodes.BaseNode import BaseNode
from typing import Type, Optional

class YesOrNoClassifier(BaseNode, LangChainUser):
    """
    A node that classifies text input as 'yes' or 'no' based on the provided prompt.
    """
    
    class Parameters(LangChainUser.Parameters):
        prompt: str = Field(...)
    
    class GraphState(BaseNode.GraphState):
        classification: Optional[str]
        quote: Optional[str]

    def __init__(self, **parameters):
        super().__init__(**parameters)
        self.openai_callback = None
        self.model = self._initialize_model()

    def classify(self, text: str) -> str:
        """
        Classify the input text as 'yes' or 'no'.

        :param text: The input text to classify.
        :return: 'yes' or 'no' based on the classification.
        """
        # Implement the classification logic here
        # For now, we will use a simple keyword-based approach
        if 'yes' in text.lower():
            return 'yes'
        elif 'no' in text.lower():
            return 'no'
        else:
            return 'unknown'

    def add_core_nodes(self, workflow: StateGraph) -> StateGraph:

        def classify(state):
            classification = self.classify(state.text)
            state.classification = classification
            state.quote = "This is a test quote"
            return state

        workflow.add_node("classify", classify)
        return workflow