from typing import Dict, List, Any, Literal, Optional, Union, Tuple
from pydantic import ConfigDict
from plexus.scores.Score import Score
from plexus.CustomLogging import logging

from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableSequence
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.tools import Tool

from langchain_aws import ChatBedrock
from langchain_openai import AzureChatOpenAI
from langchain_google_vertexai import ChatVertexAI

from langgraph.graph import StateGraph, START, END

from openai_cost_calculator.openai_cost_calculator import calculate_cost

import tiktoken
import mlflow

from langchain.memory import ChatMessageHistory
from langchain.schema import SystemMessage

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
    """

    def __init__(
        self,
        transcript: str,
        metadata: Dict[str, str],
        current_step: str = "",
        validation_result: str = "Unknown",
        explanation: str = "",
        messages: List[Union[HumanMessage, AIMessage]] = None
    ):
        """
        Initialize a ValidationState instance.

        Args:
            transcript (str): The transcript to be validated.
            metadata (Dict[str, str]): Metadata about the education claim.
            current_step (str, optional): The current validation step. Defaults to "".
            validation_result (str, optional): Result of the degree validation. Defaults to "Unknown".
            explanation (str, optional): Detailed explanation of the result. Defaults to "".
            messages (List[Union[HumanMessage, AIMessage]], optional): Message history. Defaults to None.
        """
        self.transcript = transcript
        self.metadata = metadata
        self.current_step = current_step
        self.validation_result = validation_result
        self.explanation = explanation
        self.messages = messages or []

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
            f"messages={self.messages})"
        )

class AgenticValidator(Score):
    """
    An agentic validator that uses LangGraph and advanced LangChain components to validate education information,
    specifically for degree, using both transcript and metadata.

    This validator uses a language model to analyze transcripts and validate educational claims through a multi-step
    workflow implemented with LangGraph.
    """

    class Parameters(Score.Parameters):
        """
        Parameters for configuring the AgenticValidator.

        Attributes:
            model_provider (Literal): The provider of the language model to use.
            model_name (Optional[str]): The specific model name to use (if applicable).
            temperature (float): The temperature setting for the language model.
            max_tokens (int): The maximum number of tokens for model output.
            label (str): The label of the metadata to validate.
            prompt (str): The custom prompt to use for validation.
        """
        model_config = ConfigDict(protected_namespaces=())
        model_provider: Literal["AzureChatOpenAI", "BedrockChat", "ChatVertexAI"] = "BedrockChat"
        model_name: Optional[str] = None
        temperature: float = 0.1
        max_tokens: int = 500
        label: str = ""
        prompt: str = ""

    def __init__(self, **parameters):
        """
        Initialize the AgenticValidator with the given parameters.

        Args:
            **parameters: Keyword arguments for configuring the validator.
        """
        super().__init__(**parameters)
        self.llm = None
        self.llm_with_retry = None
        self.agent = None
        self.workflow = None
        self.total_tokens = 0
        self.total_cost = 0
        self.agent_executor = None
        self.current_state = None
        self.chat_history = ChatMessageHistory()
        self.initialize_validation_workflow()
        self.encoding = tiktoken.get_encoding("cl100k_base")

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
        )
        self.workflow = self._create_workflow()
        self.agent_executor = self.create_react_agent()
        
        mlflow.log_param("model_provider", self.parameters.model_provider)
        mlflow.log_param("model_name", self.parameters.model_name)
        mlflow.log_param("temperature", self.parameters.temperature)
        mlflow.log_param("max_tokens", self.parameters.max_tokens)
        mlflow.log_param("prompt", self.parameters.prompt)
        mlflow.log_param("label", self.parameters.label)

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
            return ChatBedrock(
                model_id=model_id,
                model_kwargs={
                    "temperature": self.parameters.temperature,
                    "max_tokens": max_tokens
                }
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

        # Add the validation step
        workflow.add_node("run_prediction", lambda state: self._validate_step(state, self.parameters.label))

        # Add edges to create the workflow
        workflow.add_edge(START, "run_prediction")
        workflow.add_edge("run_prediction", END)

        return workflow.compile()

    def create_react_agent(self):
        """
        Create a ReAct agent for validation tasks.
        """
        tools = [
            Tool(
                name="Validate Claim",
                func=self._validate_claim,
                description="Validate a claim against the transcript. Input should be the claim to validate."
            )
        ]

        prompt = PromptTemplate.from_template(
            """You are an AI assistant tasked with validating educational claims based on the provided transcript.

            You have access to the following tools:

            {tools}

            Use the following format:

            Question: the input question you must answer
            Thought: you should always think about what to do
            Action: the action to take, should be one of [{tool_names}]
            Action Input: the input to the action
            Observation: the result of the action
            ... (this Thought/Action/Action Input/Observation can repeat N times)
            Thought: I now know the final answer
            Final Answer: Respond with YES or NO, followed by a comma and then a brief explanation.

            Begin!

            Transcript: {transcript}

            Question: {input}
            Thought: I have been provided with a transcript and a claim to validate. I will analyze the transcript to find evidence supporting or refuting the claim.
            {agent_scratchpad}
            """
        )

        agent = create_react_agent(self.llm, tools, prompt)
        return AgentExecutor(agent=agent, tools=tools, verbose=True, handle_parsing_errors=True)

    def _validate_claim(self, input_string: str) -> str:
        """
        Validate a specific claim against the transcript.
        This method is used as a tool by the React agent.
        """
        transcript = self.current_state.transcript
        return f"Claim to validate: {input_string}\n\n"

    def _validate_step(self, state: Dict[str, Any], step: str) -> Dict[str, Any]:
        """
        Perform validation for a specific step using the ReAct agent.
        """
        self.current_state = ValidationState(**state)
        
        try:
            label_value = self.current_state.metadata[self.parameters.label]
            
            # Use the custom prompt from the YAML file
            custom_prompt = self.parameters.prompt.format(label_value=label_value)
            
            input_string = f"Validate the following: {custom_prompt}"
            agent_input = f"{input_string}\n\nTranscript: {self.current_state.transcript}"
            
            result = self.agent_executor.invoke({
                "input": input_string,
                "transcript": self.current_state.transcript
            })
            
            # Log tokens and cost
            self._log_tokens_and_cost(agent_input, result['output'])
            
            # Parse the result
            validation_result, explanation = self._parse_validation_result(result['output'])
            
            self.current_state.current_step = step
            self.current_state.validation_result = validation_result
            self.current_state.explanation = explanation
            self.current_state.messages = [
                HumanMessage(content=input_string),
                AIMessage(content=result['output'])
            ]
            
            logging.info(f"\nValidated {step}: {validation_result}")
            logging.info(f"Explanation: {explanation}")
            
        except Exception as e:
            logging.error(f"Failed to validate {step}: {e}")
            return self._handle_validation_failure(self.current_state, step)

        return self.current_state.__dict__

    def _handle_validation_failure(self, state: ValidationState, step: str) -> Dict[str, Any]:
        """
        Handle the case when validation fails after all retry attempts.

        Args:
            state (ValidationState): The current validation state.
            step (str): The step that failed validation.

        Returns:
            Dict[str, Any]: The updated state after handling the failure.
        """
        state.current_step = step
        state.validation_result = "Unclear"
        state.explanation = f"{step.capitalize()}: Validation failed due to technical issues.\n\n"
        logging.info(f"\nFailed to validate {step}")
        return state.__dict__

    def _parse_validation_result(self, output: str) -> Tuple[str, str]:
        """
        Parse the output from the language model to determine the validation result and explanation.

        Args:
            output (str): The raw output from the language model.

        Returns:
            Tuple[str, str]: A tuple containing the validation result and explanation.
        """
        logging.info(f"Raw output to parse: {output}")
        
        # Check if the output starts with YES, NO, or UNCLEAR
        first_word = output.split(',')[0].strip().upper()
        
        if first_word == "YES":
            validation_result = "Valid"
        elif first_word == "NO":
            validation_result = "Invalid"
        else:
            validation_result = "Unclear"

        # Extract explanation (everything after the first comma)
        explanation = output.split(',', 1)[1].strip() if ',' in output else output

        logging.info(f"Parsed result: {validation_result}")
        logging.info(f"Parsed explanation: {explanation}")

        return validation_result, explanation

    def _count_tokens(self, text: str) -> int:
        return len(self.encoding.encode(text))

    def _log_tokens_and_cost(self, agent_input: str, agent_output: str):
        """
        Log the number of tokens used and calculate the cost for the React agent.
        """
        # Count tokens for input and output separately
        input_tokens = len(self.encoding.encode(agent_input))
        output_tokens = len(self.encoding.encode(agent_output))
        total_tokens = input_tokens + output_tokens
        
        # Determine the appropriate model for cost calculation
        model_name = self.parameters.model_name or "gpt-3.5-turbo"
        
        # Calculate cost
        try:
            cost_info = calculate_cost(model_name=model_name, input_tokens=input_tokens, output_tokens=output_tokens)
            total_cost = float(cost_info['total_cost'])
        except ValueError as e:
            logging.warning(f"Cost calculation failed: {str(e)}. Using fallback estimation.")
            # Fallback to a default cost estimation
            total_cost = (total_tokens * 0.00002)  # Assuming $0.02 per 1000 tokens as a fallback
        
        # Update total tokens and cost
        self.total_tokens += total_tokens
        self.total_cost += total_cost
        
        logging.info(f"Model: {model_name}")
        logging.info(f"Input tokens: {input_tokens}")
        logging.info(f"Output tokens: {output_tokens}")
        logging.info(f"Total tokens: {total_tokens}")
        logging.info(f"Estimated cost: ${total_cost:.6f}")
        
        # Log to MLflow
        mlflow.log_metric("total_tokens", self.total_tokens)
        mlflow.log_metric("total_cost", self.total_cost)

    def predict(self, model_input: Score.ModelInput) -> Score.ModelOutput:
        """
        Predict the validity of the education information based on the transcript and metadata.

        Args:
            model_input (Score.ModelInput): The input containing the transcript and metadata.

        Returns:
            Score.ModelOutput: The output containing the validation result.
        """
        logging.info(f"Predict method input: {model_input}")
        initial_state = ValidationState(
            transcript=model_input.transcript,
            metadata=model_input.metadata
        )
        logging.info(f"Initial state: {initial_state}")

        # Ensure a fresh state for each prediction
        self.total_tokens = 0
        self.total_cost = 0

        final_state = self.workflow.invoke(initial_state.__dict__)
        logging.info(f"Final state: {final_state}")

        validation_result = final_state.get('validation_result', 'Unknown')
        explanation = final_state.get('explanation', '')

        # Get the current step
        current_step = final_state.get('current_step', 'Unknown')

        logging.info(f"{current_step.capitalize()}: {validation_result}")
        logging.info(f"Explanation: {explanation}")

        # Log final token and cost metrics
        mlflow.log_metric("final_total_tokens", self.total_tokens)
        mlflow.log_metric("final_total_cost", self.total_cost)

        return self.ModelOutput(
            score=validation_result,
            explanation=explanation
        )

    def register_model(self):
        """
        Register the model with MLflow by logging relevant parameters.
        """
        mlflow.log_param("model_type", "AgenticValidator")
        mlflow.log_param("model_provider", self.parameters.model_provider)
        mlflow.log_param("model_name", self.parameters.model_name)

    def save_model(self):
        """
        Save the model to a specified path and log it as an artifact with MLflow.
        """
        model_path = f"models/AgenticValidator_{self.parameters.model_provider}_{self.parameters.model_name}"
        mlflow.log_artifact(model_path)

    class ModelInput(Score.ModelInput):
        """
        Model input containing the transcript and metadata.

        Attributes:
            metadata (Dict[str, str]): A dictionary containing degree information.
        """
        metadata: Dict[str, str]

    class ModelOutput(Score.ModelOutput):
        """
        Model output containing the validation result.

        Attributes:
            score (str): Validation result for the degree.
            explanation (str): Detailed explanation of the validation result.
        """
        score: str
        explanation: str

    def train_model(self):
        """
        Placeholder method to satisfy the base class requirement.
        This validator doesn't require traditional training.
        """
        pass

    def predict_validation(self):
        """
        Placeholder method to satisfy the base class requirement.
        This validator doesn't require traditional training.
        """
        pass