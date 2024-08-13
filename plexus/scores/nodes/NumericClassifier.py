import re
from types import FunctionType
import pydantic
from pydantic import Field
from typing import List, Dict, Any, Optional
from langgraph.graph import StateGraph, END
from langchain_core.output_parsers import BaseOutputParser
from plexus.LangChainUser import LangChainUser
from plexus.scores.nodes.BaseNode import BaseNode
from plexus.CustomLogging import logging

class NumericClassifier(BaseNode):
    """
    A node that classifies numeric input based on the provided prompt and optional range.
    """
    
    class Parameters(BaseNode.Parameters):
        numeric_min: Optional[str] = Field(default=None)
        numeric_max: Optional[str] = Field(default=None)

    def __init__(self, **parameters):
        super().__init__(**parameters)
        self.parameters = NumericClassifier.Parameters(**parameters)
        
        # Initialize the model using LangChainUser's method
        self.model = self._initialize_model()

    class GraphState(BaseNode.GraphState):
        classification: Optional[str]
        explanation: Optional[str]

    class NumericOutputParser(BaseOutputParser):
        """
        A parser that classifies the output as a number (as a string), optionally within a specified range.
        """
        numeric_min: Optional[str] = Field(default=None)
        numeric_max: Optional[str] = Field(default=None)

        def __init__(self, numeric_min: Optional[str] = None, numeric_max: Optional[str] = None):
            super().__init__()
            self.numeric_min = numeric_min
            self.numeric_max = numeric_max

        def parse(self, output: str) -> Dict[str, Any]:
            # Use regex to find a number in the output
            number_match = re.search(r'-?\d+(?:\.\d+)?', output)
            
            if number_match:
                number_str = number_match.group()
                
                # Check range if both min and max are defined
                if self.numeric_min is not None and self.numeric_max is not None:
                    if float(self.numeric_min) <= float(number_str) <= float(self.numeric_max):
                        return {
                            "classification": number_str,
                            "explanation": output
                        }
                    else:
                        return {
                            "classification": None,
                            "explanation": f"Number {number_str} is outside the valid range [{self.numeric_min}, {self.numeric_max}]."
                        }
                else:
                    # No range check if min or max is not defined
                    return {
                        "classification": number_str,
                        "explanation": output
                    }
            else:
                return {
                    "classification": None,
                    "explanation": "No valid numeric classification found in the output."
                }

    def get_classifier_node(self) -> FunctionType:
        model = self.model
        prompt_templates = self.get_prompt_templates()
        numeric_min = self.parameters.numeric_min
        numeric_max = self.parameters.numeric_max

        def classifier_node(state):
            prompt = prompt_templates[0]

            chain = prompt | model | self.NumericOutputParser(
                numeric_min=numeric_min,
                numeric_max=numeric_max
            )
            result = chain.invoke({"text": state.text})
            
            return {
                "name": "NumericClassification",
                "value": result["classification"],
                "explanation": result["explanation"]
            }

        return classifier_node

    def add_core_nodes(self, workflow: StateGraph) -> StateGraph:
        workflow.add_node("classify", self.get_classifier_node())
        return workflow