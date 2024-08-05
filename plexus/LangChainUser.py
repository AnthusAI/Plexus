import os
from pydantic import ConfigDict, BaseModel
from typing import Literal, Optional

from langchain_core.language_models import BaseLanguageModel
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from langchain_aws import ChatBedrock
from langchain_openai import AzureChatOpenAI, ChatOpenAI
from langchain_google_vertexai import ChatVertexAI
from langchain_community.callbacks import OpenAICallbackHandler

from plexus.CustomLogging import logging
from plexus.scores.Score import Score

class LangChainUser:

    class Parameters(BaseModel):
        """
        Parameters for this node.  Based on the LangGraphScore.Parameters class.
        """
        model_config = ConfigDict(protected_namespaces=())
        model_provider: Literal["ChatOpenAI", "AzureChatOpenAI", "BedrockChat", "ChatVertexAI"] = "AzureChatOpenAI"
        model_name: Optional[str] = None
        base_model_name: Optional[str] = None
        model_region: Optional[str] = None
        temperature: Optional[float] = 0.1
        max_tokens: Optional[int] = 500

    MAX_RETRY_ATTEMPTS = 20

    def _create_token_counter(self):
        """
        Create and return a token counter callback.

        This method sets up a custom callback handler to track token usage
        across different language model providers. It logs detailed information
        about each LLM call and accumulates token counts.

        :return: An instance of TokenCounterCallback.
        """
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

    def _initialize_model(self) -> BaseLanguageModel:
        """
        Initialize and return the appropriate language model based on the configured provider.

        This method sets up the specified language model with retry logic and callbacks
        for token counting. It supports various model providers including OpenAI, Azure,
        Amazon Bedrock, and Google Vertex AI.

        :return: An initialized BaseLanguageModel with retry logic and callbacks.
        :raises ValueError: If an unsupported model provider is specified.
        """
        max_tokens = self.parameters.max_tokens

        if self.parameters.model_provider in ["AzureChatOpenAI", "ChatOpenAI"]:
            self.openai_callback = OpenAICallbackHandler()
            callbacks = [self.openai_callback]
            
            if self.parameters.model_provider == "AzureChatOpenAI":
                base_model = AzureChatOpenAI(
                    azure_endpoint=os.environ.get("AZURE_API_BASE"),
                    api_version=os.environ.get("AZURE_API_VERSION"),
                    api_key=os.environ.get("AZURE_API_KEY"),
                    model=self.parameters.model_name,
                    temperature=self.parameters.temperature,
                    max_tokens=max_tokens
                )
            else:  # ChatOpenAI
                base_model = ChatOpenAI(
                    model=self.parameters.model_name,
                    api_key=os.environ.get("OPENAI_API_KEY"),
                    temperature=self.parameters.temperature,
                    max_tokens=max_tokens
                )
        elif self.parameters.model_provider == "BedrockChat":
            base_model = ChatBedrock(
                model_id=self.parameters.model_name or "anthropic.claude-3-5-sonnet-20240620-v1:0",
                model_kwargs={
                    "temperature": self.parameters.temperature,
                    "max_tokens": max_tokens
                },
                region_name=self.parameters.model_region or "us-east-1"
            )
            callbacks = [self.token_counter]
        elif self.parameters.model_provider == "ChatVertexAI":
            base_model = ChatVertexAI(
                model=self.parameters.model_name or "gemini-1.5-flash-001",
                temperature=self.parameters.temperature,
                max_output_tokens=max_tokens
            )
            callbacks = [self.token_counter]
        else:
            raise ValueError(f"Unsupported model provider: {self.parameters.model_provider}")

        return base_model.with_retry(
            retry_if_exception_type=(Exception,),
            wait_exponential_jitter=True,
            stop_after_attempt=self.MAX_RETRY_ATTEMPTS
        ).with_config(
            callbacks=callbacks,
            max_tokens=max_tokens
        )