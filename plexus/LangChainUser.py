import os
from pydantic import ConfigDict, BaseModel
from typing import Literal, Optional

from langchain_core.language_models import BaseLanguageModel
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from langchain_aws import ChatBedrock, ChatBedrockConverse

from langchain_openai import AzureChatOpenAI
from langchain_openai import ChatOpenAI
from langchain_community.callbacks import OpenAICallbackHandler
from langchain_ollama import ChatOllama

from plexus.CustomLogging import logging
from plexus.scores.Score import Score

from langchain_community.chat_models import ChatVertexAI

import threading
from azure.identity import ChainedTokenCredential, AzureCliCredential, DefaultAzureCredential

class LangChainUser:

    class Parameters(BaseModel):
        """
        Parameters for this node.  Based on the LangGraphScore.Parameters class.
        """
        model_config = ConfigDict(protected_namespaces=())
        model_provider: Literal["ChatOpenAI", "AzureChatOpenAI", "BedrockChat", "ChatVertexAI", "ChatOllama"] = "AzureChatOpenAI"
        model_name: Optional[str] = None
        base_model_name: Optional[str] = None
        reasoning_effort: Optional[str] = "low"
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
                    # Method 1: Check response.llm_output (works for most models)
                    if response.llm_output:
                        usage = response.llm_output.get("token_usage", response.llm_output.get("usage", {}))
                    
                    # Method 2: Check usage_metadata (gpt-oss models)
                    if not usage and hasattr(response, 'generations') and response.generations:
                        for gen_list in response.generations:
                            if gen_list:
                                for gen in gen_list:
                                    # Check if usage_metadata is in the message object (gpt-oss models)
                                    if hasattr(gen, 'message') and gen.message and hasattr(gen.message, '__dict__'):
                                        if 'usage_metadata' in gen.message.__dict__:
                                            usage = gen.message.__dict__['usage_metadata']
                                            if usage:
                                                break
                                if usage:
                                    break
                    
                    # Method 3: Check message.response_metadata (gpt-4.1-mini-2025-04-14)
                    if not usage and hasattr(response, 'generations') and response.generations:
                        for gen_list in response.generations:
                            if gen_list:
                                for gen in gen_list:
                                    if hasattr(gen, 'message') and hasattr(gen.message, 'response_metadata'):
                                        response_metadata = gen.message.response_metadata
                                        if 'token_usage' in response_metadata:
                                            usage = response_metadata['token_usage']
                                            break
                            if usage:
                                break

                    # Handle the nested structure
                    if "token_usage" in usage:
                        usage = usage["token_usage"]

                    # Handle different token field names (gpt-oss vs standard)
                    prompt_tokens = usage.get("prompt_tokens") or usage.get("input_tokens", 0)
                    completion_tokens = usage.get("completion_tokens") or usage.get("output_tokens", 0)
                    total_tokens = usage.get("total_tokens", 0)
                    
                    self.prompt_tokens += prompt_tokens
                    self.completion_tokens += completion_tokens
                    self.total_tokens += total_tokens
                    
                    # Track cached tokens if available
                    prompt_tokens_details = usage.get("prompt_tokens_details", {})
                    self.cached_tokens += prompt_tokens_details.get("cached_tokens", 0)

            def on_llm_error(self, error, **kwargs):
                try:
                    logging.error(
                        f"❌ LLM error: {type(error).__name__}: {error} | context_keys={list(kwargs.keys())}"
                    )
                except Exception:
                    pass

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
            
            # Models starting with or containing "gpt-5" do not support temperature/top_p
            model_lc = (params.model_name or "").lower()
            is_gpt5 = model_lc.find("gpt-5") != -1
            # Reasoning/Responses API support for OpenAI models (o*/gpt-5*)
            supports_reasoning = model_lc.startswith("gpt-5") or model_lc.startswith("o")

            if params.model_provider == "AzureChatOpenAI":
                azure_kwargs = {
                    "azure_endpoint": os.getenv("AZURE_API_BASE"),
                    "api_version": os.getenv("AZURE_API_VERSION"),
                    "api_key": os.getenv("AZURE_API_KEY"),
                    "model": params.model_name,
                    "max_tokens": max_tokens,
                }
                if not is_gpt5 and params.temperature is not None:
                    azure_kwargs["temperature"] = params.temperature
                try:
                    base_model = AzureChatOpenAI(**azure_kwargs)
                except TypeError as e:
                    logging.error(f"AzureChatOpenAI init TypeError: {e}.")
                    raise
                except Exception as e:
                    logging.error(f"AzureChatOpenAI init unexpected error: {type(e).__name__}: {e}")
                    raise
            else:  # ChatOpenAI
                # Resolve reasoning effort (guard invalid values)
                allowed_efforts = {"low", "medium", "high", "auto"}
                effort = (params.reasoning_effort or "low").lower()
                if effort not in allowed_efforts:
                    logging.info(f"Invalid reasoning_effort '{params.reasoning_effort}', defaulting to 'low'")
                    effort = "low"
                reasoning = {"effort": effort}

                chat_kwargs = {
                    "model": params.model_name,
                    "api_key": os.getenv("OPENAI_API_KEY"),
                    "max_tokens": max_tokens,
                }
                if supports_reasoning:
                    # Use the Responses API for models that support reasoning
                    chat_kwargs["use_responses_api"] = True
                    # Accumulate model_kwargs rather than replace later
                    chat_kwargs.setdefault("model_kwargs", {})
                    chat_kwargs["model_kwargs"]["reasoning"] = reasoning
                else:
                    pass
                if not is_gpt5 and params.top_p is not None:
                    # chat_kwargs.setdefault("model_kwargs", {})
                    chat_kwargs["top_p"] = params.top_p
                if not is_gpt5 and params.temperature is not None:
                    chat_kwargs["temperature"] = params.temperature
                try:
                    base_model = ChatOpenAI(**chat_kwargs)
                except TypeError as e:
                    logging.error(f"ChatOpenAI init TypeError: {e}.")
                    raise
                except Exception as e:
                    logging.error(f"ChatOpenAI init unexpected error: {type(e).__name__}: {e}")
                    raise
        elif params.model_provider == "BedrockChat":
            model_name = params.model_name or "anthropic.claude-3-haiku-20240307-v1:0"
            
            if "gpt-oss" in model_name.lower():
                bedrock_kwargs = {
                    "model": model_name,
                    "temperature": params.temperature,
                    "max_tokens": max_tokens,
                    "region_name": params.model_region or "us-west-2"
                }
                
                # Add reasoning effort for gpt-oss models
                if params.reasoning_effort:
                    allowed_efforts = {"low", "medium", "high", "auto"}
                    effort = (params.reasoning_effort or "low").lower()
                    if effort not in allowed_efforts:
                        logging.info(f"Invalid reasoning_effort '{params.reasoning_effort}', defaulting to 'low'")
                        effort = "low"
                                            # ChatBedrockConverse accepts reasoning_effort as a direct parameter
                        bedrock_kwargs["reasoning_effort"] = effort
                
                try:
                    base_model = ChatBedrockConverse(**bedrock_kwargs)
                except Exception as e:
                    raise ValueError(f"Failed to initialize gpt-oss model '{model_name}' with ChatBedrockConverse. Error: {e}. Ensure the model is available in your AWS region.")
            else:
                # Use standard ChatBedrock for non-gpt-oss models
                base_model = ChatBedrock(
                    model_id=model_name,
                    model_kwargs={
                        "temperature": params.temperature,
                        "max_tokens": max_tokens
                    },
                    region_name=params.model_region or "us-east-1"
                )
            
            callbacks = [self.token_counter]
        elif params.model_provider == "ChatVertexAI":
            base_model = ChatVertexAI(
                model=params.model_name or "gemini-1.5-flash-001",
                temperature=params.temperature,
                max_output_tokens=max_tokens
            )
            callbacks = [self.token_counter]
        elif params.model_provider == "ChatOllama":
            model_name = params.model_name or "gpt-oss:20b"
            
            # For gpt-oss models with ChatOllama, add reasoning support
            ollama_kwargs = {
                "model": model_name,
                "temperature": params.temperature,
                "max_tokens": max_tokens
            }
            
            # Add reasoning effort for gpt-oss models
            if "gpt-oss" in model_name.lower() and params.reasoning_effort:
                allowed_efforts = {"low", "medium", "high", "auto"}
                effort = (params.reasoning_effort or "low").lower()
                if effort not in allowed_efforts:
                    logging.info(f"Invalid reasoning_effort '{params.reasoning_effort}', defaulting to 'low'")
                    effort = "low"
                # Add reasoning to model_kwargs for Ollama
                ollama_kwargs.setdefault("model_kwargs", {})
                ollama_kwargs["model_kwargs"]["reasoning_effort"] = effort
            
            base_model = ChatOllama(**ollama_kwargs)
            callbacks = [self.token_counter]
        else:
            raise ValueError(f"Unsupported model provider: {params.model_provider}")
        
        # Configure retry logic
        model_with_retry = base_model.with_retry(
            retry_if_exception_type=(Exception,),
            wait_exponential_jitter=True,
            stop_after_attempt=self.MAX_RETRY_ATTEMPTS
        )
        
        # Configure callbacks and max_tokens
        configured_model = model_with_retry.with_config(
            callbacks=callbacks,
            max_tokens=max_tokens
        )
        
        return configured_model

    async def _ainitialize_model(self):
        """
        Asynchronously initialize the language model.
        """
        if self.parameters.model_provider == "ChatOpenAI":
            is_gpt5 = (self.parameters.model_name or "").lower().find("gpt-5") != -1
            kwargs = {
                "model": self.parameters.model_name,
                "max_tokens": self.parameters.max_tokens,
            }
            if not is_gpt5 and self.parameters.temperature is not None:
                kwargs["temperature"] = self.parameters.temperature
            model = ChatOpenAI(**kwargs)
            await model.agenerate([])  # Initialize the async client
            return model
        elif self.parameters.model_provider == "AzureChatOpenAI":
            is_gpt5 = (self.parameters.model_name or "").lower().find("gpt-5") != -1
            kwargs = {
                "deployment_name": self.parameters.model_name,
                "max_tokens": self.parameters.max_tokens,
            }
            if not is_gpt5 and self.parameters.temperature is not None:
                kwargs["temperature"] = self.parameters.temperature
            model = AzureChatOpenAI(**kwargs)
            await model.agenerate([])  # Initialize the async client
            return model
        # ... other model providers ...

    def get_token_usage(self):
        # For OpenAI providers, try OpenAI callback first, fallback to token counter
        if self.parameters.model_provider in ["AzureChatOpenAI", "ChatOpenAI"]:
            if hasattr(self, 'openai_callback') and self.openai_callback:
                # Check if OpenAI callback has valid token data
                if (self.openai_callback.prompt_tokens > 0 or 
                    self.openai_callback.completion_tokens > 0 or
                    self.openai_callback.successful_requests > 0):
                    return {
                        "prompt_tokens": self.openai_callback.prompt_tokens,
                        "completion_tokens": self.openai_callback.completion_tokens,
                        "total_tokens": self.openai_callback.total_tokens,
                        "successful_requests": self.openai_callback.successful_requests,
                        "cached_tokens": getattr(self.openai_callback, 'cached_tokens', 0)
                    }
        
        # Fallback to token counter (used for non-OpenAI providers or when OpenAI callback fails)
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

    # === Normalization helpers for Responses API outputs ===
    def _normalize_content_to_text(self, content) -> str:
        """
        Normalize AIMessage.content which can be a string or a list of content blocks
        (as returned by gpt-oss reasoning models) into a plain string.
        For gpt-oss models, extracts only the final answer text, excluding reasoning content.
        """
        try:
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                collected_parts = []
                for block in content:
                    if isinstance(block, dict):
                        if block.get('type') == 'reasoning_content':
                            continue  # Skip reasoning content - only want final answer
                        elif block.get('type') == 'text':
                            text_val = block.get('text', '')
                            if text_val:
                                collected_parts.append(text_val)
                        else:
                            # Handle standard formats - prefer 'text', fall back to 'content'
                            text_val = block.get('text') or block.get('content') or ''
                            if isinstance(text_val, str) and text_val:
                                collected_parts.append(text_val)
                    else:
                        try:
                            collected_parts.append(str(block))
                        except Exception:
                            pass
                
                # If we have text content, use it
                if collected_parts:
                    return "\n".join(collected_parts)
                return ""
        except Exception:
            return str(content)

    def normalize_response_text(self, response) -> str:
        """
        Extract a plain text string from a LangChain AIMessage-like response.
        """
        try:
            content = getattr(response, 'content', response)
            return self._normalize_content_to_text(content)
        except Exception:
            return str(getattr(response, 'content', ''))

    def extract_reasoning_content(self, response) -> str:
        """
        Extract reasoning content from thinking models responses for logging/debugging.
        Returns empty string for non-thinking models or if no reasoning content found.
        """
        try:
            content = getattr(response, 'content', response)
            
            if isinstance(content, list):
                reasoning_parts = []
                for block in content:
                    if isinstance(block, dict) and block.get('type') == 'reasoning_content':
                        reasoning_text = block.get('reasoning_content', {}).get('text', '')
                        if reasoning_text:
                            reasoning_parts.append(reasoning_text)
                
                if reasoning_parts:
                    return "\n".join(reasoning_parts)
            
            return ""
        except Exception:
            return ""

    def is_gpt_oss_model(self) -> bool:
        """
        Check if the current model is a gpt-oss model.
        """
        return "gpt-oss" in (getattr(self.parameters, 'model_name', '') or '').lower()

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