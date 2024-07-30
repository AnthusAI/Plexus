import rich
import click
import importlib
import plexus
import copy
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font

from plexus.CustomLogging import logging
from plexus.cli.console import console
from plexus.Registries import scorecard_registry
from plexus.scores.Score import Score

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich.pretty import pprint

@click.command(help="Predict a scorecard or specific score(s) within a scorecard, using one random sample from the training data.")
@click.option('--scorecard-name', required=True, help='The name of the scorecard.')
@click.option('--score-name', '--score-names', help='The name(s) of the score(s) to predict, separated by commas.')
@click.option('--content-id', help='The ID of a specific sample to use.')
@click.option('--number', type=int, default=1, help='Number of times to iterate over the list of scores.')
@click.option('--excel', is_flag=True, help='Output results to an Excel file.')
def predict(scorecard_name, score_name, content_id, number, excel):
    logging.info(f"Predicting Scorecard [magenta1][b]{scorecard_name}[/b][/magenta1]...")

    plexus.Scorecard.load_and_register_scorecards('scorecards/')
    scorecard_class = scorecard_registry.get(scorecard_name)

    if scorecard_class is None:
        logging.error(f"Scorecard with name '{scorecard_name}' not found.")
        return

    logging.info(f"Found registered Scorecard named [magenta1][b]{scorecard_class.name}[/b][/magenta1] implemented in Python class [magenta1][b]{scorecard_class.__name__}[/b][/magenta1]")

    if score_name:
        score_names = [name.strip() for name in score_name.split(',')]
    else:
        score_names = list(scorecard_class.scores.keys())
        logging.info(f"No score name provided. Predicting all scores for Scorecard [magenta1][b]{scorecard_class.name}[/b][/magenta1]...")

    results = []

    for iteration in range(number):
        if number > 1:
            logging.info(f"Iteration {iteration + 1} of {number}")
        
        # Select a single sample for all scores in this iteration
        sample_row, used_content_id = select_sample(scorecard_class, score_names[0], content_id)
        
        row_result = {}
        for single_score_name in score_names:
            transcript, predictions, costs = predict_score(single_score_name, scorecard_class, sample_row)
            row_result['content_id'] = used_content_id
            row_result['text'] = transcript
            for attribute, value in predictions[0].__dict__.items():
                row_result[attribute] = value
            row_result['total_cost'] = float(costs['total_cost'])
        
        if len(score_names) > 1:
            row_result['match?'] = len(set(row_result[f'{name}_value'] for name in score_names)) == 1
        
        results.append(row_result)

    if excel:
        output_excel(results, score_names, scorecard_name)
    else:
        for result in results:
            logging.info(f"Prediction result: {result}")

def output_excel(results, score_names, scorecard_name):
    df = pd.DataFrame(results)
    
    columns = ['content_id', 'text']
    for name in score_names:
        columns.extend([f'{name}_score', f'{name}_explanation', f'{name}_cost'])
    if len(score_names) > 1:
        columns.append('match?')
    
    df = df[columns]
    
    filename = f"{scorecard_name}_predictions.xlsx"
    with pd.ExcelWriter(filename, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Predictions')
        workbook = writer.book
        worksheet = writer.sheets['Predictions']
        
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(cell.value)
                except:
                    pass
            adjusted_width = (max_length + 2)
            worksheet.column_dimensions[column_letter].width = adjusted_width

        for cell in worksheet[1]:
            cell.font = Font(bold=True)

    logging.info(f"Excel file '{filename}' has been created with the prediction results.")

def select_sample(scorecard_class, score_name, content_id):
    score_configuration = scorecard_class.scores[score_name]
    score_class_name = score_configuration['class']
    score_module_path = f'plexus.scores.{score_class_name}'
    score_module = importlib.import_module(score_module_path)
    score_class = getattr(score_module, score_class_name)

    score_configuration['scorecard_name'] = scorecard_class.name
    score_configuration['score_name'] = score_name
    score_instance = score_class(**score_configuration)

    score_instance.load_data(queries=score_configuration['data']['queries'])
    score_instance.process_data()

    if content_id:
        sample_row = score_instance.dataframe[score_instance.dataframe['content_id'] == content_id]
    else:
        sample_row = score_instance.dataframe.sample(n=1)
    
    used_content_id = sample_row.iloc[0]['content_id']
    return sample_row, used_content_id

def predict_score(score_name, scorecard_class, sample_row):
    logging.info(f"Predicting Score [magenta1][b]{score_name}[/b][/magenta1]...")
    score_configuration = scorecard_class.scores[score_name]

    if score_name not in scorecard_class.scores:
        logging.error(f"Score with name '{score_name}' not found in scorecard '{scorecard_class.name}'.")
        return

    logging.info(f"Score Configuration: {rich.pretty.pretty_repr(score_configuration)}")

    # Score class instance setup

    score_class_name = score_configuration['class']
    score_module_path = f'plexus.scores.{score_class_name}'
    score_module = importlib.import_module(score_module_path)
    score_class = getattr(score_module, score_class_name)

    if not isinstance(score_class, type):
        logging.error(f"{score_class_name} is not a class.")
        return

    # Add the scorecard name and score name to the parameters.
    score_configuration['scorecard_name'] = scorecard_class.name
    score_configuration['score_name'] = score_name
    score_instance = score_class(**score_configuration)

    # Use the new instance to log its own configuration.
    score_instance.record_configuration(score_configuration)

    # Data processing
    data_queries = score_configuration['data']['queries']
    score_instance.load_data(queries=data_queries)
    score_instance.process_data()

    row_dictionary = sample_row.iloc[0].to_dict()
    logging.info(f"Sample Row: {row_dictionary}")

    text = row_dictionary['text']
    model_input_class = getattr(score_class, 'Input')
    prediction_result = score_instance.predict(
        context = {},
        model_input = model_input_class(
            text = text,
            metadata = row_dictionary
        )
    )
    costs = score_instance.get_accumulated_costs()
    logging.info(f"Prediction result: {prediction_result}")
    logging.info(f"Costs: {costs}")
    return text, prediction_result, costs