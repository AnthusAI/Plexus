"""
TactusScore - Score implementation that executes Tactus DSL code.

Tactus is a Lua-based DSL for defining AI agent workflows. This score type
allows embedding Tactus code directly in YAML configuration for classification.

Uses the Tactus runtime with in-process execution (no Docker containers)
for high-volume Plexus scenarios with trusted code.
"""

import asyncio
import inspect
import json
import logging
import os
from typing import Optional, Union, List, Any, Dict
from pydantic import ConfigDict, model_validator

from plexus.scores.Score import Score
from plexus.utils.score_result_timestamps import extract_score_result_timestamps

# Import Tactus components
from tactus.core.runtime import TactusRuntime
from tactus.adapters.memory import MemoryStorage
from tactus.adapters.cost_collector_log import CostCollectorLogHandler

logger = logging.getLogger(__name__)


class TactusScore(Score):
    """
    Score that executes embedded Tactus DSL code for classification.

    Uses Tactus runtime with in-process execution (no containers) for
    high-volume Plexus scenarios with trusted code.

    The model is specified inside the Lua code via ``default_model`` at the
    procedure level. Individual classifiers inherit it, or can override with
    their own ``model`` parameter.

    Example YAML:
        class: TactusScore
        code: |
          default_model "openai/gpt-5.4-nano"
          ClassifyProcedure {
            classes = {"YES", "NO"},
            system_message = [[
          Classification instructions...
          ]],
            user_message = [[
          Analyze: <transcript>{{ text }}</transcript>
          ]]
          }
    """

    class Parameters(Score.Parameters):
        """Configuration parameters for TactusScore."""
        model_config = ConfigDict(protected_namespaces=())

        # Required: The Tactus DSL code to execute
        code: str

        # Optional: Valid classification classes for validation
        valid_classes: Optional[List[str]] = None

        # Output mapping (optional - defaults to value/explanation)
        output: Optional[Dict[str, str]] = None

        # Model identity is specified inside the Tactus code.
        # These identity fields are kept so existing YAML configs parse.
        model_provider: Optional[str] = None
        model_name: Optional[str] = None
        base_model_name: Optional[str] = None

        # Score-wide runtime defaults. Local Tactus Model/ClassifyProcedure
        # config can still override these values.
        max_tokens: Optional[int] = None
        temperature: Optional[float] = None
        top_p: Optional[float] = None
        reasoning_effort: Optional[str] = None
        verbosity: Optional[str] = None
        model_region: Optional[str] = None
        logprobs: Optional[bool] = None
        top_logprobs: Optional[int] = None
        parse_from_start: Optional[bool] = None

        @model_validator(mode='before')
        @classmethod
        def handle_tactus_code_fallback(cls, data):
            """Accept 'tactus_code' as a fallback for 'code' during transition."""
            if isinstance(data, dict):
                if 'tactus_code' in data and 'code' not in data:
                    data['code'] = data.pop('tactus_code')
                elif 'tactus_code' in data and 'code' in data:
                    data.pop('tactus_code')
            return data

    def __init__(self, **parameters):
        """Initialize TactusScore with Tactus code."""
        Score.__init__(self, **parameters)
        self.parameters = self.Parameters(**parameters)
        isolation_mode = os.getenv("PLEXUS_TACTUS_RUNTIME_ISOLATION_MODE", "strict").lower()
        self._runtime_isolation_mode = "reuse" if isolation_mode == "reuse" else "strict"
        self._runtime_pool: Optional[List[TactusRuntime]] = None
        self._pool_condition: Optional[asyncio.Condition] = None
        self._active_runtimes = 0
        self._max_runtime_pool_size = 0

        if self._runtime_isolation_mode == "reuse":
            self._runtime_pool = []
            self._pool_condition = asyncio.Condition()
            configured_pool_size = os.getenv("PLEXUS_TACTUS_RUNTIME_POOL_SIZE", "8")
            try:
                self._max_runtime_pool_size = max(1, int(configured_pool_size))
            except ValueError:
                self._max_runtime_pool_size = 8

    @classmethod
    async def create(cls, **parameters) -> "TactusScore":
        """Factory method for async initialization."""
        return cls(**parameters)

    def _create_runtime(self) -> TactusRuntime:
        """Create a runtime instance for pool use."""
        storage = MemoryStorage()
        runtime_kwargs = {
            "procedure_id": self.parameters.name or "tactus_score",
            "storage_backend": storage,
            "openai_api_key": self._get_openai_api_key(),
            "reasoning_effort": self.parameters.reasoning_effort,
            "verbosity": self.parameters.verbosity,
            "max_tokens": self.parameters.max_tokens,
            "temperature": self.parameters.temperature,
            "reset_state_on_execute": True,
        }
        runtime_signature = inspect.signature(TactusRuntime.__init__)
        accepts_arbitrary_kwargs = any(
            parameter.kind is inspect.Parameter.VAR_KEYWORD
            for parameter in runtime_signature.parameters.values()
        )
        if accepts_arbitrary_kwargs:
            accepted_runtime_kwargs = runtime_kwargs
        else:
            accepted_runtime_kwargs = {
                key: value
                for key, value in runtime_kwargs.items()
                if key in runtime_signature.parameters
            }
        runtime = TactusRuntime(**accepted_runtime_kwargs)
        logger.debug("Created Tactus runtime for '%s'", self.parameters.name)
        return runtime

    async def _acquire_runtime(self) -> TactusRuntime:
        """Borrow a runtime from the pool, creating one if capacity allows."""
        if self._runtime_isolation_mode == "strict":
            return await asyncio.to_thread(self._create_runtime)
        return await self._acquire_pooled_runtime()

    async def _acquire_pooled_runtime(self) -> TactusRuntime:
        """Borrow a reusable runtime, creating one if pool capacity allows."""
        if self._pool_condition is None or self._runtime_pool is None:
            raise RuntimeError("Runtime pool is not initialized")
        should_create = False
        async with self._pool_condition:
            if self._runtime_pool:
                return self._runtime_pool.pop()
            if self._active_runtimes < self._max_runtime_pool_size:
                self._active_runtimes += 1
                should_create = True
            else:
                await self._pool_condition.wait_for(lambda: bool(self._runtime_pool))
                return self._runtime_pool.pop()

        if should_create:
            try:
                return await asyncio.to_thread(self._create_runtime)
            except Exception:
                async with self._pool_condition:
                    self._active_runtimes = max(0, self._active_runtimes - 1)
                    self._pool_condition.notify()
                raise

    async def _release_runtime(self, runtime: TactusRuntime) -> None:
        """Return a runtime to the pool for reuse."""
        if self._runtime_isolation_mode == "strict":
            return
        if self._pool_condition is None or self._runtime_pool is None:
            raise RuntimeError("Runtime pool is not initialized")
        async with self._pool_condition:
            self._runtime_pool.append(runtime)
            self._pool_condition.notify()

    @staticmethod
    def _execute_runtime_sync(
        runtime: TactusRuntime,
        code: str,
        tactus_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute a runtime call inside a dedicated thread event loop.

        Tactus runtime execution can be heavily synchronous before first await;
        running it in threads allows true parallel score execution.
        """
        return asyncio.run(
            runtime.execute(
                code,
                context=tactus_context,
                format="lua",
            )
        )

    def _get_openai_api_key(self) -> Optional[str]:
        """Get OpenAI API key from environment if available."""
        return os.environ.get("OPENAI_API_KEY")

    def _parse_metadata_json_strings(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse JSON strings in metadata fields into Python objects.

        Plexus metadata often contains JSON strings for nested data like 'schools'
        and 'other_data'. This method parses those strings so Lua code can access
        them as tables instead of strings.

        Parameters
        ----------
        metadata : Dict[str, Any]
            The raw metadata dictionary (may have nested 'metadata' key)

        Returns
        -------
        Dict[str, Any]
            Metadata with JSON strings parsed into Python objects
        """
        if not metadata:
            return {}

        # Handle nested metadata structure (metadata.metadata pattern)
        # The metadata dict may contain a 'metadata' key that is either:
        # 1. A JSON string (needs parsing)
        # 2. A dict (already parsed)
        # Always preserve the outer metadata structure.
        parsed = metadata.copy()
        if 'metadata' in metadata:
            if isinstance(metadata['metadata'], str):
                # metadata.metadata is a JSON string - parse it
                try:
                    parsed_inner = json.loads(metadata['metadata'])
                    parsed['metadata'] = parsed_inner
                    logger.debug(
                        "Parsed nested metadata JSON string, got keys: "
                        f"{list(parsed_inner.keys()) if isinstance(parsed_inner, dict) else 'N/A'}"
                    )
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse nested metadata JSON: {e}")
            elif isinstance(metadata['metadata'], dict):
                # metadata.metadata is already a dict
                logger.debug("Found nested metadata dict, preserving outer metadata")
                parsed['metadata'] = metadata['metadata'].copy()

        # Common fields that are JSON strings in Plexus metadata
        json_fields = ['schools', 'other_data']

        for field in json_fields:
            if field in parsed and isinstance(parsed[field], str):
                try:
                    parsed[field] = json.loads(parsed[field])
                    logger.debug(
                        "Parsed JSON string for metadata field '%s', type=%s, length=%s",
                        field,
                        type(parsed[field]),
                        len(parsed[field]) if isinstance(parsed[field], (list, dict)) else "N/A",
                    )
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse JSON in metadata field '{field}': {e}")
                    # Keep the original string if parsing fails
            elif field in parsed:
                logger.debug(
                    "Metadata field '%s' exists but is type %s, not a string",
                    field,
                    type(parsed[field]),
                )

        return parsed

    async def _enrich_explanation_with_timestamps(
        self,
        runtime: TactusRuntime,
        explanation: Optional[str],
        metadata: Dict[str, Any]
    ) -> str:
        """
        Enrich explanation text with timestamp brackets using Tactus deepgram module.

        If metadata contains deepgram data and explanation contains quotes, this will
        add bracketed timestamps like [M:SS.ff-M:SS.ff] after each quote.

        Parameters
        ----------
        runtime : TactusRuntime
            The runtime instance to use for Lua execution
        explanation : Optional[str]
            The explanation text that may contain quotes
        metadata : Dict[str, Any]
            Metadata that may contain deepgram transcript data

        Returns
        -------
        str
            The explanation with timestamps enriched (or unchanged if no deepgram data)
        """
        if not explanation:
            return explanation or ""

        # Check if we have deepgram data in metadata
        deepgram_data = None
        if metadata:
            # Handle both metadata.deepgram and metadata.metadata.deepgram patterns
            if 'deepgram' in metadata:
                deepgram_data = metadata['deepgram']
            elif 'metadata' in metadata and isinstance(metadata['metadata'], dict):
                deepgram_data = metadata['metadata'].get('deepgram')

        if not deepgram_data and metadata:
            from plexus.utils.deepgram_attachments import load_deepgram_from_attachment_metadata

            deepgram_data = load_deepgram_from_attachment_metadata(metadata)

        if not deepgram_data:
            logger.debug("No deepgram data found in metadata, skipping timestamp enrichment")
            return explanation

        from plexus.utils.quote_normalization import normalize_quotes

        # Normalize quotes so Tactus can match them against the transcript
        explanation_normalized = normalize_quotes(explanation)

        # Call Tactus deepgram.enrich_timestamps() via runtime
        enrichment_code = """
        local deepgram = require("tactus.deepgram")
        local input_text = context.text
        local data = context.data

        -- enrich_timestamps may throw if quotes aren't found - let it propagate
        return deepgram.enrich_timestamps(input_text, data)
        """

        try:
            enrichment_context = {
                'text': explanation_normalized,
                'data': deepgram_data,
            }
            result = await asyncio.to_thread(
                self._execute_runtime_sync,
                runtime,
                enrichment_code,
                enrichment_context,
            )
            enriched = result.get('result', explanation_normalized)
            logger.debug(
                "Enriched explanation with timestamps for score '%s'",
                self.parameters.name
            )
            return enriched if isinstance(enriched, str) else explanation
        except Exception as e:
            # If enrichment fails (e.g., quote not found), log warning and return original
            logger.debug(
                f"Failed to enrich timestamps for score '{self.parameters.name}': {e}"
            )
            return explanation

    async def predict(
        self,
        model_input: Score.Input,
        **_kwargs: Any
    ) -> Union[Score.Result, List[Score.Result]]:
        """
        Execute Tactus procedure and return classification result.

        Parameters
        ----------
        model_input : Score.Input
            The input data containing text and metadata

        Returns
        -------
        Score.Result
            The prediction result with value and explanation
        """
        runtime = await self._acquire_runtime()
        runtime.log_handler = CostCollectorLogHandler()

        try:
            # Build execution context for Tactus
            # Parse JSON strings in metadata so Lua code can access them as tables
            parsed_metadata = self._parse_metadata_json_strings(model_input.metadata or {})

            # Only include fields that are typically in Procedure input schemas
            tactus_context = {
                'text': model_input.text,
                'metadata': parsed_metadata,
            }
            # Only include results if there are any (avoid passing empty list)
            if model_input.results:
                tactus_context['results'] = self._convert_results(model_input.results)

            # Execute the Tactus procedure
            logger.debug(
                "Executing Tactus procedure for score '%s' with context keys: %s",
                self.parameters.name,
                list(tactus_context.keys()),
            )
            result = await asyncio.to_thread(
                self._execute_runtime_sync,
                runtime,
                self.parameters.code,
                tactus_context,
            )

            # Extract value from result
            # Tactus returns a dict with 'result' key containing procedure output
            procedure_output = result.get('result', result)

            # Handle both direct dict and nested result
            if isinstance(procedure_output, dict):
                value = procedure_output.get('value')
                explanation = procedure_output.get('explanation')
                confidence = procedure_output.get('confidence')
            else:
                value = str(procedure_output)
                explanation = None
                confidence = None

            # Enrich explanation with timestamps if deepgram data is available
            # This happens BEFORE extracting timestamps so ClassifyProcedure scores
            # get automatic timestamp enrichment without manual deepgram.enrich_timestamps()
            if explanation:
                explanation = await self._enrich_explanation_with_timestamps(
                    runtime,
                    explanation,
                    parsed_metadata
                )

            # Extract timestamps from enriched explanation or structured fields
            timestamps = extract_score_result_timestamps(
                procedure_output if isinstance(procedure_output, dict) else {},
                explanation
            )

            logger.debug("Tactus returned value '%s' for score '%s'", value, self.parameters.name)

            # Validate required output
            if value is None:
                raise ValueError("Tactus procedure must return 'value' in output")

            # Validate against valid_classes if specified
            if self.parameters.valid_classes and str(value) not in self.parameters.valid_classes:
                logger.warning(
                    f"Tactus returned '{value}' which is not in valid_classes: "
                    f"{self.parameters.valid_classes}"
                )

            # Extract and record cost information from Tactus result
            self._record_tactus_costs(result)

            return Score.Result(
                parameters=self.parameters,
                value=str(value),
                explanation=explanation,
                confidence=self._convert_confidence(confidence),
                start_time_seconds=timestamps.start_time_seconds,
                end_time_seconds=timestamps.end_time_seconds,
                metadata={
                    'tactus_output': result,
                }
            )

        except Exception as e:
            logger.error(f"TactusScore execution error: {e}", exc_info=True)
            return Score.Result(
                parameters=self.parameters,
                value='ERROR',
                error=str(e)
            )
        finally:
            await self._release_runtime(runtime)

    def _record_tactus_costs(self, tactus_result: Dict[str, Any]) -> None:
        """
        Extract cost information from Tactus result and record to cost accumulator.

        Tactus tracks costs including:
        - total_cost: Total USD cost
        - total_tokens: Combined prompt + completion tokens
        - cost_breakdown: List of individual API calls with details

        Parameters
        ----------
        tactus_result : Dict[str, Any]
            The result dictionary from TactusRuntime.execute()
        """
        if not hasattr(self, '_cost_accumulator'):
            logger.warning("TactusScore has no _cost_accumulator attribute")
            return

        # Extract cost information from Tactus result
        total_cost = tactus_result.get('total_cost', 0.0)
        total_tokens = tactus_result.get('total_tokens', 0)
        cost_breakdown = tactus_result.get('cost_breakdown', [])

        # If there's a cost breakdown, record individual API calls
        # CostEvent objects are dataclasses, not dicts — use getattr()
        if cost_breakdown:
            for call in cost_breakdown:
                provider = getattr(call, 'provider', None)
                model = getattr(call, 'model', None)
                if (not provider) and isinstance(model, str) and "/" in model:
                    provider = model.split("/", 1)[0]
                from decimal import Decimal
                self._cost_accumulator.add_api_call(
                    provider=str(provider or "tactus"),
                    model=model,
                    prompt_tokens=getattr(call, 'prompt_tokens', 0),
                    completion_tokens=getattr(call, 'completion_tokens', 0),
                    cached_tokens=getattr(call, 'cache_tokens', 0) or 0,
                    usd=Decimal(str(getattr(call, 'total_cost', 0.0))),
                    metadata={'tactus_call': str(call)}
                )
        elif total_cost > 0 or total_tokens > 0:
            # If no breakdown but we have totals, record a single aggregate call
            from decimal import Decimal
            self._cost_accumulator.add_api_call(
                provider='tactus',
                prompt_tokens=total_tokens,  # Tactus returns combined total
                completion_tokens=0,
                usd=Decimal(str(total_cost)),
                metadata={'note': 'Aggregate Tactus cost (no breakdown available)'}
            )

        logger.debug(f"Recorded Tactus costs: ${total_cost:.4f}, {total_tokens} tokens")

    def _convert_confidence(self, confidence: Any) -> Optional[float]:
        """
        Convert confidence value to float for Score.Result.

        Handles:
        - None -> None
        - float/int -> float (clamped to 0.0-1.0)
        - String numeric -> float
        - String labels ('high', 'medium', 'low') -> float mapping

        Parameters
        ----------
        confidence : Any
            The confidence value from Tactus procedure output

        Returns
        -------
        Optional[float]
            Confidence as float between 0.0 and 1.0, or None if cannot convert
        """
        if confidence is None:
            return None

        # If already numeric, convert and clamp
        if isinstance(confidence, (int, float)):
            return max(0.0, min(1.0, float(confidence)))

        # Try to parse as string
        if isinstance(confidence, str):
            # Try numeric string first
            try:
                val = float(confidence)
                return max(0.0, min(1.0, val))
            except ValueError:
                pass

            # Map string labels to float values
            confidence_map = {
                'high': 0.9,
                'medium': 0.6,
                'med': 0.6,
                'low': 0.3,
                'very high': 0.95,
                'very low': 0.1,
            }
            normalized = confidence.lower().strip()
            if normalized in confidence_map:
                return confidence_map[normalized]

            logger.warning(f"Could not convert confidence '{confidence}' to float, returning None")

        return None

    def _convert_results(self, results: Optional[List[Any]]) -> List[Dict]:
        """Convert Score.Result list to dict format for Tactus."""
        if not results:
            return []

        converted = []
        for r in results:
            if hasattr(r, '__dict__'):
                converted.append({
                    'value': getattr(r, 'value', None),
                    'explanation': getattr(r, 'explanation', None),
                    'confidence': getattr(r, 'confidence', None)
                })
            elif isinstance(r, dict):
                converted.append(r)

        return converted
