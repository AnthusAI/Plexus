from typing import List, Dict, Any, Optional, Tuple, Annotated
from pydantic import Field
from langgraph.graph import StateGraph
from langchain_core.output_parsers import BaseOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage, HumanMessage
from plexus.scores.nodes.BaseNode import BaseNode
from plexus.CustomLogging import logging

class Classifier(BaseNode):
    """
    A node that performs binary classification using a LangGraph subgraph to separate
    LLM calls from parsing and retry logic.
    """
    
    class Parameters(BaseNode.Parameters):
        positive_class: str = Field(description="The label for the positive class")
        negative_class: str = Field(description="The label for the negative class")
        explanation_message: Optional[str] = None
        maximum_retry_count: int = Field(
            default=3,
            description="Maximum number of retries for classification"
        )
        parse_from_start: Optional[bool] = False

    class GraphState(BaseNode.GraphState):
        chat_history: Annotated[List, Field(default_factory=list)]
        completion: Optional[str] = None
        classification: Optional[str] = None
        explanation: Optional[str] = None
        confidence: Optional[float] = None
        retry_count: Optional[int] = Field(
            default=0, 
            description="Number of retry attempts"
        )

    def __init__(self, **parameters):
        super().__init__(**parameters)
        self.parameters = Classifier.Parameters(**parameters)
        self.model = self._initialize_model()

    class ClassificationOutputParser(BaseOutputParser):
        """Parser that identifies one of two possible classifications."""
        positive_class: str = Field(...)
        negative_class: str = Field(...)
        parse_from_start: bool = Field(default=False)

        def parse(self, output: str) -> Dict[str, Any]:
            cleaned_output = ''.join(
                char.lower() 
                for char in output 
                if char.isalnum() or char.isspace()
            )
            words = cleaned_output.split()
            
            word_iterator = words if self.parse_from_start else reversed(words)
            classification = None
            
            for word in word_iterator:
                if word.lower() == self.positive_class.lower():
                    classification = self.positive_class
                    break
                elif word.lower() == self.negative_class.lower():
                    classification = self.negative_class
                    break
            
            return {
                "classification": classification,
                "explanation": output
            }

    def get_llm_node(self):
        """Node that only handles the LLM request."""
        model = self.model
        prompt_templates = self.get_prompt_templates()

        async def llm_request(state):
            if isinstance(state, dict):
                state = self.GraphState(**state)
            
            # Build messages from chat history or initial prompt if empty
            if not state.chat_history:
                messages = [
                    prompt_templates[0].messages[0],
                    prompt_templates[0].messages[1].format(**state.model_dump())
                ]
            else:
                messages = state.chat_history

            chat_prompt = ChatPromptTemplate.from_messages(messages)
            completion = await model.ainvoke(chat_prompt.format_prompt().to_messages())
            
            return {**state.model_dump(), "completion": completion.content}

        return llm_request

    def get_parser_node(self):
        """Node that handles parsing the completion."""
        parser = self.ClassificationOutputParser(
            positive_class=self.parameters.positive_class,
            negative_class=self.parameters.negative_class,
            parse_from_start=self.parameters.parse_from_start
        )

        async def parse_completion(state):
            if isinstance(state, dict):
                state = self.GraphState(**state)
            result = parser.parse(state.completion)
            return {**state.model_dump(), **result}

        return parse_completion

    def get_retry_node(self):
        """Node that prepares for retry by updating chat history."""
        async def prepare_retry(state):
            if isinstance(state, dict):
                state = self.GraphState(**state)
            
            retry_message = HumanMessage(content=(
                f"You responded with an invalid classification. "
                f"Please classify as either '{self.parameters.positive_class}' or "
                f"'{self.parameters.negative_class}'. This is attempt {state.retry_count + 1} "
                f"of {self.parameters.maximum_retry_count}."
            ))
            
            return {**state.model_dump(), 
                    "chat_history": [*state.chat_history, retry_message],
                    "retry_count": state.retry_count + 1}

        return prepare_retry

    def should_retry(self, state):
        """Determines whether to retry, end, or proceed based on state."""
        if state.classification is not None:
            return "end"
        if state.retry_count >= self.parameters.maximum_retry_count:
            return "max_retries"
        return "retry"

    def get_max_retries_node(self):
        """Node that handles the case when max retries are reached."""
        async def handle_max_retries(state):
            if isinstance(state, dict):
                state = self.GraphState(**state)
            
            return {**state.model_dump(), 
                    "classification": "unknown",
                    "explanation": "Maximum retries reached"}

        return handle_max_retries

    def add_core_nodes(self, workflow: StateGraph) -> StateGraph:
        # Add all nodes
        workflow.add_node("llm_request", self.get_llm_node())
        workflow.add_node("parse", self.get_parser_node())
        workflow.add_node("retry", self.get_retry_node())
        workflow.add_node("max_retries", self.get_max_retries_node())

        # Add conditional edges
        workflow.add_conditional_edges(
            "parse",
            self.should_retry,
            {
                "retry": "retry",
                "end": "__end__",
                "max_retries": "max_retries"
            }
        )
        
        # Add regular edges
        workflow.add_edge("llm_request", "parse")
        workflow.add_edge("retry", "llm_request")
        workflow.add_edge("max_retries", "__end__")
        
        # Set entry point
        workflow.set_entry_point("llm_request")
        
        return workflow