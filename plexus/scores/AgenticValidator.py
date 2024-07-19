from typing import Dict, List, Any, Literal, Optional, Union
from pydantic import ConfigDict, Field, validator
from plexus.CustomLogging import logging
from plexus.scores.LangGraphScore import LangGraphScore

from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import PromptTemplate
from langchain_core.tools import Tool
from langchain.memory import SimpleMemory

from langchain.agents import AgentExecutor
from langchain.agents.format_scratchpad import format_log_to_str
from langchain.agents.output_parsers import ReActSingleInputOutputParser
from langchain.tools.render import render_text_description

from langgraph.graph import StateGraph, END

from langchain.globals import set_debug
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.runnables import RunnablePassthrough

set_debug(True)

from langchain_aws import ChatBedrock
from langchain_openai import AzureChatOpenAI
from langchain_google_vertexai import ChatVertexAI

from openai_cost_calculator.openai_cost_calculator import calculate_cost

import mlflow
import math

from langsmith import Client
from dataclasses import dataclass, field

@dataclass
class ValidationState:
    """
    Represents the state of the validation process at any given point.

    This class encapsulates all the information needed to track the progress
    and results of the validation workflow.

    Attributes:
        transcript (str): The transcript being validated.
        metadata (Dict[str, str]): Metadata about the education claim being validated.
        current_step (str): The current step in the validation process.
        validation_result (str): Result of the degree validation.
        explanation (str): Detailed explanation of the validation result.
        messages (List[Union[HumanMessage, AIMessage]]): History of messages in the validation process.
        has_dependency (bool): Indicates whether there is a dependency prompt.
    """

    transcript: str
    metadata: Dict[str, str]
    current_step: str = ""
    validation_result: str = "Unknown"
    explanation: str = ""
    messages: List[Union[HumanMessage, AIMessage]] = field(default_factory=list)
    has_dependency: bool = False

    def __repr__(self):
        """
        Return a string representation of the ValidationState.

        Returns:
            str: A string representation of the ValidationState instance.
        """
        return (
            f"ValidationState(transcript='{self.transcript}', "
            f"metadata={self.metadata}, "
            f"current_step='{self.current_step}', "
            f"validation_result='{self.validation_result}', "
            f"explanation='{self.explanation}', "
            f"messages={self.messages}, "
            f"has_dependency={self.has_dependency})"
        )

