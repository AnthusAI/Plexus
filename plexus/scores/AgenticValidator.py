from typing import Dict, List, Any, Literal, Optional, Union, Tuple
from pydantic import ConfigDict
from plexus.scores.Score import Score
from plexus.CustomLogging import logging

from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableSequence
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from langchain_aws import ChatBedrock
from langchain_openai import AzureChatOpenAI
from langchain_google_vertexai import ChatVertexAI

from langgraph.graph import StateGraph, START, END

from openai_cost_calculator.openai_cost_calculator import calculate_cost

import tiktoken
import mlflow

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
        self.initialize_validation_workflow()
        self.encoding = tiktoken.get_encoding("cl100k_base")

    def initialize_validation_workflow(self):
        """
        Initialize the language model and create the workflow.
        This method also logs relevant parameters to MLflow.
        """
        self.llm = self._initialize_model()
        self.llm_with_retry = self.llm.with_retry(
            retry_if_exception_type=(Exception,),  # Retry on any exception
            wait_exponential_jitter=True,
            stop_after_attempt=3
        )
        self.workflow = self._create_workflow()
        
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
            model_id = self.parameters.model_name or "anthropic.claude-3-haiku-20240307-v1:0"
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

    def _validate_step(self, state: Dict[str, Any], step: str) -> Dict[str, Any]:
        """
        Perform validation for a specific step (degree) using the LLM.

        Args:
            state (Dict[str, Any]): The current state of the validation process.
            step (str): The step to validate.

        Returns:
            Dict[str, Any]: The updated state after validation.
        """
        current_state = ValidationState(**state)
        
        if not self.parameters.prompt:
            raise ValueError(f"Prompt is required in the scorecard for the '{step}' validation step. Please add a 'prompt' field to the score configuration in the YAML file.")
        
        prompt_template = PromptTemplate(
            input_variables=["label_value", "transcript"],
            template=self.parameters.prompt
        )
        
        chain = RunnableSequence(
            prompt_template,
            self.llm_with_retry,
            StrOutputParser()
        )
        
        try:
            input_text = prompt_template.format(
                label_value=current_state.metadata[step].lower(),
                transcript=current_state.transcript.lower()
            )
            result = chain.invoke({
                "label_value": current_state.metadata[step].lower(),
                "transcript": current_state.transcript.lower()
            })
            
            # Count tokens and log cost
            self._log_tokens_and_cost(input_text, result)

        except Exception as e:
            logging.error(f"Failed to validate {step} after all retry attempts: {e}")
            return self._handle_validation_failure(current_state, step)

        validation_result, explanation = self._parse_validation_result(result)
        
        current_state.current_step = step
        current_state.validation_result = validation_result
        current_state.explanation = explanation
        current_state.messages = [
            HumanMessage(content=prompt_template.format(
                label_value=current_state.metadata[step].lower(),
                transcript=current_state.transcript.lower()
            )),
            AIMessage(content=result)
        ]
        
        print(f"\nValidated {step}: {validation_result}")
        
        return current_state.__dict__

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
        print(f"\nFailed to validate {step}")
        return state.__dict__

    def _parse_validation_result(self, output: str) -> Tuple[str, str]:
        """
        Parse the output from the language model to determine the validation result and explanation.

        Args:
            output (str): The raw output from the language model.

        Returns:
            Tuple[str, str]: A tuple containing the validation result and explanation.
        """
        output_lower = output.lower()
        first_word = output_lower.split()[0] if output_lower else ""

        if first_word == "yes":
            result = "Valid"
        elif first_word == "no":
            result = "Invalid"
        else:
            # If it doesn't start with yes or no, search for them in the text
            if "yes" in output_lower:
                result = "Valid"
            elif "no" in output_lower:
                result = "Invalid"
            else:
                result = "Unclear"

        # Extract explanation (everything after the first word)
        explanation = ' '.join(output.split()[1:]).strip()

        return result, explanation

    def _count_tokens(self, text: str) -> int:
        return len(self.encoding.encode(text))

    def _log_tokens_and_cost(self, input_text: str, output_text: str):
        """Log the token usage and cost."""
        prompt_tokens = self._count_tokens(input_text)
        completion_tokens = self._count_tokens(output_text)
        total_tokens = prompt_tokens + completion_tokens
        self.total_tokens += total_tokens
        
        cost_info = calculate_cost(
            model_name=self.parameters.model_name,
            input_tokens=prompt_tokens,
            output_tokens=completion_tokens
        )
        
        self.total_cost += cost_info['total_cost']
        
        logging.info(f"Prompt tokens: {prompt_tokens}, Completion tokens: {completion_tokens}")
        mlflow.log_metric("prompt_tokens", prompt_tokens)
        mlflow.log_metric("completion_tokens", completion_tokens)
        mlflow.log_metric("total_tokens", self.total_tokens)
        mlflow.log_metric("input_cost", float(cost_info['input_cost']))
        mlflow.log_metric("output_cost", float(cost_info['output_cost']))
        mlflow.log_metric("total_cost", float(self.total_cost))

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

        final_state = self.workflow.invoke(initial_state.__dict__)
        logging.info(f"Final state: {final_state}")

        validation_result = final_state.get('validation_result', 'Unknown')
        explanation = final_state.get('explanation', '')

        # Get the current step
        current_step = final_state.get('current_step', 'Unknown')

        logging.info(f"{current_step.capitalize()}: {validation_result}")
        logging.info("\nExplanation:")
        logging.info(explanation)

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