from types import FunctionType
from pydantic import Field
from typing import List, Dict, Any, Optional
from langgraph.graph import StateGraph
from langchain_core.output_parsers import BaseOutputParser
from plexus.scores.nodes.BaseNode import BaseNode
from plexus.CustomLogging import logging
from rapidfuzz import process, fuzz

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

        def __init__(self, valid_classes: List[str], fuzzy_match: bool = False, fuzzy_match_threshold: float = 0.8):
            super().__init__()
            self.valid_classes = valid_classes
            self.fuzzy_match = fuzzy_match
            self.fuzzy_match_threshold = fuzzy_match_threshold

        def parse(self, output: str) -> Dict[str, Any]:
            # Clean the output (keep spaces for multi-word matching)
            cleaned_output = ' '.join(word.lower() for word in output.split())
            logging.info(f"Cleaned output: {cleaned_output}")

            words = cleaned_output.split()
            start_words = ' '.join(words[:1])
            end_words = ' '.join(words[-1:])
            logging.info(f'Start words: {start_words}, End words: {end_words}')

            # Check start/end words first
            for class_name in self.valid_classes:
                clean_class = class_name.lower()
                if clean_class in start_words or clean_class in end_words:
                    return {
                        "classification": class_name,
                        "explanation": output
                    }

            # Check for exact matches in the entire output
            for class_name in self.valid_classes:
                if class_name.lower() in cleaned_output:
                    return {
                        "classification": class_name,
                        "explanation": output
                    }

            # Only use fuzzy matching if the parameter is set to True
            if self.fuzzy_match:
                best_match, score, _ = process.extractOne(cleaned_output, self.valid_classes, scorer=fuzz.token_set_ratio)
                logging.info(f"Best fuzzy match: {best_match}, score: {score}")
                
                if score >= self.fuzzy_match_threshold * 100:  # Convert threshold to percentage
                    return {
                        "classification": best_match,
                        "explanation": output
                    }
            
            # If no valid class is found
            return {
                "classification": "unknown",
                "explanation": output
            }

    def get_classifier_node(self) -> FunctionType:
        model = self.model
        prompt_templates = self.get_prompt_templates()
        valid_classes = self.parameters.valid_classes
        fuzzy_match = self.parameters.fuzzy_match
        fuzzy_match_threshold = self.parameters.fuzzy_match_threshold

        def classifier_node(state):
            prompt = prompt_templates[0]

            chain = prompt | model | self.ClassificationOutputParser(
                valid_classes=valid_classes,
                fuzzy_match=fuzzy_match,
                fuzzy_match_threshold=fuzzy_match_threshold
            )
            return chain.invoke({"text": state.text})

        return classifier_node

    def add_core_nodes(self, workflow: StateGraph) -> StateGraph:
        workflow.add_node("classify", self.get_classifier_node())
        return workflow