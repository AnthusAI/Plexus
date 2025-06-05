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
from plexus.Scorecard import Scorecard
from plexus.scores.Score import Score
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.cli.shared import get_scoring_jobs_for_batch


@click.command(help="Predict a scorecard or specific score(s) within a scorecard.")
@click.option('--scorecard-name', required=True, help='The name of the scorecard.')
@click.option('--score-name', '--score-names', help='The name(s) of the score(s) to predict, separated by commas.')
@click.option('--content-id', help='The ID of a specific sample to use.')
@click.option('--number', type=int, default=1, help='Number of times to iterate over the list of scores.')
@click.option('--excel', is_flag=True, help='Output results to an Excel file.')
@click.option('--use-langsmith-trace', is_flag=True, default=False, help='Activate LangSmith trace client for LangChain components')
@click.option('--fresh', is_flag=True, help='Pull fresh, non-cached data from the data lake.')
@click.option('--task-id', default=None, type=str, help='Task ID for progress tracking')
def predict(scorecard_name, score_name, content_id, number, excel, use_langsmith_trace, fresh, task_id):
    """Predict scores for a scorecard"""
    try:
        # Configure event loop with custom exception handler
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.set_exception_handler(
            lambda l, c: handle_exception(l, c, scorecard_name, score_name)
        )

        # Create and run coroutine
        if score_name:
            score_names = [name.strip() for name in score_name.split(',')]
        else:
            score_names = []
        
        coro = predict_impl(
            scorecard_name, score_names, content_id, excel, 
            use_langsmith_trace, fresh, task_id
        )
        try:
            loop.run_until_complete(coro)
        except BatchProcessingPause as e:
            logging.info(f"Created batch job {e.batch_job_id} for thread {e.thread_id}")
            rich.print(f"[green]Created batch job {e.batch_job_id}[/green]")
            return  # Exit normally
        finally:
            # Clean up any remaining tasks
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            
            # Allow tasks to complete cancellation
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            
            loop.close()
    except KeyboardInterrupt:
        logging.info("Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error during prediction: {e}")
        logging.error(f"Full traceback: {traceback.format_exc()}")
        sys.exit(1)

