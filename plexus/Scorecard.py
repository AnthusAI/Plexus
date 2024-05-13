import os
import re
import yaml
import json
import requests
import json
import logging
import importlib.util
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor, as_completed

from plexus.Score import Score
from plexus.ScoreResult import ScoreResult
from plexus.Registries import ScoreRegistry
from plexus.Registries import scorecard_registry
from plexus.CompositeScore import CompositeScore

class Scorecard:
    """
    Represents a collection of scores and manages the computation of these scores for given inputs.

    This class provides functionality to load scores from a YAML configuration, compute individual and total scores,
    and manage the costs associated with score computations.

    Attributes:
        score_registry (ScoreRegistry): Registry holding all available scores.
        scorecard_folder_path (str): Path to the folder containing score configurations.
    """
        
    score_registry = ScoreRegistry()
    scorecard_folder_path = None
    
    def __init__(self, *, scorecard_folder_path):
        """
        Initializes a new instance of the Scorecard class.

        Args:
            scorecard_folder_path (str): The file system path to the folder containing score configurations.
        """
        self.scorecard_folder_path = scorecard_folder_path
        # Accumulators for tracking the total expenses.
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.input_cost =  Decimal('0.0')
        self.output_cost = Decimal('0.0')
        self.total_cost =  Decimal('0.0')

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
        """
        Retrieves a list of all score names registered in the scorecard.
        Incuding scores that are computed implicitly by other scores.

        Returns:
            list of str: The names of all registered scores.
        """
        return cls.scores.keys()

    @classmethod
    def score_names_to_process(cls):
        """
        Filters and returns score names that need to be processed directly.
        Some scores are computed implicitly by other scores and don't need to be directly processed.

        Returns:
            list of str: Names of scores that are marked as 'primary' and need direct processing.
        """
        return [
            score_name for score_name, details in cls.scores.items()
            if 'primary' not in details
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
        with open(yaml_file_path, 'r') as file:
            yaml_data = yaml.safe_load(file)

        scorecard_name = list(yaml_data.keys())[0]
        scorecard_data = yaml_data[scorecard_name]

        scorecard_class = type(scorecard_name, (Scorecard,), {
            'scorecard_id': classmethod(lambda cls: scorecard_data['properties']['scorecard_id']),
            'name': classmethod(lambda cls: scorecard_data['properties']['name']),
            'scorecard_folder_path': scorecard_data['properties']['scorecard_folder_path'],
            'scores': scorecard_data['scores']
        })

        scorecard_registry.register(scorecard_data['registry']['key'], scorecard_data['registry']['family'])(scorecard_class)
        scorecard_class.load_and_register_scores()

        return scorecard_class
    
    @classmethod
    def load_and_register_scores(cls):
        """
        Load and register the scores based on the `scores` dictionary.
        """
        for score_name in cls.score_names_to_process():
            normalized_score_name = cls.normalize_score_name(score_name)
            markdown_file_path = os.path.join(
                cls.scorecard_folder_path, f"{normalized_score_name}.md")

            score_class = CompositeScore.create_from_markdown(
                scorecard=cls,
                markdown_file_path=markdown_file_path,
                score_name=score_name
            )

            cls.score_registry.register(score_name, score_class)
    
    def get_score_result(self, *, score_name=None, transcript):
        """
        Get a result for a score by looking up a Score instance for that question name and calling its
        compute_score_result method with the provided transcript.

        :param question_name: The name of the question.
        :param transcript: The transcript.
        :return: The score result.
        """

        score_class = Scorecard.score_registry.get(score_name)
        if (score_class is not None):
            logging.info("Found score for question: " + score_name)

            score_instance = score_class(
                transcript=transcript
            )
            score_result = score_instance.compute_result()
            logging.debug(f"Score result: {score_result}")

            score_total_cost = score_instance.accumulated_expenses()
            logging.info(f"Total cost: {score_total_cost}")

            self.prompt_tokens       += score_total_cost['prompt_tokens']
            self.completion_tokens   += score_total_cost['completion_tokens']
            self.input_cost          += score_total_cost['input_cost']
            self.output_cost         += score_total_cost['output_cost']
            self.total_cost          += score_total_cost['total_cost']

            score_result[0].metadata.update(score_total_cost)
            return score_result

        else:
            error_string = f"No score found for question: \"{score_name}\""
            logging.info(error_string)
            return ScoreResult(value="Error", error=error_string)

    def score_entire_transcript(self, *, transcript, subset_of_score_names=None, thread_pool_size=25):
        if subset_of_score_names is None:
            subset_of_score_names = self.score_names_to_process()

        score_results_dict = {}
        with ThreadPoolExecutor(max_workers=thread_pool_size) as executor:
            future_to_score_name = {
                executor.submit(self.get_score_result, score_name=score_name, transcript=transcript): score_name
                for score_name in subset_of_score_names
            }
            for future in as_completed(future_to_score_name):
                score_name = future_to_score_name[future]
                try:
                    results_list = future.result()
                    for result in results_list:
                        score_results_dict[result.name] = result.to_dict()
                except Exception as e:
                    logging.exception(f"Exception occurred for score {score_name}: {e}", exc_info=True)
                    score_results_dict[score_name] = {
                        'name':  score_name,
                        'value': "Error",
                        'error': str(e)
                    }

        return score_results_dict

    def accumulated_expenses(self):
        return {
            'prompt_tokens': self.prompt_tokens,
            'completion_tokens': self.completion_tokens,
            'input_cost': self.input_cost,
            'output_cost': self.output_cost,
            'total_cost': self.total_cost
        }