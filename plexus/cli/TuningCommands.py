import rich
import click
import plexus
import os
import json
import pandas as pd
from openpyxl.styles import Font
from langchain_core.prompts import ChatPromptTemplate

from plexus.CustomLogging import logging
from plexus.Registries import scorecard_registry

@click.group()
def tuning():
    """Commands for fine-tuning models."""
    pass

@tuning.command(help="Generate JSON-L files for training and validation.")
@click.option('--model-name', required=True, help='The name of the model.')
@click.option('--scorecard-name', required=True, help='The name of the scorecard.')
@click.option('--score-name', help='The name of the score to generate JSON-L for.')
@click.option('--number', type=int, default=100, help='Number of samples, total.')
def data(model_name, scorecard_name, score_name, number):
    logging.info(f"Generating JSON-L for [magenta1][b]{score_name}[/b][/magenta1] on [magenta1][b]{scorecard_name}[/b][/magenta1]...")

    # Find the scorecard
    plexus.Scorecard.load_and_register_scorecards('scorecards/')
    scorecard_class = scorecard_registry.get(scorecard_name)
    if scorecard_class is None:
        logging.error(f"No scorecard named [magenta1][b]{scorecard_name}[/b][/magenta1] found.")
        return
    
    # Instantiate the score class using the configuration parameters.
    score_configuration = scorecard_class.scores.get(score_name, {})
    logging.info(f"Score Configuration: {rich.pretty.pretty_repr(score_configuration)}")
    score_class = scorecard_class.score_registry.get(score_name)
    if score_class is None:
        logging.error(f"Score class for '{score_name}' not found in the registry.")
        return
    score_configuration['scorecard_name'] = scorecard_class.name
    score_configuration['score_name'] = score_name
    try:
        score_instance = score_class(**score_configuration)
    except Exception as e:
        logging.error(f"Failed to instantiate score class for '{score_name}': {str(e)}")
        return

    # Get data
    sample_rows = None
    score_instance = score_class(**score_configuration)
    score_instance.load_data(queries=score_configuration['data'].get('queries'))
    score_instance.process_data()

    sample_rows = score_instance.dataframe.sample(n=number)

    # Log sample rows
    logging.info(f"Sample rows: {sample_rows.to_dict('records')}")

    # Calculate the number of training samples
    num_training_samples = int(len(sample_rows) * 0.8)

    training_data = []
    validation_data = []

    # Get templates
    templates = score_instance.get_prompt_templates()
    logging.info(f"Templates: {templates}")

    # Loop through the sample rows and generate JSON-L
    for index, row in sample_rows.iterrows():
        formatted_messages = []
        for node_templates in templates:
            for template in node_templates:
                if isinstance(template, ChatPromptTemplate):
                    try:
                        messages = template.format_messages(text=row['text'])
                        formatted_messages.extend([
                            {"role": message.type, "content": message.content}
                            for message in messages
                        ])
                    except Exception as e:
                        logging.error(f"Error formatting messages for row {index}: {e}")

        if not formatted_messages:
            logging.warning(f"No formatted messages for row {index}. Skipping.")
            continue

        logging.info(f"Formatted messages for row {index}: {formatted_messages}")

        completion = row[score_name]
        logging.info(f"Completion for row {index}: {completion}")
        formatted_messages.append({"role": "assistant", "content": completion})

        message = {"messages": formatted_messages}

        if len(training_data) < num_training_samples:
            training_data.append(message)
        else:
            validation_data.append(message)

    logging.info(f"Number of training samples: {len(training_data)}")
    logging.info(f"Number of validation samples: {len(validation_data)}")

    # Ensure the directory exists
    output_dir = f"tuning/{scorecard_name}/{score_name}"
    os.makedirs(output_dir, exist_ok=True)
    
    # Save to JSON-L files
    with open(f"{output_dir}/{model_name}_training.jsonl", "w") as train_file:
        for entry in training_data:
            train_file.write(f"{json.dumps(entry)}\n")
    
    with open(f"{output_dir}/{model_name}_validation.jsonl", "w") as val_file:
        for entry in validation_data:
            val_file.write(f"{json.dumps(entry)}\n")