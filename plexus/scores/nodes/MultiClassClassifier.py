from types import FunctionType
from pydantic import Field
from typing import List, Dict, Any, Optional
from langgraph.graph import StateGraph
from langchain_core.output_parsers import BaseOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from plexus.scores.nodes.BaseNode import BaseNode
from plexus.CustomLogging import logging
from rapidfuzz import process, fuzz
from time import sleep

class MultiClassClassifier(BaseNode):
    """
    A node that classifies text input as one of multiple classes based on the provided prompt.
    """
    
    class Parameters(BaseNode.Parameters):
        fuzzy_match: bool = Field(default=False)
        fuzzy_match_threshold: float = Field(default=0.8)
        valid_classes: List[str] = Field(default_factory=list)
        explanation_message: Optional[str] = None
        maximum_retry_count: int = Field(default=3, description="Maximum number of retries for classification")
        parse_from_start: Optional[bool] = False

    def __init__(self, **parameters):
        super().__init__(**parameters)
        self.parameters = MultiClassClassifier.Parameters(**parameters)
        
        # Initialize the model using LangChainUser's method
        self.model = self._initialize_model()

    class GraphState(BaseNode.GraphState):
        classification: Optional[str]
        explanation: Optional[str]
        retry_count: Optional[int] = Field(default=0, description="Number of retry attempts")

    class ClassificationOutputParser(BaseOutputParser):
        """
        A parser that classifies the output as one of the valid classes.
        """
        valid_classes: List[str] = Field(...)
        fuzzy_match: bool = Field(default=False)
        fuzzy_match_threshold: float = Field(default=0.8)
        parse_from_start: bool = Field(default=False)

        def __init__(self, valid_classes: List[str], fuzzy_match: bool = False, 
                     fuzzy_match_threshold: float = 0.8, parse_from_start: bool = False):
            super().__init__()
            self.valid_classes = valid_classes
            self.fuzzy_match = fuzzy_match
            self.fuzzy_match_threshold = fuzzy_match_threshold
            self.parse_from_start = parse_from_start

        def parse(self, output: str) -> Dict[str, Any]:
            # Clean the output (keep spaces for multi-word matching)
            cleaned_output = ' '.join(word.lower() for word in output.split())
            logging.debug(f"Cleaned output: {cleaned_output}")

            # Determine max words in any valid class
            max_words = max(len(class_name.split()) for class_name in self.valid_classes)
            logging.debug(f"Max words in valid classes: {max_words}")

            # Split into words but keep more context for multi-word matches
            words = cleaned_output.split()
            if not self.parse_from_start:
                # Take the last N words where N is the length of the longest valid class
                end_phrase = ' '.join(words[-max_words:])
                logging.debug(f'End phrase: {end_phrase}')
            else:
                # Take the first N words where N is the length of the longest valid class
                end_phrase = ' '.join(words[:max_words])
                logging.debug(f'Start phrase: {end_phrase}')

            # Check for exact matches in the end/start phrase first
            for class_name in self.valid_classes:
                clean_class = class_name.lower()
                if clean_class in end_phrase:
                    return {"classification": class_name}

            # Check for exact matches in the entire output
            for class_name in self.valid_classes:
                if class_name.lower() in cleaned_output:
                    return {"classification": class_name}

            # Fuzzy matching (if enabled)
            if self.fuzzy_match:
                best_match, score, _ = process.extractOne(cleaned_output, self.valid_classes, scorer=fuzz.token_set_ratio)
                logging.debug(f"Best fuzzy match: {best_match}, score: {score}")
                
                if score >= self.fuzzy_match_threshold * 100:
                    return {"classification": best_match}
            
            return {"classification": None}

    def get_classifier_node(self) -> FunctionType:
        model = self.model
        prompt_templates = self.get_prompt_templates()
        valid_classes = self.parameters.valid_classes
        fuzzy_match = self.parameters.fuzzy_match
        fuzzy_match_threshold = self.parameters.fuzzy_match_threshold
        parse_from_start = self.parameters.parse_from_start

        def classifier_node(state):
            logging.info(f"Classifier node state: {state.model_dump()}")
            initial_prompt = prompt_templates[0]
            retry_count = 0 if state.retry_count is None else state.retry_count
            use_existing_completion = True

            # Initialize chat history
            chat_history = [
                initial_prompt.messages[0],
                initial_prompt.messages[1].format(**state.dict())
            ]

            while retry_count < self.parameters.maximum_retry_count:
                if use_existing_completion and hasattr(state, 'completion'):
                    current_completion = state.completion
                else:
                    # Create a ChatPromptTemplate from the current chat history
                    chat_prompt = ChatPromptTemplate.from_messages(chat_history)
                    
                    # Invoke the model with the current chat history
                    current_completion = model.invoke(chat_prompt.format_prompt().to_messages())
                    current_completion = current_completion.content

                # Parse the completion
                result = self.ClassificationOutputParser(
                    valid_classes=valid_classes,
                    fuzzy_match=fuzzy_match,
                    fuzzy_match_threshold=fuzzy_match_threshold,
                    parse_from_start=parse_from_start
                ).parse(current_completion)

                if result["classification"] is not None:
                    if self.parameters.explanation_message:
                        explanation_prompt = ChatPromptTemplate.from_messages([
                            *chat_history,
                            AIMessage(content=current_completion),
                            HumanMessage(content=self.parameters.explanation_message)
                        ])
                        explanation = model.invoke(explanation_prompt.format_prompt().to_messages())
                        result["explanation"] = explanation.content
                    else:
                        result["explanation"] = current_completion

                    final_state = {**state.dict(), **result, "retry_count": retry_count}
                    logging.debug(f"Classifier returning state: {final_state}")
                    return final_state

                # If we reach here, the classification was unknown, so we need to retry
                chat_history.extend([
                    ('assistant', current_completion),
                    ('user', f"You responded with an unknown classification. Please try again. This is attempt {retry_count + 1} of {self.parameters.maximum_retry_count}. Valid classes are: {', '.join(valid_classes)}.")
                ])

                retry_count += 1
                use_existing_completion = False  # Use model for subsequent retries
                sleep(1)

            return {**state.dict(), "classification": "unknown", "explanation": "Maximum retries reached", "retry_count": retry_count}

        return classifier_node

    def add_core_nodes(self, workflow: StateGraph) -> StateGraph:
        workflow.add_node("classify", self.get_classifier_node())
        return workflow