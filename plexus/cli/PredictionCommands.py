import os
import json
import rich
import click
import plexus
import pandas as pd
from openpyxl.styles import Font
import asyncio

from plexus.CustomLogging import logging
from plexus.Registries import scorecard_registry


@click.command(help="Predict a scorecard or specific score(s) within a scorecard.")
@click.option('--scorecard-name', required=True, help='The name of the scorecard.')
@click.option('--score-name', '--score-names', help='The name(s) of the score(s) to predict, separated by commas.')
@click.option('--content-id', help='The ID of a specific sample to use.')
@click.option('--number', type=int, default=1, help='Number of times to iterate over the list of scores.')
@click.option('--excel', is_flag=True, help='Output results to an Excel file.')
@click.option('--use-langsmith-trace', is_flag=True, default=False, help='Activate LangSmith trace client for LangChain components')
@click.option('--fresh', is_flag=True, help='Pull fresh, non-cached data from the data lake.')
def predict(scorecard_name, score_name, content_id, number, excel, use_langsmith_trace, fresh):
    if use_langsmith_trace:
        os.environ['LANGCHAIN_TRACING_V2'] = 'true'
        logging.info("LangSmith tracing enabled")
    else:
        os.environ.pop('LANGCHAIN_TRACING_V2', None)
        logging.info("LangSmith tracing disabled")

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
        
        sample_row, used_content_id = select_sample(scorecard_class, score_names[0], content_id, fresh)
        
        row_result = {}
        for single_score_name in score_names:
            transcript, predictions, costs = asyncio.run(predict_score(
                single_score_name, scorecard_class, sample_row, used_content_id))
            row_result['content_id'] = used_content_id
            row_result['text'] = transcript
            for attribute, value in predictions[0].__dict__.items():
                row_result[attribute] = value
            row_result['total_cost'] = float(costs['total_cost'])
        
        if len(score_names) > 1:
            row_result['match?'] = len(set(row_result[f'{name}_value'] for name in score_names if row_result[f'{name}_value'] is not None)) == 1
        
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

def select_sample(scorecard_class, score_name, content_id, fresh):

    score_configuration = next((score for score in scorecard_class.scores if score['name'] == score_name), {})
    
    # Check if the score uses the new data-driven approach
    if 'data' in score_configuration:
        return select_sample_data_driven(scorecard_class, score_name, content_id, score_configuration, fresh)
    else:
        # Use labeled-samples.csv for old scores
        scorecard_key = scorecard_class.properties.get('key')        
        csv_path = os.path.join('scorecards', scorecard_key, 'experiments', 'labeled-samples.csv')
        return select_sample_csv(csv_path, content_id)

def select_sample_data_driven(scorecard_class, score_name, content_id, score_configuration, fresh):
    score_class = scorecard_class.score_registry.get(score_name)
    if score_class is None:
        logging.error(f"Score class for '{score_name}' not found in the registry.")
        raise ValueError(f"Score class for '{score_name}' not found in the registry.")

    score_configuration['scorecard_name'] = scorecard_class.name
    score_configuration['score_name'] = score_name

    score_instance = score_class(**score_configuration)
    score_instance.load_data(data=score_configuration['data'], fresh=fresh)
    score_instance.process_data()

    if content_id:
        sample_row = score_instance.dataframe[score_instance.dataframe['content_id'] == content_id]
        if sample_row.empty:
            logging.warning(f"Content ID '{content_id}' not found in the data. Selecting a random sample.")
            sample_row = score_instance.dataframe.sample(n=1)
    else:
        sample_row = score_instance.dataframe.sample(n=1)
    
    used_content_id = sample_row.iloc[0]['content_id']
    return sample_row, used_content_id

def select_sample_csv(csv_path, content_id):
    if not os.path.exists(csv_path):
        logging.error(f"labeled-samples.csv not found at {csv_path}")
        raise FileNotFoundError(f"labeled-samples.csv not found at {csv_path}")

    df = pd.read_csv(csv_path)
    if content_id:
        sample_row = df[df['id'] == content_id]
        if sample_row.empty:
            logging.warning(f"ID '{content_id}' not found in {csv_path}. Selecting a random sample.")
            sample_row = df.sample(n=1)
    else:
        sample_row = df.sample(n=1)
    
    used_content_id = sample_row.iloc[0]['id']
    return sample_row, used_content_id

async def predict_score(score_name, scorecard_class, sample_row, content_id):
    logging.info(f"Predicting Score [magenta1][b]{score_name}[/b][/magenta1]...")
    score_configuration = next((score for score in scorecard_class.scores if score['name'] == score_name), {})

    if not score_configuration:
        logging.error(f"Score with name '{score_name}' not found in scorecard '{scorecard_class.name}'.")
        return None, None, None

    logging.info(f"Score Configuration: {rich.pretty.pretty_repr(score_configuration)}")

    score_class = scorecard_class.score_registry.get(score_name)
    if score_class is None:
        logging.error(f"Score class for '{score_name}' not found in the registry.")
        return None, None, None

    score_configuration['scorecard_name'] = scorecard_class.name
    score_configuration['score_name'] = score_name

    try:
        score_instance = score_class(**score_configuration)
    except Exception as e:
        logging.error(f"Failed to instantiate score class for '{score_name}': {str(e)}")
        return None, None, None

    score_instance.record_configuration(score_configuration)

    score_input_class = getattr(score_class, 'Input', None)
    if score_input_class is None:
        logging.warning(f"Input class not found for score '{score_name}'. Using a default input.")
        score_input = {'id': content_id, 'text': ""}
    else:
        if sample_row is not None:
            row_dictionary = sample_row.iloc[0].to_dict()
            logging.info(f"Sample Row: {row_dictionary}")
            text = row_dictionary.get('text', '')
            metadata_str = row_dictionary.get('metadata', '{}')
            metadata = json.loads(metadata_str)
            score_input = score_input_class(text=text, metadata=metadata)
        else:
            score_input = score_input_class(id=content_id, text="")

    prediction_result = await score_instance.predict(
        context={},
        model_input=score_input
    )
    costs = score_instance.get_accumulated_costs()

    logging.info(f"Prediction result: {prediction_result}")
    logging.info(f"Costs: {costs}")
    return text if sample_row is not None else "", prediction_result, costs