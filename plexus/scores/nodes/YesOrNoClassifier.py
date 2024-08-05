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
        system_message: Optional[str] = None
        user_message: Optional[str] = None

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
            cleaned_output = ''.join(char.lower() for char in output if char.isalnum() or char.isspace())
            words = cleaned_output.split()
            last_word = words[-1] if words else ""
            
            if last_word == "yes":
                return {
                    "classification": "yes",
                    "explanation": output
                }
            elif last_word == "no":
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
        prompt = self.get_prompt_templates()

        def classifier_node(state):
            chain = prompt[0] | model | self.ClassificationOutputParser()
            return chain.invoke({"text": state.text})

        return classifier_node

    def add_core_nodes(self, workflow: StateGraph) -> StateGraph:
        workflow.add_node("classify", self.get_classifier_node())
        return workflow