import os
import json
import rich
import click
import plexus
import pandas as pd
from openpyxl.styles import Font
import asyncio
import sys
import traceback

from plexus.CustomLogging import logging
from plexus.Registries import scorecard_registry
from langgraph.errors import NodeInterrupt
from plexus.scores.LangGraphScore import BatchProcessingPause


@click.command(help="Predict a scorecard or specific score(s) within a scorecard.")
@click.option('--scorecard-name', required=True, help='The name of the scorecard.')
@click.option('--score-name', '--score-names', help='The name(s) of the score(s) to predict, separated by commas.')
@click.option('--content-id', help='The ID of a specific sample to use.')
@click.option('--number', type=int, default=1, help='Number of times to iterate over the list of scores.')
@click.option('--excel', is_flag=True, help='Output results to an Excel file.')
@click.option('--use-langsmith-trace', is_flag=True, default=False, help='Activate LangSmith trace client for LangChain components')
@click.option('--fresh', is_flag=True, help='Pull fresh, non-cached data from the data lake.')
def predict(scorecard_name, score_name, content_id, number, excel, use_langsmith_trace, fresh):
    """Click command wrapper that runs the async predict_impl function"""
    
    # Get or create event loop
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    # Create coroutine
    coro = predict_impl(
        scorecard_name, score_name, content_id, number, excel,
        use_langsmith_trace, fresh
    )

    try:
        # Set the exception handler
        loop.set_exception_handler(lambda l, ctx: handle_exception(
            l, ctx, scorecard_name=scorecard_name, score_name=score_name
        ))
        
        # Run the coroutine
        loop.run_until_complete(coro)
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as e:
        if not isinstance(e, BatchProcessingPause):
            logging.error(f"Unexpected error: {e}")
            raise
    finally:
        loop.close()

async def predict_impl(scorecard_name, score_name, content_id, number, excel, use_langsmith_trace, fresh):
    """Async implementation of the predict command"""
    try:
        logging.info("=== Starting predict_impl() ===")
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
            
            sample_row, used_content_id = select_sample(
                scorecard_class, score_names[0], content_id, fresh
            )
            
            row_result = {}
            for single_score_name in score_names:
                try:
                    logging.info(f"Starting prediction for score: {single_score_name}")
                    transcript, predictions, costs = await predict_score(
                        single_score_name, scorecard_class, sample_row, used_content_id
                    )
                    
                    logging.info(f"Got predictions: {predictions}")
                    
                    # Initialize basic result fields
                    row_result['content_id'] = used_content_id
                    row_result['text'] = transcript if transcript else ""
                    
                    # Check if we have valid predictions
                    if predictions and isinstance(predictions, list) and len(predictions) > 0:
                        prediction = predictions[0]
                        logging.info(f"Processing prediction: {prediction}")
                        
                        row_result[f'{single_score_name}_value'] = prediction.value
                        row_result[f'{single_score_name}_explanation'] = \
                            prediction.explanation
                        row_result[f'{single_score_name}_cost'] = float(costs['total_cost'])
                    else:
                        logging.info(
                            f"No valid predictions returned for {single_score_name} - "
                            "likely hit a breakpoint or got empty result"
                        )
                        row_result[f'{single_score_name}_value'] = None
                        row_result[f'{single_score_name}_explanation'] = None
                        row_result[f'{single_score_name}_cost'] = 0.0
                    
                except BatchProcessingPause:
                    # Let it propagate up to be handled by the event loop handler
                    raise
                except Exception as e:
                    logging.error(f"Error processing score {single_score_name}: {e}")
                    logging.error(f"Full traceback: {traceback.format_exc()}")
                    raise
            
            # Only add row_result if we have any non-None values
            if any(
                row_result.get(f'{name}_value') is not None 
                for name in score_names
            ):
                if len(score_names) > 1:
                    # Only compare non-None values
                    values = [
                        row_result[f'{name}_value'] 
                        for name in score_names 
                        if row_result.get(f'{name}_value') is not None
                    ]
                    row_result['match?'] = len(set(values)) == 1 if values else None
                results.append(row_result)

        if excel and results:
            output_excel(results, score_names, scorecard_name)
        elif results:
            for result in results:
                truncated_result = {
                    k: f"{str(v)[:80]}..." if isinstance(v, str) and len(str(v)) > 80 
                    else v
                    for k, v in result.items()
                }
                logging.info(f"Prediction result: {truncated_result}")
    except BatchProcessingPause:
        # Let it propagate up to be handled by the event loop handler
        raise
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        logging.error(f"Full traceback: {traceback.format_exc()}")
        raise

