from typing import Dict, List, Tuple, Any, Literal, Optional
from pydantic import BaseModel, Field
from plexus.scores.MLClassifier import MLClassifier
from plexus.CustomLogging import logging
import mlflow
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.language_models import BaseLanguageModel
from langchain_core.runnables import RunnablePassthrough
from langchain_core.runnables.retry import RunnableRetry
from langchain_core.messages import AIMessage

from langchain_aws import ChatBedrock
from langchain_openai import AzureChatOpenAI
from langchain_google_vertexai import ChatVertexAI

from langgraph.graph import StateGraph, END

import json
import re
from langchain_core.messages import AIMessage

class ValidationState(BaseModel):
    transcript: str
    metadata: Dict[str, str]
    current_step: str
    validation_results: Dict[str, Any] = Field(default_factory=dict)
    overall_validity: str = "Unknown"
    explanation: str = ""

class StepOutput(BaseModel):
    result: str = Field(description="The validation result (e.g., 'Yes', 'No', 'Unclear')")
    explanation: Optional[str] = Field(default=None, description="Explanation for the result")

def parse_llm_response(response: AIMessage) -> StepOutput:
    content = response.content.strip().lower()
    logging.info(f"Parsing response: {content}")
    
    # Extract result (Yes or No)
    result = "Yes" if content.startswith("yes") else "No" if content.startswith("no") else "Unclear"
    logging.info(f"Extracted result: {result}")
    
    # Everything after "yes" or "no" is considered explanation
    explanation = content[3:].strip() if result in ["Yes", "No"] else content
    logging.info(f"Extracted explanation: {explanation}")
    
    return StepOutput(result=result, explanation=explanation)

