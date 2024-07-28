import os
import rich
from plexus.CustomLogging import logging
from plexus.scores.Score import Score
from typing import Dict, Any
import boto3
from botocore.exceptions import ClientError
import nltk
from nltk.tokenize import sent_tokenize
import re

class AWSComprehendEntityExtractor(Score):
    """
    This score uses AWS Comprehend to extract the first named entity from the transcript.
    """

    def __init__(self, **parameters):
        super().__init__(**parameters)
        self.comprehend_client = boto3.client('comprehend', region_name=os.environ.get('AWS_REGION_NAME'))
        nltk.download('punkt', quiet=True)  # Download the necessary data for the tokenizer

    class Result(Score.Result):
        """
        Model output data structure.

        Attributes
        ----------
        score : str
            The predicted score label.
        """
        ...
        explanation: str
                
    def predict(self, context, model_input: Score.Input):
        rich.print("[b][magenta1]AWSComprehendEntityExtractor[/magenta1][/b]")
        rich.print(model_input)

        first_named_entity = self.extract_first_person_entity(model_input.transcript)
        
        quotes = self.extract_quotes_that_include_first_person_entity(model_input.transcript, first_named_entity)

        return [
            self.Result(
                name =        self.parameters.score_name,
                value =       first_named_entity,
                explanation = f"First person entity extracted: {first_named_entity}. Relevant quotes: {quotes}"
            )
        ]

    def extract_first_person_entity(self, transcript: str) -> str:
        try:
            response = self.comprehend_client.detect_entities(
                Text=transcript,
                LanguageCode='en'
            )
            
            for entity in response['Entities']:
                if entity['Type'] == 'PERSON':
                    return entity['Text']
            
            return ""
        except ClientError as e:
            logging.error(f"Error calling AWS Comprehend: {e}")
            return ""
        
    def extract_quotes_that_include_first_person_entity(self, transcript: str, first_person_entity: str) -> list[str]:
        if not first_person_entity:
            return []

        sentences = sent_tokenize(transcript)
        quote_pattern = r'"([^"]*)"'
        entity_quotes = []

        for sentence in sentences:
            if first_person_entity in sentence:
                quotes = re.findall(quote_pattern, sentence)
                entity_quotes.extend(quotes)

        return entity_quotes

    def register_model(self):
        """
        Register the model with MLflow by logging relevant parameters.
        """
        pass

    def save_model(self):
        """
        Save the model to a specified path and log it as an artifact with MLflow.
        """
        pass

    def train_model(self):
        """
        Placeholder method to satisfy the base class requirement.
        This validator doesn't require traditional training.
        """
        pass

    def predict_validation(self):
        """
        Placeholder method to satisfy the base class requirement.
        This validator doesn't require traditional training.
        """
        pass