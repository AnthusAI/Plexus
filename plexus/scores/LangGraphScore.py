from plexus.scores.Score import Score
from langchain_core.language_models import BaseLanguageModel
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from typing import Tuple, Literal, Optional
from pydantic import ConfigDict

from langchain_core.runnables.graph import MermaidDrawMethod, NodeColors

from langchain_aws import ChatBedrock
from langchain_openai import AzureChatOpenAI
from langchain_google_vertexai import ChatVertexAI

import mlflow
import os
import logging
import traceback

class LangGraphScore(Score):
    class Parameters(Score.Parameters):
        model_config = ConfigDict(protected_namespaces=())
        model_provider: Literal["AzureChatOpenAI", "BedrockChat", "ChatVertexAI"] = "BedrockChat"
        model_name: Optional[str] = None
        model_region: Optional[str] = None
        temperature: float = 0.1
        max_tokens: int = 500

    def __init__(self, **parameters):
        super().__init__(**parameters)
        self.llm = None
        self.llm_with_retry = None
        self.token_counter = self._create_token_counter()
        self.initialize_model()

    def _create_token_counter(self):
        class TokenCounterCallback(BaseCallbackHandler):
            def __init__(self):
                self.prompt_tokens = 0
                self.completion_tokens = 0
                self.total_tokens = 0
                self.llm_calls = 0

            def on_llm_start(self, serialized, prompts, **kwargs):
                self.llm_calls += 1
                logging.info(f"LLM Call {self.llm_calls} started")

            def on_llm_end(self, response: LLMResult, **kwargs):
                logging.info(f"LLM Call {self.llm_calls} ended")
                logging.info(f"Response type: {type(response)}")
                logging.info(f"Response content: {response}")

                usage = {}
                if isinstance(response, LLMResult):
                    if response.llm_output:
                        usage = response.llm_output.get("usage", {})
                        logging.info(f"Token usage from llm_output: {usage}")
                    else:
                        logging.info("No llm_output in response")
                        
                    if response.generations and response.generations[0]:
                        generation = response.generations[0][0]
                        if hasattr(generation, 'generation_info') and generation.generation_info:
                            usage = generation.generation_info.get("token_usage", {})
                            logging.info(f"Token usage from generation_info: {usage}")
                        elif hasattr(generation, 'message') and hasattr(generation.message, 'usage_metadata'):
                            usage = generation.message.usage_metadata
                            logging.info(f"Token usage from usage_metadata: {usage}")
                        else:
                            logging.info("No token usage information found in generation")
                    else:
                        logging.info("No generations in response")

                self.prompt_tokens += usage.get("input_tokens", 0) or usage.get("prompt_tokens", 0)
                self.completion_tokens += usage.get("output_tokens", 0) or usage.get("completion_tokens", 0)
                self.total_tokens += usage.get("total_tokens", 0) or (self.prompt_tokens + self.completion_tokens)

                logging.info(f"Current cumulative token usage - Prompt: {self.prompt_tokens}, Completion: {self.completion_tokens}, Total: {self.total_tokens}")

            def on_chain_end(self, outputs, **kwargs):
                logging.info(f"Chain ended. Cumulative token usage - Prompt: {self.prompt_tokens}, Completion: {self.completion_tokens}, Total: {self.total_tokens}")

        return TokenCounterCallback()

    def initialize_model(self):
        self.llm = self._initialize_model()
        self.llm_with_retry = self.llm.with_retry(
            retry_if_exception_type=(Exception,),
            wait_exponential_jitter=True,
            stop_after_attempt=3
        ).with_config(callbacks=[self.token_counter])
        
        self.log_model_params()

    def log_model_params(self):
        mlflow.log_param("model_provider", self.parameters.model_provider)
        mlflow.log_param("model_name", self.parameters.model_name)
        mlflow.log_param("model_region", self.parameters.model_region)
        mlflow.log_param("temperature", self.parameters.temperature)
        mlflow.log_param("max_tokens", self.parameters.max_tokens)

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

    def _split_name(self, name: str, separator: str = "\n") -> str:
        """
        Split a name into two parts, separated by the given separator.
        
        Args:
            name (str): The name to split.
            separator (str, optional): The separator to use. Defaults to "\n".
        
        Returns:
            str: The name split into two parts.
        """
        words = name.replace(":", "").split()
        mid = len(words) // 2
        return f"{' '.join(words[:mid])}{separator}{' '.join(words[mid:])}"

    def generate_graph_visualization(self, output_path: str = "./tmp/workflow_graph.png"):
        """
        Generate and save a PNG visualization of the workflow graph.

        Args:
            output_path (str): The path where the PNG file will be saved.
        """
        try:
            # Get the graph
            graph = self.workflow.get_graph()

            # Ensure the directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Set a larger wrap_label_n_words to accommodate longer node names
            wrap_label_n_words = 1  # Adjust this value as needed

            graph.draw_mermaid_png(
                draw_method=MermaidDrawMethod.API,
                node_colors=NodeColors(
                    start="#73fa97",
                    end="#f086bb",
                    other="#deeffa"
                ),
                background_color="white",
                padding=10,
                output_file_path=output_path,
                wrap_label_n_words=wrap_label_n_words
            )

            logging.info(f"Graph visualization saved to {output_path}")
            
            # Log the graph as an artifact in MLflow
            mlflow.log_artifact(output_path)
        except Exception as e:
            error_msg = f"Failed to generate graph visualization: {str(e)}\n{traceback.format_exc()}"
            logging.error(error_msg)


    def _parse_validation_result(self, output: str) -> Tuple[str, str]:
        """
        Parse the output from the language model to determine the validation result and explanation.

        Args:
            output (str): The raw output from the language model.

        Returns:
            Tuple[str, str]: A tuple containing the validation result and explanation.
        """
        logging.info(f"Raw output to parse: {output}")
        
        # Clean and normalize the output
        cleaned_output = output.strip().lower()
        
        # Extract the first word, handling potential punctuation
        first_word = cleaned_output.split(None, 1)[0].rstrip('.,')
        
        if first_word == "yes":
            validation_result = "Yes"
        elif first_word == "no":
            validation_result = "No"
        else:
            validation_result = "Unclear"

        # Extract explanation (everything after the first word)
        explanation = cleaned_output[len(first_word):].lstrip('., ')

        logging.info(f"Parsed result: {validation_result}")
        logging.info(f"Parsed explanation: {explanation}")

        return validation_result, explanation

    def register_model(self):
        """
        Register the model with MLflow by logging relevant parameters.
        """
        mlflow.log_param("model_type", self.__class__.__name__)
        mlflow.log_param("model_provider", self.parameters.model_provider)
        mlflow.log_param("model_name", self.parameters.model_name)

    def save_model(self):
        """
        Save the model to a specified path and log it as an artifact with MLflow.
        """
        model_path = f"models/{self.__class__.__name__}_{self.parameters.model_provider}_{self.parameters.model_name}"
        mlflow.log_artifact(model_path)