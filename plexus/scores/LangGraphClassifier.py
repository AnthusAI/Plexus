from enum import Enum
from typing import List, TypedDict, Dict, Any, Optional, Union
from pydantic import BaseModel, Field, ValidationError
from langsmith import Client
from rapidfuzz import fuzz, process

from plexus.CustomLogging import logging
from plexus.scores.LangGraphScore import LangGraphScore

from openai_cost_calculator.openai_cost_calculator import calculate_cost

from langgraph.graph import StateGraph, END

from langchain_core.messages import AIMessage
from langchain_core.prompts import PromptTemplate
from langchain.schema import BaseOutputParser, AIMessage
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
    
    def parse(self, output: str) -> Dict[str, Any]:
        # Remove any leading/trailing whitespace and quotes
        output = output.strip().strip('"')
        
        # Remove the prefix if it exists
        prefix = "Quote:"
        if output.startswith(prefix):
            output = output[len(prefix):].strip()
        
        output = output.strip('"\'')
        
        logging.info(f"Cleaned output: {output}")
        
        # Use RapidFuzz to find the best match
        result = process.extractOne(
            output, 
            [self.text[i:i+len(output)] for i in range(len(self.text) - len(output) + 1)],
            scorer=fuzz.partial_ratio,
            score_cutoff=70  # Lowered the score cutoff
        )
        
        if result:
            match, score, start_index = result
            logging.info(f"Best match found with score {score} at index {start_index}")
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

    def __init__(self, **parameters):
        super().__init__(**parameters)
        self.workflow = None
        self.total_tokens = 0
        self.total_cost = 0
        self.current_state = None
        self.langsmith_client = Client()
        self.llm = self._initialize_model()
        self.llm_with_retry = self.llm.with_retry(
            retry_if_exception_type=(Exception,),
            wait_exponential_jitter=True,
            stop_after_attempt=3
        ).with_config(
            callbacks=[self.token_counter],
            max_tokens=self.parameters.max_tokens
        )
        
        self.initialize_validation_workflow()

    def initialize_validation_workflow(self):
        workflow = StateGraph(GraphState)

        # Add nodes for each operation
        workflow.add_node("agent_presented_rate_quote", self.agent_presented_rate_quote)
        workflow.add_node("initial_slice", self.initial_slice)
        workflow.add_node("rate_quote_slice", self.rate_quote_slice)
        workflow.add_node("examine", self._examine)
        workflow.add_node("classify", self._classify)
        workflow.add_node("set_na_output", self.set_na_output)

        # Define the routing function
        def route_based_on_rate_quote(x: dict) -> str:
            return "initial_slice" if x["agent_presented_rate_quote"] == YesOrNo.YES else "set_na_output"

        # Add edges with conditional logic
        workflow.add_conditional_edges(
            "agent_presented_rate_quote",
            route_based_on_rate_quote
        )
        workflow.add_edge("initial_slice", "rate_quote_slice")
        workflow.add_edge("rate_quote_slice", "examine")
        workflow.add_edge("examine", "classify")
        workflow.add_edge("classify", END)
        workflow.add_edge("set_na_output", END)

        workflow.set_entry_point("agent_presented_rate_quote")

        self.workflow = workflow.compile()
        self.generate_graph_visualization()

    def set_na_output(self, state: GraphState) -> GraphState:
        state["classification"] = "NA"
        state["is_not_empty"] = False
        state["explanation"] = "The agent did not present a rate quote."
        return state

    def agent_presented_rate_quote(self, state: GraphState) -> GraphState:
        score_parser = EnumOutputParser(enum=YesOrNo)

        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an AI assistant tasked with analyzing a transcript of a conversation between an insurance agent and a customer. Your job is to determine if the agent has presented a rate quote to the customer."),
            ("human", """Here's a transcript of a conversation between an insurance agent and a customer:

<transcript>
{transcript}
</transcript>

Before the agent can move to the application process, the agent must have presented rate quotes to the customer. This typically involves presenting a monthly price for coverage. Did the agent present specific rate quotes?
Provide your answer as either "Yes" or "No".
""")
        ])
        chain = prompt | self.llm_with_retry | score_parser

        result = chain.invoke({"transcript": state['transcript']})

        state["agent_presented_rate_quote"] = result
        return state

    def _slice_transcript(self, state: GraphState, system_message: str, human_message: str, slice_key: str) -> GraphState:
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_message),
            ("human", human_message)
        ])

        chain = prompt | self.llm_with_retry | CustomOutputParser(text=state['transcript'])
        result = chain.invoke({"transcript": state['transcript']})
        state[slice_key] = result['input_text_after_slice']
        state['transcript'] = result['input_text_after_slice']  # Update the main transcript
        logging.info(f"{slice_key.capitalize()}: {state[slice_key][:100]}...")
        return state

    def initial_slice(self, state: GraphState) -> GraphState:
        system_message = "You are an AI assistant tasked with analyzing a transcript of a conversation between an insurance agent and a customer. Your job is to identify the portion of the conversation where the agent asks the last health and lifestyle question prior to presenting the rate quote."
        human_message = """Here's a transcript of a conversation between an insurance agent and a customer. Please follow these steps:

1. Identify where the agent asks the last health and lifestyle question.
2. Provide a short, exact quote (1-2 sentences) where the agent starts this section of questions.
3. The quote should be word-for-word from the transcript.

<transcript>
{transcript}
</transcript>

Remember, I need a short, exact quote from the transcript, not a summary or paraphrase. Start your response with 'Quote:'"""
        return self._slice_transcript(state, system_message, human_message, 'health_questions_slice')

    def rate_quote_slice(self, state: GraphState) -> GraphState:
        system_message = "You are an AI assistant tasked with analyzing a transcript of a conversation between an insurance agent and a customer. Your job is to identify the exact moment when the agent first presents rate quotes after completing all health and lifestyle questions."
        human_message = """Here's a transcript of a conversation between an insurance agent and a customer, starting from where health and lifestyle questions begin. Please follow these steps:

1. Carefully identify where the agent completes asking ALL health and lifestyle questions.
2. After that point, find the first instance where the agent presents specific rate quotes to the customer, given as a monthly or yearly cost.
3. Provide a short, exact quote (1-2 sentences) where the agent first presents these rate quotes. The quote should be word-for-word from the transcript, including the specific cost mentioned.

<transcript>
{transcript}
</transcript>

Remember, I need a short, exact quote from the transcript, not a summary or paraphrase. Only consider rate quotes that come after ALL health and lifestyle questions and are presented as a monthly or yearly cost. Start your response with 'Quote:'"""
        return self._slice_transcript(state, system_message, human_message, 'rate_quote_slice')

    def _examine(self, state: GraphState) -> GraphState:
        logging.info(f"Examining state: {state}")
        
        examine_input = state['transcript']
        
        logging.info(f"Length of examine input: {len(examine_input)}")
        logging.info(f"First 100 characters of examine input: {examine_input[:100]}")

        prompt = PromptTemplate(
            template="""
Analyze the following transcript excerpt, which begins immediately after the agent has presented rate quotes to the customer:

<transcript>
{transcript}
</transcript>

Question: Did the agent effectively guide the conversation towards closing the deal immediately after presenting the rates?

Context: 
- The agent should assume the customer wants to apply today and guide them into the application process without directly asking for permission.
- This should occur immediately following the rate presentation.
- The agent should use a closing technique that assumes the customer is ready to proceed.

Qualifying examples of effective guidance include:
1. "So the next step is to get you approved. I just need to ask a few more questions from the carrier and we can get that started, it usually takes 1-2 months for the approval process."
2. "ABC carrier does a phone application, so I'll just get a little more info from you and then get you transferred right over to one of our enrollers who will go through that with you."
3. "XYZ carrier uses an online application, so I'll just need to ask a few more questions and then I can have them email the application to you, then you just click the link in the email and fill it out."

Examples that do NOT qualify as effective guidance:
1. "Would you want to proceed with that?"
2. "Do you want to try and get approved for that?"
3. "Do you have time to do the phone interview today?"
4. "Do you want to submit an application?"

Please analyze the transcript and determine if the agent effectively guided the conversation towards closing the deal without explicitly asking for permission. Provide a detailed 2-4 sentence explanation of your reasoning, citing specific examples from the transcript where possible.

Focus on:
1. The agent's immediate actions after presenting the rates.
2. Any language that assumes the customer's readiness to proceed.
3. Specific steps mentioned for moving forward with the application or enrollment process.
4. Absence of direct questions seeking permission.

Your analysis should clearly state whether the agent did or did not effectively guide the conversation towards closing the deal, based on the criteria provided.
"""
        )

        score_chain = prompt | self.llm_with_retry

        state["reasoning"] = score_chain.invoke(
            {
                "transcript": state['transcript']
            }
        )
        return state

    def _classify(self, state: GraphState) -> GraphState:
        score_parser = EnumOutputParser(enum=YesOrNo)

        # Extract only the content from the reasoning if it's an AIMessage
        reasoning_content = state["reasoning"].content if isinstance(state["reasoning"], AIMessage) else state["reasoning"]

        prompt = PromptTemplate(
            template="""

Based on the following reasoning about whether the agent proceeded with the application process without explicitly asking for permission:

<reasoning>
{reasoning}
</reasoning>

Does this reasoning indicate that the agent proceeded without explicitly asking for permission?
Provide your answer as either "Yes" or "No".
""",
            input_variables=["reasoning"]
        )

        score_chain = prompt | self.llm_with_retry | score_parser

        classification = score_chain.invoke({"reasoning": reasoning_content})

        state["classification"] = classification
        state["is_not_empty"] = classification == YesOrNo.YES
        
        # Ensure the explanation is a string
        state["explanation"] = reasoning_content
        
        return state

    def predict(self, model_input: LangGraphScore.ModelInput) -> LangGraphScore.ModelOutput:
        logging.info(f"Predict method input: {model_input}")
        
        initial_state = GraphState(
            transcript=model_input.transcript,
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
        final_state = self.workflow.invoke(initial_state, config={"callbacks": [self.openai_callback if isinstance(self.llm, (AzureChatOpenAI, ChatOpenAI)) else self.token_counter]})
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

        return LangGraphScore.ModelOutput(
            score=score,
            explanation=explanation
        )

    class ModelInput(LangGraphScore.ModelInput):
        pass