def output_excel(results, score_names, scorecard_name):
    df = pd.DataFrame(results)
    
    logging.info(f"Available DataFrame columns: {df.columns.tolist()}")
    
    columns = ['content_id', 'text']
    for name in score_names:
        columns.extend([
            f'{name}_value',
            f'{name}_explanation',
            f'{name}_cost'
        ])
    if len(score_names) > 1:
        columns.append('match?')
    
    logging.info(f"Requested columns: {columns}")
    existing_columns = [col for col in columns if col in df.columns]
    logging.info(f"Found columns: {existing_columns}")
    
    df = df[existing_columns]
    
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

    batch_mode = os.getenv('PLEXUS_ENABLE_BATCH_MODE', '').lower() == 'true'
    
    if content_id:
        sample_row = score_instance.dataframe[score_instance.dataframe['content_id'] == content_id]
        if sample_row.empty:
            logging.warning(f"Content ID '{content_id}' not found in the data. Selecting a random sample.")
            if batch_mode:
                # Use a consistent seed for batch mode testing
                sample_row = score_instance.dataframe.sample(n=1, random_state=42)
            else:
                sample_row = score_instance.dataframe.sample(n=1)
    else:
        if batch_mode:
            # Use a consistent seed for batch mode testing
            sample_row = score_instance.dataframe.sample(n=1, random_state=42)
        else:
            sample_row = score_instance.dataframe.sample(n=1)
    
    used_content_id = sample_row.iloc[0]['content_id']
    logging.info(f"Selected content_id: {used_content_id}")
    
    # Add required metadata for batch processing
    metadata = {
        "content_id": str(used_content_id),
        "account_key": "call-criteria",
        "scorecard_key": scorecard_class.properties.get('key'),
        "score_name": score_name
    }
    sample_row['metadata'] = json.dumps(metadata)
    
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
    
    # Get scorecard key from the csv_path
    # Path format is 'scorecards/<scorecard_key>/experiments/labeled-samples.csv'
    scorecard_key = csv_path.split('/')[1]
    
    # Add required metadata for batch processing
    metadata = {
        "content_id": str(used_content_id),
        "account_key": "call-criteria",
        "scorecard_key": scorecard_key,
        "score_name": "accuracy"
    }
    sample_row['metadata'] = json.dumps(metadata)
    
    return sample_row, used_content_id

async def predict_score(score_name, scorecard_class, sample_row, used_content_id):
    """Async function to predict a single score"""
    try:
        logging.info(f"Entering predict_score for {score_name}")
        logging.info(f"Predicting Score [magenta1][b]{score_name}[/b][/magenta1]...")
        score_configuration = next(
            (score for score in scorecard_class.scores if score['name'] == score_name), 
            {}
        )

        if not score_configuration:
            logging.error(
                f"Score with name '{score_name}' not found in scorecard "
                f"'{scorecard_class.name}'."
            )
            return None, None, None

        score_class = scorecard_class.score_registry.get(score_name)
        if score_class is None:
            logging.error(f"Score class for '{score_name}' not found in the registry.")
            return None, None, None

        score_configuration['scorecard_name'] = scorecard_class.name
        score_configuration['score_name'] = score_name

        # Create score instance without context manager
        score_instance = score_class(**score_configuration)
        await score_instance.async_setup()
        
        try:
            # Create input
            score_input_class = getattr(score_class, 'Input', None)
            if score_input_class is None:
                logging.warning(
                    f"Input class not found for score '{score_name}'. Using default."
                )
                metadata = {"content_id": str(used_content_id)}
                score_input = {'id': used_content_id, 'text': "", 'metadata': metadata}
            else:
                if sample_row is not None:
                    row_dictionary = sample_row.iloc[0].to_dict()
                    text = row_dictionary.get('text', '')
                    metadata_str = row_dictionary.get('metadata', '{}')
                    metadata = json.loads(metadata_str)
                    if 'content_id' not in metadata:
                        metadata['content_id'] = str(used_content_id)
                    score_input = score_input_class(text=text, metadata=metadata)
                else:
                    metadata = {"content_id": str(used_content_id)}
                    score_input = score_input_class(
                        id=used_content_id, text="", metadata=metadata
                    )

            result = await predict_score_impl(score_instance, {}, score_input)
            return result
            
        except BatchProcessingPause:
            # Clean up and re-raise
            await score_instance.cleanup()
            raise
        except Exception as e:
            logging.error(f"Error during prediction: {e}")
            logging.error(f"Full traceback: {traceback.format_exc()}")
            await score_instance.cleanup()
            raise
            
    except BatchProcessingPause:
        # Expected condition - re-raise
        raise
    except Exception as e:
        logging.error(f"Error in predict_score: {e}")
        logging.error(f"Full traceback: {traceback.format_exc()}")
        raise

