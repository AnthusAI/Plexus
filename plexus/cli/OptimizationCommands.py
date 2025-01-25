import importlib
import json
import logging
import click
import os
import pandas as pd
from plexus.apos.optimize_evaluation import optimize_evaluation
from plexus.apos.config import load_config
from plexus.Scorecard import Scorecard
from plexus.Registries import scorecard_registry
import asyncio

@click.group()
def optimize():
    """Commands for optimizing evaluations."""
    pass

def create_sample_data(scorecard_name: str, score_name: str) -> str:
    """Create sample data file for optimization."""
    # Load scorecard
    Scorecard.load_and_register_scorecards('scorecards/')
    scorecard_type = scorecard_registry.get(scorecard_name)
    if scorecard_type is None:
        raise ValueError(f"Scorecard with name '{scorecard_name}' not found.")
    
    scorecard_instance = scorecard_type(scorecard=scorecard_name)
    
    # Get score config
    score_config = next((score for score in scorecard_instance.scores 
                        if score['name'] == score_name), None)
    if not score_config:
        raise ValueError(f"Score '{score_name}' not found in scorecard.")
    
    # Get samples using existing function
    samples = get_samples(scorecard_instance, score_name, score_config)
    
    # Create directory if it doesn't exist
    os.makedirs('tests/data', exist_ok=True)
    
    # Convert samples to DataFrame and save
    samples_path = 'tests/data/address_verification_samples.csv'
    df = pd.DataFrame(samples)
    df.to_csv(samples_path, index=False)
    
    return samples_path

@optimize.command()
@click.option('--scorecard-name', required=True, help='Name of scorecard to optimize')
@click.option('--score-name', help='Specific score to optimize')
@click.option('--config', help='Path to configuration file')
@click.option('--number-of-samples', type=int, help='Number of samples to use per iteration')
def evaluation(scorecard_name: str, score_name: str = None, config: str = None, number_of_samples: int = None):
    """Run automated evaluation optimization."""
    asyncio.run(optimize_evaluation(
        scorecard_name=scorecard_name,
        score_name=score_name,
        config=load_config(config) if config else None,
        number_of_samples=number_of_samples
    ))

def get_samples(scorecard_instance, score_name, score_config):
    score_class_name = score_config['class']
    score_module_path = f'plexus.scores.{score_class_name}'
    score_module = importlib.import_module(score_module_path)
    score_class = getattr(score_module, score_class_name)

    score_config['scorecard_name'] = scorecard_instance.name
    score_config['score_name'] = score_name
    score_instance = score_class(**score_config)

    score_instance.load_data(data=score_config['data'])
    score_instance.process_data()

    # Log dataframe information
    logging.info(f"Dataframe info for score {score_name}:")
    logging.info(f"Columns: {score_instance.dataframe.columns.tolist()}")
    logging.info(f"Shape: {score_instance.dataframe.shape}")

    samples = score_instance.dataframe.to_dict('records')

    score_name_column_name = score_name
    if score_config.get('label_score_name'):
        score_name = score_config['label_score_name']
    if score_config.get('label_field'):
        score_name_column_name = f"{score_name} {score_config['label_field']}"

    processed_samples = []
    for sample in samples:
        # Get metadata from the sample if it exists
        metadata = sample.get('metadata', {})
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError:
                logging.warning(f"Failed to parse metadata as JSON for content_id {sample.get('content_id')}")
                metadata = {}
        
        # Create the sample dictionary with metadata included
        processed_sample = {
            'text': sample.get('text', ''),
            f'{score_name_column_name}_label': sample.get(score_name_column_name, ''),
            'content_id': sample.get('content_id', ''),
            'columns': {
                **{k: v for k, v in sample.items() if k not in ['text', score_name, 'content_id', 'metadata']},
                'metadata': metadata  # Include the metadata in the columns
            }
        }
        processed_samples.append(processed_sample)

    return processed_samples 