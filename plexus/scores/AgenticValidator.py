from typing import Dict, List, Any, Literal, Optional, Union, Tuple
from pydantic import ConfigDict
from plexus.scores.Score import Score
from plexus.CustomLogging import logging
import mlflow
from langchain_core.language_models import BaseLanguageModel
from langchain_core.runnables import RunnablePassthrough
from langchain_core.runnables.retry import RunnableRetry
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import Tool

from langchain_aws import ChatBedrock
from langchain_openai import AzureChatOpenAI
from langchain_google_vertexai import ChatVertexAI

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import create_react_agent

from langchain_core.messages import AIMessage

class ValidationState:
    def __init__(
        self,
        transcript: str,
        metadata: Dict[str, str],
        current_step: str = "",
        validation_results: Dict[str, Any] = None,
        overall_validity: str = "Unknown",
        explanation: str = "",
        messages: List[Union[HumanMessage, AIMessage]] = None
    ):
        self.transcript = transcript
        self.metadata = metadata
        self.current_step = current_step
        self.validation_results = validation_results or {}
        self.overall_validity = overall_validity
        self.explanation = explanation
        self.messages = messages or []

    def __repr__(self):
        return (
            f"ValidationState(transcript='{self.transcript}', "
            f"metadata={self.metadata}, "
            f"current_step='{self.current_step}', "
            f"validation_results={self.validation_results}, "
            f"overall_validity='{self.overall_validity}', "
            f"explanation='{self.explanation}', "
            f"messages={self.messages})"
        )

