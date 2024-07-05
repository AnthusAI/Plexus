from typing import Dict, List, Tuple, Any, Literal, Optional
from pydantic import BaseModel, Field
from plexus.scores.MLClassifier import MLClassifier
from plexus.CustomLogging import logging
import mlflow
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.output_parsers import PydanticOutputParser
from langgraph.graph import StateGraph, END
from langchain_aws import ChatBedrock
from langchain_openai import AzureChatOpenAI
from langchain_google_vertexai import ChatVertexAI
from langchain_core.language_models import BaseLanguageModel
from langchain_core.runnables import RunnablePassthrough
from langchain_core.runnables.retry import RunnableRetry
import json
import re

class ValidationState(BaseModel):
    transcript: str
    metadata: Dict[str, str]
    current_step: str
    validation_results: Dict[str, Any] = Field(default_factory=dict)
    overall_validity: str = "Unknown"
    confidence: float = 0.0
    explanation: str = ""
    message_history: ChatMessageHistory = Field(default_factory=ChatMessageHistory)

class StepOutput(BaseModel):
    result: str = Field(description="The validation result (e.g., 'Correct', 'Incorrect', 'Unclear')")
    confidence: float = Field(description="The confidence score between 0 and 1")

class AgenticValidator(MLClassifier):
    """
    An agentic validator that uses LangGraph and advanced LangChain components to validate education information,
    specifically for school, degree, and modality, using both transcript and metadata.
    """
    class Parameters(MLClassifier.Parameters):
        model_provider: Literal["AzureChatOpenAI", "BedrockChat", "ChatVertexAI"] = "AzureChatOpenAI"
        model_name: Optional[str] = None
        temperature: float = 0.3
        max_tokens: Optional[int] = None

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
        max_tokens = self.parameters.max_tokens or self.DEFAULT_MAX_TOKENS.get(self.parameters.model_provider, 1000)

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

    def _call_llm(self, **kwargs):
        return self.retry_config.invoke(lambda: self.llm(**kwargs))

    def _create_chain(self, system_message: str, human_message: str):
        parser = PydanticOutputParser(pydantic_object=StepOutput)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_message),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", human_message + "\n\nProvide your response in the following JSON format:\n{format_instructions}")
        ])

        def parse_llm_output(output: Any) -> Dict[str, Any]:
            if isinstance(output, StepOutput):
                return {"result": output.result, "confidence": output.confidence}
            elif isinstance(output, dict):
                return output
            elif isinstance(output, str):
                try:
                    return json.loads(output)
                except json.JSONDecodeError:
                    result_match = re.search(r"result\s*=\s*['\"](.*?)['\"]", output)
                    confidence_match = re.search(r"confidence\s*=\s*([\d.]+)", output)
                    
                    if result_match and confidence_match:
                        return {
                            "result": result_match.group(1),
                            "confidence": float(confidence_match.group(1))
                        }
                    else:
                        raise ValueError(f"Unable to parse LLM output: {output}")
            else:
                raise TypeError(f"Unexpected output type: {type(output)}")

        chain = prompt | self._call_llm | parse_llm_output | parser

        return RunnableWithMessageHistory(
            chain,
            lambda session_id: ChatMessageHistory(),
            input_messages_key="input",
            history_messages_key="chat_history"
        ), parser

    def _validate_step(self, state: ValidationState, step_name: str, prompt: str) -> ValidationState:
        chain, parser = self._create_chain(
            "You are an expert in validating educational information.",
            prompt
        )
        
        input_data = {
            "input": f"{step_name.capitalize()}: {state.metadata[step_name.lower()]} \nTranscript: {state.transcript}",
            step_name.lower(): state.metadata[step_name.lower()],
            "transcript": state.transcript,
            "format_instructions": parser.get_format_instructions(),
            "chat_history": state.message_history.messages
        }
        
        try:
            result = self._call_llm(input_data)
            if isinstance(result, StepOutput):
                state.validation_results[step_name] = result.result
            else:
                state.validation_results[step_name] = result.get('result', 'Unclear')
            state.message_history.add_user_message(f"Validate {step_name}: {state.metadata[step_name.lower()]}")
            state.message_history.add_ai_message(str(result))
        except Exception as e:
            logging.error(f"Error in _validate_step for {step_name}: {str(e)}")
            state.validation_results[step_name] = "Error"
        
        return state

    def _validate_school(self, state: ValidationState) -> ValidationState:
        return self._validate_step(state, "school", "Validate if the school '{school}' is mentioned in the transcript: {transcript}")

    def _validate_degree(self, state: ValidationState) -> ValidationState:
        return self._validate_step(state, "degree", "Validate if the degree '{degree}' is mentioned in the transcript: {transcript}")

    def _validate_modality(self, state: ValidationState) -> ValidationState:
        return self._validate_step(state, "modality", "Validate if the modality '{modality}' is mentioned or implied in the transcript: {transcript}")

    def _determine_overall_validity(self, state: ValidationState) -> ValidationState:
        chain, parser = self._create_chain(
            "You are an expert in validating educational information.",
            "Given the validation results: {validation_results}, determine the overall validity and provide an explanation."
        )
        result = chain.invoke(
            {"input": f"Validation results: {state.validation_results}"},
            config={"configurable": {"session_id": "overall_validity"}}
        )
        
        state.overall_validity = result.result
        state.explanation = str(result.confidence)
        state.confidence = sum([1 for v in state.validation_results.values() if "Correct" in v]) / 3.0
        state.message_history.add_user_message("Determine overall validity")
        state.message_history.add_ai_message(str(result))
        return state

    def predict(self, model_input: MLClassifier.ModelInput) -> MLClassifier.ModelOutput:
        initial_state = ValidationState(
            transcript=model_input.transcript,
            metadata=model_input.metadata,
            current_step="validate_school"
        )
        final_state = self.workflow.invoke(initial_state)
        return self.ModelOutput(
            classification={
                "school_validation": final_state.validation_results.get('school', 'Unclear'),
                "degree_validation": final_state.validation_results.get('degree', 'Unclear'),
                "modality_validation": final_state.validation_results.get('modality', 'Unclear'),
                "overall_validity": final_state.overall_validity,
                "explanation": final_state.explanation
            },
            confidence=final_state.confidence
        )

    def is_relevant(self, transcript, metadata):
        model_input = self.ModelInput(transcript=transcript, metadata=metadata)
        result = self.predict(model_input)
        return result.classification["overall_validity"].lower() in ["valid", "partial"]

    def predict_validation(self):
        self.val_labels = self.dataframe[self.parameters.score_name]
        self.val_predictions = []
        self.val_confidence_scores = []

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
            self.val_confidence_scores.append(prediction.confidence)

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
        confidence: float