class AgenticValidator(LangGraphScore):
    """
    An agentic validator that uses LangGraph and advanced LangChain components to validate education information,
    specifically for degree, using both transcript and metadata.

    This validator uses a language model to analyze transcripts and validate educational claims through a multi-step
    workflow implemented with LangGraph.
    """

    class Parameters(LangGraphScore.Parameters):
        """
        Parameters for configuring the AgenticValidator.

        Attributes:
            model_provider (Literal): The provider of the language model to use.
            model_name (Optional[str]): The specific model name to use (if applicable).
            temperature (float): The temperature setting for the language model.
            max_tokens (int): The maximum number of tokens for model output.
            label (str): The label of the metadata to validate.
            prompt (str): The custom prompt to use for validation.
            dependency (Optional[Dict[str, str]]): The dependency configuration.
        """
        model_config = ConfigDict(protected_namespaces=())
        model_provider: Literal["AzureChatOpenAI", "BedrockChat", "ChatVertexAI"] = "BedrockChat"
        model_name: Optional[str] = None
        model_region: Optional[str] = None
        temperature: float = 0.1
        max_tokens: int = 500
        label: str = ""
        prompt: str = ""
        dependency: Optional[Dict[str, str]] = None

    class ReActAgentOutputParser(ReActSingleInputOutputParser):
        def parse(self, text: str) -> Union[AgentAction, AgentFinish]:
            try:
                if "Action: Finish" in text:
                    # Extract the final answer after "Action Input:"
                    final_answer = text.split("Action Input:")[-1].strip()
                    return AgentFinish(return_values={"output": final_answer}, log=text)
                elif "Action:" in text and "Action Input:" in text:
                    action = text.split("Action:")[-1].split("\n")[0].strip()
                    action_input = text.split("Action Input:")[-1].strip()
                    return AgentAction(tool=action, tool_input=action_input, log=text)
                else:
                    raise ValueError(f"Could not parse LLM output: {text}")
            except Exception as e:
                logging.error(f"Parsing error: {e}")
                logging.error(f"Problematic text: {text}")
                raise ValueError(f"Could not parse LLM output: {text}") from e

    def __init__(self, **parameters):
        """
        Initialize the AgenticValidator with the given parameters.

        Args:
            **parameters: Keyword arguments for configuring the validator.
        """
        super().__init__(**parameters)
        self.agent = None
        self.workflow = None
        self.total_tokens = 0
        self.total_cost = 0
        self.agent_executor = None
        self.current_state = None
        self.langsmith_client = Client()
        self.dependency = self.parameters.dependency
        self.initialize_validation_workflow()

    def initialize_validation_workflow(self):
        """
        Initialize the language model and create the workflow.
        This method also logs relevant parameters to MLflow.
        """
        self.llm = self._initialize_model()
        self.llm_with_retry = self.llm.with_retry(
            retry_if_exception_type=(Exception,),
            wait_exponential_jitter=True,
            stop_after_attempt=3
        ).with_config(callbacks=[self.token_counter])
        self.workflow = self._create_workflow()
        self.agent_executor = self.create_lcel_agent()
        
        mlflow.log_param("model_provider", self.parameters.model_provider)
        mlflow.log_param("model_name", self.parameters.model_name)
        mlflow.log_param("model_region", self.parameters.model_region)
        mlflow.log_param("temperature", self.parameters.temperature)
        mlflow.log_param("max_tokens", self.parameters.max_tokens)
        mlflow.log_param("prompt", self.parameters.prompt)
        mlflow.log_param("label", self.parameters.label)

        # Generate and save the graph visualization
        self.generate_graph_visualization()

    def _initialize_model(self) -> BaseLanguageModel:
        """
        Initialize and return the appropriate language model based on the configured provider.

        Returns:
            BaseLanguageModel: The initialized language model.

        Raises:
            ValueError: If an unsupported model provider is specified.
        """
        max_tokens = self.parameters.max_tokens

        if self.parameters.model_provider == "AzureChatOpenAI":
            return AzureChatOpenAI(
                temperature=self.parameters.temperature,
                max_tokens=max_tokens
            )
        elif self.parameters.model_provider == "BedrockChat":
            model_id = self.parameters.model_name or "anthropic.claude-3-5-sonnet-20240620-v1:0"
            model_region = self.parameters.model_region or "us-east-1"
            return ChatBedrock(
                model_id=model_id,
                model_kwargs={
                    "temperature": self.parameters.temperature,
                    "max_tokens": max_tokens
                },
                region_name=model_region
            )
        elif self.parameters.model_provider == "ChatVertexAI":
            model_name = self.parameters.model_name or "gemini-1.5-flash-001"
            return ChatVertexAI(
                model=model_name,
                temperature=self.parameters.temperature,
                max_output_tokens=max_tokens
            )
        else:
            raise ValueError(f"Unsupported model provider: {self.parameters.model_provider}")

    def _create_workflow(self):
        """
        Create and return the LangGraph workflow for the validation process.

        Returns:
            StateGraph: The compiled workflow graph.
        """
        workflow = StateGraph(ValidationState)

        # Define custom start node
        BEGIN_VALIDATION = self.parameters.score_name

        # Define new "Has Dependency?" node
        HAS_DEPENDENCY = "Has Dependency?"

        # Define dependency check node
        if self.parameters.dependency and 'name' in self.parameters.dependency:
            DEPENDENCY_CHECK = self.parameters.dependency['name']
        else:
            DEPENDENCY_CHECK = "Dependency Check"

        # Add all nodes, including custom start node, new "Has Dependency?" node, and dependency check node
        workflow.add_node(BEGIN_VALIDATION, self._initialize_memory)
        workflow.add_node(HAS_DEPENDENCY, self._has_dependency_prompt)
        workflow.add_node(DEPENDENCY_CHECK, self._check_dependency)
        workflow.add_node("Run Prediction", self._validate_step)

        # Add conditional edges
        workflow.add_edge(BEGIN_VALIDATION, HAS_DEPENDENCY)
        
        workflow.add_conditional_edges(
            HAS_DEPENDENCY,
            lambda x: x.has_dependency,
            {
                True: DEPENDENCY_CHECK,
                False: "Run Prediction"
            }
        )

        workflow.add_conditional_edges(
            DEPENDENCY_CHECK,
            self._should_continue_validation,
            {
                True: "Run Prediction",
                False: END
            }
        )

        workflow.add_edge("Run Prediction", END)

        # Set the custom start node
        workflow.set_entry_point(BEGIN_VALIDATION)

        return workflow.compile()

    def _initialize_memory(self, state: ValidationState) -> ValidationState:
        """
        Initialize the agent's memory with the transcript.
        """
        self.agent_executor.memory.memories["transcript"] = state.transcript
        return state

    def _has_dependency_prompt(self, state: ValidationState) -> ValidationState:
        """
        Check if the current validation has a dependency prompt and update the state.
        """
        state.has_dependency = bool(self.parameters.dependency and self.parameters.dependency.get('prompt'))
        return state

    def _check_dependency(self, state: ValidationState) -> ValidationState:
        """
        Perform the dependency check using a direct LLM call.
        """
        self.current_state = state
        
        try:
            if not self.dependency or 'prompt' not in self.dependency:
                raise ValueError("Dependency prompt is not properly configured")
            
            prompt = self.dependency['prompt']
            
            full_prompt = f"""
            Based on the following transcript, {prompt}
            
            Transcript:
            {state.transcript}
            
            Answer with YES or NO, followed by a brief explanation.
            """
            
            response = self.llm_with_retry.invoke(full_prompt)
            
            # Use the inherited _parse_validation_result method
            validation_result, explanation = self._parse_validation_result(response.content)
            
            self.current_state.current_step = "dependency_check"
            self.current_state.validation_result = validation_result
            self.current_state.explanation = explanation
            self.current_state.messages = [
                HumanMessage(content=full_prompt),
                AIMessage(content=response.content)
            ]
            
            logging.info(f"\nDependency check result: {validation_result}")
            logging.info(f"Explanation: {explanation}")
            
        except Exception as e:
            logging.error(f"Failed to perform dependency check: {e}")
            return self._handle_validation_failure(self.current_state, "dependency_check")

        return self.current_state

    def _should_continue_validation(self, state: ValidationState) -> bool:
        """
        Determine if we should continue to the main validation step based on the dependency check result.
        """
        return state.validation_result.lower() != "no"

    def create_lcel_agent(self):
        """
        Create an LCEL-based agent for validation tasks with memory for the transcript.
        """
        tools = [
            Tool(
                name="Validate Claim",
                func=self._validate_claim,
                description="Answer the question based on the transcript stored in memory. Input should be the question to answer."
            )
        ]

        prompt = PromptTemplate.from_template(
            """You are an AI assistant tasked with validating educational claims based on the provided transcript.

            You have access to the following tools:

            {tools}

            Use the following format:

            Question: the input question you must answer
            Observation: observe the initial information provided
            Action: the action to take, should be one of [{tool_names}]
            Action Input: the input to the action
            Observation: the result of the action
            Reasoning: analyze the observations and draw conclusions
            Action: choose to either use a tool again or Finish
            Action Input: if using a tool, provide the input; if Finish, respond with YES or NO, followed by a comma and then a detailed 2-3 sentence explanation.

            Continue this process until you have enough information to provide a final answer.

            Begin!

            Question: {input}
            Observation: I have been provided with a transcript in my memory and a claim to validate.
            Action: Validate Claim
            Action Input: Analyze the transcript to find evidence supporting or refuting the claim: {input}
            {agent_scratchpad}
            """
        )

        tool_names = ", ".join([tool.name for tool in tools])
        prompt = prompt.partial(tools=render_text_description(tools), tool_names=tool_names)

        llm_with_stop = self.llm_with_retry.bind(stop=["\nObservation:", "\nHuman:", "\nQuestion:"])

        agent = (
            RunnablePassthrough.assign(
                agent_scratchpad = lambda x: format_log_to_str(x["intermediate_steps"])
            )
            | prompt
            | llm_with_stop
            | self.ReActAgentOutputParser()
        )

        return AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
            handle_parsing_errors=True,
            memory=SimpleMemory(memories={"transcript": ""}),
            callbacks=[self.token_counter]
        )

    def _validate_claim(self, input_string: str) -> str:
        """
        Validate a specific claim against the transcript stored in memory.
        This method is used as a tool by the React agent.
        """
        transcript = self.agent_executor.memory.memories.get("transcript", "")
        return f"--- Begin Transcript ---\n{transcript}\n--- End Transcript ---\n\n Question: {input_string}"

    def _validate_step(self, state: ValidationState) -> ValidationState:
        """
        Perform validation for a specific step using the React agent.
        """
        self.current_state = state
        
        try:
            logging.info(f"Metadata Contents: {self.current_state.metadata}")

            # Find all keys that match the pattern school_\d+_{label}
            matching_keys = [key for key in self.current_state.metadata.keys() 
                             if key.startswith("school_") and key.endswith(f"_{self.parameters.label}")]

            if not matching_keys:
                raise ValueError(f"No values found for label '{self.parameters.label}' in the metadata")

            # Extract all values for the matching keys, remove duplicates, and filter out None and empty values
            label_values = list(set(str(value) for key in matching_keys if (value := self.current_state.metadata.get(key)) not in (None, "", "nan")))

            if not label_values:
                raise ValueError(f"No valid values found for label '{self.parameters.label}' in the metadata")

            # Join unique values if there's more than one, otherwise use the single value
            label_value = " and ".join(label_values) if len(label_values) > 1 else label_values[0]

            logging.info(f"Extracted unique label values: {label_value}")
            
            # Use the custom prompt from the YAML file
            custom_prompt = self.parameters.prompt.format(label_value=label_value)
            
            input_string = f"Answer the following: {custom_prompt}"
            
            # Log the agent's memory before execution
            logging.info("Agent's memory before execution:")
            for key, value in self.agent_executor.memory.memories.items():
                logging.info(f"{key}: {value}")
            
            logging.info("Starting agent execution")
            result = self.agent_executor.invoke({
                "input": input_string
            })
            logging.info("Agent execution completed")
            
            logging.info(f"Agent executor result: {result}")
            logging.info(f"Token usage after agent execution: Prompt: {self.token_counter.prompt_tokens}, Completion: {self.token_counter.completion_tokens}, Total: {self.token_counter.total_tokens}")
            
            # Get the full output including all steps and observations
            full_output = result['output']
            
            # Parse the result
            validation_result, explanation = self._parse_validation_result(full_output)
            
            self.current_state.current_step = "main_validation"
            self.current_state.validation_result = validation_result
            self.current_state.explanation = explanation
            self.current_state.messages = [
                HumanMessage(content=input_string),
                AIMessage(content=full_output)
            ]
            
            logging.info(f"\nValidated main step: {validation_result}")
            logging.info(f"Explanation: {explanation}")
            
        except Exception as e:
            logging.error(f"Failed to validate main step: {e}")
            return self._handle_validation_failure(self.current_state, "main_validation")

        return self.current_state

    def _handle_validation_failure(self, state: ValidationState, step: str) -> ValidationState:
        """
        Handle the case when validation fails after all retry attempts.

        Args:
            state (ValidationState): The current validation state.
            step (str): The step that failed validation.

        Returns:
            ValidationState: The updated state after handling the failure.
        """
        state.current_step = step
        state.validation_result = "Unclear"
        state.explanation = f"{step.capitalize()}: Validation failed due to technical issues.\n\n"
        logging.info(f"\nFailed to validate {step}")
        return state

    def predict(self, model_input: LangGraphScore.ModelInput) -> LangGraphScore.ModelOutput:
        """
        Predict the validity of the education information based on the transcript and metadata.

        Args:
            model_input (LangGraphScore.ModelInput): The input containing the transcript and metadata.

        Returns:
            LangGraphScore.ModelOutput: The output containing the validation result.
        """
        logging.info(f"Predict method input: {model_input}")
        initial_state = ValidationState(
            transcript=model_input.transcript,
            metadata=model_input.metadata
        )
        self.current_state = initial_state  # Set the initial state
        logging.info(f"Initial state: {initial_state}")

        # Reset token counter before each prediction
        self.token_counter.prompt_tokens = 0
        self.token_counter.completion_tokens = 0
        self.token_counter.total_tokens = 0
        self.token_counter.llm_calls = 0

        logging.info("Starting workflow invocation")
        final_state = self.workflow.invoke(initial_state, config={"callbacks": [self.token_counter]})
        logging.info("Workflow invocation completed")
        
        logging.info(f"Token usage after workflow - Prompt: {self.token_counter.prompt_tokens}, Completion: {self.token_counter.completion_tokens}, Total: {self.token_counter.total_tokens}")

        logging.info(f"Final state: {final_state}")

        # Handle the case where final_state is an AddableValuesDict
        if isinstance(final_state, dict):
            validation_result = final_state.get('validation_result', 'Unknown')
            explanation = final_state.get('explanation', '')
        else:
            validation_result = final_state.validation_result
            explanation = final_state.explanation

        # Get the current step
        current_step = final_state.get('current_step', '') if isinstance(final_state, dict) else final_state.current_step

        logging.info(f"{current_step.capitalize()}: {validation_result}")
        logging.info(f"Explanation: {explanation}")

        # Get token usage from our counter
        prompt_tokens = self.token_counter.prompt_tokens
        completion_tokens = self.token_counter.completion_tokens
        total_tokens = self.token_counter.total_tokens
        llm_calls = self.token_counter.llm_calls

        logging.info(f"Final token usage - Total LLM calls: {llm_calls}")
        logging.info(f"Final token usage - Total tokens used: {total_tokens}")
        logging.info(f"Final token usage - Prompt tokens: {prompt_tokens}")
        logging.info(f"Final token usage - Completion tokens: {completion_tokens}")
        logging.info(f"Parameters: {self.parameters}")

        # Log token metrics
        mlflow.log_metric("final_total_tokens", total_tokens)
        mlflow.log_metric("final_prompt_tokens", prompt_tokens)
        mlflow.log_metric("final_completion_tokens", completion_tokens)

        # Calculate cost
        try:
            cost_info = calculate_cost(
                model_name=self.parameters.model_name,
                input_tokens=prompt_tokens,
                output_tokens=completion_tokens
            )
            total_cost = cost_info['total_cost']
            logging.info(f"Total cost: ${total_cost:.6f}")
            mlflow.log_metric("final_total_cost", float(total_cost))
        except ValueError as e:
            logging.error(f"Could not calculate cost: {str(e)}")

        return self.ModelOutput(
            score=validation_result,
            explanation=explanation
        )

    class ModelInput(LangGraphScore.ModelInput):
        """
        Model input containing the transcript and metadata.

        Attributes:
            metadata (Dict[str, Any]): A dictionary containing degree information.
        """
        metadata: Dict[str, Any] = Field(default_factory=dict)

        @validator('metadata', pre=True, each_item=True)
        def handle_nan(cls, v):
            if isinstance(v, float) and math.isnan(v):
                return None
            return v

    class ModelOutput(LangGraphScore.ModelOutput):
        """
        Model output containing the validation result.

        Attributes:
            score (str): Validation result for the degree.
            explanation (str): Detailed explanation of the validation result.
        """
        score: str
        explanation: str