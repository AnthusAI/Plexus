import re
from enum import Enum
from typing import TypedDict, Dict, Any
from pydantic import Field
from rapidfuzz import fuzz, process
import nltk
from nltk.tokenize import sent_tokenize

from plexus.CustomLogging import logging
from plexus.scores.LangGraphScore import LangGraphScore

from openai_cost_calculator.openai_cost_calculator import calculate_cost

from langgraph.graph import StateGraph, END

from langchain_core.messages import AIMessage
from langchain_core.prompts import PromptTemplate
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import BaseOutputParser

from langchain_core.exceptions import OutputParserException

from langchain_openai import AzureChatOpenAI, ChatOpenAI
from langchain.globals import set_debug, set_verbose
from langchain.output_parsers import EnumOutputParser

set_debug(True)
set_verbose(True)

class GraphState(TypedDict):
    text: str
    is_not_empty: bool
    explanation: str
    input_text_after_slice: str
    reasoning: str
    classification: str

class CustomOutputParser(BaseOutputParser[dict]):
    FUZZY_MATCH_SCORE_CUTOFF = 70
    text: str = Field(...)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        nltk.download('punkt', quiet=True)  # Download the punkt tokenizer data

    @property
    def _type(self) -> str:
        return "custom_output_parser"
    
    def parse(self, output: str) -> Dict[str, Any]:
        # Remove any leading/trailing whitespace and quotes
        output = output.strip().strip('"')
        
        # Remove the prefix if it exists
        prefix = "Quote:"
        if output.startswith(prefix):
            output = output[len(prefix):].strip()
        
        output = output.strip('"\'')
        
        logging.info(f"Cleaned output: {output}")
        
        # Tokenize the text into sentences
        sentences = sent_tokenize(self.text)
        
        # Use RapidFuzz to find the best match among sentences
        result = process.extractOne(
            output,
            sentences,
            scorer=fuzz.partial_ratio,
            score_cutoff=self.FUZZY_MATCH_SCORE_CUTOFF
        )
        
        if result:
            match, score, index = result
            logging.info(f"Best match found with score {score} at sentence index {index}")
            start_index = self.text.index(match)
            input_text_after_slice = self.text[start_index:]
        else:
            logging.warning(f"No exact match found for output: '{output}'. Using the entire remaining text.")
            input_text_after_slice = self.text

        logging.info(f"Length of input_text_after_slice: {len(input_text_after_slice)}")
        logging.info(f"First 100 characters of input_text_after_slice: {input_text_after_slice[:100]}")

        return {
            "input_text_after_slice": input_text_after_slice
        }

class YesOrNo(Enum):
    YES = "Yes"
    NO = "No"

