import mlflow
from enum import Enum
from typing import List, Union, TypedDict, Dict, Any
from pydantic import BaseModel, Field
from langsmith import Client
from dataclasses import dataclass, field
import re
from difflib import SequenceMatcher

from plexus.CustomLogging import logging
from plexus.scores.LangGraphScore import LangGraphScore

from openai_cost_calculator.openai_cost_calculator import calculate_cost

from langgraph.graph import StateGraph, END

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import PromptTemplate
from langchain.schema import BaseOutputParser, OutputParserException, AIMessage, PromptValue
from langchain_core.prompts import ChatPromptTemplate
from langchain.output_parsers import EnumOutputParser

from langchain_openai import AzureChatOpenAI, ChatOpenAI
from langchain.globals import set_debug

set_debug(True)

class GraphState(TypedDict):
    transcript: str
    is_not_empty: bool
    explanation: str
    input_text_after_slice: str
    reasoning: str
    classification: str

class CustomOutputParser(BaseOutputParser[dict]):
    text: str = Field(...)

    @property
    def _type(self) -> str:
        return "custom_output_parser"

    def get_format_instructions(self):
        return "Provide an exact quote from the transcript when the agent first presented rate quotes after the health and lifestyle questions."

    def parse(self, output: str) -> Dict[str, Any]:
        # Remove any leading/trailing whitespace and quotes
        output = output.strip().strip('"')
        
        # Remove the prefix and extract the quote
        prefix = "The agent first presented rate quotes after the health and lifestyle questions with this exact quote from the transcript:"
        if output.startswith(prefix):
            output = output[len(prefix):].strip()
        
        output = output.strip('"\'')
        
        logging.info(f"Cleaned output: {output}")
        logging.info(f"Text length: {len(self.text)}")
        logging.info(f"First 100 characters of text: {self.text[:100]}")
        
        # Try to find an exact match first
        if output in self.text:
            start_index = self.text.index(output)
            logging.info(f"Exact match found at index {start_index}")
        else:
            # If no exact match, find the most similar substring
            best_match = ""
            best_ratio = 0
            for i in range(len(self.text) - len(output) + 1):
                substring = self.text[i:i+len(output)]
                ratio = SequenceMatcher(None, output, substring).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_match = substring
            
            logging.info(f"Best match ratio: {best_ratio}")
            logging.info(f"Best match: {best_match}")
            
            if best_ratio > 0.7:  # Lowered the threshold
                start_index = self.text.index(best_match)
                logging.info(f"Similar match found at index {start_index}")
            else:
                logging.error(f"No similar match found for output: '{output}'")
                raise OutputParserException(f"No similar match found for output: '{output}'")

        # Include the quote and everything after it
        input_text_after_slice = self.text[start_index:]
        
        logging.info(f"Length of input_text_after_slice: {len(input_text_after_slice)}")
        logging.info(f"First 100 characters of input_text_after_slice: {input_text_after_slice[:100]}")

        return {
            "input_text_after_slice": input_text_after_slice
        }

@dataclass
class ValidationState:
    transcript: str
    current_step: str = ""
    validation_result: str = "Unknown"
    explanation: str = ""
    messages: List[Union[HumanMessage, AIMessage]] = field(default_factory=list)

    def __repr__(self):
        return (
            f"ValidationState(transcript='{self.transcript}', "
            f"current_step='{self.current_step}', "
            f"validation_result='{self.validation_result}', "
            f"explanation='{self.explanation}', "
            f"messages={self.messages})"
        )

class YesOrNo(Enum):
    YES = "Yes"
    NO = "No"

class CustomYesNoParser:
    def parse(self, text: str) -> YesOrNo:
        lowered = text.lower().strip()
        if lowered.startswith("yes"):
            return YesOrNo.YES
        elif lowered.startswith("no"):
            return YesOrNo.NO
        else:
            raise OutputParserException(f"Expected 'Yes' or 'No', got: {text}")

