import os
import re
import yaml
import json
import requests
import json
import rich
import logging
import pandas as pd
import importlib.util
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List, Dict, Union, Any
import asyncio
import boto3
from botocore.exceptions import ClientError
import tiktoken
from os import getenv
from ruamel.yaml import YAML
from datetime import datetime

from plexus.Registries import ScoreRegistry
from plexus.Registries import scorecard_registry
import plexus.scores
from plexus.scores.Score import Score
from plexus.plexus_logging.Cloudwatch import CloudWatchLogger
from plexus.scores.LangGraphScore import BatchProcessingPause, LangGraphScore
from plexus.utils.dict_utils import truncate_dict_strings_inner, truncate_dict_strings

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
        self.input_cost =  Decimal('0.0')
        self.output_cost = Decimal('0.0')
        self.total_cost =  Decimal('0.0')
        self.scorecard_total_cost = Decimal('0.0')
        self.cost_per_text = Decimal('0.0')
        # Track how many texts have been processed by this scorecard instance
        self.number_of_texts_processed = 0

        self.cloudwatch_logger = CloudWatchLogger()
        # Optional preference to load only from local YAML files (no API)
        # Can be set by callers (e.g., CLI/MCP) after construction as well
        self.yaml_only = False
        
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
            if hasattr(self.__class__, 'properties'):
                self.properties = self.__class__.properties
            if hasattr(self.__class__, 'scores'):
                self.scores = self.__class__.scores
                
    def initialize_from_api_data(self):
        """
        Initialize scores from API data and register them in the instance's score registry.
        
        This method handles score instantiation when data is loaded directly from the API
        rather than from YAML files.
        """
        if not hasattr(self, 'scores_config') or not self.scores_config:
            logging.warning("No score configurations provided for API-first initialization")
            return
            
        # Process each score configuration
        parsed_configs = []  # Store parsed configs
        for score_config in self.scores_config:
            # Check if this is a string (YAML) that needs parsing
            if isinstance(score_config, str):
                try:
                    yaml_parser = YAML(typ='safe')
                    score_config = yaml_parser.load(score_config)
                    # Always use database UUID from API data if available
                    if score_config.get('name') and hasattr(self, 'properties') and self.properties:
                        for section in self.properties.get('sections', {}).get('items', []):
                            for score_item in section.get('scores', {}).get('items', []):
                                if score_item.get('name') == score_config.get('name'):
                                    # Always use database UUID from API, not external ID from YAML
                                    api_id = score_item.get('id')
                                    original_id = score_config.get('id')
                                    if api_id and original_id != api_id:
                                        logging.info(f"Replacing ID {original_id} with database UUID {api_id} for score {score_config.get('name')}")
                                        score_config['id'] = api_id
                                        # Preserve the original external ID for matching purposes
                                        score_config['originalExternalId'] = str(original_id)
                                    if not score_config.get('version'):
                                        score_config['version'] = score_item.get('championVersionId')
                                        logging.info(f"Setting version {score_item.get('championVersionId')} for score {score_config.get('name')}")
                                    break
                    parsed_configs.append(score_config)
                except Exception as e:
                    logging.warning(f"Invalid score configuration format: {type(score_config)}")
                    continue
            elif isinstance(score_config, dict):
                # For dict configs, always use the database UUID from API data if available
                if score_config.get('name') and hasattr(self, 'properties') and self.properties:
                    for section in self.properties.get('sections', {}).get('items', []):
                        for score_item in section.get('scores', {}).get('items', []):
                            if score_item.get('name') == score_config.get('name'):
                                # Always use database UUID from API, not external ID from YAML
                                api_id = score_item.get('id')
                                original_id = score_config.get('id')
                                if api_id and original_id != api_id:
                                    logging.info(f"Replacing ID {original_id} with database UUID {api_id} for score {score_config.get('name')}")
                                    score_config['id'] = api_id
                                    # Preserve the original external ID for matching purposes
                                    score_config['originalExternalId'] = str(original_id)
                                if not score_config.get('version'):
                                    score_config['version'] = score_item.get('championVersionId')
                                    logging.info(f"Setting version {score_item.get('championVersionId')} for score {score_config.get('name')}")
                                break
                parsed_configs.append(score_config)
            else:
                logging.warning(f"Invalid score configuration format: {type(score_config)}")
                continue
                
            # Extract necessary information
            score_class_name = score_config.get('class')
            if not score_class_name:
                logging.warning(f"Missing class name in score config: {score_config.get('name')}")
                continue
                
            # Import score class
            try:
                score_module = importlib.import_module(f'plexus.scores')
                score_class = getattr(score_module, score_class_name)
            except (ImportError, AttributeError) as e:
                logging.error(f"Failed to import score class {score_class_name}: {str(e)}")
                continue
                
            # Before registering, log the ID we're about to use
            logging.info(f"Registering score {score_config.get('name')} with ID: {score_config.get('id')}")
                
            # Register in instance's registry
            self.score_registry.register(
                cls=score_class,
                properties=score_config,
                name=score_config.get('name'),
                key=score_config.get('key'),
                id=score_config.get('id')  # Ensure this is the API ID, not zero
            )
            
        # Set scores attribute for compatibility with other methods
        self.scores = parsed_configs
        
        # Log and verify all IDs were preserved
        id_verification = [(score.get('name'), score.get('id')) for score in self.scores]
        logging.info(f"ID verification after initialization: {id_verification}")
        logging.info(f"Successfully initialized {len(self.scores)} scores from API data")

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
        return [score['name'] for score in cls.scores]

    def name(self):
        """
        Returns the name of this scorecard instance.
        
        Returns:
            str: The name of the scorecard, from properties if available, otherwise the class name.
        """
        if hasattr(self, 'properties') and isinstance(self.properties, dict) and 'name' in self.properties:
            return self.properties['name']
        return self.__class__.__name__

    @classmethod
    def score_names_to_process(cls):
        """
        Filters and returns score names that need to be processed directly.
        Some scores are computed implicitly by other scores and don't need to be directly processed.

        Returns:
            list of str: Names of scores that need direct processing.
        """
        return [
            score['name'] for score in cls.scores
            if 'primary' not in score
        ]
        
    def score_names_to_process(self):
        """
        Instance method for filtering score names that need to be processed directly.
        
        Returns:
            list of str: Names of scores that need direct processing.
        """
        scores_to_use = self.scores if hasattr(self, 'scores') else getattr(self.__class__, 'scores', [])
        return [
            score['name'] for score in scores_to_use
            if 'primary' not in score
        ]

    @classmethod
    def normalize_score_name(cls, score_name):
        """
        Normalizes a score name by removing whitespace and non-word characters.

        Args:
            score_name (str): The original score name.

        Returns:
            str: A normalized score name suitable for file names or dictionary keys.
        """
        return re.sub(r'\W+', '', score_name.replace(' ', ''))

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
        with open(yaml_file_path, 'r') as file:
                scorecard_properties = yaml.safe_load(file)

        scorecard_name = scorecard_properties['name']

        scorecard_class = type(scorecard_name, (Scorecard,), {
            'properties':            scorecard_properties,
            'name':                  scorecard_properties['name'],
            'scores':                scorecard_properties['scores'],
            'score_registry':        ScoreRegistry()
        })

        # Register the scorecard class.
        registration_args = {
            'properties': scorecard_properties,
        }
        if 'id' in scorecard_properties:
            registration_args['id'] = scorecard_properties['id']
        if 'key' in scorecard_properties:
            registration_args['key'] = scorecard_properties['key']
        if 'name' in scorecard_properties:
            registration_args['name'] = scorecard_properties['name']
        
        scorecard_registry.register(
            cls=scorecard_class,
            **registration_args
        )

        # Register any other scores that are in the YAML file.
        for score_info in scorecard_properties['scores']:
            score_info['scorecard_name'] = scorecard_properties['name']
            if 'class' in score_info:
                class_name = score_info['class']
                module = importlib.import_module('plexus.scores')
                score_class = getattr(module, class_name)
                scorecard_class.score_registry.register(
                    cls=score_class,
                    properties=score_info,
                    name=score_info.get('name'),
                    key=score_info.get('key'),
                    id=score_info.get('id')
                )

        return scorecard_class
    
    @classmethod
    def load_and_register_scorecards(cls, directory_path):
        for file_name in os.listdir(directory_path):
            if file_name.endswith('.yaml'):
                yaml_file_path = os.path.join(directory_path, file_name)
                cls.create_from_yaml(yaml_file_path)

    async def get_score_result(self, *, scorecard, score, text, metadata, modality, results):
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

        Returns:
            Union[List[Score.Result], Score.Result]: Either a single Result object or a list of Result objects.
            The Result object contains the score value and any associated metadata.

        Raises:
            BatchProcessingPause: When scoring needs to be suspended for batch processing.
            ValueError: When required environment variables are missing.
        """
        logging.info(f"Getting score result for: {score}")
        
        score_class = self.score_registry.get(score)
        if score_class is None:
            logging.error(f"Score with name '{score}' not found.")
            return [Score.Result(value="ERROR", error=f"Score with name '{score}' not found.")]

        score_configuration = self.score_registry.get_properties(score)
        if (score_class is not None):
            logging.info(f"Found score class for: {score}")

            # Check if score is disabled - check both 'disabled' (YAML) and 'isDisabled' (API) fields
            is_disabled = score_configuration.get('disabled') or score_configuration.get('isDisabled')
            if is_disabled is True:
                logging.info(f"Score '{score}' is disabled")
                return [Score.Result(
                    parameters=Score.Parameters(name=score),
                    value="DISABLED",
                    error=f"Score '{score}' is disabled",
                    code="403"
                )]

            # Calculate content item length in tokens using a general-purpose encoding
            encoding = tiktoken.get_encoding("cl100k_base")
            item_tokens = len(encoding.encode(text))
            logging.info(f"Item tokens for {score}: {item_tokens}")

            # Ensure the scorecard_name is always provided
            score_configuration.update({
                'scorecard_name': scorecard,
                'score_name': score
            })
                        
            score_instance = await score_class.create(**score_configuration)

            if score_instance is None:
                logging.error(f"Score with name '{score}' not found in scorecard '{self.name()}'.")
                return [Score.Result(value="ERROR", error=f"Score with name '{score}' not found in scorecard '{self.name()}'.")]

            # Add required metadata for LangGraphScore
            if isinstance(score_instance, LangGraphScore):
                account_key = os.getenv('PLEXUS_ACCOUNT_KEY')
                if not account_key:
                    raise ValueError("PLEXUS_ACCOUNT_KEY not found in environment")
                metadata = metadata or {}
                metadata.update({
                    'account_key': account_key,
                    'scorecard_name': self.name() if callable(self.name) else self.name,
                    'score_name': score
                })

            try:
                # Convert results to Score.Result objects if needed
                converted_results = []
                for result in results:
                    if isinstance(result, Score.Result):
                        converted_results.append(result)
                    elif isinstance(result, dict):
                        converted_results.append(Score.Result(
                            value=result['value'],
                            metadata=result.get('metadata', {}),
                            parameters=Score.Parameters(name=result['name']),
                            error=result.get('error')
                        ))
                    else:
                        raise TypeError(f"Expected Score.Result or dict but got {type(result)}")

                # Let BatchProcessingPause propagate up
                score_result = await score_instance.predict(
                    context=None,
                    model_input=Score.Input(
                        text=text,
                        metadata=metadata,
                        results=converted_results
                    )
                )

                # Get the total cost for this score
                score_total_cost = score_instance.get_accumulated_costs()

                # Update scorecard's cost accumulators
                self.prompt_tokens += score_total_cost.get('prompt_tokens', 0)
                self.completion_tokens += score_total_cost.get('completion_tokens', 0)
                self.cached_tokens += score_total_cost.get('cached_tokens', 0)
                self.llm_calls += score_total_cost.get('llm_calls', 0)
                self.input_cost += score_total_cost.get('input_cost', 0)
                self.output_cost += score_total_cost.get('output_cost', 0)
                self.total_cost += Decimal(str(score_total_cost.get('total_cost', 0)))
                self.scorecard_total_cost += Decimal(str(score_total_cost.get('total_cost', 0)))
                self.cost_per_text += Decimal(str(score_total_cost.get('cost_per_text', 0)))

                # Log CloudWatch metrics for this individual score
                total_tokens = score_total_cost.get('prompt_tokens', 0) + score_total_cost.get('completion_tokens', 0)
                dimensions = {
                    'ScoreCardID': str(self.properties.get('id', 'unknown')),
                    'ScoreCardName': str(self.properties.get('name', 'unknown')),
                    'Score': str(score_configuration.get('name', 'unknown')),
                    'ScoreID': str(score_configuration.get('id', 'unknown')),
                    'Modality': modality or 'Development',
                    'Environment': os.getenv('environment') or 'Unknown'
                }
                
                self.cloudwatch_logger.log_metric('Cost', score_total_cost.get('total_cost', 0), dimensions)
                self.cloudwatch_logger.log_metric('PromptTokens', score_total_cost.get('prompt_tokens', 0), dimensions)
                self.cloudwatch_logger.log_metric('CompletionTokens', score_total_cost.get('completion_tokens', 0), dimensions)
                self.cloudwatch_logger.log_metric('TotalTokens', total_tokens, dimensions)
                self.cloudwatch_logger.log_metric('CachedTokens', score_total_cost.get('cached_tokens', 0), dimensions)
                self.cloudwatch_logger.log_metric('ExternalAIRequests', score_total_cost.get('llm_calls', 0), dimensions)

                scorecard_dimensions = {
                    'ScoreCardName': str(self.properties.get('name', 'unknown')),
                    'Environment': os.getenv('environment') or 'Unknown'
                }

                self.cloudwatch_logger.log_metric('CostByScorecard', score_total_cost.get('total_cost', 0), scorecard_dimensions)
                self.cloudwatch_logger.log_metric('PromptTokensByScorecard', score_total_cost.get('prompt_tokens', 0), scorecard_dimensions)
                self.cloudwatch_logger.log_metric('CompletionTokensByScorecard', score_total_cost.get('completion_tokens', 0), scorecard_dimensions)
                self.cloudwatch_logger.log_metric('TotalTokensByScorecard', total_tokens, scorecard_dimensions)
                self.cloudwatch_logger.log_metric('CachedTokensByScorecard', score_total_cost.get('cached_tokens', 0), scorecard_dimensions)
                self.cloudwatch_logger.log_metric('ExternalAIRequestsByScorecard', score_total_cost.get('llm_calls', 0), scorecard_dimensions)

                # Ensure we always return a list of results
                if isinstance(score_result, list):
                    return score_result
                else:
                    return [score_result]

            except BatchProcessingPause:
                # Re-raise BatchProcessingPause to be handled by API
                logging.info(f"BatchProcessingPause caught in get_score_result for {score}")
                raise

        else:
            error_string = f"No score found for question: \"{score}\""
            logging.error(error_string)
            return [Score.Result(value="ERROR", error=error_string)]

    async def score_entire_text(self, *, text: str, metadata: dict, modality: Optional[str] = None, subset_of_score_names: Optional[List[str]] = None) -> Dict[str, Score.Result]:
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
                logging.info(f"Attempting on-demand load for missing score '{score_name}'")
                # Prefer provided identifier; fallback to display name if needed
                scorecard_identifier = self.scorecard_identifier or (
                    self.name() if callable(self.name) else self.name
                )
                # Use the standardized loader which pulls champion config from API or YAML cache
                # Honor yaml-only preference when loading scores on-demand
                yaml_only_prefer = getattr(self, 'yaml_only', False)
                loaded_instance = Score.load(
                    scorecard_identifier=scorecard_identifier,
                    score_name=score_name,
                    use_cache=True,
                    yaml_only=yaml_only_prefer
                )
                if not loaded_instance:
                    logging.warning(f"Failed to load score instance for '{score_name}'")
                    return False

                # Build properties from the loaded instance's parameters
                parameters_dict = loaded_instance.parameters.model_dump()
                # Ensure required metadata is present
                parameters_dict['name'] = parameters_dict.get('name') or score_name
                parameters_dict['class'] = loaded_instance.__class__.__name__

                # Register into this instance's registry
                self.score_registry.register(
                    cls=loaded_instance.__class__,
                    properties=parameters_dict,
                    name=parameters_dict.get('name'),
                    key=parameters_dict.get('key'),
                    id=parameters_dict.get('id')
                )

                # Maintain self.scores list so dependency graph builder can see it
                try:
                    if not hasattr(self, 'scores') or not isinstance(self.scores, list):
                        # Start from class scores if available
                        base_scores = getattr(self.__class__, 'scores', [])
                        self.scores = list(base_scores) if isinstance(base_scores, list) else []
                    # Avoid duplicates by name
                    existing_names = {s.get('name') for s in self.scores if isinstance(s, dict)}
                    if parameters_dict.get('name') not in existing_names:
                        self.scores.append(dict(parameters_dict))
                except Exception as append_err:
                    logging.warning(f"Could not append loaded score '{score_name}' to self.scores: {append_err}")

                logging.info(f"On-demand loaded and registered score '{score_name}'")
                return True
            except Exception as e:
                logging.warning(f"On-demand load failed for score '{score_name}': {e}")
                return False

        # Ensure requested scores themselves are loaded first
        for requested_score in list(subset_of_score_names):
            if not self.score_registry.get_properties(requested_score):
                loaded_ok = ensure_score_loaded(requested_score)
                if not loaded_ok:
                    logging.warning(f"No properties found for score: {requested_score}")

        # Add dependent scores to the subset of score names, loading any that are missing
        dependent_scores_added = []
        for score_name in subset_of_score_names:
            score_info = self.score_registry.get_properties(score_name)
            if score_info is None:
                # Try on-demand load before giving up
                if not ensure_score_loaded(score_name):
                    logging.warning(f"No properties found for score: {score_name}")
                    continue
                score_info = self.score_registry.get_properties(score_name)
                
            if 'depends_on' in score_info:
                deps = score_info['depends_on']
                if isinstance(deps, list):
                    for dependency in deps:
                        # Ensure dependency is registered/loaded
                        if not self.score_registry.get_properties(dependency):
                            ensure_score_loaded(dependency)
                        if dependency not in subset_of_score_names:
                            dependent_scores_added.append(dependency)
                            subset_of_score_names.append(dependency)
                elif isinstance(deps, dict):
                    for dependency in deps.keys():
                        # Ensure dependency is registered/loaded
                        if not self.score_registry.get_properties(dependency):
                            ensure_score_loaded(dependency)
                        if dependency not in subset_of_score_names:
                            dependent_scores_added.append(dependency)
                            subset_of_score_names.append(dependency)
        logging.info(f"Added dependent scores: {dependent_scores_added}")

        dependency_graph, name_to_id = self.build_dependency_graph(subset_of_score_names)
        logging.info(f"Built dependency graph: {dependency_graph}")

        results_by_score_id = {}
        results = []
        processing_queue = asyncio.Queue()

        # Initialize queue with scores that have no dependencies
        for score_id, score_info in dependency_graph.items():
            if not score_info['deps']:
                await processing_queue.put(score_id)
                logging.info(f"Added score with no dependencies to queue: {score_info['name']} (ID: {score_id})")

        async def process_score(score_id: str):
            score_name = dependency_graph[score_id]['name']
            logging.info(f"Starting to process score: {score_name} (ID: {score_id})")
            
            try:
                # Check if conditions are met
                if not self.check_dependency_conditions(score_id, dependency_graph, results_by_score_id):
                    logging.info(f"Conditions not met for {score_name}. Skipping.")
                    result = "SKIPPED"
                    results_by_score_id[score_id] = result
                    
                    # Enqueue scores that depend on this one
                    for dependent_id, dependent_info in dependency_graph.items():
                        if score_id in dependent_info['deps']:
                            # Check if all dependencies for this dependent score are now processed
                            if all(dep_id in results_by_score_id for dep_id in dependent_info['deps']):
                                logging.info(f"Enqueuing dependent score: {dependent_info['name']}")
                                await processing_queue.put(dependent_id)
                    
                    return
                
                logging.info(f"About to predict score {score_name} at {datetime.now().isoformat()}")
                
                # Extract previous results needed for this score
                score_deps = dependency_graph[score_id]['deps']
                previous_results = []
                logging.info(f"Processing score: {score_name} with dependencies: {score_deps}")
                logging.info(f"Results available: {list(results_by_score_id.keys())}")
                
                for dep_id in score_deps:
                    if dep_id in results_by_score_id:
                        dep_result = results_by_score_id[dep_id]
                        if dep_result != "SKIPPED":
                            previous_results.append(dep_result)
                
                # Ensure the scorecard_name is included in the score parameters
                score_registry_props = self.score_registry.get_properties(score_name)
                if score_registry_props and 'scorecard_name' not in score_registry_props:
                    score_registry_props['scorecard_name'] = self.name() if callable(self.name) else self.name
                
                # Get the score result
                score_result = await self.get_score_result(
                    scorecard=self.name() if callable(self.name) else self.name,
                    score=score_name,
                    text=text,
                    metadata=metadata,
                    modality=modality,
                    results=previous_results
                )
                
                if score_result is None:
                    logging.info(f"Score {score_name} returned None (possibly paused for batch processing)")
                    return
                
                # Handle both single Result objects and lists of results
                if isinstance(score_result, list):
                    result = score_result[0]
                else:
                    result = score_result

                # Get the score instance to access cost information
                score_class = self.score_registry.get(score_name)
                if score_class:
                    score_config = self.score_registry.get_properties(score_name)
                    try:
                        temp_score_instance = await score_class.create(**score_config)
                        # Get the total cost for this score and update scorecard's cost accumulators
                        score_total_cost = temp_score_instance.get_accumulated_costs()
                        total_tokens = score_total_cost.get('prompt_tokens', 0) + score_total_cost.get('completion_tokens', 0)
                    except Exception:
                        # If we can't create the instance, use default values
                        score_total_cost = {}
                        total_tokens = 0
                else:
                    score_total_cost = {}
                    total_tokens = 0

                self.prompt_tokens += score_total_cost.get('prompt_tokens', 0)
                self.completion_tokens += score_total_cost.get('completion_tokens', 0)
                self.cached_tokens += score_total_cost.get('cached_tokens', 0)
                self.llm_calls += score_total_cost.get('llm_calls', 0)
                self.input_cost += score_total_cost.get('input_cost', 0)
                self.output_cost += score_total_cost.get('output_cost', 0)
                self.total_cost += Decimal(str(score_total_cost.get('total_cost', 0)))
                self.scorecard_total_cost += Decimal(str(score_total_cost.get('total_cost', 0)))
                self.cost_per_text += Decimal(str(score_total_cost.get('cost_per_text', 0)))

                # Log CloudWatch metrics for this individual score
                score_config = score_config if 'score_config' in locals() else self.score_registry.get_properties(score_name)
                dimensions = {
                    'ScoreCardID': str(self.properties.get('id', 'unknown')),
                    'ScoreCardName': str(self.properties.get('name', 'unknown')),
                    'Score': str(score_config.get('name', score_name)),
                    'ScoreID': str(score_config.get('id', '')),
                    'Modality': modality or 'Development',
                    'Environment': os.getenv('environment') or 'Unknown'
                }
                
                self.cloudwatch_logger.log_metric('Cost', score_total_cost.get('total_cost', 0), dimensions)
                self.cloudwatch_logger.log_metric('PromptTokens', score_total_cost.get('prompt_tokens', 0), dimensions)
                self.cloudwatch_logger.log_metric('CompletionTokens', score_total_cost.get('completion_tokens', 0), dimensions)
                self.cloudwatch_logger.log_metric('TotalTokens', total_tokens, dimensions)
                self.cloudwatch_logger.log_metric('CachedTokens', score_total_cost.get('cached_tokens', 0), dimensions)
                self.cloudwatch_logger.log_metric('ExternalAIRequests', score_total_cost.get('llm_calls', 0), dimensions)
                self.cloudwatch_logger.log_metric('ItemTokens', item_tokens, dimensions)

                scorecard_dimensions = {
                    'ScoreCardName': str(self.properties.get('name', 'unknown')),
                    'Environment': os.getenv('environment') or 'Unknown'
                }

                self.cloudwatch_logger.log_metric('CostByScorecard', score_total_cost.get('total_cost', 0), scorecard_dimensions)
                self.cloudwatch_logger.log_metric('PromptTokensByScorecard', score_total_cost.get('prompt_tokens', 0), scorecard_dimensions)
                self.cloudwatch_logger.log_metric('CompletionTokensByScorecard', score_total_cost.get('completion_tokens', 0), scorecard_dimensions)
                self.cloudwatch_logger.log_metric('TotalTokensByScorecard', total_tokens, scorecard_dimensions)
                self.cloudwatch_logger.log_metric('CachedTokensByScorecard', score_total_cost.get('cached_tokens', 0), scorecard_dimensions)
                self.cloudwatch_logger.log_metric('ExternalAIRequestsByScorecard', score_total_cost.get('llm_calls', 0), scorecard_dimensions)
                self.cloudwatch_logger.log_metric('ItemTokensByScorecard', item_tokens, scorecard_dimensions)
                # Use aggregated scorecard costs for CostPerText instead of per-score value
                aggregated_costs = self.get_accumulated_costs()
                self.cloudwatch_logger.log_metric('CostPerText', aggregated_costs.get('cost_per_text', 0), scorecard_dimensions)
                    
                results_by_score_id[score_id] = result
                results.append({
                    'id': score_id,
                    'name': score_name,
                    'result': result
                })
                logging.info(f"Processed score: {score_name} (ID: {score_id})")

                # Check if any waiting scores can now be processed
                # Only check scores that directly depend on this score
                for waiting_score_id, waiting_score_info in dependency_graph.items():
                    if score_id in waiting_score_info['deps']:  # Only check if this score is a dependency
                        if waiting_score_id not in results_by_score_id and \
                           all(dep in results_by_score_id for dep in waiting_score_info['deps']):
                            await processing_queue.put(waiting_score_id)

            except Score.SkippedScoreException as e:
                logging.info(f"Score {score_name} was skipped: {e.reason}")
                return

            except BatchProcessingPause as e:
                logging.info(f"Score {score_name} paused for batch processing (thread_id: {e.thread_id})")
                # Store the paused state in results
                results_by_score_id[score_id] = Score.Result(
                    value="PAUSED",
                    error=str(e),
                    parameters=Score.Parameters(
                        name=score_name,
                        scorecard=self.name
                    ),
                    metadata={
                        'thread_id': e.thread_id,
                        'batch_job_id': e.batch_job_id
                    }
                )
                # Re-raise to be handled by higher-level code
                raise

        remaining_scores = set(dependency_graph.keys())
        while remaining_scores:
            try:
                score_id_to_process = await processing_queue.get()
                if score_id_to_process not in remaining_scores:
                    continue
                
                logging.info(f"Processing score: {dependency_graph[score_id_to_process]['name']}")
                await process_score(score_id_to_process)
                remaining_scores.discard(score_id_to_process)
                
            except BatchProcessingPause as e:
                # Don't remove from remaining scores, just re-raise to be handled by caller
                raise

        logging.info(f"All scores processed. Total scores: {len(results_by_score_id)}")
        return results_by_score_id

    def get_accumulated_costs(self):
        from decimal import Decimal
        cost_per_text = Decimal('0')
        if getattr(self, 'number_of_texts_processed', 0):
            # Avoid division by zero and ensure Decimal division
            cost_per_text = (self.total_cost / Decimal(str(self.number_of_texts_processed)))

        return {
            'prompt_tokens': self.prompt_tokens,
            'completion_tokens': self.completion_tokens,
            'cached_tokens': self.cached_tokens,
            'llm_calls': self.llm_calls,
            'input_cost': self.input_cost,
            'output_cost': self.output_cost,
            'total_cost': self.total_cost,
            'cost_per_text': cost_per_text
        }

    def get_model_name(self, name=None, id=None, key=None):
        """Return the model name used for a specific score or the scorecard."""
        if name or id or key:
            identifier = id or key or name
            score_class = self.score_registry.get(identifier)
            if score_class:
                return score_class.get_model_name()
        
        # If no specific score is found or requested, return the scorecard's model name
        return self.properties.get('model_name') or \
               self.properties.get('parameters', {}).get('model_name') or \
               'Unknown'

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
        scores_to_use = self.scores if hasattr(self, 'scores') else getattr(self.__class__, 'scores', [])
        
        # Build complete name_to_id mapping from ALL available scores (not just subset)
        # This is needed for dependency resolution
        for score in scores_to_use:
            score_id = str(score.get('id', ''))
            score_name = score['name']
            name_to_id[score_name] = score_id
        
        # Build dependency graph only for scores in the subset
        for score in scores_to_use:
            if score['name'] in subset_of_score_names:
                score_id = str(score.get('id', ''))
                score_name = score['name']
                
                # Handle both simple list and conditional dependencies
                dependencies = score.get('depends_on', [])
                if isinstance(dependencies, list):
                    # Simple list of dependencies - include ALL dependencies that exist in name_to_id
                    deps = []
                    for dep in dependencies:
                        dep_id = name_to_id.get(dep)
                        if dep_id:  # Only include if we have the dependency loaded
                            deps.append(dep_id)
                        else:
                            logging.warning(f"Dependency '{dep}' for score '{score_name}' not found in loaded scores")
                    graph[score_id] = {
                        'name': score_name,
                        'deps': deps,
                        'conditions': {}
                    }
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
                                conditions[dep_id] = {
                                    'operator': '==',
                                    'value': condition
                                }
                        else:
                            logging.warning(f"Dependency '{dep}' for score '{score_name}' not found in loaded scores")
                    graph[score_id] = {
                        'name': score_name,
                        'deps': deps,
                        'conditions': conditions
                    }
                else:
                    # Invalid dependency format
                    logging.warning(f"Invalid dependency format for score {score_name}")
                    graph[score_id] = {
                        'name': score_name,
                        'deps': [],
                        'conditions': {}
                    }
        return graph, name_to_id

    def check_dependency_conditions(self, score_id: str, dependency_graph: dict, results_by_score_id: dict) -> bool:
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
        if not score_info or not score_info['conditions']:
            return True
            
        for dep_id, condition in score_info['conditions'].items():
            if dep_id not in results_by_score_id:
                return False
                
            dep_result = results_by_score_id[dep_id]
            if isinstance(dep_result, str) and dep_result == "PAUSED":
                return False
                
            # Extract value from result, handling both Score.Result objects and direct values
            if hasattr(dep_result, 'value'):
                dep_value = str(dep_result.value).lower().strip()
            else:
                dep_value = str(dep_result).lower().strip()

            operator = condition.get('operator', '==')
            expected_value = str(condition.get('value', '')).lower().strip()
            
            logging.info(f"Checking condition: {dep_value} {operator} {expected_value}")
            
            if operator == '==':
                if dep_value != expected_value:
                    logging.info(f"Condition not met: {dep_value} != {expected_value}")
                    return False
            elif operator == '!=':
                if dep_value == expected_value:
                    logging.info(f"Condition not met: {dep_value} == {expected_value}")
                    return False
            elif operator == 'in':
                if not isinstance(condition.get('value'), list):
                    expected_values = [str(v).lower().strip() for v in [expected_value]]
                else:
                    expected_values = [str(v).lower().strip() for v in condition.get('value')]
                if dep_value not in expected_values:
                    logging.info(f"Condition not met: {dep_value} not in {expected_values}")
                    return False
            elif operator == 'not in':
                if not isinstance(condition.get('value'), list):
                    expected_values = [str(v).lower().strip() for v in [expected_value]]
                else:
                    expected_values = [str(v).lower().strip() for v in condition.get('value')]
                if dep_value in expected_values:
                    logging.info(f"Condition not met: {dep_value} in {expected_values}")
                    return False
            else:
                logging.warning(f"Unsupported operator {operator} for score {score_id}")
                return False
                
        return True
                
    @staticmethod
    def create_instance_from_api_data(scorecard_id: str, api_data: Dict[str, Any], scores_config: List[Dict[str, Any]]) -> 'Scorecard':
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
        if 'sections' in api_data and 'items' in api_data.get('sections', {}):
            all_api_scores = []
            for section in api_data.get('sections', {}).get('items', []):
                for score in section.get('scores', {}).get('items', []):
                    all_api_scores.append(score)
                    
            # Ensure scores_config has the correct IDs from API data
            for config in scores_config:
                if isinstance(config, dict) and 'name' in config:
                    # Look for the corresponding score in API data
                    for api_score in all_api_scores:
                        if api_score.get('name') == config.get('name'):
                            # Always use database UUID from API, not external ID from config
                            api_id = api_score.get('id')
                            original_id = config.get('id')
                            if api_id and original_id != api_id:
                                logging.info(f"Replacing ID {original_id} with database UUID {api_id} for config {config.get('name')}")
                                config['id'] = api_id
                                # Preserve the original external ID for matching purposes
                                config['originalExternalId'] = str(original_id)
                            if not config.get('version'):
                                # Reorder fields in the exact order: name, key, id, version, parent
                                ordered_config = {}
                                
                                # Add name if it exists
                                if 'name' in config:
                                    ordered_config['name'] = config['name']
                                
                                # Add key if it exists
                                if 'key' in config:
                                    ordered_config['key'] = config['key']
                                
                                # Add id if it exists
                                if 'id' in config:
                                    ordered_config['id'] = config['id']
                                
                                # Add version
                                ordered_config['version'] = api_score.get('championVersionId')
                                
                                # Add parent if it exists
                                if 'parent' in config:
                                    ordered_config['parent'] = config['parent']
                                
                                # Add all other fields
                                for key, value in config.items():
                                    if key not in ['name', 'key', 'id', 'version', 'parent']:
                                        ordered_config[key] = value
                                
                                # Replace the original config with ordered config
                                for key in list(config.keys()):
                                    del config[key]
                                for key, value in ordered_config.items():
                                    config[key] = value
                                
                                logging.info(f"Setting version {api_score.get('championVersionId')} for config {config.get('name')}")
                            break
        else:
            logging.warning("API data does not contain expected structure (sections.items)")
            
        # The scores_config should already be parsed configurations, so we can use them directly
        scorecard_instance = Scorecard(
            scorecard=scorecard_id,
            api_data=api_data,
            scores_config=scores_config
        )
        
        # Verify IDs after instance creation
        if hasattr(scorecard_instance, 'scores'):
            id_verification = [(score.get('name'), score.get('id')) for score in scorecard_instance.scores]
            logging.info(f"ID verification after instance creation: {id_verification}")
            
        return scorecard_instance