class LangGraphClassifier(LangGraphScore):
        
    class Parameters(LangGraphScore.Parameters):
        label: str = ""
        prompt: str = ""
        max_tokens: int = 300
        prompts: Dict[str, Any] = Field(default_factory=dict)
        model_overrides: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

    def __init__(self, **parameters):
        super().__init__(**parameters)
        self.workflow = None
        self.total_tokens = 0
        self.total_cost = 0
        self.current_state = None
        self.model_overrides = parameters.get('model_overrides', {})
        
        self.initialize_validation_workflow()

    def initialize_validation_workflow(self):
        workflow = StateGraph(GraphState)

        workflow.add_node("check_rate_quote_presented", self.check_rate_quote_presented)
        workflow.add_node("slice_health_questions", self.slice_health_questions)
        workflow.add_node("slice_rate_quote", self.slice_rate_quote)
        workflow.add_node("analyze_main_question", self.analyze_main_question)
        workflow.add_node("classify_reasoning_as_yes_or_no", self.classify_reasoning_as_yes_or_no)
        workflow.add_node("set_na_output", self.set_na_output)

        def route_to_next_step_or_end_with_na(x: dict) -> str:
            return "slice_health_questions" if x["rate_quote_presented"] == YesOrNo.YES else "set_na_output"

        workflow.add_conditional_edges(
            "check_rate_quote_presented",
            route_to_next_step_or_end_with_na
        )
        
        workflow.set_entry_point("check_rate_quote_presented")

        workflow.add_edge("slice_health_questions", "slice_rate_quote")
        workflow.add_edge("slice_rate_quote", "analyze_main_question")
        workflow.add_edge("analyze_main_question", "classify_reasoning_as_yes_or_no")
        workflow.add_edge("classify_reasoning_as_yes_or_no", END)
        workflow.add_edge("set_na_output", END)

        self.workflow = workflow.compile()
        self.generate_graph_visualization()

    def set_na_output(self, state: GraphState) -> GraphState:
        state["classification"] = "NA"
        state["is_not_empty"] = False
        state["explanation"] = "The agent did not present a rate quote."
        return state

    def check_rate_quote_presented(self, state: GraphState) -> GraphState:
        score_parser = EnumOutputParser(enum=YesOrNo)

        prompt = ChatPromptTemplate.from_messages([
            ("system", self.parameters.prompts["check_rate_quote_presented"]["system"]),
            ("human", self.parameters.prompts["check_rate_quote_presented"]["human"])
        ])
        
        # Use a specific model for this step if defined in model_overrides
        model = self._initialize_model("check_rate_quote_presented")
        chain = prompt | model

        result = chain.invoke({"text": state['text']})

        def fallback_parser(response: str) -> YesOrNo:
            response_lower = response.lower()
            if "yes" in response_lower:
                return YesOrNo.YES
            elif "no" in response_lower:
                return YesOrNo.NO
            else:
                raise ValueError(f"Could not extract Yes or No from: {response}")

        # Extract the content from the AIMessage
        result_content = result.content if isinstance(result, AIMessage) else result

        try:
            parsed_result = score_parser.parse(result_content)
        except OutputParserException:
            try:
                parsed_result = fallback_parser(result_content)
            except ValueError as e:
                logging.warning(f"Fallback parser failed: {str(e)}")
                # Default to NO if both parsing attempts fail
                parsed_result = YesOrNo.NO

        state["rate_quote_presented"] = parsed_result
        return state

    def _slice_text(self, state: GraphState, prompt_key: str, slice_key: str) -> GraphState:
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.parameters.prompts[prompt_key]["system"]),
            ("human", self.parameters.prompts[prompt_key]["human"])
        ])

        # Use a specific model for this step if defined in model_overrides
        model = self._initialize_model(prompt_key)
        chain = prompt | model | CustomOutputParser(text=state['text'])
        result = chain.invoke({"text": state['text']})
        state[slice_key] = result['input_text_after_slice']
        state['text'] = result['input_text_after_slice']  # Update the main text
        logging.info(f"{slice_key.capitalize()}: {state[slice_key][:100]}...")
        return state

    def slice_health_questions(self, state: GraphState) -> GraphState:
        return self._slice_text(state, "slice_health_questions", 'health_questions_slice')

    def slice_rate_quote(self, state: GraphState) -> GraphState:
        return self._slice_text(state, "slice_rate_quote", 'rate_quote_slice')

    def analyze_main_question(self, state: GraphState) -> GraphState:
        logging.info(f"Examining state: {state}")
        
        examine_input = state['text']
        
        logging.info(f"Length of examine input: {len(examine_input)}")
        logging.info(f"First 100 characters of examine input: {examine_input[:100]}")

        prompt = PromptTemplate(
            template=self.parameters.prompts["analyze_main_question"]["template"]
        )

        score_chain = prompt | self.model

        state["reasoning"] = score_chain.invoke(
            {
                "text": state['text']
            }
        )
        return state

    def classify_reasoning_as_yes_or_no(self, state: GraphState) -> GraphState:
        reasoning_content = state["reasoning"].content if isinstance(state["reasoning"], AIMessage) else state["reasoning"]

        prompt = PromptTemplate(
            template=self.parameters.prompts["classify_reasoning_as_yes_or_no"]["template"],
            input_variables=["reasoning"]
        )

        # Use a specific model for this step if defined in model_overrides
        model = self._initialize_model("classify_reasoning_as_yes_or_no")
        score_chain = prompt | model

        result = score_chain.invoke({"reasoning": reasoning_content})

        # Extract the content from the AIMessage if it's an AIMessage object
        result_content = result.content if isinstance(result, AIMessage) else result

        # Clean up the result and attempt to parse it
        cleaned_result = result_content.strip().lower().rstrip('.').strip()
        if cleaned_result == "yes":
            classification = YesOrNo.YES
        elif cleaned_result == "no":
            classification = YesOrNo.NO
        else:
            logging.warning(f"Unexpected response: {result_content}. Defaulting to NO.")
            classification = YesOrNo.NO

        state["classification"] = classification
        state["is_not_empty"] = classification == YesOrNo.YES
        state["explanation"] = reasoning_content
        
        return state

    def predict(self, context, model_input: LangGraphScore.Input) -> LangGraphScore.Result:
        logging.info(f"Predict method input: {model_input}")
        
        initial_state = GraphState(
            text=model_input.text,
            is_not_empty=False,
            explanation="",
            reasoning="",
            health_questions_slice="",
            rate_quote_slice=""
        )
        
        self.current_state = initial_state
        logging.info(f"Initial state keys: {initial_state.keys()}")

        self.reset_token_usage()

        logging.info("Starting workflow invocation")
        final_state = self.workflow.invoke(initial_state, config={"callbacks": [self.openai_callback if isinstance(self.model, (AzureChatOpenAI, ChatOpenAI)) else self.token_counter]})
        logging.info("Workflow invocation completed")
        
        logging.info(f"Final state keys: {final_state.keys()}")

        validation_result = final_state['classification']
        if validation_result == "NA":
            score = "NA"
        else:
            score = "Yes" if final_state['is_not_empty'] else "No"
        
        # Extract the content from the AIMessage if it's an AIMessage object
        explanation = final_state['explanation'].content if isinstance(final_state['explanation'], AIMessage) else final_state['explanation']
        
        token_usage = self.get_token_usage()
        
        logging.info(f"Final token usage - Total LLM calls: {token_usage['successful_requests']}")
        logging.info(f"Final token usage - Total tokens used: {token_usage['total_tokens']}")
        logging.info(f"Final token usage - Prompt tokens: {token_usage['prompt_tokens']}")
        logging.info(f"Final token usage - Completion tokens: {token_usage['completion_tokens']}")
        
        logging.info(f"Parameters: {self.parameters}")

        try:
            cost_info = calculate_cost(
                model_name=self.parameters.model_name,
                input_tokens=token_usage['prompt_tokens'],
                output_tokens=token_usage['completion_tokens']
            )
            total_cost = cost_info['total_cost']
            logging.info(f"Total cost: ${total_cost:.6f}")
        except ValueError as e:
            logging.error(f"Could not calculate cost: {str(e)}")

        return [
            LangGraphScore.Result(
                name        = self.parameters.score_name,
                value       = validation_result,
                explanation = explanation
            )
        ]

    class Input(LangGraphScore.Input):
        pass