class LangGraphClassifier(LangGraphScore):
    class Parameters(LangGraphScore.Parameters):
        label: str = ""
        prompt: str = ""
        agent_type: str = "langgraph"

    def __init__(self, **parameters):
        super().__init__(**parameters)
        self.workflow = None
        self.total_tokens = 0
        self.total_cost = 0
        self.current_state = None
        self.langsmith_client = Client()
        self.initialize_validation_workflow()

    def initialize_validation_workflow(self):
        self.llm = self._initialize_model()
        self.llm_with_retry = self.llm.with_retry(
            retry_if_exception_type=(Exception,),
            wait_exponential_jitter=True,
            stop_after_attempt=3
        ).with_config(callbacks=[self.token_counter])
        
        self.workflow = self._create_langgraph_workflow()
        
        mlflow.log_param("model_provider", self.parameters.model_provider)
        mlflow.log_param("model_name", self.parameters.model_name)
        mlflow.log_param("model_region", self.parameters.model_region)
        mlflow.log_param("temperature", self.parameters.temperature)
        mlflow.log_param("max_tokens", self.parameters.max_tokens)
        mlflow.log_param("prompt", self.parameters.prompt)
        mlflow.log_param("label", self.parameters.label)

        self.generate_graph_visualization()

    def _create_langgraph_workflow(self):
        workflow = StateGraph(GraphState)

        workflow.add_node("slice", self._slice)
        workflow.add_node("examine", self._examine)
        workflow.add_node("classify", self._classify)

        workflow.add_edge("slice", "examine")
        workflow.add_edge("examine", "classify")
        workflow.add_edge("classify", END)

        workflow.set_entry_point("slice")

        return workflow.compile()

    def _slice(self, state: GraphState) -> GraphState:
        text = state['transcript']

        prompt_template = ChatPromptTemplate.from_messages([
            ("system", "You are an AI assistant tasked with analyzing a transcript of a conversation between an insurance agent and a customer. Your job is to identify the exact moment when the agent first presents rate quotes after completing health and lifestyle questions."),
            ("human", "Here's a transcript of a conversation between an insurance agent and a customer. Please follow these steps:"),
            ("human", "1. Identify where the agent completes asking health and lifestyle questions."),
            ("human", "2. After that point, find the first instance where the agent presents specific rate quotes to the customer."),
            ("human", "3. Provide the exact quote where the agent first presents these rate quotes. The quote should be word-for-word from the transcript, including any numbers or specific details mentioned."),
            ("human", "Transcript: {text}"),
            ("human", "Remember, I need the exact quote from the transcript, not a summary or paraphrase. Only consider rate quotes that come after the health and lifestyle questions. Start your response with 'The agent first presented rate quotes after the health and lifestyle questions with this exact quote from the transcript:'")
        ])

        custom_parser = CustomOutputParser(text=text)
        chain = prompt_template | self.llm_with_retry | custom_parser

        slices = chain.invoke({"text": text})
        state.update(slices)  # This will set state['input_text_after_slice']
        
        # Remove the full transcript from the state to ensure we're only working with the sliced portion
        state.pop('transcript', None)
        
        return state

    def _examine(self, state: GraphState) -> GraphState:
        logging.info(f"Examining state: {state}")
        logging.info(f"Length of input_text_after_slice: {len(state['input_text_after_slice'])}")
        logging.info(f"First 100 characters of input_text_after_slice: {state['input_text_after_slice'][:100]}")

        prompt = PromptTemplate(
            template="""
    This is the part of the call after the agent presented rate quotes.
    <after>
    {input_text_after_slice}
    </after>

    After presenting the rates, the agent should proceed with the application process without explicitly asking the customer for permission to do so. The agent should use language and techniques that assume the customer is ready to move forward. This can include, but is not limited to:

    1. Guiding the conversation towards the next steps in the application process.
    2. Mentioning enrollment or moving forward with the policy.
    3. Discussing the approval process or getting the customer approved.
    4. Talking about sending or completing application forms.
    5. Using phrases that imply continuation of the process without directly asking if the customer wants to proceed.

    The key is that the agent should not ask a direct question like "Do you want to apply?" or "Shall we proceed with the application?" Instead, they should use language that assumes the customer's readiness to move forward.

    Based on the transcript provided, did the agent continue to proceed with the application process without explicitly asking for permission?

    Please provide a detailed explanation of your reasoning, citing specific examples from the transcript where possible.
    """
        )

        score_chain = prompt | self.llm_with_retry

        state["reasoning"] = score_chain.invoke(
            {
                "input_text_after_slice": state['input_text_after_slice']
            }
        )
        return state

    def _classify(self, state: GraphState) -> GraphState:
        class YesOrNo(Enum):
            YES = "Yes"
            NO = "No"

        score_parser = EnumOutputParser(enum=YesOrNo)

        prompt = PromptTemplate(
            template="""
    {format_instructions}

    Based on the following reasoning about whether the agent proceeded with the application process without explicitly asking for permission:

    <reasoning>
    {reasoning}
    </reasoning>

    Does this reasoning indicate that the agent proceeded without explicitly asking for permission?
    Provide your answer as either "Yes" or "No".
    """,
            input_variables=["reasoning"],
            partial_variables={"format_instructions": score_parser.get_format_instructions()},
        )

        score_chain = prompt | self.llm_with_retry | score_parser

        classification = score_chain.invoke({"reasoning": state["reasoning"]})

        state["classification"] = classification
        state["is_not_empty"] = classification == YesOrNo.YES
        
        # Ensure the explanation is a string
        if isinstance(state["reasoning"], AIMessage):
            state["explanation"] = state["reasoning"].content
        else:
            state["explanation"] = str(state["reasoning"])
        
        return state

    def predict(self, model_input: LangGraphScore.ModelInput) -> LangGraphScore.ModelOutput:
        logging.info(f"Predict method input: {model_input}")
        
        initial_state = GraphState(
            transcript=model_input.transcript,
            input_text_after_slice="",
            is_not_empty=False,
            explanation=""
        )
        
        self.current_state = initial_state
        logging.info(f"Initial state: {initial_state}")

        self.reset_token_usage()

        logging.info("Starting workflow invocation")
        final_state = self.workflow.invoke(initial_state, config={"callbacks": [self.openai_callback if isinstance(self.llm, (AzureChatOpenAI, ChatOpenAI)) else self.token_counter]})
        logging.info("Workflow invocation completed")
        
        logging.info(f"Final state: {final_state}")

        validation_result = "Yes" if final_state['is_not_empty'] else "No"
        
        # Extract the content from the AIMessage if it's an AIMessage object
        explanation = final_state['explanation'].content if isinstance(final_state['explanation'], AIMessage) else final_state['explanation']
        
        token_usage = self.get_token_usage()
        
        logging.info(f"Final token usage - Total LLM calls: {token_usage['successful_requests']}")
        logging.info(f"Final token usage - Total tokens used: {token_usage['total_tokens']}")
        logging.info(f"Final token usage - Prompt tokens: {token_usage['prompt_tokens']}")
        logging.info(f"Final token usage - Completion tokens: {token_usage['completion_tokens']}")
        logging.info(f"Parameters: {self.parameters}")

        mlflow.log_metric("final_total_tokens", token_usage['total_tokens'])
        mlflow.log_metric("final_prompt_tokens", token_usage['prompt_tokens'])
        mlflow.log_metric("final_completion_tokens", token_usage['completion_tokens'])

        try:
            cost_info = calculate_cost(
                model_name=self.parameters.model_name,
                input_tokens=token_usage['prompt_tokens'],
                output_tokens=token_usage['completion_tokens']
            )
            total_cost = cost_info['total_cost']
            logging.info(f"Total cost: ${total_cost:.6f}")
            mlflow.log_metric("final_total_cost", float(total_cost))
        except ValueError as e:
            logging.error(f"Could not calculate cost: {str(e)}")

        return LangGraphScore.ModelOutput(
            score=validation_result,
            explanation=explanation
        )

    class ModelInput(LangGraphScore.ModelInput):
        pass