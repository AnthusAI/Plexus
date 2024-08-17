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

from plexus.Registries import ScoreRegistry
from plexus.Registries import scorecard_registry
import plexus.scores

class Scorecard:
    """
    Represents a collection of scores and manages the computation of these scores for given inputs.

    This class provides functionality to load scores from a YAML configuration, compute individual and total scores,
    and manage the costs associated with score computations.

    Attributes:
        score_registry (ScoreRegistry): Registry holding all available scores.
    """
        
    score_registry = ScoreRegistry()
    
    def __init__(self, *, scorecard_name):
        """
        Initializes a new instance of the Scorecard class.

        Args:
            scorecard_name (str): The name of the scorecard.
        """
        self.scorecard_name = scorecard_name

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
            'metadata':              scorecard_properties['metadata'],
            'scores':                scorecard_properties['scores'],
            'score_registry':        ScoreRegistry()
        })

        # Register the scorecard class.
        scorecard_registry.register(
            scorecard_properties['key'],
            scorecard_properties['family'])(scorecard_class)

        # Find the path of the Markdown files for individual scores from the file name.
        file_name = os.path.splitext(os.path.basename(yaml_file_path))[0]
        markdown_folder_path = os.path.join(
            'scorecards', file_name)

        # Register scores that come from Markdown files.
        scorecard_class.load_and_register_scores(markdown_folder_path)

        # Register any other scores that are in the YAML file.
        for score_name, score_info in scorecard_properties['scores'].items():
            if 'class' in score_info:
                class_name = score_info['class']
                module = importlib.import_module('plexus.scores')
                score_class = getattr(module, class_name)
                scorecard_class.score_registry.register(score_name)(score_class)

        return scorecard_class
    
    @classmethod
    def load_and_register_scorecards(cls, directory_path):
        for file_name in os.listdir(directory_path):
            if file_name.endswith('.yaml'):
                yaml_file_path = os.path.join(directory_path, file_name)
                cls.create_from_yaml(yaml_file_path)

    @classmethod
    def load_and_register_scores(cls, markdown_folder_path):
        """
        Load and register the scores based on the `scores` dictionary.
        """
        for score_name in cls.score_names_to_process():
            normalized_score_name = cls.normalize_score_name(score_name)
            markdown_file_path = os.path.join(
                markdown_folder_path, f"{normalized_score_name}.md")

            score_class = plexus.scores.CompositeScore.create_from_markdown(
                scorecard=cls,
                markdown_file_path=markdown_file_path,
                score_name=score_name
            )

            cls.score_registry.register(score_name, score_class)
    
    def get_score_result(self, *, score_name=None, text):
        """
        Get a result for a score by looking up a Score instance for that question name and calling its
        compute_score_result method with the provided transcript.

        :param question_name: The name of the question.
        :param transcript: The transcript.
        :return: The score result.
        """
        
        # Get score configuration
        logging.info(f"Predicting Score [magenta1][b]{score_name}[/b][/magenta1]...")
        score_configuration = self.scores[score_name]

        if score_name not in self.scores:
            logging.error(f"Score with name '{score_name}' not found in scorecard '{self.name}'.")
            return

        logging.info(f"Score Configuration: {rich.pretty.pretty_repr(score_configuration)}")

        score_class = self.score_registry.get(score_name)
        if (score_class is not None):
            logging.info("Found score for question: " + score_name)

            score_configuration.update({
                'scorecard_name': self.name,
                'score_name': score_name
            })
            score_instance = score_class(**score_configuration)

            score_result = score_instance.predict(
                context=None,
                model_input=plexus.scores.Score.Input(
                    text=text,
                    metadata={}
                )
            )
            logging.info(f"Score result: {score_result}")

            if hasattr(score_instance, 'get_accumulated_costs'):
                score_total_cost = score_instance.get_accumulated_costs()
                logging.info(f"Total cost: {score_total_cost}")

                self.prompt_tokens       += score_total_cost.get('prompt_tokens', 0)
                self.completion_tokens   += score_total_cost.get('completion_tokens', 0)
                self.input_cost          += score_total_cost.get('input_cost', 0)
                self.output_cost         += score_total_cost.get('output_cost', 0)
                self.total_cost          += score_total_cost.get('total_cost', 0)

                # TODO: Find a different way of passing the costs with the score result.
                # Maybe add support for `costs` and `metadata` in Score.Result?
                # score_result[0].metadata.update(score_total_cost)
            return score_result

        else:
            error_string = f"No score found for question: \"{score_name}\""
            logging.info(error_string)
            return plexus.scores.Score.Result(value="Error", error=error_string)

    def score_entire_text(self, *, text, subset_of_score_names=None, thread_pool_size=25):
        logging.info(f"score_entire_text method. subset_of_score_names: {subset_of_score_names}")
        if subset_of_score_names is None:
            subset_of_score_names = self.score_names_to_process()

        score_results_dict = {}
        with ThreadPoolExecutor(max_workers=thread_pool_size) as executor:
            future_to_score_name = {
                executor.submit(self.get_score_result, score_name=score_name, text=text): score_name
                for score_name in subset_of_score_names
            }
            for future in as_completed(future_to_score_name):
                results_list = future.result()
                for result in results_list:
                    score_results_dict[result.name] = result

        return score_results_dict

    def get_accumulated_costs(self):
        return {
            'prompt_tokens': self.prompt_tokens,
            'completion_tokens': self.completion_tokens,
            'input_cost': self.input_cost,
            'output_cost': self.output_cost,
            'total_cost': self.total_cost
        }