class AgenticValidator(Score):
    """
    An agentic validator that uses LangGraph and advanced LangChain components to validate education information,
    specifically for school, degree, and modality, using both transcript and metadata.

    This validator uses a language model to analyze transcripts and validate educational claims.
    """

    class Parameters(Score.Parameters):
        """
        Parameters for configuring the AgenticValidator.
        """
        model_config = ConfigDict(protected_namespaces=())
        model_provider: Literal["AzureChatOpenAI", "BedrockChat", "ChatVertexAI"] = "AzureChatOpenAI"
        model_name: Optional[str] = None
        temperature: float = 0.1
        max_tokens: int = 500

    def __init__(self, **parameters):
        super().__init__(**parameters)
        self.llm = None
        self.workflow = None
        self.retry_config = RunnableRetry(
            max_attempts=3,
            wait_exponential_jitter=True,
            bound=RunnablePassthrough()
        )
        self.react_agent = None

    def train_model(self):
        self.llm = self._initialize_model()
        self.workflow = self._create_workflow()
        
        tools = [
            Tool(
                name="validate_school",
                description="Validate if the school is mentioned in the transcript",
                func=lambda x: f"Validation result for query: {x}"
            ),
            Tool(
                name="validate_degree",
                description="Validate if the degree is mentioned in the transcript",
                func=lambda x: f"Validation result for query: {x}"
            ),
            Tool(
                name="validate_modality",
                description="Validate if the modality is mentioned in the transcript",
                func=lambda x: f"Validation result for query: {x}"
            )
        ]
        
        self.react_agent = create_react_agent(self.llm, tools)
        
        mlflow.log_param("model_provider", self.parameters.model_provider)
        mlflow.log_param("model_name", self.parameters.model_name)
        mlflow.log_param("temperature", self.parameters.temperature)

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
                },
            )
        elif self.parameters.model_provider == "ChatVertexAI":
            model_name = self.parameters.model_name or "gemini-1.5-flash-001"
            return ChatVertexAI(
                model=model_name,
                temperature=self.parameters.temperature,
                max_output_tokens=max_tokens,
            )
        else:
            raise ValueError(f"Unsupported model provider: {self.parameters.model_provider}")

    def _create_workflow(self):
        workflow = StateGraph(ValidationState)

        # Define validation steps
        workflow.add_node("validate_school", lambda state: self._validate_step(state, "school"))
        workflow.add_node("validate_degree", lambda state: self._validate_step(state, "degree"))
        workflow.add_node("validate_modality", lambda state: self._validate_step(state, "modality"))

        # Define finalization step
        def finalize(state: Dict[str, Any]) -> Dict[str, Any]:
            logging.info(f"Finalizing state: {state}")
            validation_results = state.get('validation_results', {})
            overall_validity = self._determine_overall_validity(validation_results)
            state['overall_validity'] = overall_validity
            logging.info(f"Final state: {state}")
            return state

        workflow.add_node("finalize", finalize)

        # Add edges to create the workflow
        workflow.add_edge("validate_school", "validate_degree")
        workflow.add_edge("validate_degree", "validate_modality")
        workflow.add_edge("validate_modality", "finalize")

        # Set the entry point
        workflow.set_entry_point("validate_school")

        return workflow.compile()

    def _validate_step(self, state: Dict[str, Any], step: str) -> Dict[str, Any]:
        current_state = ValidationState(**state)
        
        prompt = f"Is the {step} '{current_state.metadata[step]}' mentioned in the following transcript? Transcript: {current_state.transcript}. Answer with YES or NO, followed by your reasoning."
        
        tools = [
            Tool(
                name="validate_" + step,
                description=f"Validate if the {step} is mentioned in the transcript",
                func=lambda x: f"Validation result for query: {x}"
            )
        ]
        
        react_agent = create_react_agent(self.llm, tools)
        
        result = react_agent.invoke({
            "messages": [HumanMessage(content=prompt)],
                "input": current_state
            })
        
        ai_messages = [msg for msg in result['messages'] if isinstance(msg, AIMessage)]
        if ai_messages:
            last_ai_message = ai_messages[-1]
            content = last_ai_message.content
        else:
            content = f"Unable to validate {step}. Please check the input and try again."
        
        validation_result, explanation = self._parse_validation_result(content)
        
        current_state.current_step = step
        current_state.validation_results[step] = validation_result
        current_state.explanation += f"{step.capitalize()}: {validation_result}\n\nReasoning:\n{explanation}\n\n"
        current_state.messages = result['messages']
        
        print(f"\nValidated {step}: {validation_result}")
        
        return current_state.__dict__

    def _determine_overall_validity(self, validation_results: Dict[str, str]) -> str:
        valid_count = sum(1 for result in validation_results.values() if result == "Valid")
        total_count = len(validation_results)
        if total_count == 0:
            return "Unknown"
        elif valid_count == total_count:
            return "Valid"
        elif valid_count == 0:
            return "Invalid"
        else:
            return "Partial"
    
    def _parse_validation_result(self, output: str) -> Tuple[str, str]:
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

    def _validate_step_string(self, query: str) -> str:
        """
        Validate a step based on a string query.

        Args:
            query (str): The query string to validate.

        Returns:
            str: A string indicating the validation result.
        """
        # Here you would implement the logic to validate the query string
        # For now, we'll just return the query as is
        return f"Validation result for query: {query}"

    def predict(self, model_input: Score.ModelInput) -> Score.ModelOutput:
        logging.info(f"Predict method input: {model_input}")
        initial_state = ValidationState(
            transcript=model_input.transcript,
            metadata=model_input.metadata
        )
        logging.info(f"Initial state: {initial_state}")

        final_state = self.workflow.invoke(initial_state.__dict__)
        logging.info(f"Final state: {final_state}")

        if isinstance(final_state, ValidationState):
            final_state = final_state.__dict__

        classification = {
            'school_validation': final_state.get('validation_results', {}).get('school', 'Unclear'),
            'degree_validation': final_state.get('validation_results', {}).get('degree', 'Unclear'),
            'modality_validation': final_state.get('validation_results', {}).get('modality', 'Unclear'),
            'overall_validity': final_state.get('overall_validity', 'Unknown'),
            'explanation': final_state.get('explanation', '')
        }

        logging.info("\nValidation Results:")
        logging.info(f"School: {classification['school_validation']}")
        logging.info(f"Degree: {classification['degree_validation']}")
        logging.info(f"Modality: {classification['modality_validation']}")
        logging.info(f"Overall Validity: {classification['overall_validity']}")
        logging.info("\nExplanation:")
        logging.info(classification['explanation'])

        return self.ModelOutput(
            classification=classification,
        )

    def is_relevant(self, transcript, metadata):
        """
        Determine if the given transcript and metadata are relevant based on the overall validity.

        Args:
            transcript: The transcript to be validated.
            metadata: The metadata containing school, degree, and modality information.

        Returns:
            bool: True if the overall validity is "valid" or "partial", False otherwise.
        """
        model_input = self.ModelInput(transcript=transcript, metadata=metadata)
        result = self.predict(model_input)
        return result.classification["overall_validity"].lower() in ["valid", "partial"]

    def predict_validation(self):
        """
        Predict the validation results for the entire dataframe and store the predictions.
        """
        self.val_labels = self.dataframe[self.parameters.score_name]
        self.val_predictions = []

        for _, row in self.dataframe.iterrows():
            model_input = self.ModelInput(
                transcript=row['Transcription'],
                metadata={
                    'school': row['School'],
                    'degree': row['Degree'],
                    'modality': row['Modality']
                }
            )
            prediction = self.predict(model_input)
            self.val_predictions.append(prediction.classification)

    def register_model(self):
        """
        Register the model with MLflow.
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
        """
        metadata: Dict[str, str]

    class ModelOutput(Score.ModelOutput):
        """
        Model output containing the classification results.
        """
        classification: Dict[str, Any]