class AgenticValidator(MLClassifier):
    """
    An agentic validator that uses LangGraph and advanced LangChain components to validate education information,
    specifically for school, degree, and modality, using both transcript and metadata.
    """
    class Parameters(MLClassifier.Parameters):
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

    def train_model(self):
        self.llm = self._initialize_model()
        self.workflow = self._create_workflow()
        
        mlflow.log_param("model_provider", self.parameters.model_provider)
        mlflow.log_param("model_name", self.parameters.model_name)
        mlflow.log_param("temperature", self.parameters.temperature)

    def _initialize_model(self) -> BaseLanguageModel:
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

        # Define steps
        workflow.add_node("validate_school", self._validate_school)
        workflow.add_node("validate_degree", self._validate_degree)
        workflow.add_node("validate_modality", self._validate_modality)
        workflow.add_node("determine_overall_validity", self._determine_overall_validity)

        # Define edges
        workflow.add_edge("validate_school", "validate_degree")
        workflow.add_edge("validate_degree", "validate_modality")
        workflow.add_edge("validate_modality", "determine_overall_validity")
        workflow.add_edge("determine_overall_validity", END)

        # Set entry point
        workflow.set_entry_point("validate_school")

        return workflow.compile()

    def _call_llm(self, input, **kwargs):
        return self.retry_config.invoke(lambda: self.llm.invoke(input))

    def _create_chain(self, system_message: str, human_message: str):
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_message),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", human_message)
        ])

        chain = prompt | self.llm

        def get_session_history(session_id: str) -> InMemoryChatMessageHistory:
            return InMemoryChatMessageHistory()

        return RunnableWithMessageHistory(
            chain,
            get_session_history,
            input_messages_key="input",
            history_messages_key="chat_history"
        )

    def _validate_step(self, state: ValidationState, step_name: str, prompt: str) -> ValidationState:
        chain = self._create_chain(
            "You are an expert in validating educational information. Carefully examine the entire transcript for the requested information.",
            prompt
        )
        
        # Normalize the input by converting to lowercase
        normalized_metadata = state.metadata[step_name.lower()].lower()
        normalized_transcript = state.transcript.lower()
        
        input_data = {
            "input": f"Carefully examine this transcript: '{normalized_transcript}'\n\nQuestion: {prompt.format(**{step_name.lower(): normalized_metadata})}",
            step_name.lower(): normalized_metadata,
            "transcript": normalized_transcript,
        }
        
        # Log the input to the model
        logging.info(f"Validating {step_name}:")
        logging.info(f"Input: {input_data['input']}")
        
        try:
            response = chain.invoke(
                input_data,
                config={"configurable": {"session_id": step_name}},
            )
            
            # Log the raw response from the model
            logging.info(f"Raw model response: {response.content}")
            
            # Ask for a yes/no summary
            summary_response = self._get_yes_no_summary(chain, step_name, normalized_metadata)
            
            parsed_result = parse_llm_response(summary_response)
            state.validation_results[step_name] = parsed_result.result
            
            # Log the parsed result
            logging.info(f"Parsed result: {parsed_result}")
            
        except Exception as e:
            logging.error(f"Error in _validate_step for {step_name}: {str(e)}")
            state.validation_results[step_name] = "Error"
        
        return state

    def _get_yes_no_summary(self, chain, step_name: str, metadata: str) -> AIMessage:
        summary_prompt = "Based on your previous response, can you summarize whether the information was found in the transcript with a simple 'Yes' or 'No', followed by a brief explanation?"
        
        summary_response = chain.invoke(
            {
                "input": summary_prompt,
                step_name: metadata,  # Add this line to include the necessary variable
            },
            config={"configurable": {"session_id": step_name}},
        )
        
        logging.info(f"Summary response: {summary_response.content}")
        return summary_response

    def _validate_school(self, state: ValidationState) -> ValidationState:
        return self._validate_step(state, "school", "Is the school '{school}' mentioned in the transcript?")

    def _validate_degree(self, state: ValidationState) -> ValidationState:
        return self._validate_step(state, "degree", "Is the degree '{degree}' or a very close equivalent mentioned in the transcript?")

    def _validate_modality(self, state: ValidationState) -> ValidationState:
        return self._validate_step(state, "modality", "Is the modality '{modality}' or a very close synonym mentioned in the transcript?")

    def _determine_overall_validity(self, state: ValidationState) -> ValidationState:
        yes_count = sum(1 for result in state.validation_results.values() if result == "Yes")
        no_count = sum(1 for result in state.validation_results.values() if result == "No")
        unclear_count = sum(1 for result in state.validation_results.values() if result == "Unclear")
        total_count = len(state.validation_results)
        
        if yes_count == total_count:
            state.overall_validity = "Valid"
        elif no_count == total_count:
            state.overall_validity = "Invalid"
        elif unclear_count == total_count:
            state.overall_validity = "Unclear"
        else:
            state.overall_validity = "Partial"
        
        state.explanation = f"{yes_count} out of {total_count} validations were successful, {no_count} failed, and {unclear_count} were unclear."
        
        return state

    def predict(self, model_input: MLClassifier.ModelInput) -> MLClassifier.ModelOutput:
        initial_state = ValidationState(
            transcript=model_input.transcript,
            metadata=model_input.metadata,
            current_step="validate_school"
        )
        final_state = self.workflow.invoke(initial_state)
        
        # Convert AddableValuesDict to regular dict if necessary
        validation_results = dict(final_state.get('validation_results', {}))
        
        # Prepare the classification result
        classification = {
            "school_validation": validation_results.get('school', 'Unclear'),
            "degree_validation": validation_results.get('degree', 'Unclear'),
            "modality_validation": validation_results.get('modality', 'Unclear'),
            "overall_validity": final_state.get('overall_validity', 'Unknown'),
            "explanation": final_state.get('explanation', '')
        }
        
        # Log the validation results
        logging.info("=" * 50)
        logging.info("VALIDATION RESULTS")
        logging.info("=" * 50)
        logging.info(f"School ({model_input.metadata['school']}): {classification['school_validation']}")
        logging.info(f"Degree ({model_input.metadata['degree']}): {classification['degree_validation']}")
        logging.info(f"Modality ({model_input.metadata['modality']}): {classification['modality_validation']}")
        logging.info("-" * 50)
        logging.info(f"Overall Validity: {classification['overall_validity']}")
        logging.info(f"Explanation: {classification['explanation']}")
        logging.info("=" * 50)
        
        return self.ModelOutput(
            classification=classification,
            confidence=1.0  # Set a default confidence since we're not calculating it
        )

    def is_relevant(self, transcript, metadata):
        model_input = self.ModelInput(transcript=transcript, metadata=metadata)
        result = self.predict(model_input)
        return result.classification["overall_validity"].lower() in ["valid", "partial"]

    def predict_validation(self):
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
        # Implement model registration logic here
        mlflow.log_param("model_type", "AgenticValidator")
        mlflow.log_param("model_provider", self.parameters.model_provider)
        mlflow.log_param("model_name", self.parameters.model_name)

    def save_model(self):
        # Implement model saving logic here
        model_path = f"models/AgenticValidator_{self.parameters.model_provider}_{self.parameters.model_name}"
        mlflow.log_artifact(model_path)

    class ModelInput(MLClassifier.ModelInput):
        metadata: Dict[str, str]

    class ModelOutput(MLClassifier.ModelOutput):
        classification: Dict[str, Any]
        confidence: float = 1.0  # Default confidence to 1.0 since we're not calculating it
