import os
from pydantic import ConfigDict, BaseModel
from typing import Literal, Optional

from langchain_core.language_models import BaseLanguageModel
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from langchain_aws import ChatBedrock
from langchain_community.chat_models import AzureChatOpenAI
from langchain_openai import ChatOpenAI
from langchain_community.callbacks import OpenAICallbackHandler
from langchain_community.cache import SQLiteCache
from langchain_core.globals import set_llm_cache

from plexus.CustomLogging import logging
from plexus.scores.Score import Score

from langchain_community.chat_models import BedrockChat, ChatVertexAI

import threading
from azure.identity import ChainedTokenCredential, AzureCliCredential, DefaultAzureCredential

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
        temperature: Optional[float] = 0
        top_p: Optional[float] = 0.03
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
                self.cached_tokens = 0  # New attribute to track cached tokens

            def on_llm_start(self, serialized, prompts, **kwargs):
                self.llm_calls += 1

            def on_llm_end(self, response: LLMResult, **kwargs):
                usage = {}
                if isinstance(response, LLMResult):
                    if response.llm_output:
                        logging.info(f"LLM output: {response.llm_output}")
                        usage = response.llm_output.get("token_usage", response.llm_output.get("usage", {}))
                        logging.debug(f"Token usage: {usage}")

                    # Handle the nested structure
                    if "token_usage" in usage:
                        usage = usage["token_usage"]

                    self.prompt_tokens += usage.get("prompt_tokens", 0)
                    self.completion_tokens += usage.get("completion_tokens", 0)
                    self.total_tokens += usage.get("total_tokens", 0)
                    
                    # Track cached tokens if available
                    prompt_tokens_details = usage.get("prompt_tokens_details", {})
                    self.cached_tokens += prompt_tokens_details.get("cached_tokens", 0)

                    logging.info(f"Current cumulative token usage - Prompt: {self.prompt_tokens}, Completion: {self.completion_tokens}, Total: {self.total_tokens}, Cached: {self.cached_tokens}")

            def on_chain_end(self, outputs, **kwargs):
                logging.info(f"Chain ended. Cumulative token usage - Prompt: {self.prompt_tokens}, Completion: {self.completion_tokens}, Total: {self.total_tokens}, Cached: {self.cached_tokens}")

        return TokenCounterCallback()

    def __init__(self, **parameters):
        self.parameters = self.Parameters(**parameters)
        self.token_counter = self._create_token_counter()
        self.openai_callback = None
        
        self.model = self._initialize_model()

    def _initialize_model(self, custom_params: Optional[dict] = None) -> BaseLanguageModel:
        """
        Initialize and return the appropriate language model based on the configured provider.

        Args:
            custom_params (Optional[dict]): Optional dictionary of parameters to override the default ones

        Returns:
            BaseLanguageModel: An initialized model with retry logic and callbacks.
        """
        # If custom parameters are provided, create a temporary combined parameters object
        params = self.Parameters(**(custom_params or {})) if custom_params else self.parameters
        max_tokens = params.max_tokens

        if params.model_provider in ["AzureChatOpenAI", "ChatOpenAI"]:
            self.openai_callback = OpenAICallbackHandler()
            callbacks = [self.openai_callback, self.token_counter]
            
            if params.model_provider == "AzureChatOpenAI":
                base_model = AzureChatOpenAI(
                    azure_endpoint=os.getenv("AZURE_API_BASE"),
                    api_version=os.getenv("AZURE_API_VERSION"),
                    api_key=os.getenv("AZURE_API_KEY"),
                    model=params.model_name,
                    temperature=params.temperature,
                    max_tokens=max_tokens
                )
            else:  # ChatOpenAI
                # Special handling for o3-mini models
                if params.model_name and "o3-mini" in params.model_name:
                    base_model = ChatOpenAI(
                        model=params.model_name,
                        api_key=os.getenv("OPENAI_API_KEY")
                    )
                else:
                    base_model = ChatOpenAI(
                        model=params.model_name,
                        api_key=os.getenv("OPENAI_API_KEY"),
                        max_tokens=max_tokens,
                        model_kwargs={"top_p": params.top_p},
                        temperature=params.temperature
                    )
        elif params.model_provider == "BedrockChat":
            base_model = ChatBedrock(
                model_id=params.model_name or "anthropic.claude-3-haiku-20240307-v1:0",
                model_kwargs={
                    "temperature": params.temperature,
                    "max_tokens": max_tokens
                },
                region_name=params.model_region or "us-east-1",
                provider="anthropic"
            )
            callbacks = [self.token_counter]
        elif params.model_provider == "ChatVertexAI":
            base_model = ChatVertexAI(
                model=params.model_name or "gemini-1.5-flash-001",
                temperature=params.temperature,
                max_output_tokens=max_tokens
            )
            callbacks = [self.token_counter]
        else:
            raise ValueError(f"Unsupported model provider: {params.model_provider}")

        return base_model.with_retry(
            retry_if_exception_type=(Exception,),
            wait_exponential_jitter=True,
            stop_after_attempt=self.MAX_RETRY_ATTEMPTS
        ).with_config(
            callbacks=callbacks,
            max_tokens=max_tokens
        )

    async def _ainitialize_model(self):
        """
        Asynchronously initialize the language model.
        """
        if self.parameters.model_provider == "ChatOpenAI":
            model = ChatOpenAI(
                model_name=self.parameters.model_name,
                temperature=self.parameters.temperature,
                max_tokens=self.parameters.max_tokens
            )
            await model.agenerate([])  # Initialize the async client
            return model
        elif self.parameters.model_provider == "AzureChatOpenAI":
            model = AzureChatOpenAI(
                deployment_name=self.parameters.model_name,
                temperature=self.parameters.temperature,
                max_tokens=self.parameters.max_tokens
            )
            await model.agenerate([])  # Initialize the async client
            return model
        # ... other model providers ...

    def get_token_usage(self):
        # if self.parameters.model_provider in ["AzureChatOpenAI", "ChatOpenAI"]:
        #     return {
        #         "prompt_tokens": self.openai_callback.prompt_tokens,
        #         "completion_tokens": self.openai_callback.completion_tokens,
        #         "total_tokens": self.openai_callback.total_tokens,
        #         "successful_requests": self.openai_callback.successful_requests
        #     }
        # else:
            return {
                "prompt_tokens": self.token_counter.prompt_tokens,
                "completion_tokens": self.token_counter.completion_tokens,
                "total_tokens": self.token_counter.total_tokens,
                "successful_requests": self.token_counter.llm_calls,
                "cached_tokens": self.token_counter.cached_tokens
            }

    def get_azure_credential(self):
        """Get Azure credential for authentication."""
        if not hasattr(self, '_credential'):
            self._credential = ChainedTokenCredential(
                AzureCliCredential(process_timeout=10),
                DefaultAzureCredential(process_timeout=10),
            )
            # Name the credential refresh threads
            for thread in threading.enumerate():
                if thread.name.startswith('Thread-'):
                    if 'azure' in str(thread._target).lower():
                        thread.name = f"AzureCredential-{thread.ident}"
        return self._credential

    async def cleanup(self):
        """Clean up Azure credentials and any associated threads."""
        if hasattr(self, '_credential'):
            try:
                logging.info("Force closing Azure credential...")
                # Force close any underlying sessions
                if hasattr(self._credential, '_client'):
                    if hasattr(self._credential._client, '_pipeline'):
                        pipeline = self._credential._client._pipeline
                        if hasattr(pipeline, '_transport'):
                            transport = pipeline._transport
                            if hasattr(transport, '_session'):
                                transport._session.close()
                await self._credential.close()
                self._credential = None
                logging.info("Azure credential force closed")
            except Exception as e:
                logging.error(f"Error closing Azure credential: {e}")