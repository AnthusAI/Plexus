from types import FunctionType
import pydantic
from pydantic import Field
from langgraph.graph import StateGraph, END
from langchain_core.output_parsers import BaseOutputParser
from langchain_core.prompts import ChatPromptTemplate
from plexus.LangChainUser import LangChainUser
from plexus.scores.LangGraphScore import LangGraphScore
from plexus.scores.nodes.BaseNode import BaseNode
from typing import Type, Optional, Dict, Any

class YesOrNoClassifier(BaseNode, LangChainUser):
    """
    A node that classifies text input as 'yes' or 'no' based on the provided prompt.
    """
    
    class Parameters(LangChainUser.Parameters):
        prompt: str

    def __init__(self, **parameters):
        # We intentionally override super().__init__() to allow for a carefully-crafted Pydantic model here.
        combined_parameters_model = pydantic.create_model(
            "CombinedParameters",
            __base__=(YesOrNoClassifier.Parameters, LangChainUser.Parameters))
        self.parameters = combined_parameters_model(**parameters)
        self.openai_callback = None
        self.model = self._initialize_model()

    class GraphState(BaseNode.GraphState):
        classification: Optional[str]
        explanation: Optional[str]

    class ClassificationOutputParser(BaseOutputParser[dict]):
        def parse(self, output: str) -> Dict[str, Any]:
            output = output.strip().strip('"')
            if 'yes' in output.lower():
                return {
                    "classification": "yes",
                    "explanation": output
                }
            elif 'no' in output.lower():
                return {
                    "classification": "no",
                    "explanation": output
                }
            else:
                return {
                    "classification": "unknown",
                    "explanation": output
                }

    def get_classifier_node(self) -> FunctionType:
        model = self.model
        prompt = self.parameters.prompt

        def classifier_node(state):
            
            chain = ChatPromptTemplate.from_messages([
                ("system", prompt)
            ]) | model | self.ClassificationOutputParser()
            
            return chain.invoke({"text": state.text})

        return classifier_node

    def add_core_nodes(self, workflow: StateGraph) -> StateGraph:
        workflow.add_node("classify", self.get_classifier_node())
        return workflow