from typing import Dict, List, Any, Literal, Optional, TypedDict, Union
from pydantic import BaseModel, Field, ConfigDict
from plexus.scores.Score import Score
from plexus.CustomLogging import logging
import mlflow
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.language_models import BaseLanguageModel
from langchain_core.runnables import RunnablePassthrough
from langchain_core.runnables.retry import RunnableRetry
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
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

class StepOutput(BaseModel):
    result: str = Field(description="The validation result (e.g., 'Yes', 'No', 'Unclear')")
    explanation: Optional[str] = Field(default=None, description="Explanation for the result")

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
        """
        Initialize the AgenticValidator with the given parameters.

        Args:
            **parameters: Keyword arguments for configuring the validator.
        """
        super().__init__(**parameters)
        self.current_state = {}
        self.llm = None
        self.workflow = None
        self.retry_config = RunnableRetry(
            max_attempts=3,
            wait_exponential_jitter=True,
            bound=RunnablePassthrough()
        )
        self.current_state = {}  # Initialize current_state

    def train_model(self):
        """
        Initialize the language model and create the workflow for validation.
        This method also logs the model parameters using MLflow.
        """
        self.llm = self._initialize_model()
        self.workflow = self._create_workflow()
        
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
        tools = [
            Tool(
                name="validate_school",
                func=self._validate_school,
                description="Validate if the given school is mentioned in the transcript."
            ),
            Tool(
                name="validate_degree",
                func=self._validate_degree,
                description="Validate if the given degree or a close equivalent is mentioned in the transcript."
            ),
            Tool(
                name="validate_modality",
                func=self._validate_modality,
                description="Validate if the given modality or a close synonym is mentioned in the transcript."
            ),
        ]

        react_agent = create_react_agent(self.llm, tools)

        workflow = StateGraph(ValidationState)

        def validate_step(state: Dict[str, Any], step: str) -> Dict[str, Any]:
            print(f"Validating step: {step}")
            print(f"Input state: {state}")
            
            # If the state doesn't contain all expected keys, it might be a partial update
            # In this case, we need to merge it with the previous state
            if 'transcript' not in state or 'metadata' not in state:
                # Assume these are stored as class attributes
                state = {**self.current_state, **state}
            
            current_state = ValidationState(**state)
            
            human_message = HumanMessage(content=f"Validate the {step} using the transcript: {current_state.transcript}. {step.capitalize()}: {current_state.metadata[step]}")
            current_state.messages.append(human_message)
            
            result = react_agent.invoke({
                "messages": current_state.messages,
                "input": current_state  # Pass the entire state to the agent
            })
            print(f"React agent result: {result}")
            
            # Extract the last AIMessage from the result
            ai_messages = [msg for msg in result['messages'] if isinstance(msg, AIMessage)]
            if ai_messages:
                last_ai_message = ai_messages[-1]
                content = last_ai_message.content
            else:
                content = f"Unable to validate {step}. Please check the input and try again."
            
            validation_result = self._parse_validation_result(content)
            
            # Update the state
            current_state.current_step = step
            current_state.validation_results[step] = validation_result
            current_state.messages = result['messages']
            
            # Store the current state as a class attribute
            self.current_state = current_state.__dict__
            
            print(f"Updated state: {current_state}")
            return current_state.__dict__

        workflow.add_node("validate_school", lambda state: validate_step(state, "school"))
        workflow.add_node("validate_degree", lambda state: validate_step(state, "degree"))
        workflow.add_node("validate_modality", lambda state: validate_step(state, "modality"))

        def router(state: Dict[str, Any]) -> Dict[str, str]:
            print(f"Router input state: {state}")
            current_step = state.get('current_step', '')
            if current_step == "":
                return {"current_step": "validate_school"}
            elif current_step == "validate_school":
                return {"current_step": "validate_degree"}
            elif current_step == "validate_degree":
                return {"current_step": "validate_modality"}
            else:
                # Instead of ending, return the final state
                return {"current_step": "final"}

        def finalize(state: Dict[str, Any]) -> Dict[str, Any]:
            # Determine overall validity
            validation_results = state.get('validation_results', {})
            overall_validity = self._determine_overall_validity(validation_results)
            state['overall_validity'] = overall_validity
            return state

        workflow.add_node("router", router)
        workflow.add_node("final", finalize)
        
        # Add edges
        workflow.add_edge("validate_school", "router")
        workflow.add_edge("validate_degree", "router")
        workflow.add_edge("validate_modality", "router")
        workflow.add_edge("final", END)
        workflow.add_conditional_edges(
            "router",
            lambda state: state['current_step']
        )

        workflow.set_entry_point("router")

        return workflow.compile()

    def _determine_overall_validity(self, validation_results: Dict[str, str]) -> str:
        valid_count = sum(1 for result in validation_results.values() if result == "Valid")
        if valid_count == 3:
            return "Valid"
        elif valid_count == 0:
            return "Invalid"
        else:
            return "Partial"
    
    
    def parse_llm_response(self, response: AIMessage) -> StepOutput:
        """
        Parse the response from the language model into a structured StepOutput.

        Args:
            response (AIMessage): The response from the language model.

        Returns:
            StepOutput: A structured output containing the result and explanation.
        """
        content = response.content.strip()
        logging.info(f"Parsing response: {content}")
        
        # Split the response into result and explanation
        parts = content.split(':', 1)
        result = parts[0].strip().lower()
        explanation = parts[1].strip() if len(parts) > 1 else ""
        
        result = "Yes" if result.startswith("yes") else "No" if result.startswith("no") else "Unclear"
        logging.info(f"Extracted result: {result}")
        logging.info(f"Extracted explanation: {explanation}")
        
        return StepOutput(result=result, explanation=explanation)

    def _parse_validation_result(self, output: str) -> str:
        output_lower = output.lower()
        if "yes" in output_lower or "valid" in output_lower:
            return "Valid"
        elif "no" in output_lower or "invalid" in output_lower:
            return "Invalid"
        else:
            return "Unclear"

    def _validate_school(self, state_or_query: Union[ValidationState, str]) -> str:
        """
        Validate if the given school is mentioned in the transcript.

        Args:
            state_or_query (Union[ValidationState, str]): The current validation state or a query string.

        Returns:
            str: A string indicating the validation result for the school.
        """
        if isinstance(state_or_query, str):
            return self._validate_step_string(state_or_query)
        else:
            return self._validate_step(state_or_query, "school", f"Is the school '{state_or_query.metadata['school']}' mentioned in the transcript?")

    def _validate_degree(self, state_or_query: Union[ValidationState, str]) -> str:
        """
        Validate if the given degree or a close equivalent is mentioned in the transcript.

        Args:
            state_or_query (Union[ValidationState, str]): The current validation state or a query string.

        Returns:
            str: A string indicating the validation result for the degree.
        """
        if isinstance(state_or_query, str):
            return self._validate_step_string(state_or_query)
        else:
            return self._validate_step(state_or_query, "degree", f"Is the degree '{state_or_query.metadata['degree']}' or a very close equivalent mentioned in the transcript?")

    def _validate_modality(self, state_or_query: Union[ValidationState, str]) -> str:
        """
        Validate if the given modality or a close synonym is mentioned in the transcript.

        Args:
            state_or_query (Union[ValidationState, str]): The current validation state or a query string.

        Returns:
            str: A string indicating the validation result for the modality.
        """
        if isinstance(state_or_query, str):
            return self._validate_step_string(state_or_query)
        else:
            return self._validate_step(state_or_query, "modality", f"Is the modality '{state_or_query.metadata['modality']}' or a very close synonym mentioned in the transcript?")

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

    def _call_llm(self, input):
        """
        Call the language model with retry logic.

        Args:
            input: The input to be passed to the language model.

        Returns:
            The response from the language model.
        """
        return self.retry_config.invoke(self.llm.invoke)(input)

    def _validate_step(self, state: ValidationState, step_name: str, prompt: str) -> ValidationState:
        """
        Perform a single validation step using the language model.

        Args:
            state (ValidationState): The current validation state.
            step_name (str): The name of the validation step.
            prompt (str): The prompt to be sent to the language model.

        Returns:
            ValidationState: The updated validation state after the step.
        """
        chain = self._create_chain(
            "You are an expert in validating educational information. Carefully examine the entire transcript for the requested information. Respond with 'Yes' or 'No', followed by a brief explanation.",
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
            
            parsed_result = self.parse_llm_response(response)
            state.validation_results[step_name] = f"{parsed_result.result}"
            
            # Log the parsed result
            logging.info(f"Parsed result: {parsed_result}")
            
        except Exception as e:
            logging.error(f"Error in _validate_step for {step_name}: {str(e)}")
            state.validation_results[step_name] = "Error"
        
        return state

    def predict(self, model_input: Score.ModelInput) -> Score.ModelOutput:
        """
        Predict the validity of the educational information based on the transcript and metadata.

        Args:
            model_input (Score.ModelInput): The input containing the transcript and metadata.

        Returns:
            Score.ModelOutput: The prediction result including the classification.
        """
        print(f"Predict method input: {model_input}")
        initial_state = ValidationState(
            transcript=model_input.transcript,
            metadata=model_input.metadata
        )
        print(f"Initial state: {initial_state}")

        self.current_state = initial_state.__dict__  # Store the initial state
        final_state = self.workflow.invoke(self.current_state)
        print(f"Final state: {final_state}")

        # Ensure final_state is a dictionary
        if isinstance(final_state, ValidationState):
            final_state = final_state.__dict__

        classification = self._combine_results(final_state.get('validation_results', {}))
        classification["overall_validity"] = final_state.get('overall_validity', 'Unknown')

        print(f"Classification: {classification}")
        return self.ModelOutput(
            classification=classification,
        )

    def _create_chain(self, system_message: str, human_message: str):
        """
        Create a chain for processing messages with the language model.

        Args:
            system_message (str): The system message to be used in the prompt.
            human_message (str): The human message to be used in the prompt.

        Returns:
            RunnableWithMessageHistory: A chain that can process messages with history.
        """
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

    def _combine_results(self, validation_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Combine the results of individual validations into an overall classification.

        Args:
            validation_results (Dict[str, Any]): The validation results from the agent.

        Returns:
            Dict[str, Any]: A dictionary containing the overall classification and explanation.
        """
        classification = {
            "school_validation": "Unclear",
            "degree_validation": "Unclear",
            "modality_validation": "Unclear",
            "overall_validity": "Unknown",
            "explanation": ""
        }

        for key, value in validation_results.items():
            if "school" in key:
                classification["school_validation"] = value
            elif "degree" in key:
                classification["degree_validation"] = value
            elif "modality" in key:
                classification["modality_validation"] = value

        valid_count = sum(1 for val in [classification['school_validation'], classification['degree_validation'], classification['modality_validation']] if val == "Valid")
        if valid_count == 3:
            classification['overall_validity'] = "Valid"
        elif valid_count == 0:
            classification['overall_validity'] = "Invalid"
        else:
            classification['overall_validity'] = "Partial"

        classification['explanation'] = f"{valid_count} out of 3 validations were successful."

        return classification

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

class AgentState(TypedDict):
    messages: List[AnyMessage]
    agent_outcome: Literal["CONTINUE", "FINISH"]
    validation_results: Dict[str, Any]