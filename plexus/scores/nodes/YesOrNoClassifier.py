from types import FunctionType
import pydantic
from pydantic import Field
from langgraph.graph import StateGraph, END
from langchain_core.output_parsers import BaseOutputParser
from langchain_core.prompts import ChatPromptTemplate
from plexus.LangChainUser import LangChainUser
from plexus.scores.LangGraphScore import LangGraphScore
from plexus.scores.nodes.BaseNode import BaseNode
from typing import Type, Optional, Dict, Any, List
from langchain_core.messages import AIMessage, HumanMessage

class YesOrNoClassifier(BaseNode):
    """
    A node that classifies text input as 'yes' or 'no' based on the provided prompt.
    """

    class Parameters(BaseNode.Parameters):
        explanation_message: Optional[str] = None

    def __init__(self, **parameters):
        LangChainUser.__init__(self, **parameters)
        # We intentionally override super().__init__() to allow for a carefully-crafted Pydantic model here.
        combined_parameters_model = pydantic.create_model(
            "CombinedParameters",
            __base__=(YesOrNoClassifier.Parameters, LangChainUser.Parameters))
        self.parameters = combined_parameters_model(**parameters)
        
        # Initialize the model using LangChainUser's method
        self.model = self._initialize_model()

    class GraphState(BaseNode.GraphState):
        classification: Optional[str]
        explanation: Optional[str]

    class ClassificationOutputParser(BaseOutputParser[dict]):
        def parse(self, output: str) -> Dict[str, Any]:
            cleaned_output = ''.join(char.lower() for char in output if char.isalnum() or char.isspace())
            words = cleaned_output.split()
            
            for word in words:
                if word == "yes":
                    return {"classification": "yes"}
                elif word == "no":
                    return {"classification": "no"}
            
            return {"classification": "unknown"}

    def get_classifier_node(self) -> FunctionType:
        model = self.model
        prompt_templates = self.get_prompt_templates()

        def classifier_node(state):
            initial_prompt = prompt_templates[0]
            initial_chain = initial_prompt | model | self.ClassificationOutputParser()
            result = initial_chain.invoke({"text": state.text})

            if self.parameters.explanation_message:
                explanation_messages = ChatPromptTemplate(
                    messages=[
                        HumanMessage(initial_prompt.format(text=state.text)),
                        AIMessage(content=result['classification']),
                        HumanMessage(content=self.parameters.explanation_message)
                    ]
                )
                explanation_chain = explanation_messages | model
                explanation = explanation_chain.invoke({})
                result["explanation"] = explanation.content
            else:
                full_response = model.invoke(initial_prompt.format(text=state.text))
                result["explanation"] = full_response.content

            return result

        return classifier_node

    def add_core_nodes(self, workflow: StateGraph) -> StateGraph:
        workflow.add_node("classify", self.get_classifier_node())
        return workflow