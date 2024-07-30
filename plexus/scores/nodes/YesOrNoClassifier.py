from langgraph.graph import StateGraph, END
from plexus.scores.LangGraphScore import LangGraphScore
from plexus.scores.nodes.BaseNode import BaseNode
from typing import Type, Optional

class YesOrNoClassifier(BaseNode):
    """
    A node that classifies text input as 'yes' or 'no' based on the provided prompt.
    """
    
    class GraphState(BaseNode.GraphState):
        classification: Optional[str]

    def __init__(self, prompt: str, **kwargs):
        super().__init__(**kwargs)
        self.prompt = prompt

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

    def build_compiled_workflow(self, graph_state_class: Type[LangGraphScore.GraphState]):
        """
        Build the workflow for the YesOrNoClassifier node.
        """
        def classify_node(state):
            classification = self.classify(state.text)
            state.classification = classification
            return state

        workflow = StateGraph(graph_state_class)
        workflow.add_node("classify", classify_node)
        workflow.set_entry_point("classify")
        workflow.add_edge("classify", END)

        return workflow.compile()
