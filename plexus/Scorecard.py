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
from typing import Optional, List, Dict
import asyncio
import boto3
from botocore.exceptions import ClientError
import tiktoken

from plexus.Registries import ScoreRegistry
from plexus.Registries import scorecard_registry
import plexus.scores
from plexus.scores.Score import Score

class Scorecard:
    """
    Represents a collection of scores and manages the computation of these scores for given inputs.

    This class provides functionality to load scores from a YAML configuration, compute individual and total scores,
    and manage the costs associated with score computations.
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

        self.cloudwatch_client = boto3.client('cloudwatch')

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
        Get a result for a score by looking up a Score instance for that question name and calling its
        compute_score_result method with the provided transcript.

        :param score: The score identifier.
        :param text: The transcript.
        :param metadata: The metadata.
        :param modality: The modality.
        :return: The score result.
        """
        logging.info(f"Getting score result for: {score}")
        
        score_class = self.score_registry.get(score)
        if score_class is None:
            logging.error(f"Score with name '{score}' not found.")
            return

        score_configuration = self.score_registry.get_properties(score)
        if (score_class is not None):
            logging.info(f"Found score class for: {score}")

            # Calculate content item length in tokens using a general-purpose encoding
            encoding = tiktoken.get_encoding("cl100k_base")
            item_tokens = len(encoding.encode(text))
            logging.info(f"Item tokens for {score}: {item_tokens}")

            score_configuration.update({
                'scorecard_name': self.name,
                'score_name': score
            })
            score_instance = await score_class.create(**score_configuration)

            if score_instance is None:
                logging.error(f"Score with name '{score}' not found in scorecard '{self.name}'.")
                return

            logging.info(f"Predicting score for: {score}")
            score_result = await score_instance.predict(
                context=None,
                model_input=plexus.scores.Score.Input(
                    text=text,
                    metadata=metadata,
                    results=results
                )
            )
            logging.info(f"Prediction complete for: {score}")
            logging.debug(f"Score result for {score}: {score_result}")

            if hasattr(score_instance, 'get_accumulated_costs'):
                score_total_cost = score_instance.get_accumulated_costs()
                logging.info(f"Total cost for {score}: {score_total_cost}")

                self.prompt_tokens       += score_total_cost.get('prompt_tokens', 0)
                self.completion_tokens   += score_total_cost.get('completion_tokens', 0)
                self.cached_tokens       += score_total_cost.get('cached_tokens', 0)
                self.llm_calls           += score_total_cost.get('llm_calls', 0)
                self.input_cost          += score_total_cost.get('input_cost', 0)
                self.output_cost         += score_total_cost.get('output_cost', 0)
                self.total_cost          += score_total_cost.get('total_cost', 0)
                self.scorecard_total_cost += score_total_cost.get('total_cost', Decimal('0.0'))

                total_tokens = self.prompt_tokens + self.completion_tokens

                # TODO: Find a different way of passing the costs with the score result.
                # Maybe add support for `costs` and `metadata` in Score.Result?
                # score_result[0].metadata.update(score_total_cost)
                
                # Log the cost for this individual score
                dimensions = {
                    'ScoreCardID': str(self.properties['id']),
                    'ScoreCardName': str(self.properties['name']),
                    'Score': str(score_configuration.get('name')),
                    'ScoreID': str(score_configuration.get('id')),
                    'Modality': modality or 'Development',
                    'Environment': os.getenv('environment') or 'Unknown'
                }
                
                self.log_metric_to_cloudwatch('Cost', score_total_cost.get('total_cost', 0), dimensions)
                self.log_metric_to_cloudwatch('PromptTokens', score_total_cost.get('prompt_tokens', 0), dimensions)
                self.log_metric_to_cloudwatch('CompletionTokens', score_total_cost.get('completion_tokens', 0), dimensions)
                self.log_metric_to_cloudwatch('TotalTokens', total_tokens, dimensions)
                self.log_metric_to_cloudwatch('CachedTokens', score_total_cost.get('cached_tokens', 0), dimensions)
                self.log_metric_to_cloudwatch('ExternalAIRequests', score_total_cost.get('llm_calls', 0), dimensions)
                self.log_metric_to_cloudwatch('ItemTokens', item_tokens, dimensions)

                scorecard_dimensions = {
                    'ScoreCardName': str(self.properties['name']),
                    'Environment': os.getenv('environment') or 'Unknown'
                }

                self.log_metric_to_cloudwatch('CostByScorecard', score_total_cost.get('total_cost', 0), scorecard_dimensions)

            return score_result

        else:
            error_string = f"No score found for question: \"{score}\""
            logging.error(error_string)
            return plexus.scores.Score.Result(value="Error", error=error_string)

    async def score_entire_text(self, *, text: str, metadata: dict, modality: Optional[str] = None, subset_of_score_names: Optional[List[str]] = None) -> Dict[str, Score.Result]:
        if subset_of_score_names is None:
            subset_of_score_names = self.score_names_to_process()
        
        logging.info(f"Starting to process scores: {subset_of_score_names}")

        # Add dependend scores to the subset of score names.
        dependent_scores_added = []
        for score_name in subset_of_score_names:
            score_info = self.score_registry.get_properties(score_name)
            if 'depends_on' in score_info:
                for dependency in score_info['depends_on']:
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
                score_result = await asyncio.wait_for(
                    self.get_score_result(
                        scorecard=self.scorecard_identifier,
                        score=score_name,
                        text=text,
                        metadata=metadata,
                        modality=modality,
                        results=results
                    ),
                    timeout=1200
                )
                results_by_score_id[score_id] = score_result[0]  # Store result by score ID
                results.append({
                    'id': score_id,
                    'name': score_name,
                    'result': score_result[0]
                })
                logging.info(f"Processed score: {score_name} (ID: {score_id})")

                # Check if any waiting scores can now be processed
                for waiting_score_id, waiting_score_info in dependency_graph.items():
                    if waiting_score_id not in results_by_score_id and all(dep in results_by_score_id for dep in waiting_score_info['deps']):
                        await processing_queue.put(waiting_score_id)
                        logging.info(f"Added score to queue as dependencies are met: {waiting_score_info['name']} (ID: {waiting_score_id})")

            except asyncio.TimeoutError:
                logging.error(f"Timeout processing score: {score_name} (ID: {score_id})")
            except Exception as e:
                logging.error(f"Error processing score {score_name} (ID: {score_id}): {str(e)}")

        while len(results_by_score_id) < len(subset_of_score_names):
            score_id_to_process = await processing_queue.get()
            logging.info(f"Retrieved score from queue for processing: {dependency_graph[score_id_to_process]['name']} (ID: {score_id_to_process})")
            logging.info(f"Current results: {list(results_by_score_id.keys())}")
            logging.info(f"Remaining scores: {set(dependency_graph.keys()) - set(results_by_score_id.keys())}")
            await process_score(score_id_to_process)

        logging.info(f"All scores processed. Total scores: {len(results_by_score_id)}")
        logging.info(f"Scorecard total cost: {self.scorecard_total_cost}")
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

    def log_metric_to_cloudwatch(self, metric_name, metric_value, dimensions):
        try:
            metric_data = {
                'MetricName': metric_name,
                'Value': float(metric_value),
                'Unit': 'None',
                'Dimensions': [{'Name': k, 'Value': str(v)} for k, v in dimensions.items()]
            }

            self.cloudwatch_client.put_metric_data(
                Namespace='Plexus',
                MetricData=[metric_data]
            )
            logging.info(f"Successfully logged {metric_name} to CloudWatch with dimensions: {dimensions}")
        except ClientError as e:
            logging.error(f"Failed to log metric to CloudWatch: {e}")

    def build_dependency_graph(self, subset_of_score_names):
        graph = {}
        name_to_id = {}
        for score in self.scores:
            if score['name'] in subset_of_score_names:
                score_id = str(score['id'])
                score_name = score['name']
                name_to_id[score_name] = score_id
                dependencies = score.get('depends_on', [])
                graph[score_id] = {
                    'name': score_name,
                    'deps': [name_to_id.get(dep, dep) for dep in dependencies if dep in subset_of_score_names]
                }
        return graph, name_to_id



