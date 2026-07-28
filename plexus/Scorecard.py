import os
import re
import yaml
import logging
import importlib.util
import json
import hashlib
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List, Dict, Any
import asyncio
import tiktoken
from ruamel.yaml import YAML
from datetime import datetime

from plexus.Registries import ScoreRegistry
from plexus.Registries import scorecard_registry
from plexus.scores.Score import Score
from plexus.scores import resolve_score_class

SCORE_RESULT_TRACE_SCHEMA_VERSION = "score_result_dependency_v1"
DEFAULT_TRACE_SCORE_IDENTIFIERS = {
    "information accuracy (composite)",
    "information-accuracy-composite",
    "258bee07-c6c0-492d-b95f-96581a5cfc6c",
    "48813",
    "910707",
}


def _is_lang_graph_score_instance(value: Any) -> bool:
    if value.__class__.__name__ != "LangGraphScore":
        return False
    from plexus.scores.LangGraphScore import LangGraphScore

    return isinstance(value, LangGraphScore)


def _is_batch_processing_pause(value: BaseException) -> bool:
    return (
        value.__class__.__name__ == "BatchProcessingPause"
        and value.__class__.__module__ == "plexus.scores.LangGraphScore"
    )


def _normalize_trace_identifier(value: Any) -> str:
    return str(value or "").strip().lower()


