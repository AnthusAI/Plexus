"""
TactusScore - Score implementation that executes Tactus DSL code.

Tactus is a Lua-based DSL for defining AI agent workflows. This score type
allows embedding Tactus code directly in YAML configuration for classification.

Uses the Tactus runtime with in-process execution (no Docker containers)
for high-volume Plexus scenarios with trusted code.
"""

import json
import logging
from typing import Optional, Union, List, Any, Dict
from pydantic import ConfigDict, model_validator

from plexus.scores.Score import Score
from plexus.LangChainUser import LangChainUser

# Import Tactus components
from tactus.core.runtime import TactusRuntime
from tactus.adapters.memory import MemoryStorage

logger = logging.getLogger(__name__)


class TactusScore(Score, LangChainUser):
    """
    Score that executes embedded Tactus DSL code for classification.

    Uses Tactus runtime with in-process execution (no containers) for
    high-volume Plexus scenarios with trusted code.

    Data flow:
        1. Agent analyzes transcript and returns text response
        2. Lua code in Procedure parses/extracts what it needs
        3. Procedure returns {value, explanation, confidence}
        4. TactusScore maps Procedure output to Score.Result

    Example YAML:
        class: TactusScore
        model_provider: ChatOpenAI
        model_name: gpt-4o-mini
        code: |
          classifier = Agent {
            system_prompt = "Classify sentiment as positive, negative, or neutral..."
          }

          Procedure {
            input = {text = field.string{required = true}},
            output = {value = field.string{required = true}},
            function(input)
              local response = classifier({message = input.text})
              -- Parse the agent's response to extract classification
              local value = "neutral"
              if response:lower():find("positive") then
                value = "positive"
              elseif response:lower():find("negative") then
                value = "negative"
              end
              return {value = value, explanation = response}
            end
          }
    """

    class Parameters(Score.Parameters, LangChainUser.Parameters):
        """Configuration parameters for TactusScore."""
        model_config = ConfigDict(protected_namespaces=())

        # Required: The Tactus DSL code to execute
        code: str

        # Optional: Valid classification classes for validation
        valid_classes: Optional[List[str]] = None

        # Output mapping (optional - defaults to value/explanation)
        output: Optional[Dict[str, str]] = None

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
        """Initialize TactusScore with Tactus code and model configuration."""
        Score.__init__(self, **parameters)
        LangChainUser.__init__(self, **parameters)
        self.parameters = self.Parameters(**parameters)
        self._runtime: Optional[TactusRuntime] = None

    @classmethod
    async def create(cls, **parameters) -> "TactusScore":
        """Factory method for async initialization."""
        instance = cls(**parameters)
        await instance._setup_runtime()
        return instance

    async def _setup_runtime(self):
        """Initialize Tactus runtime with in-process execution."""
        # Use MemoryStorage for stateless score execution
        # (each prediction is independent, no need for persistence)
        storage = MemoryStorage()

        self._runtime = TactusRuntime(
            procedure_id=self.parameters.name or "tactus_score",
            storage_backend=storage,
            openai_api_key=self._get_openai_api_key(),
        )
        logger.info(f"TactusScore initialized for '{self.parameters.name}'")

    def _get_openai_api_key(self) -> Optional[str]:
        """Get OpenAI API key from environment if available."""
        import os
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
                    logger.info(
                        "Parsed nested metadata JSON string, got keys: "
                        f"{list(parsed_inner.keys()) if isinstance(parsed_inner, dict) else 'N/A'}"
                    )
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse nested metadata JSON: {e}")
            elif isinstance(metadata['metadata'], dict):
                # metadata.metadata is already a dict
                logger.info("Found nested metadata dict, preserving outer metadata")
                parsed['metadata'] = metadata['metadata'].copy()

        # Common fields that are JSON strings in Plexus metadata
        json_fields = ['schools', 'other_data']

        for field in json_fields:
            if field in parsed and isinstance(parsed[field], str):
                try:
                    parsed[field] = json.loads(parsed[field])
                    logger.info(f"Parsed JSON string for metadata field '{field}', type={type(parsed[field])}, length={len(parsed[field]) if isinstance(parsed[field], (list, dict)) else 'N/A'}")
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse JSON in metadata field '{field}': {e}")
                    # Keep the original string if parsing fails
            elif field in parsed:
                logger.info(f"Metadata field '{field}' exists but is type {type(parsed[field])}, not a string")

        return parsed

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
        # Create a fresh runtime for each prediction
        # TactusRuntime holds state that doesn't reset cleanly between executions
        storage = MemoryStorage()
        runtime = TactusRuntime(
            procedure_id=self.parameters.name or "tactus_score",
            storage_backend=storage,
            openai_api_key=self._get_openai_api_key(),
        )

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
            logger.debug(f"Executing Tactus procedure with context keys: {list(tactus_context.keys())}")
            result = await runtime.execute(
                self.parameters.code,
                context=tactus_context,
                format="lua"
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
        if cost_breakdown:
            for call in cost_breakdown:
                from decimal import Decimal
                self._cost_accumulator.add_api_call(
                    provider='tactus',
                    model=call.get('model'),
                    prompt_tokens=call.get('prompt_tokens', 0),
                    completion_tokens=call.get('completion_tokens', 0),
                    cached_tokens=call.get('cached_tokens', 0),
                    usd=Decimal(str(call.get('cost', 0.0))),
                    metadata={'tactus_call': call}
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
