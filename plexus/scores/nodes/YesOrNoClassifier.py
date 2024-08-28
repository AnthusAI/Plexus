from types import FunctionType
from time import sleep
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
        retry_count: Optional[int] = Field(default=0, description="Number of retry attempts")

    class Parameters(BaseNode.Parameters):
        explanation_message: Optional[str] = None
        parse_from_start: Optional[bool] = False
        maximum_retry_count: int = Field(default=40, description="Maximum number of retries for classification")

    class ClassificationOutputParser(BaseOutputParser[dict]):
        parse_from_start: bool = Field(default=False)

        def parse(self, output: str) -> Dict[str, Any]:
            cleaned_output = ''.join(char.lower() for char in output if char.isalnum() or char.isspace())
            words = cleaned_output.split()
            
            if not self.parse_from_start:
                words = reversed(words)
            
            for word in words:
                if word == "yes":
                    return {
                        "classification": "yes",
                        "explanation": None
                    }
                elif word == "no":
                    return {
                        "classification": "no",
                        "explanation": output
                    }
            
            return {"classification": "unknown"}

    def __init__(self, **parameters):
        super().__init__(**parameters)
        self.parameters = self.Parameters(**parameters)

    def get_classifier_node(self) -> FunctionType:
        model = self.model
        prompt_templates = self.get_prompt_templates()

        def classifier_node(state):
            initial_prompt = prompt_templates[0]
            retry_count = 0 if state.retry_count is None else state.retry_count

            while retry_count < self.parameters.maximum_retry_count:
                initial_chain = initial_prompt | model | \
                    self.ClassificationOutputParser(
                        parse_from_start=self.parameters.parse_from_start)
                result = initial_chain.invoke({
                    "text": state.text,
                    "retry_feedback": f"You responded with {state.explanation}, but we need a \"Yes\" or a \"No\". Please try again. This is attempt {retry_count + 1} of {self.parameters.maximum_retry_count}." if retry_count > 0 else ""
                })

                if result["classification"] != "unknown":
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

                    return {**state.dict(), **result, "retry_count": retry_count}

                retry_count += 1
                sleep(1)

            return {**state.dict(), "classification": "unknown", "explanation": "Maximum retries reached", "retry_count": retry_count}

        return classifier_node

    def add_core_nodes(self, workflow: StateGraph) -> StateGraph:
        workflow.add_node("classify", self.get_classifier_node())
        return workflow