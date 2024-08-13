from types import FunctionType
import pydantic
from pydantic import Field
from typing import List, Dict, Any, Optional
from langgraph.graph import StateGraph, END
from langchain_core.output_parsers import BaseOutputParser
from plexus.LangChainUser import LangChainUser
from plexus.scores.nodes.BaseNode import BaseNode
from plexus.CustomLogging import logging

class MultiClassClassifier(BaseNode):
    """
    A node that classifies text input as one of multiple classes based on the provided prompt.
    """
    
    class Parameters(BaseNode.Parameters):
        fuzzy_match: bool = Field(default=False)
        fuzzy_match_threshold: float = Field(default=0.8)
        valid_classes: List[str] = Field(default_factory=list)

    def __init__(self, **parameters):
        super().__init__(**parameters)
        self.parameters = MultiClassClassifier.Parameters(**parameters)
        
        # Initialize the model using LangChainUser's method
        self.model = self._initialize_model()

    class GraphState(BaseNode.GraphState):
        classification: Optional[str]
        explanation: Optional[str]

    class ClassificationOutputParser(BaseOutputParser):
        """
        A parser that classifies the output as one of the valid classes.
        """
        valid_classes: List[str] = Field(...)
        fuzzy_match: bool = Field(default=False)
        fuzzy_match_threshold: float = Field(default=0.8)

        def __init__(self, valid_classes: List[str], fuzzy_match: bool, fuzzy_match_threshold: float):
            super().__init__()
            self.valid_classes = valid_classes
            self.fuzzy_match = fuzzy_match
            self.fuzzy_match_threshold = fuzzy_match_threshold

        def parse(self, output: str) -> Dict[str, Any]:
            # Clean and lowercase the output
            cleaned_output = ''.join(char.lower() for char in output if char.isalnum() or char.isspace())
            logging.info(f"Cleaned output: {cleaned_output}")
            
            # Split the output into words
            words = cleaned_output.split()
            
            # Check the first few words and the last few words
            start_words = ' '.join(words[:1])
            end_words = ' '.join(words[-1:])  # Check the last 5 words
            logging.info(f'End words: {end_words}')
            for class_name in self.valid_classes:
                clean_class = class_name.lower()
                if clean_class in start_words or clean_class in end_words:
                    return {
                        "classification": class_name,
                        "explanation": output
                    }
            
            # If no valid class is found,
            if self.fuzzy_match:
                # TODO: Fuzzy match the output to the valid classes
                # Pick the closest match
                # Loop back and ask the LLM again if there is still no match that way.
                return {
                    "classification": output,
                    "explanation": output
                }
            else:
                # Return "unknown"
                return {
                    "classification": "unknown",
                    "explanation": output
                }

    def get_classifier_node(self) -> FunctionType:
        model = self.model
        prompt_templates = self.get_prompt_templates()
        valid_classes = self.parameters.valid_classes

        def classifier_node(state):
            prompt = prompt_templates[0]

            chain = prompt | model | self.ClassificationOutputParser(
                valid_classes=valid_classes,
                fuzzy_match=self.parameters.fuzzy_match,
                fuzzy_match_threshold=self.parameters.fuzzy_match_threshold
            )
            return chain.invoke({"text": state.text})

        return classifier_node

    def add_core_nodes(self, workflow: StateGraph) -> StateGraph:
        workflow.add_node("classify", self.get_classifier_node())
        return workflow