def _stable_fingerprint(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def _excerpt(value: Any, limit: int = 500) -> Optional[str]:
    if value is None:
        return None
    text_value = str(value)
    if len(text_value) <= limit:
        return text_value
    return f"{text_value[:limit]}... [truncated {len(text_value) - limit} chars]"


def _metadata_dict(result: Any) -> dict:
    metadata = getattr(result, "metadata", {}) or {}
    return metadata if isinstance(metadata, dict) else {}


def _score_version_id(score_props: Optional[dict]) -> Optional[str]:
    if not score_props:
        return None
    for key in ("scoreVersionId", "version", "championVersionId", "version_id"):
        value = score_props.get(key)
        if value:
            return str(value)
    return None


def _score_config_fingerprint(score_props: Optional[dict]) -> Optional[str]:
    if not score_props:
        return None
    return _stable_fingerprint(score_props)


def _summarize_metadata_results(metadata_results: Any) -> Any:
    if not metadata_results:
        return None
    if isinstance(metadata_results, list):
        return [
            {
                "name": item.get("name") if isinstance(item, dict) else None,
                "value": item.get("value") if isinstance(item, dict) else None,
                "explanation_excerpt": _excerpt(
                    item.get("explanation") if isinstance(item, dict) else item
                ),
            }
            for item in metadata_results
        ]
    if isinstance(metadata_results, dict):
        return {
            str(key): {
                "value": value.get("value") if isinstance(value, dict) else None,
                "explanation_excerpt": _excerpt(
                    value.get("explanation") if isinstance(value, dict) else value
                ),
            }
            for key, value in metadata_results.items()
        }
    return _excerpt(metadata_results)


def _summarize_score_result(result: Any, *, score_name: Optional[str] = None) -> dict:
    metadata = _metadata_dict(result)
    explanation = metadata.get("explanation") or getattr(result, "explanation", None)
    return {
        "name": score_name or getattr(getattr(result, "parameters", None), "name", None),
        "id": getattr(getattr(result, "parameters", None), "id", None),
        "key": getattr(getattr(result, "parameters", None), "key", None),
        "value": getattr(result, "value", None),
        "explanation_excerpt": _excerpt(explanation),
        "explanation_hash": _stable_fingerprint(explanation) if explanation else None,
        "failed_elements": metadata.get("failed_elements"),
        "metadata_results_summary": _summarize_metadata_results(metadata.get("results")),
        "error": getattr(result, "error", None),
    }


def _should_capture_dependency_trace(score_name: str, score_id: str, score_props: Optional[dict]) -> bool:
    if os.getenv("PLEXUS_SCORE_TRACE_ALL", "").lower() in {"1", "true", "yes"}:
        return True

    configured = os.getenv("PLEXUS_SCORE_TRACE_ALLOWLIST", "")
    allowlist = set(DEFAULT_TRACE_SCORE_IDENTIFIERS)
    allowlist.update(
        _normalize_trace_identifier(token)
        for token in configured.split(",")
        if token.strip()
    )
    candidates = {
        _normalize_trace_identifier(score_name),
        _normalize_trace_identifier(score_id),
        _normalize_trace_identifier((score_props or {}).get("id")),
        _normalize_trace_identifier((score_props or {}).get("key")),
        _normalize_trace_identifier((score_props or {}).get("name")),
    }
    return bool(candidates & allowlist)


def _build_dependency_trace(
    *,
    caller_path: str,
    scorecard_properties: Optional[dict],
    target_score_id: str,
    target_score_name: str,
    target_score_props: Optional[dict],
    dependency_graph: dict,
    execution_order: List[str],
    executed_scores: List[dict],
    composite_input_results: List[dict],
    final_result: Score.Result,
) -> dict:
    failed_elements = _metadata_dict(final_result).get("failed_elements") or []
    child_no_roots = [
        item.get("name")
        for item in composite_input_results
        if str(item.get("value", "")).lower() == "no"
    ]
    failed_set = {str(item) for item in failed_elements}
    child_no_set = {str(item) for item in child_no_roots}
    target_deps = dependency_graph.get(target_score_id, {}).get("deps", [])
    composite_input_names = {item.get("name") for item in composite_input_results}

    return {
        "trace_schema_version": SCORE_RESULT_TRACE_SCHEMA_VERSION,
        "caller_path": caller_path,
        "generated_at": datetime.now().isoformat(),
        "scorecard": {
            "id": (scorecard_properties or {}).get("id"),
            "key": (scorecard_properties or {}).get("key"),
            "name": (scorecard_properties or {}).get("name"),
        },
        "target_score": {
            "id": (target_score_props or {}).get("id", target_score_id),
            "name": target_score_name,
            "key": (target_score_props or {}).get("key"),
            "display_name": (target_score_props or {}).get("name"),
            "scoreVersionId": _score_version_id(target_score_props),
            "score_config_fingerprint": _score_config_fingerprint(target_score_props),
        },
        "dependency_graph": {
            "target": target_score_name,
            "execution_order": execution_order,
            "edges": {
                node_id: {
                    "name": node_data.get("name"),
                    "deps": node_data.get("deps", []),
                    "dependency_names": [
                        dependency_graph.get(dep_id, {}).get("name", dep_id)
                        for dep_id in node_data.get("deps", [])
                    ],
                }
                for node_id, node_data in dependency_graph.items()
            },
        },
        "executed_scores": executed_scores,
        "composite_input_results": composite_input_results,
        "composite_output": _summarize_score_result(final_result, score_name=target_score_name),
        "integrity_checks": {
            "child_no_roots": child_no_roots,
            "failed_elements": failed_elements,
            "failed_elements_match_child_no_roots": failed_set == child_no_set,
            "symmetric_diff": sorted(failed_set.symmetric_difference(child_no_set)),
            "missing_required_dependencies": sorted(
                dependency_graph.get(dep_id, {}).get("name", dep_id)
                for dep_id in target_deps
                if dependency_graph.get(dep_id, {}).get("name", dep_id) not in composite_input_names
            ),
        },
        "memoization": {
            "lookup_performed": False,
            "cache_hit": False,
            "reason": "evaluation_path_executes_same_run_scores",
        },
    }


class Scorecard:
    """
    Represents a collection of scores and manages the computation of these scores for given inputs.

    A Scorecard is the primary way to organize and run classifications in Plexus. Each scorecard
    is typically defined in a YAML file and contains multiple Score instances that work together
    to analyze content. Scorecards support:

    - Hierarchical organization of scores with dependencies
    - Parallel execution of independent scores
    - Cost tracking for API-based scores
    - Integration with MLFlow for experiment tracking
    - Integration with the Plexus dashboard for monitoring

    Common usage patterns:
    1. Loading from YAML:
        scorecard = Scorecard.create_from_yaml('scorecards/qa.yaml')

    2. Scoring content:
        results = await scorecard.score_entire_text(
            text="content to analyze",
            metadata={"source": "phone_call"}
        )

    3. Batch processing:
        for text in texts:
            results = await scorecard.score_entire_text(
                text=text,
                metadata={"batch_id": "123"}
            )
            costs = scorecard.get_accumulated_costs()

    4. Subset scoring:
        results = await scorecard.score_entire_text(
            text="content to analyze",
            subset_of_score_names=["IVR_Score", "Compliance_Score"]
        )

    The Scorecard class is commonly used with Evaluation for measuring accuracy
    and with the dashboard for monitoring production deployments.
    """

    score_registry = None

    @classmethod
    def initialize_registry(cls):
        if cls.score_registry is None:
            cls.score_registry = ScoreRegistry()

    def __init__(self, *, scorecard, api_data=None, scores_config=None):
        """
        Initializes a new instance of the Scorecard class.

        Args:
            scorecard (str): The name or identifier of the scorecard.
            api_data (dict, optional): API-sourced data for the scorecard when using API-first loading.
            scores_config (dict, optional): Dictionary of score configurations when using API-first loading.
        """
        self.initialize_registry()
        self.scorecard_identifier = scorecard

        # Accumulators for tracking the total expenses.
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.cached_tokens = 0
        self.llm_calls = 0
        self.input_cost = Decimal("0.0")
        self.output_cost = Decimal("0.0")
        self.total_cost = Decimal("0.0")
        self.scorecard_total_cost = Decimal("0.0")
        self.cost_per_text = Decimal("0.0")
        self.cost_components = []
        # Track how many texts have been processed by this scorecard instance
        self.number_of_texts_processed = 0

        # Optional preference to load only from local YAML files (no API)
        # Can be set by callers (e.g., CLI/MCP) after construction as well
        self.yaml_only = False

        # Cache for score instances to avoid recreating them for each prediction
        # Key: score name, Value: score instance
        self._score_instance_cache = {}
        # Cost providers report cumulative totals for cached score instances.
        # Track the last seen snapshot per score so scorecard/evaluation totals add
        # only the cost incurred by the current score invocation.
        self._score_cost_snapshots = {}

        # For API-first loading
        if api_data is not None:
            self.properties = api_data
            self.scores_config = scores_config or []
            # Create a fresh registry for this instance
            self.score_registry = ScoreRegistry()

            # Register scores if configurations are provided
            if scores_config:
                self.initialize_from_api_data()
        else:
            # Legacy flow - shared registry approach
            self.score_registry = self.__class__.score_registry
            if hasattr(self.__class__, "properties"):
                self.properties = self.__class__.properties
            if hasattr(self.__class__, "scores"):
                self.scores = self.__class__.scores

    def initialize_from_api_data(self):
        """
        Initialize scores from API data and register them in the instance's score registry.

        This method handles score instantiation when data is loaded directly from the API
        rather than from YAML files.
        """
        if not hasattr(self, "scores_config") or not self.scores_config:
            logging.warning(
                "No score configurations provided for API-first initialization"
            )
            return

        # Process each score configuration
        parsed_configs = []  # Store parsed configs
        for score_config in self.scores_config:
            # Check if this is a string (YAML) that needs parsing
            if isinstance(score_config, str):
                try:
                    yaml_parser = YAML(typ="safe")
                    score_config = yaml_parser.load(score_config)
                    # Always use database UUID from API data if available
                    if (
                        score_config.get("name")
                        and hasattr(self, "properties")
                        and self.properties
                    ):
                        for section in self.properties.get("sections", {}).get(
                            "items", []
                        ):
                            for score_item in section.get("scores", {}).get(
                                "items", []
                            ):
                                if score_item.get("name") == score_config.get("name"):
                                    # Always use database UUID from API, not external ID from YAML
                                    api_id = score_item.get("id")
                                    original_id = score_config.get("id")
                                    if api_id and original_id != api_id:
                                        logging.info(
                                            f"Replacing ID {original_id} with database UUID {api_id} for score {score_config.get('name')}"
                                        )
                                        score_config["id"] = api_id
                                        # Preserve the original external ID for matching purposes
                                        score_config["originalExternalId"] = str(
                                            original_id
                                        )
                                    if not score_config.get("version"):
                                        score_config["version"] = score_item.get(
                                            "championVersionId"
                                        )
                                        logging.info(
                                            f"Setting version {score_item.get('championVersionId')} for score {score_config.get('name')}"
                                        )

                                    # Always copy isDisabled status from API data to config
                                    if "isDisabled" in score_item:
                                        score_config["isDisabled"] = score_item.get(
                                            "isDisabled"
                                        )
                                        logging.info(
                                            f"Setting isDisabled={score_item.get('isDisabled')} for score {score_config.get('name')}"
                                        )
                                    break
                    parsed_configs.append(score_config)
                except Exception as e:
                    logging.warning(
                        f"Invalid score configuration format: {type(score_config)}"
                    )
                    continue
            elif isinstance(score_config, dict):
                # For dict configs, always use the database UUID from API data if available
                if (
                    score_config.get("name")
                    and hasattr(self, "properties")
                    and self.properties
                ):
                    for section in self.properties.get("sections", {}).get("items", []):
                        for score_item in section.get("scores", {}).get("items", []):
                            if score_item.get("name") == score_config.get("name"):
                                # Always use database UUID from API, not external ID from YAML
                                api_id = score_item.get("id")
                                original_id = score_config.get("id")
                                if api_id and original_id != api_id:
                                    logging.info(
                                        f"Replacing ID {original_id} with database UUID {api_id} for score {score_config.get('name')}"
                                    )
                                    score_config["id"] = api_id
                                    # Preserve the original external ID for matching purposes
                                    score_config["originalExternalId"] = str(
                                        original_id
                                    )
                                if not score_config.get("version"):
                                    score_config["version"] = score_item.get(
                                        "championVersionId"
                                    )
                                    logging.info(
                                        f"Setting version {score_item.get('championVersionId')} for score {score_config.get('name')}"
                                    )

                                # Always copy isDisabled status from API data to config
                                if "isDisabled" in score_item:
                                    score_config["isDisabled"] = score_item.get(
                                        "isDisabled"
                                    )
                                    logging.info(
                                        f"Setting isDisabled={score_item.get('isDisabled')} for score {score_config.get('name')}"
                                    )
                                break
                parsed_configs.append(score_config)
            else:
                logging.warning(
                    f"Invalid score configuration format: {type(score_config)}"
                )
                continue

            # Extract necessary information
            score_class_name = score_config.get("class")
            if not score_class_name:
                logging.warning(
                    f"Missing class name in score config: {score_config.get('name')}"
                )
                continue

            # Import score class
            try:
                score_class = resolve_score_class(score_class_name)
            except (ImportError, AttributeError) as e:
                logging.error(
                    f"Failed to import score class {score_class_name}: {str(e)}"
                )
                continue

            # Before registering, log the ID we're about to use
            logging.info(
                f"Registering score {score_config.get('name')} with ID: {score_config.get('id')}"
            )

            # Register in instance's registry
            self.score_registry.register(
                cls=score_class,
                properties=score_config,
                name=score_config.get("name"),
                key=score_config.get("key"),
                id=score_config.get("id"),  # Ensure this is the API ID, not zero
            )

        # Set scores attribute for compatibility with other methods
        self.scores = parsed_configs

        # Log and verify all IDs were preserved
        id_verification = [
            (score.get("name"), score.get("id")) for score in self.scores
        ]
        logging.info(f"ID verification after initialization: {id_verification}")
        logging.info(
            f"Successfully initialized {len(self.scores)} scores from API data"
        )

    @classmethod
    def name(cls):
        """
        Returns the class name of the scorecard.

        Returns:
            str: The name of the class.
        """
        return cls.__name__

    @classmethod
    def score_names(cls):
        # Support both class-level (from create_from_yaml) and instance-level (from create_instance_from_api_data) usage
        # When called on an instance, cls is still the class, but we need to check if it's being called on an instance
        # that has instance-level scores
        if hasattr(cls, "scores") and isinstance(cls.scores, list):
            return [score["name"] for score in cls.scores]
        # If no class-level scores, this might be an instance call - but classmethods can't access instance attributes
        # So we need a separate instance method
        return []

    def get_score_names(self):
        """Instance method to get score names. Works for instances created via create_instance_from_api_data."""
        if hasattr(self, "scores") and isinstance(self.scores, list):
            return [score["name"] for score in self.scores]
        # Fall back to class method for backwards compatibility
        return self.__class__.score_names()

    def name(self):
        """
        Returns the name of this scorecard instance.

        Returns:
            str: The name of the scorecard, from properties if available, otherwise the class name.
        """
        if (
            hasattr(self, "properties")
            and isinstance(self.properties, dict)
            and "name" in self.properties
        ):
            return self.properties["name"]
        return self.__class__.__name__

    @classmethod
    def score_names_to_process(cls):
        """
        Filters and returns score names that need to be processed directly.
        Some scores are computed implicitly by other scores and don't need to be directly processed.

        Returns:
            list of str: Names of scores that need direct processing.
        """
        return [score["name"] for score in cls.scores if "primary" not in score]

    def score_names_to_process(self):
        """
        Instance method for filtering score names that need to be processed directly.

        Returns:
            list of str: Names of scores that need direct processing.
        """
        scores_to_use = (
            self.scores
            if hasattr(self, "scores")
            else getattr(self.__class__, "scores", [])
        )
        return [score["name"] for score in scores_to_use if "primary" not in score]

    @classmethod
    def normalize_score_name(cls, score_name):
        """
        Normalizes a score name by removing whitespace and non-word characters.

        Args:
            score_name (str): The original score name.

        Returns:
            str: A normalized score name suitable for file names or dictionary keys.
        """
        return re.sub(r"\W+", "", score_name.replace(" ", ""))

    @classmethod
    def create_from_yaml(cls, yaml_file_path):
        """
        Creates a Scorecard class dynamically from a YAML file.

        Args:
            yaml_file_path (str): The file path to the YAML file containing the scorecard properties.

        Returns:
            type: A dynamically created Scorecard class.
        """
        logging.info(f"Loading scorecard from YAML file: {yaml_file_path}")
        with open(yaml_file_path, "r") as file:
            scorecard_properties = yaml.safe_load(file)

        scorecard_name = scorecard_properties["name"]

        scorecard_class = type(
            scorecard_name,
            (Scorecard,),
            {
                "properties": scorecard_properties,
                "name": scorecard_properties["name"],
                "scores": scorecard_properties["scores"],
                "score_registry": ScoreRegistry(),
            },
        )

        # Register the scorecard class.
        registration_args = {
            "properties": scorecard_properties,
        }
        if "id" in scorecard_properties:
            registration_args["id"] = scorecard_properties["id"]
        if "key" in scorecard_properties:
            registration_args["key"] = scorecard_properties["key"]
        if "name" in scorecard_properties:
            registration_args["name"] = scorecard_properties["name"]

        scorecard_registry.register(cls=scorecard_class, **registration_args)

        # Register any other scores that are in the YAML file.
        for score_info in scorecard_properties["scores"]:
            score_info["scorecard_name"] = scorecard_properties["name"]
            if "class" in score_info:
                class_name = score_info["class"]
                score_class = resolve_score_class(class_name)
                scorecard_class.score_registry.register(
                    cls=score_class,
                    properties=score_info,
                    name=score_info.get("name"),
                    key=score_info.get("key"),
                    id=score_info.get("id"),
                )

        return scorecard_class

    @classmethod
    def load_and_register_scorecards(cls, directory_path):
        for file_name in os.listdir(directory_path):
            if file_name.endswith(".yaml"):
                yaml_file_path = os.path.join(directory_path, file_name)
                cls.create_from_yaml(yaml_file_path)

    async def get_score_result(
        self, *, scorecard, score, text, metadata, modality, results, item=None
    ):
        """
        Get a result for a score by looking up a Score instance for that score name and calling its
        predict method with the provided input.

        Args:
            scorecard (str): The scorecard identifier.
            score (str): The score identifier.
            text (str): The text content to analyze.
            metadata (dict): Additional metadata for the score.
            modality (str, optional): The modality of the content (e.g., 'Development', 'Production').
            results (list): Previous score results that may be needed for dependent scores.
            item (Item, optional): Item object with attachedFiles for input sources.

        Returns:
            Union[List[Score.Result], Score.Result]: Either a single Result object or a list of Result objects.
            The Result object contains the score value and any associated metadata.

        Raises:
            BatchProcessingPause: When scoring needs to be suspended for batch processing.
            ValueError: When required environment variables are missing.
        """
        logging.info(f"Getting score result for: {score}")

        # Defensive checks for None inputs
        if text is None:
            logging.error(f"Text input is None for score '{score}'")
            return [
                Score.Result(
                    value="ERROR", error=f"Text input is None for score '{score}'"
                )
            ]

        if metadata is None:
            logging.warning(f"Metadata is None for score '{score}', using empty dict")
            metadata = {}

        score_class = self.score_registry.get(score)
        if score_class is None:
            logging.error(f"Score with name '{score}' not found.")
            logging.error(
                f"Available scores in registry: {list(self.score_registry._classes_by_name.keys())}"
            )
            return [
                Score.Result(
                    value="ERROR",
                    error=f"Score with name '{score}' not found.",
                    parameters=Score.Parameters(name=score),
                )
            ]

        score_configuration = self.score_registry.get_properties(score)
        if score_class is not None:
            logging.info(f"Found score class for: {score}")

            # Check if score is disabled - check both 'disabled' (YAML) and 'isDisabled' (API) fields
            is_disabled = score_configuration.get(
                "disabled"
            ) or score_configuration.get("isDisabled")
            if is_disabled is True:
                logging.info(f"Score '{score}' is disabled")
                return [
                    Score.Result(
                        parameters=Score.Parameters(name=score),
                        value="DISABLED",
                        error=f"Score '{score}' is disabled",
                        code="403",
                    )
                ]

            # Calculate content item length in tokens using a general-purpose encoding
            encoding = tiktoken.get_encoding("cl100k_base")
            item_tokens = len(encoding.encode(text))
            logging.info(f"Item tokens for {score}: {item_tokens}")

            # Ensure the scorecard_name is always provided
            score_configuration.update(
                {"scorecard_name": scorecard, "score_name": score}
            )

            # Check if we have a cached instance for this score
            # Use score name as cache key since configuration shouldn't change during evaluation
            if score in self._score_instance_cache:
                logging.debug(f"Reusing cached score instance for: {score}")
                score_instance = self._score_instance_cache[score]
            else:
                logging.info(f"Creating new score instance for: {score}")
                score_instance = await score_class.create(**score_configuration)
                # Cache the instance for reuse
                self._score_instance_cache[score] = score_instance

            if score_instance is None:
                logging.error(
                    f"Score with name '{score}' not found in scorecard '{self.name()}'."
                )
                return [
                    Score.Result(
                        value="ERROR",
                        error=f"Score with name '{score}' not found in scorecard '{self.name()}'.",
                    )
                ]

            # Add required metadata for LangGraphScore
            if _is_lang_graph_score_instance(score_instance):
                account_key = os.getenv("PLEXUS_ACCOUNT_KEY")
                if not account_key:
                    raise ValueError("PLEXUS_ACCOUNT_KEY not found in environment")
                metadata = metadata or {}
                metadata.update(
                    {
                        "account_key": account_key,
                        "scorecard_name": (
                            self.name() if callable(self.name) else self.name
                        ),
                        "score_name": score,
                    }
                )

            try:
                # Convert results to Score.Result objects if needed
                converted_results = []
                for result in results:
                    if isinstance(result, Score.Result):
                        converted_results.append(result)
                    elif isinstance(result, dict):
                        converted_results.append(
                            Score.Result(
                                value=result["value"],
                                metadata=result.get("metadata", {}),
                                parameters=Score.Parameters(name=result["name"]),
                                error=result.get("error"),
                            )
                        )
                    else:
                        raise TypeError(
                            f"Expected Score.Result or dict but got {type(result)}"
                        )

                # Apply input source BEFORE processors (if configured)
                # Note: Errors from input sources are NOT caught - they propagate up
                item_config = score_configuration.get("item")

                # Step 1: Apply input source if class is specified
                if item_config:
                    source_class = item_config.get("class")
                    if source_class and not item:
                        raise ValueError(
                            f"Item is required for input source '{source_class}' but no Item was provided."
                        )

                if item_config and item:
                    source_class = item_config.get("class")

                    if source_class:
                        source_options = item_config.get("options", {})
                        from plexus.input_sources import InputSourceFactory

                        logging.info(
                            f"Using input source '{source_class}' for score '{score}'"
                        )

                        # Create and apply input source (exceptions propagate)
                        input_source = InputSourceFactory.create_input_source(
                            source_class, **source_options
                        )
                        score_input = input_source.extract(
                            item
                        )  # May raise ValueError or other exceptions
                        text = score_input.text
                        if score_input.metadata:
                            metadata = {
                                **score_input.metadata,
                                **(metadata or {}),
                            }

                        logging.info(f"Input source extracted {len(text)} characters")

                # If no input source class specified (or no item config), text remains as item.text (default)

                # Step 2: Apply processors
                # Priority: item.processors > data.processors (for backwards compatibility)
                processors_config = None

                # Check item.processors first (new location)
                if item_config and "processors" in item_config:
                    processors_config = item_config["processors"]
                    logging.info(
                        f"Using item.processors for '{score}': {[p.get('class') for p in processors_config]}"
                    )
                # Fall back to data.processors (legacy location)
                elif (
                    "data" in score_configuration
                    and "processors" in score_configuration["data"]
                ):
                    processors_config = score_configuration["data"]["processors"]
                    logging.info(
                        f"Using data.processors for '{score}': {[p.get('class') for p in processors_config]}"
                    )
                # Fall back to scorecard-level processors
                elif hasattr(self, "properties") and "processors" in self.properties:
                    processors_config = self.properties["processors"]
                    logging.info(
                        f"Using scorecard-level processors for '{score}': {[p.get('class') for p in processors_config]}"
                    )

                # Apply processors if configured
                if processors_config:
                    try:
                        original_text_preview = text[:100] if text else ""
                        processed_input = Score.apply_processors(
                            Score.Input(
                                text=text,
                                metadata=metadata or {},
                                results=converted_results,
                            ),
                            processors_config,
                        )
                        processed_text = processed_input.text
                        processed_text_preview = (
                            processed_text[:100] if processed_text else ""
                        )
                        logging.info(
                            f"Applied {len(processors_config)} processor(s) to text for score '{score}'"
                        )
                        logging.debug(
                            f"Original text preview: {original_text_preview}..."
                        )
                        logging.debug(
                            f"Processed text preview: {processed_text_preview}..."
                        )
                        text = processed_text
                        metadata = processed_input.metadata or {}
                    except Exception as e:
                        logging.error(
                            f"Error applying processors for score '{score}': {e}"
                        )
                        # Continue with unprocessed text rather than failing the prediction
                        logging.warning("Continuing with unprocessed text")

                # Enhanced error handling for predict call
                try:
                    # Additional defensive checks before prediction
                    if text is None:
                        raise ValueError(f"Text is None for score '{score}'")
                    if metadata is None:
                        metadata = {}
                        logging.warning(
                            f"Using empty metadata dict for score '{score}'"
                        )

                    # Let BatchProcessingPause propagate up
                    score_result = await score_instance.predict(
                        context=None,
                        model_input=Score.Input(
                            text=text, metadata=metadata, results=converted_results
                        ),
                    )
                except TypeError as te:
                    if "NoneType" in str(te) and "iterable" in str(te):
                        error_msg = (
                            f"NoneType iteration error in score '{score}': {str(te)}"
                        )
                        logging.error(error_msg)
                        logging.error(
                            f"Input validation - text type: {type(text)}, metadata type: {type(metadata)}"
                        )
                        logging.error(
                            f"Converted results: {len(converted_results)} items"
                        )
                        for i, res in enumerate(converted_results):
                            logging.error(
                                f"  Result {i}: {type(res)} with value {getattr(res, 'value', 'N/A')}"
                            )
                        raise TypeError(error_msg) from te
                    else:
                        raise

                # Get the incremental cost for this score invocation.
                score_total_cost = self._get_score_cost_delta(score, score_instance)

                def attach_incremental_cost(result_item):
                    if isinstance(result_item, Score.Result):
                        if result_item.metadata is None:
                            result_item.metadata = {}
                        if isinstance(result_item.metadata, dict):
                            result_item.metadata["cost"] = self._json_safe_cost(score_total_cost)

                if isinstance(score_result, list):
                    for single_result in score_result:
                        attach_incremental_cost(single_result)
                else:
                    attach_incremental_cost(score_result)

                # Update scorecard's cost accumulators
                self.prompt_tokens += score_total_cost.get("prompt_tokens", 0)
                self.completion_tokens += score_total_cost.get("completion_tokens", 0)
                self.cached_tokens += score_total_cost.get("cached_tokens", 0)
                self.llm_calls += score_total_cost.get("llm_calls", 0)
                self.input_cost += Decimal(str(score_total_cost.get("input_cost", 0)))
                self.output_cost += Decimal(str(score_total_cost.get("output_cost", 0)))
                self.total_cost += Decimal(str(score_total_cost.get("total_cost", 0)))
                self.scorecard_total_cost += Decimal(
                    str(score_total_cost.get("total_cost", 0))
                )
                self.cost_per_text += Decimal(
                    str(score_total_cost.get("cost_per_text", 0))
                )
                if isinstance(score_total_cost.get("components"), list):
                    self.cost_components.extend(score_total_cost.get("components"))

                # Persist the final text that was sent to the model (after input source/processors)
                # so downstream consumers (e.g., evaluation dashboard views) can show what was scored.
                if isinstance(score_result, list):
                    for single_result in score_result:
                        if isinstance(single_result, Score.Result):
                            if single_result.metadata is None:
                                single_result.metadata = {}
                            if isinstance(single_result.metadata, dict):
                                single_result.metadata["text"] = text
                elif isinstance(score_result, Score.Result):
                    if score_result.metadata is None:
                        score_result.metadata = {}
                    if isinstance(score_result.metadata, dict):
                        score_result.metadata["text"] = text

                # Ensure we always return a list of results
                if isinstance(score_result, list):
                    return score_result
                else:
                    return [score_result]

            except Exception as e:
                if _is_batch_processing_pause(e):
                    # Re-raise BatchProcessingPause to be handled by API
                    logging.info(
                        f"BatchProcessingPause caught in get_score_result for {score}"
                    )
                    raise
                raise
            finally:
                if hasattr(score_instance, "cleanup"):
                    try:
                        await score_instance.cleanup()
                    except Exception as cleanup_error:
                        logging.error(
                            f"Error cleaning up score instance for '{score}': {cleanup_error}"
                        )
        else:
            # Defensive fallback to guarantee list return contract.
            return [
                Score.Result(
                    value="ERROR",
                    error=f"Score with name '{score}' is unavailable.",
                    parameters=Score.Parameters(name=score),
                )
            ]

    async def score_entire_text(
        self,
        *,
        score_input: 'Score.Input' = None,
        text: str = None,
        metadata: dict = None,
        modality: Optional[str] = None,
        subset_of_score_names: Optional[List[str]] = None,
        item=None,
    ) -> Dict[str, Score.Result]:
        """
        Score text content using the scorecard's scores.

        Args:
            score_input: Score.Input object (NEW PREFERRED METHOD)
            text: Text to score (DEPRECATED - use score_input instead)
            metadata: Additional metadata (DEPRECATED - use score_input instead)
            modality: Optional modality specification
            subset_of_score_names: Optional list of specific scores to run
            item: Optional Item object

        Returns:
            Dictionary mapping score names to Score.Result objects
        """
        # Handle backwards compatibility: support both old (text, metadata) and new (score_input) signatures
        if score_input is not None:
            # New signature: use Score.Input
            text = score_input.text
            metadata = score_input.metadata if score_input.metadata else {}
        elif text is not None:
            # Old signature: text and metadata provided separately
            if metadata is None:
                metadata = {}
        else:
            raise ValueError("Either score_input or text must be provided")
        if subset_of_score_names is None:
            subset_of_score_names = self.score_names_to_process()

        logging.info(f"Starting to process scores: {subset_of_score_names}")

        # Increment processed text counter for cost-per-text calculations
        try:
            self.number_of_texts_processed += 1
        except Exception:
            # Be resilient if attribute not set for any reason
            self.number_of_texts_processed = 1

        # Calculate content item length in tokens using a general-purpose encoding
        encoding = tiktoken.get_encoding("cl100k_base")
        item_tokens = len(encoding.encode(text))
        logging.info(f"Item tokens for scorecard: {item_tokens}")

        # Helper: ensure a score is loaded/registered (API/YAML on-demand)
        def ensure_score_loaded(score_name: str) -> bool:
            # Already registered
            if self.score_registry.get_properties(score_name):
                return True
            try:
                logging.info(
                    f"Attempting on-demand load for missing score '{score_name}'"
                )
                # Prefer provided identifier; fallback to display name if needed
                scorecard_identifier = self.scorecard_identifier or (
                    self.name() if callable(self.name) else self.name
                )
                logging.info(
                    f"Using scorecard identifier '{scorecard_identifier}' to load score '{score_name}'"
                )

                # Use the standardized loader which pulls champion config from API or YAML cache
                # Honor yaml-only preference when loading scores on-demand
                yaml_only_prefer = getattr(self, "yaml_only", False)
                logging.info(
                    f"Loading with yaml_only={yaml_only_prefer}, use_cache=True"
                )

                loaded_instance = Score.load(
                    scorecard_identifier=scorecard_identifier,
                    score_name=score_name,
                    use_cache=True,
                    yaml_only=yaml_only_prefer,
                )
                if not loaded_instance:
                    logging.warning(
                        f"Score.load() returned None for score '{score_name}' in scorecard '{scorecard_identifier}'"
                    )
                    logging.warning(
                        f"This could mean the score doesn't exist, has a different name, or is in a different scorecard"
                    )
                    return False

                # Build properties from the loaded instance's parameters
                parameters_dict = loaded_instance.parameters.model_dump()
                # Ensure required metadata is present
                parameters_dict["name"] = parameters_dict.get("name") or score_name
                parameters_dict["class"] = loaded_instance.__class__.__name__

                # Register into this instance's registry
                self.score_registry.register(
                    cls=loaded_instance.__class__,
                    properties=parameters_dict,
                    name=parameters_dict.get("name"),
                    key=parameters_dict.get("key"),
                    id=parameters_dict.get("id"),
                )

                # Maintain self.scores list so dependency graph builder can see it
                try:
                    if not hasattr(self, "scores") or not isinstance(self.scores, list):
                        # Start from class scores if available
                        base_scores = getattr(self.__class__, "scores", [])
                        self.scores = (
                            list(base_scores) if isinstance(base_scores, list) else []
                        )
                        logging.info(
                            f"Initialized self.scores with {len(self.scores)} base scores"
                        )

                    # Avoid duplicates by name
                    existing_names = {
                        s.get("name") for s in self.scores if isinstance(s, dict)
                    }
                    if parameters_dict.get("name") not in existing_names:
                        self.scores.append(dict(parameters_dict))
                        logging.info(
                            f"Added score '{score_name}' to self.scores (now has {len(self.scores)} scores)"
                        )
                    else:
                        logging.info(
                            f"Score '{score_name}' already exists in self.scores"
                        )
                except Exception as append_err:
                    logging.warning(
                        f"Could not append loaded score '{score_name}' to self.scores: {append_err}"
                    )

                logging.info(f"On-demand loaded and registered score '{score_name}'")
                return True
            except Exception as e:
                logging.warning(f"On-demand load failed for score '{score_name}': {e}")
                return False

        # Ensure requested scores themselves are loaded first
        for requested_score in list(subset_of_score_names):
            if not self.score_registry.get_properties(requested_score):
                logging.info(f"Loading missing score on-demand: {requested_score}")
                loaded_ok = ensure_score_loaded(requested_score)
                if not loaded_ok:
                    logging.warning(f"Failed to load score: {requested_score}")
                else:
                    logging.info(f"Successfully loaded score: {requested_score}")

        # Recursively add dependent scores to the subset of score names, loading any that are missing
        dependent_scores_added = []
        scores_to_process = list(subset_of_score_names)  # Create a copy to iterate over
        processed_scores = (
            set()
        )  # Track what we've already processed to avoid infinite loops

        logging.info(
            f"Starting recursive dependency resolution for {len(scores_to_process)} initial scores"
        )

        while scores_to_process:
            score_name = scores_to_process.pop(0)

            # Skip if already processed (avoid infinite loops)
            if score_name in processed_scores:
                continue
            processed_scores.add(score_name)

            logging.info(f"Processing dependencies for score: {score_name}")

            score_info = self.score_registry.get_properties(score_name)
            if score_info is None:
                # Try on-demand load before giving up
                if not ensure_score_loaded(score_name):
                    logging.warning(f"No properties found for score: {score_name}")
                    continue
                score_info = self.score_registry.get_properties(score_name)

            # Additional safety check - score_info could still be None after loading attempt
            if score_info is None:
                logging.warning(
                    f"Score info is still None after loading attempt for: {score_name}"
                )
                continue

            if "depends_on" in score_info:
                deps = score_info["depends_on"]
                if isinstance(deps, list):
                    for dependency in deps:
                        # Ensure dependency is registered/loaded
                        if not self.score_registry.get_properties(dependency):
                            logging.info(
                                f"Loading dependency: {dependency} for score: {score_name}"
                            )
                            loaded_ok = ensure_score_loaded(dependency)
                            if not loaded_ok:
                                logging.warning(
                                    f"Failed to load dependency {dependency} for score {score_name}"
                                )
                                continue
                        if dependency not in subset_of_score_names:
                            dependent_scores_added.append(dependency)
                            subset_of_score_names.append(dependency)
                            scores_to_process.append(
                                dependency
                            )  # Add to processing queue for recursive dependency discovery
                            logging.info(
                                f"Added dependency {dependency} to processing queue"
                            )
                elif isinstance(deps, dict):
                    for dependency in deps.keys():
                        # Ensure dependency is registered/loaded
                        if not self.score_registry.get_properties(dependency):
                            logging.info(
                                f"Loading dict dependency: {dependency} for score: {score_name}"
                            )
                            loaded_ok = ensure_score_loaded(dependency)
                            if not loaded_ok:
                                logging.warning(
                                    f"Failed to load dict dependency {dependency} for score {score_name}"
                                )
                                continue
                        if dependency not in subset_of_score_names:
                            dependent_scores_added.append(dependency)
                            subset_of_score_names.append(dependency)
                            scores_to_process.append(
                                dependency
                            )  # Add to processing queue for recursive dependency discovery
                            logging.info(
                                f"Added dict dependency {dependency} to processing queue"
                            )

        logging.info(
            f"Recursive dependency resolution complete. Added {len(dependent_scores_added)} dependent scores: {dependent_scores_added}"
        )
        logging.info(
            f"Final score list contains {len(subset_of_score_names)} scores: {subset_of_score_names}"
        )

        dependency_graph, name_to_id = self.build_dependency_graph(
            subset_of_score_names
        )
        logging.info(f"Built dependency graph: {dependency_graph}")

        results_by_score_id = {}
        results = []
        execution_order_trace = []
        executed_score_traces = []

        async def process_score(score_id: str):
            score_name = dependency_graph[score_id]["name"]
            logging.info(f"Starting to process score: {score_name} (ID: {score_id})")

            try:
                # Check if conditions are met
                if not self.check_dependency_conditions(
                    score_id, dependency_graph, results_by_score_id
                ):
                    logging.info(f"Conditions not met for {score_name}. Skipping.")
                    result = Score.Result(
                        value="SKIPPED",
                        explanation="Score was skipped because dependency conditions were not met",
                        parameters=Score.Parameters(
                            name=score_name, scorecard=self.name
                        ),
                    )
                    results_by_score_id[score_id] = result
                    return

                logging.info(
                    f"About to predict score {score_name} at {datetime.now().isoformat()}"
                )

                # Extract previous results needed for this score
                score_deps = dependency_graph[score_id]["deps"]
                previous_results = []
                logging.info(
                    f"Processing score: {score_name} with dependencies: {score_deps}"
                )
                logging.info(f"Results available: {list(results_by_score_id.keys())}")

                # Detailed logging of dependency results
                dependency_details = []
                previous_result_summaries = []
                for dep_id in score_deps:
                    if dep_id in results_by_score_id:
                        dep_result = results_by_score_id[dep_id]
                        if not (
                            isinstance(dep_result, Score.Result)
                            and dep_result.value == "SKIPPED"
                        ):
                            previous_results.append(dep_result)
                            dep_name = dependency_graph.get(dep_id, {}).get(
                                "name", dep_id
                            )
                            previous_result_summaries.append(
                                _summarize_score_result(
                                    dep_result,
                                    score_name=dep_name,
                                )
                            )
                            dep_value = (
                                getattr(dep_result, "value", "unknown")
                                if hasattr(dep_result, "value")
                                else str(dep_result)
                            )
                            dependency_details.append(f"{dep_name}={dep_value}")
                        else:
                            dep_name = dependency_graph.get(dep_id, {}).get(
                                "name", dep_id
                            )
                            dependency_details.append(f"{dep_name}=SKIPPED")
                    else:
                        dep_name = dependency_graph.get(dep_id, {}).get("name", dep_id)
                        dependency_details.append(f"{dep_name}=MISSING")

                if dependency_details:
                    logging.info(
                        f"📊 STARTING SCORING '{score_name}' using dependency results: [{', '.join(dependency_details)}]"
                    )
                else:
                    logging.info(
                        f"📊 STARTING SCORING '{score_name}' with no dependencies"
                    )

                # Ensure the scorecard_name is included in the score parameters
                score_registry_props = self.score_registry.get_properties(score_name)
                if (
                    score_registry_props
                    and "scorecard_name" not in score_registry_props
                ):
                    score_registry_props["scorecard_name"] = (
                        self.name() if callable(self.name) else self.name
                    )

                # Get the score result
                score_result = await self.get_score_result(
                    scorecard=self.name() if callable(self.name) else self.name,
                    score=score_name,
                    text=text,
                    metadata=metadata,
                    modality=modality,
                    results=previous_results,
                    item=item,
                )

                if score_result is None:
                    logging.info(
                        f"Score {score_name} returned None (possibly paused for batch processing)"
                    )
                    return

                # Handle both single Result objects and lists of results
                if isinstance(score_result, list):
                    result = score_result[0]
                else:
                    result = score_result

                score_config = self.score_registry.get_properties(score_name) or {}
                execution_order_trace.append(score_name)
                executed_score_traces.append({
                    "score": {
                        "id": score_config.get("id", score_id),
                        "name": score_name,
                        "key": score_config.get("key"),
                        "display_name": score_config.get("name"),
                        "scoreVersionId": _score_version_id(score_config),
                        "score_config_fingerprint": _score_config_fingerprint(score_config),
                    },
                    "skipped": False,
                    "input_dependency_names": [
                        item.get("name") for item in previous_result_summaries
                    ],
                    "input_dependencies": previous_result_summaries,
                    "output": _summarize_score_result(result, score_name=score_name),
                })

                if _should_capture_dependency_trace(score_name, score_id, score_config):
                    result.metadata = dict(result.metadata or {})
                    result.metadata["trace"] = _build_dependency_trace(
                        caller_path="scorecard.score_entire_text",
                        scorecard_properties=getattr(self, "properties", {}),
                        target_score_id=score_id,
                        target_score_name=score_name,
                        target_score_props=score_config,
                        dependency_graph=dependency_graph,
                        execution_order=list(execution_order_trace),
                        executed_scores=list(executed_score_traces),
                        composite_input_results=previous_result_summaries,
                        final_result=result,
                    )

                results_by_score_id[score_id] = result
                results.append({"id": score_id, "name": score_name, "result": result})
                logging.info(f"Processed score: {score_name} (ID: {score_id})")

            except Score.SkippedScoreException as e:
                logging.info(f"Score {score_name} was skipped: {e.reason}")
                return

            except Exception as e:
                if _is_batch_processing_pause(e):
                    logging.info(
                        f"Score {score_name} paused for batch processing (thread_id: {e.thread_id})"
                    )
                    # Store the paused state in results
                    results_by_score_id[score_id] = Score.Result(
                        value="PAUSED",
                        error=str(e),
                        parameters=Score.Parameters(name=score_name, scorecard=self.name),
                        metadata={"thread_id": e.thread_id, "batch_job_id": e.batch_job_id},
                    )
                    # Re-raise to be handled by higher-level code
                    raise
                raise

        remaining_scores = set(dependency_graph.keys())
        while remaining_scores:
            try:
                ready_scores = [
                    score_id
                    for score_id in remaining_scores
                    if all(
                        dep in results_by_score_id
                        for dep in dependency_graph[score_id]["deps"]
                    )
                ]
                if not ready_scores:
                    unresolved = ", ".join(
                        dependency_graph[score_id]["name"] for score_id in remaining_scores
                    )
                    raise RuntimeError(
                        f"No dependency-ready scores found. Remaining: {unresolved}"
                    )

                ready_batch = ready_scores
                logging.info(
                    "Processing %s score(s) in parallel (remaining=%s)",
                    len(ready_batch),
                    len(remaining_scores),
                )

                batch_outcomes = await asyncio.gather(
                    *(process_score(score_id) for score_id in ready_batch),
                    return_exceptions=True,
                )
                for score_id, outcome in zip(ready_batch, batch_outcomes):
                    if isinstance(outcome, Exception) and _is_batch_processing_pause(outcome):
                        raise outcome
                    if isinstance(outcome, Exception):
                        raise outcome
                    remaining_scores.discard(score_id)

            except Exception as e:
                if _is_batch_processing_pause(e):
                    # Don't remove from remaining scores, just re-raise to be handled by caller
                    raise
                raise

        logging.info(f"All scores processed. Total scores: {len(results_by_score_id)}")
        return results_by_score_id

    def get_accumulated_costs(self):
        from decimal import Decimal

        cost_per_text = Decimal("0")
        if getattr(self, "number_of_texts_processed", 0):
            # Avoid division by zero and ensure Decimal division
            cost_per_text = self.total_cost / Decimal(
                str(self.number_of_texts_processed)
            )

        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "cached_tokens": self.cached_tokens,
            "llm_calls": self.llm_calls,
            "input_cost": self.input_cost,
            "output_cost": self.output_cost,
            "total_cost": self.total_cost,
            "cost_per_text": cost_per_text,
            "components": self.cost_components,
        }

    @staticmethod
    def _decimal_value(value):
        try:
            return Decimal(str(value or 0))
        except Exception:
            return Decimal("0")

    @staticmethod
    def _component_key(component):
        if not isinstance(component, dict):
            return None
        metadata = component.get("metadata")
        try:
            metadata_key = json.dumps(metadata or {}, sort_keys=True, default=str)
        except Exception:
            metadata_key = str(metadata)
        return (
            component.get("type"),
            component.get("provider"),
            component.get("model"),
            component.get("service"),
            component.get("engine"),
            component.get("operation"),
            component.get("label"),
            metadata_key,
        )

    @classmethod
    def _aggregate_components_by_key(cls, components):
        grouped = {}
        for component in components or []:
            if not isinstance(component, dict):
                continue
            key = cls._component_key(component)
            if key is None:
                continue
            if key not in grouped:
                grouped[key] = dict(component)
            else:
                row = grouped[key]
                for field in (
                    "prompt_tokens",
                    "completion_tokens",
                    "cached_tokens",
                    "llm_calls",
                    "duration_ms",
                    "usd",
                ):
                    if field in component:
                        row[field] = cls._decimal_value(row.get(field)) + cls._decimal_value(component.get(field))
        return grouped

    @classmethod
    def _subtract_cost_snapshots(cls, current, previous):
        if not isinstance(current, dict):
            return {"total_cost": 0}
        if not isinstance(previous, dict):
            previous = {}

        integer_fields = ("prompt_tokens", "completion_tokens", "cached_tokens", "llm_calls")
        money_fields = ("input_cost", "output_cost", "total_cost", "scorecard_total_cost", "cost_per_text")

        delta = dict(current)
        for field in integer_fields:
            delta[field] = max(
                0,
                int(current.get(field, 0) or 0) - int(previous.get(field, 0) or 0),
            )
        for field in money_fields:
            if field in current or field in previous:
                value = cls._decimal_value(current.get(field)) - cls._decimal_value(previous.get(field))
                delta[field] = value if value > 0 else Decimal("0")

        current_components = current.get("components")
        previous_components = previous.get("components")
        if isinstance(current_components, list):
            if isinstance(previous_components, list) and len(current_components) >= len(previous_components):
                if current_components[: len(previous_components)] == previous_components:
                    delta["components"] = current_components[len(previous_components):]
                    return delta

            current_grouped = cls._aggregate_components_by_key(current_components)
            previous_grouped = cls._aggregate_components_by_key(previous_components or [])
            component_deltas = []
            for key, component in current_grouped.items():
                previous_component = previous_grouped.get(key, {})
                row = dict(component)
                has_delta = False
                for field in (
                    "prompt_tokens",
                    "completion_tokens",
                    "cached_tokens",
                    "llm_calls",
                    "duration_ms",
                ):
                    if field in component or field in previous_component:
                        value = int(cls._decimal_value(component.get(field)) - cls._decimal_value(previous_component.get(field)))
                        row[field] = max(0, value)
                        has_delta = has_delta or row[field] > 0
                if "usd" in component or "usd" in previous_component:
                    usd_delta = cls._decimal_value(component.get("usd")) - cls._decimal_value(previous_component.get("usd"))
                    row["usd"] = float(usd_delta if usd_delta > 0 else Decimal("0"))
                    has_delta = has_delta or row["usd"] > 0
                if has_delta:
                    component_deltas.append(row)
            delta["components"] = component_deltas

        return delta

    @classmethod
    def _json_safe_cost(cls, value):
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, dict):
            return {key: cls._json_safe_cost(item) for key, item in value.items()}
        if isinstance(value, list):
            return [cls._json_safe_cost(item) for item in value]
        return value

    def _get_score_cost_delta(self, score_name, score_instance):
        current_costs = score_instance.get_accumulated_costs()
        if not isinstance(current_costs, dict):
            return {"total_cost": 0}
        previous_costs = self._score_cost_snapshots.get(score_name)
        delta = self._subtract_cost_snapshots(current_costs, previous_costs)
        self._score_cost_snapshots[score_name] = current_costs
        return delta

    def get_model_name(self, name=None, id=None, key=None):
        """Return the model name used for a specific score or the scorecard."""
        if name or id or key:
            identifier = id or key or name
            score_class = self.score_registry.get(identifier)
            if score_class:
                return score_class.get_model_name()

        # If no specific score is found or requested, return the scorecard's model name
        return (
            self.properties.get("model_name")
            or self.properties.get("parameters", {}).get("model_name")
            or "Unknown"
        )

    def build_dependency_graph(self, subset_of_score_names):
        """
        Build a dependency graph for the specified subset of scores.

        Args:
            subset_of_score_names: List of score names to include in the graph

        Returns:
            Tuple of (graph, name_to_id) where:
            - graph is a dictionary mapping score IDs to dependency information
            - name_to_id is a dictionary mapping score names to IDs
        """
        graph = {}
        name_to_id = {}

        # Determine which scores collection to use
        scores_to_use = (
            self.scores
            if hasattr(self, "scores")
            else getattr(self.__class__, "scores", [])
        )
        logging.info(
            f"Building dependency graph from {len(scores_to_use)} scores in self.scores"
        )

        # Build complete name_to_id mapping from ALL available scores (not just subset)
        # This is needed for dependency resolution
        for score in scores_to_use:
            score_id = str(score.get("id", ""))
            score_name = score["name"]
            name_to_id[score_name] = score_id
            logging.debug(f"Added to name_to_id mapping: {score_name} -> {score_id}")

        # Also check the score registry for any scores that might not be in self.scores
        logging.info("Checking score registry for additional scores...")
        registry_names = []
        for score_name in subset_of_score_names:
            if score_name not in name_to_id:
                # Try to get the score properties from the registry
                score_props = self.score_registry.get_properties(score_name)
                if score_props:
                    score_id = str(score_props.get("id", ""))
                    if score_id:
                        name_to_id[score_name] = score_id
                        registry_names.append(score_name)
                        logging.info(
                            f"Added score from registry: {score_name} -> {score_id}"
                        )
                    else:
                        logging.warning(f"Score '{score_name}' in registry has no ID")
                else:
                    logging.warning(
                        f"Score '{score_name}' not found in registry or self.scores"
                    )

        if registry_names:
            logging.info(
                f"Added {len(registry_names)} scores from registry: {registry_names}"
            )

        logging.info(
            f"Final name_to_id mapping has {len(name_to_id)} entries: {list(name_to_id.keys())}"
        )

        # Build dependency graph only for scores in the subset
        for score_name in subset_of_score_names:
            # First try to find the score in scores_to_use
            score_data = None
            for score in scores_to_use:
                if score["name"] == score_name:
                    score_data = score
                    break

            # If not found in scores_to_use, try the registry
            if not score_data:
                score_props = self.score_registry.get_properties(score_name)
                if score_props:
                    score_data = score_props
                    logging.info(f"Using score data from registry for: {score_name}")

            if not score_data:
                logging.warning(
                    f"No data found for score '{score_name}' in scores_to_use or registry"
                )
                continue

            score_id = str(score_data.get("id", ""))
            if not score_id:
                logging.warning(
                    f"Score '{score_name}' has no ID, skipping dependency graph entry"
                )
                continue

            # Handle both simple list and conditional dependencies
            dependencies = score_data.get("depends_on", [])
            if isinstance(dependencies, list):
                # Simple list of dependencies - include ALL dependencies that exist in name_to_id
                deps = []
                for dep in dependencies:
                    dep_id = name_to_id.get(dep)
                    if dep_id:  # Only include if we have the dependency loaded
                        deps.append(dep_id)
                    else:
                        logging.warning(
                            f"Dependency '{dep}' for score '{score_name}' not found in loaded scores"
                        )
                graph[score_id] = {"name": score_name, "deps": deps, "conditions": {}}
            elif isinstance(dependencies, dict):
                # Dictionary with conditions - include ALL dependencies that exist in name_to_id
                deps = []
                conditions = {}
                for dep, condition in dependencies.items():
                    dep_id = name_to_id.get(dep)
                    if dep_id:  # Only include if we have the dependency loaded
                        deps.append(dep_id)
                        if isinstance(condition, dict):
                            conditions[dep_id] = condition
                        elif isinstance(condition, str):
                            conditions[dep_id] = {"operator": "==", "value": condition}
                    else:
                        logging.warning(
                            f"Dependency '{dep}' for score '{score_name}' not found in loaded scores"
                        )
                graph[score_id] = {
                    "name": score_name,
                    "deps": deps,
                    "conditions": conditions,
                }
            else:
                # Invalid dependency format or no dependencies
                logging.info(
                    f"Score '{score_name}' has no dependencies or invalid dependency format"
                )
                graph[score_id] = {"name": score_name, "deps": [], "conditions": {}}
        return graph, name_to_id

    def check_dependency_conditions(
        self, score_id: str, dependency_graph: dict, results_by_score_id: dict
    ) -> bool:
        """
        Check if all conditions for a score's dependencies are met.

        Args:
            score_id: The ID of the score to check
            dependency_graph: The dependency graph containing conditions
            results_by_score_id: Dictionary of score results

        Returns:
            bool: True if all conditions are met, False otherwise
        """
        score_info = dependency_graph.get(score_id)
        if not score_info or not score_info["conditions"]:
            return True

        for dep_id, condition in score_info["conditions"].items():
            if dep_id not in results_by_score_id:
                return False

            dep_result = results_by_score_id[dep_id]
            if isinstance(dep_result, Score.Result) and dep_result.value == "PAUSED":
                return False

            # Extract value from result, handling both Score.Result objects and direct values
            if hasattr(dep_result, "value"):
                dep_value = str(dep_result.value).lower().strip()
            else:
                dep_value = str(dep_result).lower().strip()

            operator = condition.get("operator", "==")
            expected_value = str(condition.get("value", "")).lower().strip()

            logging.info(f"Checking condition: {dep_value} {operator} {expected_value}")

            if operator == "==":
                if dep_value != expected_value:
                    logging.info(f"Condition not met: {dep_value} != {expected_value}")
                    return False
            elif operator == "!=":
                if dep_value == expected_value:
                    logging.info(f"Condition not met: {dep_value} == {expected_value}")
                    return False
            elif operator == "in":
                if not isinstance(condition.get("value"), list):
                    expected_values = [str(v).lower().strip() for v in [expected_value]]
                else:
                    expected_values = [
                        str(v).lower().strip() for v in condition.get("value")
                    ]
                if dep_value not in expected_values:
                    logging.info(
                        f"Condition not met: {dep_value} not in {expected_values}"
                    )
                    return False
            elif operator == "not in":
                if not isinstance(condition.get("value"), list):
                    expected_values = [str(v).lower().strip() for v in [expected_value]]
                else:
                    expected_values = [
                        str(v).lower().strip() for v in condition.get("value")
                    ]
                if dep_value in expected_values:
                    logging.info(f"Condition not met: {dep_value} in {expected_values}")
                    return False
            else:
                logging.warning(f"Unsupported operator {operator} for score {score_id}")
                return False

        return True

    @staticmethod
    def create_instance_from_api_data(
        scorecard_id: str, api_data: Dict[str, Any], scores_config: List[Dict[str, Any]]
    ) -> "Scorecard":
        """
        Create a Scorecard instance directly from API data.

        Args:
            scorecard_id: The ID of the scorecard
            api_data: Dictionary containing scorecard metadata from the API
            scores_config: List of score configurations

        Returns:
            A Scorecard instance populated with the API data
        """

        # Verify that the API data contains the correct structure
        if "sections" in api_data and "items" in api_data.get("sections", {}):
            all_api_scores = []
            for section in api_data.get("sections", {}).get("items", []):
                for score in section.get("scores", {}).get("items", []):
                    all_api_scores.append(score)

            # Ensure scores_config has the correct IDs from API data
            for config in scores_config:
                if isinstance(config, dict) and "name" in config:
                    # Look for the corresponding score in API data
                    for api_score in all_api_scores:
                        if api_score.get("name") == config.get("name"):
                            # Always use database UUID from API, not external ID from config
                            api_id = api_score.get("id")
                            original_id = config.get("id")
                            if api_id and original_id != api_id:
                                logging.info(
                                    f"Replacing ID {original_id} with database UUID {api_id} for config {config.get('name')}"
                                )
                                config["id"] = api_id
                                # Preserve the original external ID for matching purposes
                                config["originalExternalId"] = str(original_id)
                            if not config.get("version"):
                                # Reorder fields in the exact order: name, key, id, version, parent
                                ordered_config = {}

                                # Add name if it exists
                                if "name" in config:
                                    ordered_config["name"] = config["name"]

                                # Add key if it exists
                                if "key" in config:
                                    ordered_config["key"] = config["key"]

                                # Add id if it exists
                                if "id" in config:
                                    ordered_config["id"] = config["id"]

                                # Add version
                                ordered_config["version"] = api_score.get(
                                    "championVersionId"
                                )

                                # Add parent if it exists
                                if "parent" in config:
                                    ordered_config["parent"] = config["parent"]

                                # Add all other fields
                                for key, value in config.items():
                                    if key not in [
                                        "name",
                                        "key",
                                        "id",
                                        "version",
                                        "parent",
                                    ]:
                                        ordered_config[key] = value

                                # Replace the original config with ordered config
                                for key in list(config.keys()):
                                    del config[key]
                                for key, value in ordered_config.items():
                                    config[key] = value

                                logging.info(
                                    f"Setting version {api_score.get('championVersionId')} for config {config.get('name')}"
                                )

                            # Always copy isDisabled status from API data to config (regardless of version)
                            if "isDisabled" in api_score:
                                config["isDisabled"] = api_score.get("isDisabled")
                                logging.info(
                                    f"Setting isDisabled={api_score.get('isDisabled')} for score {config.get('name')}"
                                )
                            break
        else:
            logging.warning(
                "API data does not contain expected structure (sections.items)"
            )

        # The scores_config should already be parsed configurations, so we can use them directly
        scorecard_instance = Scorecard(
            scorecard=scorecard_id, api_data=api_data, scores_config=scores_config
        )

        unregistered_scores = []
        for config in scores_config:
            if not isinstance(config, dict):
                continue
            identifiers = (
                config.get("id"),
                config.get("key"),
                config.get("name"),
            )
            if not any(
                identifier
                and scorecard_instance.score_registry.get_properties(identifier)
                for identifier in identifiers
            ):
                unregistered_scores.append(
                    f"{config.get('name') or config.get('key') or config.get('id')} "
                    f"({config.get('class') or 'missing class'})"
                )

        if unregistered_scores:
            raise RuntimeError(
                "Failed to register requested score configurations: "
                + ", ".join(unregistered_scores)
            )

        # Verify IDs after instance creation
        if hasattr(scorecard_instance, "scores"):
            id_verification = [
                (score.get("name"), score.get("id"))
                for score in scorecard_instance.scores
            ]
            logging.info(f"ID verification after instance creation: {id_verification}")

        return scorecard_instance