async def predict_score_impl(score_instance, context, input_data):
    """Predict a single score."""
    logging.info("Entering predict_score_impl")
    try:
        logging.info("Starting score prediction...")
        
        # Get thread_id for config
        thread_id = input_data.metadata.get('content_id')
        config = {
            "configurable": {
                "thread_id": str(thread_id)
            }
        }
        
        # If we have a checkpoint, pass None as input to resume
        if hasattr(score_instance, 'checkpointer') and score_instance.checkpointer:
            checkpoint = await score_instance.checkpointer.aget(config)
            if checkpoint:
                logging.info(f"Found checkpoint for thread {thread_id}, resuming execution")
                prediction_result = await score_instance.workflow.ainvoke(
                    None,  # Pass None to resume from checkpoint
                    config=config  # Just pass thread_id in config
                )
                logging.info(f"Got prediction_result: {prediction_result}")
            else:
                logging.info("No checkpoint found, starting fresh prediction")
                prediction_result = await score_instance.predict(context, input_data)
                logging.info(f"Fresh prediction result: {prediction_result}")
        else:
            logging.info("No checkpointer, starting fresh prediction")
            prediction_result = await score_instance.predict(context, input_data)
            logging.info(f"Fresh prediction result: {prediction_result}")
            
        costs = score_instance.get_accumulated_costs()
        logging.info("Returning final results")
        return input_data.text, prediction_result, costs
        
    except BatchProcessingPause as e:
        # Clean up and re-raise with full context
        await score_instance.cleanup()
        logging.info(f"Batch job created: {e.message}")
        raise
    except Exception as e:
        logging.error(f"Error in predict_score_impl: {e}")
        logging.error(f"Full traceback: {traceback.format_exc()}")
        await score_instance.cleanup()
        raise

def handle_exception(loop, context, scorecard_name=None, score_name=None):
    """Custom exception handler for the event loop"""
    exception = context.get('exception')
    message = context.get('message', '')
    
    if isinstance(exception, BatchProcessingPause):
        logging.info("=== BatchProcessingPause caught in event loop exception handler ===")
        
        # Show a nicely formatted message about the batch job
        print("\n" + "="*80)
        print("Workflow Paused for Batch Processing")
        print("=" * 80)
        print(f"\nBatch Job Created")
        print(f"Thread ID: {exception.thread_id}")
        print(f"Message: {exception.message}")
        print("\nTo resume this workflow:")
        print("1. Keep PLEXUS_ENABLE_BATCH_MODE=true for checkpointing")
        print("2. Either:")
        print("   a. Set PLEXUS_ENABLE_LLM_BREAKPOINTS=false to run without stopping")
        print("   b. Keep PLEXUS_ENABLE_LLM_BREAKPOINTS=true to continue stopping at breakpoints")
        print(f"3. Run the same command with --content-id {exception.thread_id}")
        print("\nExample:")
        print(f"  plexus predict --scorecard-name {scorecard_name}", end="")
        if score_name:
            print(f" --score-name {score_name}", end="")
        print(f" --content-id {exception.thread_id}")
        print("=" * 80 + "\n")
        
        # Stop the event loop gracefully
        loop.stop()
    else:
        logging.error(f"Unhandled exception in event loop: {message}")
        logging.error(f"Exception: {exception}")
        loop.default_exception_handler(context)
        loop.stop()