async def predict_impl(
    scorecard_name: str,
    score_names: list,
    content_id: str = None,
    excel: bool = False,
    use_langsmith_trace: bool = False,
    fresh: bool = False,
    task_id: str = None
):
    """Implementation of predict command"""
    try:
        results = []
        scorecard_class = get_scorecard_class(scorecard_name)
        
        for score_name in score_names:
            sample_row, used_content_id = select_sample(
                scorecard_class, score_name, content_id, fresh
            )
            
            row_result = {'content_id': used_content_id}
            if sample_row is not None:
                row_result['text'] = sample_row.iloc[0].get('text', '')
            
            try:
                transcript, predictions, costs = await predict_score(
                    score_name, scorecard_class, sample_row, used_content_id
                )
                
                if predictions:
                    if isinstance(predictions, list):
                        # Handle list of results
                        prediction = predictions[0] if predictions else None
                        if prediction:
                            row_result[f'{score_name}_value'] = prediction.value
                            row_result[f'{score_name}_explanation'] = prediction.explanation
                            row_result[f'{score_name}_cost'] = costs
                            logging.info(f"Got predictions: {predictions}")
                    else:
                        # Handle Score.Result object
                        if hasattr(predictions, 'value') and predictions.value is not None:
                            row_result[f'{score_name}_value'] = predictions.value
                            # Try to get explanation from the result object
                            explanation = None
                            if hasattr(predictions, 'explanation'):
                                explanation = predictions.explanation
                            elif hasattr(predictions, 'metadata') and predictions.metadata:
                                explanation = predictions.metadata.get('explanation')
                            row_result[f'{score_name}_explanation'] = explanation
                            row_result[f'{score_name}_cost'] = costs
                            logging.info(f"Got predictions: {predictions}")
                else:
                    row_result[f'{score_name}_value'] = None
                    row_result[f'{score_name}_explanation'] = None
                    row_result[f'{score_name}_cost'] = None
                
            except BatchProcessingPause:
                raise
            except Exception as e:
                logging.error(f"Error processing score {score_name}: {e}")
                logging.error(f"Full traceback: {traceback.format_exc()}")
                raise
            
            if any(row_result.get(f'{name}_value') is not None for name in score_names):
                results.append(row_result)

        if excel and results:
            output_excel(results, score_names, scorecard_name)
        elif results:
            # Print results to console for user visibility
            rich.print("\n[bold green]Prediction Results:[/bold green]")
            for result in results:
                rich.print(f"\n[bold]Content ID:[/bold] {result.get('content_id')}")
                if result.get('text'):
                    text_preview = result['text'][:200] + "..." if len(result['text']) > 200 else result['text']
                    rich.print(f"[bold]Text Preview:[/bold] {text_preview}")
                
                for name in score_names:
                    value = result.get(f'{name}_value')
                    explanation = result.get(f'{name}_explanation')
                    cost = result.get(f'{name}_cost')
                    
                    rich.print(f"\n[bold cyan]{name} Score:[/bold cyan]")
                    rich.print(f"  [bold]Value:[/bold] {value}")
                    if explanation:
                        rich.print(f"  [bold]Explanation:[/bold] {explanation}")
                    if cost:
                        rich.print(f"  [bold]Cost:[/bold] {cost}")
                
                # Also log the truncated version for debugging
                truncated_result = {
                    k: f"{str(v)[:80]}..." if isinstance(v, str) and len(str(v)) > 80 
                    else v
                    for k, v in result.items()
                }
                logging.info(f"Prediction result: {truncated_result}")
        else:
            rich.print("[yellow]No prediction results to display.[/yellow]")
    except BatchProcessingPause:
        # Let it propagate up to be handled by the event loop handler
        raise
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        logging.error(f"Full traceback: {traceback.format_exc()}")
        raise
    finally:
        # Final cleanup of any remaining tasks
        for task in asyncio.all_tasks():
            if not task.done() and task != asyncio.current_task():
                task.cancel()

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
        # Convert content_id to integer since all values in DataFrame are integers
        try:
            content_id_int = int(content_id)
            exists = content_id_int in score_instance.dataframe['content_id'].values
            logging.info(f"Content ID {content_id_int} {'exists' if exists else 'does not exist'} in dataset")
            
            sample_row = score_instance.dataframe[
                score_instance.dataframe['content_id'] == content_id_int
            ]
            if sample_row.empty:
                logging.warning(f"Content ID '{content_id}' not found in the data. Selecting a random sample.")
                sample_row = score_instance.dataframe.sample(n=1)
        except ValueError:
            logging.error(f"Invalid content ID format: {content_id}. Must be an integer.")
            raise
    else:
        sample_row = score_instance.dataframe.sample(n=1)
    
    used_content_id = sample_row.iloc[0]['content_id']
    logging.info(f"Selected content_id: {used_content_id}")
    
    # Add required metadata for batch processing
    metadata = {
        "content_id": str(used_content_id),
        "account_key": os.getenv('PLEXUS_ACCOUNT_KEY', 'call-criteria'),
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
    """Predict a single score."""
    score_instance = None  # Initialize outside try block
    try:
        # Create score instance
        score_input = create_score_input(
            sample_row=sample_row, 
            content_id=used_content_id, 
            scorecard_class=scorecard_class,
            score_name=score_name
        )
        
        # Run prediction
        try:
            result = await predict_score_impl(
                scorecard_class=scorecard_class,
                score_name=score_name,
                content_id=used_content_id,
                input_data=score_input,
                fresh=False
            )
            
            if result[0] is not None:  # Check if we got actual results
                return result
            logging.info(f"No valid predictions returned for {score_name} - likely hit a breakpoint or got empty result")
            return None, None, None
            
        except BatchProcessingPause:
            raise  # Just re-raise, no cleanup needed here
        except Exception as e:
            logging.error(f"Error during prediction: {e}")
            logging.error(f"Full traceback: {traceback.format_exc()}")
            raise
            
    except BatchProcessingPause:
        raise  # Just re-raise
    except Exception as e:
        logging.error(f"Error in predict_score: {e}")
        logging.error(f"Full traceback: {traceback.format_exc()}")
        raise

async def predict_score_impl(
    scorecard_class,
    score_name,
    content_id,
    input_data,
    use_langsmith_trace=False,
    fresh=False
):
    try:
        score_instance = Score.from_name(scorecard_class.properties['key'], score_name)
        async with score_instance:
            await score_instance.async_setup()
            prediction_result = await score_instance.predict(input_data)
            
            # Get costs if available
            costs = None
            if hasattr(score_instance, 'get_accumulated_costs'):
                try:
                    costs = score_instance.get_accumulated_costs()
                except Exception as e:
                    logging.warning(f"Failed to get costs: {e}")
                    costs = None
                    
            return score_instance, prediction_result, costs
            
    except BatchProcessingPause:
        # Just let it propagate up - state is already stored in batch job
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

def get_scorecard_class(scorecard_name: str):
    """Get the scorecard class from the registry."""
    Scorecard.load_and_register_scorecards('scorecards/')
    scorecard_class = scorecard_registry.get(scorecard_name)
    if scorecard_class is None:
        logging.error(f"Scorecard with name '{scorecard_name}' not found.")
        raise ValueError(f"Scorecard with name '{scorecard_name}' not found.")
    return scorecard_class

def create_score_input(sample_row, content_id, scorecard_class, score_name):
    """Create a Score.Input object from sample data."""
    score_class = Score.from_name(scorecard_class.properties['key'], score_name)
    score_input_class = getattr(score_class, 'Input', None)
    
    if score_input_class is None:
        logging.warning(f"Input class not found. Using Score.Input default.")
        score_input_class = Score.Input
    
    if sample_row is not None:
        row_dictionary = sample_row.iloc[0].to_dict()
        text = row_dictionary.get('text', '')
        metadata_str = row_dictionary.get('metadata', '{}')
        metadata = json.loads(metadata_str)
        if 'content_id' not in metadata:
            metadata['content_id'] = str(content_id)
        return score_input_class(text=text, metadata=metadata)
    else:
        metadata = {"content_id": str(content_id)}
        return score_input_class(text="", metadata=metadata)