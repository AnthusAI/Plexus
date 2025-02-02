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
import logging
from typing import Type, Optional, Dict, Any, List
from langchain_core.messages import AIMessage, HumanMessage
import asyncio
from concurrent.futures import ThreadPoolExecutor
import time

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
        explanation_model: Optional[Dict[str, Any]] = None
        parse_from_start: Optional[bool] = False
        maximum_retry_count: int = Field(default=3, description="Maximum number of retries for classification")

    class ClassificationOutputParser(BaseOutputParser[dict]):
        parse_from_start: bool = Field(default=False)

        def parse(self, output: str) -> Dict[str, Any]:
            cleaned_output = ''.join(char.lower() for char in output if char.isalnum() or char.isspace())
            words = cleaned_output.split()
            classification = "unknown"
            
            word_iterator = words if self.parse_from_start else reversed(words)
            
            for word in word_iterator:
                if word == "yes":
                    classification = "yes"
                    break
                elif word == "no":
                    classification = "no"
                    break
            
            return {
                "classification": classification,
                "explanation": output  # Always include the full LLM response as explanation
            }

    def get_classifier_node(self) -> FunctionType:
        model = self.model
        prompt_templates = self.get_prompt_templates()
        executor = ThreadPoolExecutor(max_workers=1)

        def classifier_node(state):
            initial_prompt = prompt_templates[0]
            retry_count = 0 if state.retry_count is None else state.retry_count

            def run_chain():
                nonlocal retry_count
                while retry_count < self.parameters.maximum_retry_count:
                    initial_chain = initial_prompt | model | \
                        self.ClassificationOutputParser(
                            parse_from_start=self.parameters.parse_from_start)
                    
                    try:
                        # Pass the entire state as a dictionary and add retry_feedback
                        invoke_input = {
                            **state.dict(),
                            "retry_feedback": (
                                f"You responded with {state.explanation}, but we need a \"Yes\" or a \"No\". "
                                f"Please try again. This is attempt {retry_count + 1} of {self.parameters.maximum_retry_count}."
                                if retry_count > 0 else ""
                            )
                        }
                        result = initial_chain.invoke(invoke_input)
                        return result
                    except Exception as e:
                        retry_count += 1
                        if retry_count >= self.parameters.maximum_retry_count:
                            return {"classification": "unknown", "explanation": f"Error: {str(e)}"}
                        time.sleep(1)  # Add a small delay before retrying

                return {"classification": "unknown", "explanation": "Maximum retries reached"}

            result = executor.submit(run_chain).result()

            if result["classification"] != "unknown":
                explanation = result["explanation"]

                if self.parameters.explanation_message:
                    explanation_messages = ChatPromptTemplate(
                        messages=[
                            HumanMessage(initial_prompt.format(text=state.text)),
                            AIMessage(content=result['classification']),
                            HumanMessage(content=self.parameters.explanation_message)
                        ]
                    )
                    explanation_model = (
                        self._initialize_model(self.parameters.explanation_model)
                        if self.parameters.explanation_model
                        else model
                    )
                    explanation_chain = explanation_messages | explanation_model
                    detailed_explanation = explanation_chain.invoke({})
                    explanation = detailed_explanation.content

                result["explanation"] = explanation

            return {**state.dict(), **result, "retry_count": retry_count}

        return classifier_node

    def add_core_nodes(self, workflow: StateGraph) -> StateGraph:
        workflow.add_node(self.node_name, self.get_classifier_node())
        return workflow