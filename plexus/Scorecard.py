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
from typing import Optional, List, Dict, Union
import asyncio
import boto3
from botocore.exceptions import ClientError
import tiktoken
from os import getenv

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
            

    def __init__(self, *, scorecard):
        """
        Initializes a new instance of the Scorecard class.

        Args:
            scorecard (str): The name of the scorecard.
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

        self.cloudwatch_logger = CloudWatchLogger()

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

            score_configuration.update({
                'scorecard_name': self.name,
                'score_name': score
            })
            score_instance = await score_class.create(**score_configuration)

            if score_instance is None:
                logging.error(f"Score with name '{score}' not found in scorecard '{self.name}'.")
                return [Score.Result(value="ERROR", error=f"Score with name '{score}' not found in scorecard '{self.name}'.")]

            # Add required metadata for LangGraphScore
            if isinstance(score_instance, LangGraphScore):
                account_key = os.getenv('PLEXUS_ACCOUNT_KEY')
                if not account_key:
                    raise ValueError("PLEXUS_ACCOUNT_KEY not found in environment")
                metadata = metadata or {}
                metadata.update({
                    'account_key': account_key,
                    'scorecard_name': self.name,
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

                # Log CloudWatch metrics for this individual score
                total_tokens = score_total_cost.get('prompt_tokens', 0) + score_total_cost.get('completion_tokens', 0)
                dimensions = {
                    'ScoreCardID': str(self.properties['id']),
                    'ScoreCardName': str(self.properties['name']),
                    'Score': str(score_configuration.get('name')),
                    'ScoreID': str(score_configuration.get('id')),
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
                    'ScoreCardName': str(self.properties['name']),
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

        # Calculate content item length in tokens using a general-purpose encoding
        encoding = tiktoken.get_encoding("cl100k_base")
        item_tokens = len(encoding.encode(text))
        logging.info(f"Item tokens for scorecard: {item_tokens}")

        # Add dependend scores to the subset of score names.
        dependent_scores_added = []
        for score_name in subset_of_score_names:
            score_info = self.score_registry.get_properties(score_name)
            if 'depends_on' in score_info:
                deps = score_info['depends_on']
                if isinstance(deps, list):
                    for dependency in deps:
                        if dependency not in subset_of_score_names:
                            dependent_scores_added.append(dependency)
                            subset_of_score_names.append(dependency)
                elif isinstance(deps, dict):
                    for dependency in deps.keys():
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
                    logging.info(f"Skipping score {score_name} as conditions are not met")
                    # Remove this score from remaining scores but don't add it to results
                    remaining_scores.discard(score_id)
                    raise Score.SkippedScoreException(
                        score_name=score_name,
                        reason="Dependency conditions not met"
                    )
                    
                logging.info(f"About to predict score {score_name} at {pd.Timestamp.now()}")
                # Create list of results in the format expected by get_score_result
                current_results = []
                for name, result in results_by_score_id.items():
                    # Convert to Score.Result if it isn't already
                    if not isinstance(result, Score.Result):
                        if isinstance(result, dict):
                            result = Score.Result(
                                value=result['value'],
                                metadata=result.get('metadata', {}),
                                parameters=Score.Parameters(name=name),
                                error=result.get('error')
                            )
                    current_results.append(result)

                logging.info(f"Processing score: {score_name} with dependencies: {[r.parameters.name for r in current_results]}")
                logging.info(f"Results available: {[r.value for r in current_results]}")

                # Get the score class and create an instance
                score_class = self.score_registry.get(score_name)
                if not score_class:
                    raise ValueError(f"No score class found for {score_name}")
                    
                score_configuration = self.score_registry.get_properties(score_name)
                score_configuration.update({
                    'scorecard_name': self.name,
                    'score_name': score_name
                })
                score_instance = await score_class.create(**score_configuration)
                if not score_instance:
                    raise ValueError(f"Failed to create score instance for {score_name}")

                score_result = await score_instance.predict(
                    context=None,
                    model_input=Score.Input(
                        text=text,
                        metadata=metadata,
                        results=current_results
                    )
                )
                
                if score_result is None:
                    logging.info(f"Score {score_name} returned None (possibly paused for batch processing)")
                    return
                
                # Handle both single Result objects and lists of results
                if isinstance(score_result, list):
                    result = score_result[0]
                else:
                    result = score_result

                # Get the total cost for this score and update scorecard's cost accumulators
                score_total_cost = score_instance.get_accumulated_costs()
                total_tokens = score_total_cost.get('prompt_tokens', 0) + score_total_cost.get('completion_tokens', 0)

                self.prompt_tokens += score_total_cost.get('prompt_tokens', 0)
                self.completion_tokens += score_total_cost.get('completion_tokens', 0)
                self.cached_tokens += score_total_cost.get('cached_tokens', 0)
                self.llm_calls += score_total_cost.get('llm_calls', 0)
                self.input_cost += score_total_cost.get('input_cost', 0)
                self.output_cost += score_total_cost.get('output_cost', 0)
                self.total_cost += Decimal(str(score_total_cost.get('total_cost', 0)))
                self.scorecard_total_cost += Decimal(str(score_total_cost.get('total_cost', 0)))

                # Log CloudWatch metrics for this individual score
                dimensions = {
                    'ScoreCardID': str(self.properties['id']),
                    'ScoreCardName': str(self.properties['name']),
                    'Score': str(score_configuration.get('name')),
                    'ScoreID': str(score_configuration.get('id')),
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
                    'ScoreCardName': str(self.properties['name']),
                    'Environment': os.getenv('environment') or 'Unknown'
                }

                self.cloudwatch_logger.log_metric('CostByScorecard', score_total_cost.get('total_cost', 0), scorecard_dimensions)
                self.cloudwatch_logger.log_metric('PromptTokensByScorecard', score_total_cost.get('prompt_tokens', 0), scorecard_dimensions)
                self.cloudwatch_logger.log_metric('CompletionTokensByScorecard', score_total_cost.get('completion_tokens', 0), scorecard_dimensions)
                self.cloudwatch_logger.log_metric('TotalTokensByScorecard', total_tokens, scorecard_dimensions)
                self.cloudwatch_logger.log_metric('CachedTokensByScorecard', score_total_cost.get('cached_tokens', 0), scorecard_dimensions)
                self.cloudwatch_logger.log_metric('ExternalAIRequestsByScorecard', score_total_cost.get('llm_calls', 0), scorecard_dimensions)
                self.cloudwatch_logger.log_metric('ItemTokensByScorecard', item_tokens, scorecard_dimensions)
                    
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
        return {
            'prompt_tokens': self.prompt_tokens,
            'completion_tokens': self.completion_tokens,
            'cached_tokens': self.cached_tokens,
            'llm_calls': self.llm_calls,
            'input_cost': self.input_cost,
            'output_cost': self.output_cost,
            'total_cost': self.total_cost
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
        graph = {}
        name_to_id = {}
        for score in self.scores:
            if score['name'] in subset_of_score_names:
                score_id = str(score['id'])
                score_name = score['name']
                name_to_id[score_name] = score_id
                
                # Handle both simple list and conditional dependencies
                dependencies = score.get('depends_on', [])
                if isinstance(dependencies, list):
                    # Simple list of dependencies
                    graph[score_id] = {
                        'name': score_name,
                        'deps': [name_to_id.get(dep, dep) for dep in dependencies if dep in subset_of_score_names],
                        'conditions': {}
                    }
                elif isinstance(dependencies, dict):
                    # Dictionary with conditions
                    deps = []
                    conditions = {}
                    for dep, condition in dependencies.items():
                        if dep in subset_of_score_names:
                            deps.append(name_to_id.get(dep, dep))
                            if isinstance(condition, dict):
                                conditions[name_to_id.get(dep, dep)] = condition
                            elif isinstance(condition, str):
                                conditions[name_to_id.get(dep, dep)] = {
                                    'operator': '==',
                                    'value': condition
                                }
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