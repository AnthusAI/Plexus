from typing import Dict, List, Any, Literal, Optional, TypedDict
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
from langchain_core.messages import AIMessage, AnyMessage
from langchain_core.tools import Tool

from langchain_aws import ChatBedrock
from langchain_openai import AzureChatOpenAI
from langchain_google_vertexai import ChatVertexAI

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import create_react_agent

from langchain_core.messages import AIMessage

class ValidationState(BaseModel):
    transcript: str
    metadata: Dict[str, str]
    current_step: str
    validation_results: Dict[str, Any] = Field(default_factory=dict)
    overall_validity: str = "Unknown"
    explanation: str = ""
    overall_confidence: float = 0.5

class StepOutput(BaseModel):
    result: str = Field(description="The validation result (e.g., 'Yes', 'No', 'Unclear')")
    explanation: Optional[str] = Field(default=None, description="Explanation for the result")
    confidence: float = Field(default=1.0, description="Confidence score for the result")

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

        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert in validating educational information. Use the provided tools to validate the given information based on the transcript."),
            ("human", "{input}"),
            ("human", "Validate the school, degree, and modality information using the appropriate tools."),
        ])

        def _modify_messages(messages: List[AnyMessage]) -> List[AnyMessage]:
            return prompt.invoke({"input": messages[0].content}).to_messages()

        react_agent = create_react_agent(self.llm, tools, messages_modifier=_modify_messages)

        workflow = StateGraph(AgentState)

        def agent_node(state: AgentState) -> AgentState:
            result = react_agent.invoke({"messages": state["messages"]})
            state["messages"].extend(result["messages"])
            
            # Extract validation results from the agent's output
            for message in result["messages"]:
                if isinstance(message, AIMessage):
                    content = message.content.lower()
                    if "school validation result" in content:
                        state["validation_results"]["school"] = self._parse_validation_result(content)
                    elif "degree validation result" in content:
                        state["validation_results"]["degree"] = self._parse_validation_result(content)
                    elif "modality validation result" in content:
                        state["validation_results"]["modality"] = self._parse_validation_result(content)
            
            # Check if all validations are complete
            required_validations = ["school", "degree", "modality"]
            state["agent_outcome"] = "FINISH" if all(key in state["validation_results"] for key in required_validations) else "CONTINUE"
            
            return state

        def _parse_validation_result(self, content: str) -> str:
            result = "Valid" if "yes" in content else "Invalid" if "no" in content else "Unclear"
            confidence = float(content.split("Confidence: ")[-1].split()[0]) if "Confidence: " in content else 0.5
            return f"{result} (Confidence: {confidence})"

        workflow.add_node("agent", agent_node)

        def router(state: AgentState) -> Literal["agent", "end"]:
            return "end" if state["agent_outcome"] == "FINISH" else "agent"

        workflow.add_node("router", router)

        workflow.add_edge("agent", "router")
        workflow.add_edge("router", "agent")

        workflow.set_entry_point("agent")

        return workflow.compile()
    
    def parse_llm_response(self, response: AIMessage) -> StepOutput:
        content = response.content.strip()
        logging.info(f"Parsing response: {content}")
        
        # Split the response into result and explanation
        parts = content.split(':', 1)
        result = parts[0].strip().lower()
        explanation = parts[1].strip() if len(parts) > 1 else ""
        
        result = "Yes" if result.startswith("yes") else "No" if result.startswith("no") else "Unclear"
        logging.info(f"Extracted result: {result}")
        logging.info(f"Extracted explanation: {explanation}")
        
        uncertainty_words = ["maybe", "possibly", "perhaps", "not sure", "uncertain", "unclear"]
        confidence = 1.0 - sum(word in explanation.lower() for word in uncertainty_words) * 0.1
        confidence = max(0.5, min(1.0, confidence))
        logging.info(f"Calculated confidence: {confidence}")
        
        return StepOutput(result=result, explanation=explanation, confidence=confidence)

    def _validate_school(self, school: str) -> str:
        """Validate if the given school is mentioned in the transcript."""
        state = ValidationState(
            transcript=self.current_state.transcript,
            metadata=self.current_state.metadata,
            current_step="validate_school"
        )
        result = self._validate_step(state, "school", f"Is the school '{school}' mentioned in the transcript?")
        return f"School validation result: {result.validation_results['school']}"

    def _validate_degree(self, degree: str) -> str:
        """Validate if the given degree or a close equivalent is mentioned in the transcript."""
        state = ValidationState(
            transcript=self.current_state.transcript,
            metadata=self.current_state.metadata,
            current_step="validate_degree"
        )
        result = self._validate_step(state, "degree", f"Is the degree '{degree}' or a very close equivalent mentioned in the transcript?")
        return f"Degree validation result: {result.validation_results['degree']}"

    def _validate_modality(self, modality: str) -> str:
        """Validate if the given modality or a close synonym is mentioned in the transcript."""
        state = ValidationState(
            transcript=self.current_state.transcript,
            metadata=self.current_state.metadata,
            current_step="validate_modality"
        )
        result = self._validate_step(state, "modality", f"Is the modality '{modality}' or a very close synonym mentioned in the transcript?")
        return f"Modality validation result: {result.validation_results['modality']}"

    def _call_llm(self, input):
        return self.retry_config.invoke(self.llm.invoke)(input)

    def _validate_step(self, state: ValidationState, step_name: str, prompt: str) -> ValidationState:
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
            state.validation_results[step_name] = f"{parsed_result.result} (Confidence: {parsed_result.confidence})"
            
            # Log the parsed result
            logging.info(f"Parsed result: {parsed_result}")
            
        except Exception as e:
            logging.error(f"Error in _validate_step for {step_name}: {str(e)}")
            state.validation_results[step_name] = "Error (Confidence: 0.5)"
        
        return state

    def predict(self, model_input: MLClassifier.ModelInput) -> MLClassifier.ModelOutput:
        self.current_state = ValidationState(
            transcript=model_input.transcript.lower(),  # Convert transcript to lowercase
            metadata={k: v.lower() for k, v in model_input.metadata.items()},  # Convert metadata values to lowercase
            current_step="school"
        )

        # Validate school
        school_result = self._validate_single_item("school", self.current_state.metadata['school'])
        
        # Validate degree
        degree_result = self._validate_single_item("degree", self.current_state.metadata['degree'])
        
        # Validate modality
        modality_result = self._validate_single_item("modality", self.current_state.metadata['modality'])

        # Combine results
        classification = self._combine_results(school_result, degree_result, modality_result)
        
        return self.ModelOutput(
            classification=classification,
            confidence=classification.get('overall_confidence', 0.5)
        )

    def _validate_single_item(self, item_type: str, item_value: str) -> Dict[str, Any]:
        # Convert item_value and transcript to lowercase
        item_value = item_value.lower()
        lowercase_transcript = self.current_state.transcript.lower()
        
        # First, ask the LLM to confirm the transcript content
        confirm_prompt = f"Please confirm the content of the following transcript by repeating it: '{lowercase_transcript}'"
        confirmation = self._call_llm(confirm_prompt)
        logging.info(f"Transcript confirmation: {confirmation.content}")

        prompt = f"""Transcript: '{lowercase_transcript}'

Question: Is the exact {item_type} '{item_value}' or a very close synonym mentioned in the above transcript?

Instructions:
1. Carefully read the entire transcript.
2. Check if the {item_type} '{item_value}' or a very close synonym is mentioned.
3. Respond with 'Yes' or 'No' followed by a colon and your reasoning.

Example responses:
Yes: The transcript clearly mentions '{item_value}'.
No: The transcript does not mention '{item_value}' or any close synonyms."""

        response = self._call_llm(prompt)
        
        # Log the raw response from the model
        logging.info(f"Raw model response for {item_type}: {response.content}")
        
        parsed_result = self.parse_llm_response(response)
        
        # Log the parsed result
        logging.info(f"Parsed result for {item_type}: {parsed_result}")
        
        return {
            f"{item_type}_validation": parsed_result.result,
            f"{item_type}_confidence": parsed_result.confidence,
            f"{item_type}_explanation": parsed_result.explanation
        }

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

    def _combine_results(self, school_result: Dict[str, Any], degree_result: Dict[str, Any], modality_result: Dict[str, Any]) -> Dict[str, Any]:
        classification = {**school_result, **degree_result, **modality_result}
        
        valid_count = sum(1 for key, val in classification.items() if key.endswith('_validation') and val == "Yes")
        if valid_count == 3:
            classification['overall_validity'] = "Valid"
        elif valid_count == 0:
            classification['overall_validity'] = "Invalid"
        else:
            classification['overall_validity'] = "Partial"

        classification['explanation'] = f"{valid_count} out of 3 validations were successful."
        classification['overall_confidence'] = (
            classification['school_confidence'] + 
            classification['degree_confidence'] + 
            classification['modality_confidence']
        ) / 3

        return classification

    def _parse_agent_output(self, validation_results: Dict[str, Any]) -> Dict[str, Any]:
        classification = {
            "school_validation": "Unclear",
            "school_confidence": 0.5,
            "degree_validation": "Unclear",
            "degree_confidence": 0.5,
            "modality_validation": "Unclear",
            "modality_confidence": 0.5,
            "overall_validity": "Unknown",
            "explanation": ""
        }

        for key, value in validation_results.items():
            if "school" in key:
                classification["school_validation"] = value.split(" (Confidence: ")[0]
                classification["school_confidence"] = float(value.split(" (Confidence: ")[1].split(")")[0])
            elif "degree" in key:
                classification["degree_validation"] = value.split(" (Confidence: ")[0]
                classification["degree_confidence"] = float(value.split(" (Confidence: ")[1].split(")")[0])
            elif "modality" in key:
                classification["modality_validation"] = value.split(" (Confidence: ")[0]
                classification["modality_confidence"] = float(value.split(" (Confidence: ")[1].split(")")[0])

        valid_count = sum(1 for val in [classification['school_validation'], classification['degree_validation'], classification['modality_validation']] if val == "Valid")
        if valid_count == 3:
            classification['overall_validity'] = "Valid"
        elif valid_count == 0:
            classification['overall_validity'] = "Invalid"
        else:
            classification['overall_validity'] = "Partial"

        classification['explanation'] = f"{valid_count} out of 3 validations were successful."
        classification['overall_confidence'] = (classification['school_confidence'] + classification['degree_confidence'] + classification['modality_confidence']) / 3

        return classification

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
        #confidence: float = 1.0

class AgentState(TypedDict):
    messages: List[AnyMessage]
    agent_outcome: Literal["CONTINUE", "FINISH"]
    validation_results: Dict[str, Any]