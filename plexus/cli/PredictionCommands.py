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
from plexus.cli.identifier_resolution import resolve_scorecard_identifier, resolve_score_identifier, resolve_item_identifier
from plexus.cli.memoized_resolvers import memoized_resolve_scorecard_identifier, memoized_resolve_item_identifier


@click.command(help="Predict a scorecard or specific score(s) within a scorecard.")
@click.option('--scorecard', required=True, help='The scorecard to use (accepts ID, name, key, or external ID).')
@click.option('--score', '--scores', help='The score(s) to predict (accepts ID, name, key, or external ID), separated by commas.')
@click.option('--item', help='The item to use (accepts ID or any identifier value).')
@click.option('--number', type=int, default=1, help='Number of times to iterate over the list of scores.')
@click.option('--excel', is_flag=True, help='Output results to an Excel file.')
@click.option('--use-langsmith-trace', is_flag=True, default=False, help='Activate LangSmith trace client for LangChain components')
@click.option('--fresh', is_flag=True, help='Pull fresh, non-cached data from the data lake.')
@click.option('--task-id', default=None, type=str, help='Task ID for progress tracking')
@click.option('--format', type=click.Choice(['fixed', 'json']), default='fixed', help='Output format: fixed (human-readable) or json (parseable JSON)')
def predict(scorecard, score, item, number, excel, use_langsmith_trace, fresh, task_id, format):
    """Predict scores for a scorecard"""
    try:
        # Configure event loop with custom exception handler
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.set_exception_handler(
            lambda l, c: handle_exception(l, c, scorecard, score)
        )

        # Create and run coroutine
        if score:
            score_names = [name.strip() for name in score.split(',')]
        else:
            score_names = []
        
        coro = predict_impl(
            scorecard, score_names, item, excel, 
            use_langsmith_trace, fresh, task_id, format
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
    scorecard_identifier: str,
    score_names: list,
    item_identifier: str = None,
    excel: bool = False,
    use_langsmith_trace: bool = False,
    fresh: bool = False,
    task_id: str = None,
    format: str = 'fixed'
):
    """Implementation of predict command"""
    try:
        results = []
        scorecard_class = get_scorecard_class(scorecard_identifier)
        
        for score_name in score_names:
            sample_row, used_item_id = select_sample(
                scorecard_class, score_name, item_identifier, fresh
            )
            
            row_result = {'item_id': used_item_id}
            if sample_row is not None:
                row_result['text'] = sample_row.iloc[0].get('text', '')
            
            try:
                transcript, predictions, costs = await predict_score(
                    score_name, scorecard_class, sample_row, used_item_id
                )
                
                if predictions:
                    if isinstance(predictions, list):
                        # Handle list of results
                        prediction = predictions[0] if predictions else None
                        if prediction:
                            row_result[f'{score_name}_value'] = prediction.value
                            row_result[f'{score_name}_explanation'] = prediction.explanation
                            row_result[f'{score_name}_cost'] = costs
                            # Extract trace information
                            if hasattr(prediction, 'trace'):
                                row_result[f'{score_name}_trace'] = prediction.trace
                            elif hasattr(prediction, 'metadata') and prediction.metadata:
                                row_result[f'{score_name}_trace'] = prediction.metadata.get('trace')
                            else:
                                row_result[f'{score_name}_trace'] = None
                            logging.info(f"Got predictions: {predictions}")
                    else:
                        # Handle Score.Result object
                        if hasattr(predictions, 'value') and predictions.value is not None:
                            row_result[f'{score_name}_value'] = predictions.value
                            # ✅ ENHANCED: Get explanation from direct field first, then metadata
                            explanation = (
                                getattr(predictions, 'explanation', None) or
                                predictions.metadata.get('explanation', '') if hasattr(predictions, 'metadata') and predictions.metadata else
                                ''
                            )
                            row_result[f'{score_name}_explanation'] = explanation
                            row_result[f'{score_name}_cost'] = costs
                            # Extract trace information
                            trace = None
                            if hasattr(predictions, 'trace'):
                                trace = predictions.trace
                            elif hasattr(predictions, 'metadata') and predictions.metadata:
                                trace = predictions.metadata.get('trace')
                            row_result[f'{score_name}_trace'] = trace
                            logging.info(f"Got predictions: {predictions}")
                else:
                    row_result[f'{score_name}_value'] = None
                    row_result[f'{score_name}_explanation'] = None
                    row_result[f'{score_name}_cost'] = None
                    row_result[f'{score_name}_trace'] = None
                
            except BatchProcessingPause:
                raise
            except Exception as e:
                logging.error(f"Error processing score {score_name}: {e}")
                logging.error(f"Full traceback: {traceback.format_exc()}")
                raise
            
            if any(row_result.get(f'{name}_value') is not None for name in score_names):
                results.append(row_result)

        if excel and results:
            output_excel(results, score_names, scorecard_identifier)
        elif results:
            if format == 'json':
                # JSON format: only output parseable JSON
                json_results = []
                for result in results:
                    json_result = {
                        'item_id': result.get('item_id')
                    }
                    for name in score_names:
                        json_result[name] = {
                            'value': result.get(f'{name}_value'),
                            'explanation': result.get(f'{name}_explanation'),
                            'cost': result.get(f'{name}_cost'),
                            'trace': result.get(f'{name}_trace')
                        }
                    json_results.append(json_result)
                
                import json
                from decimal import Decimal
                
                # Custom JSON encoder to handle Decimal objects
                class DecimalEncoder(json.JSONEncoder):
                    def default(self, obj):
                        if isinstance(obj, Decimal):
                            return float(obj)
                        return super(DecimalEncoder, self).default(obj)
                
                print(json.dumps(json_results, indent=2, cls=DecimalEncoder))
            else:
                # Fixed format: human-readable output
                rich.print("\n[bold green]Prediction Results:[/bold green]")
                for result in results:
                    rich.print(f"\n[bold]Item ID:[/bold] {result.get('item_id')}")
                    if result.get('text'):
                        text_preview = result['text'][:200] + "..." if len(result['text']) > 200 else result['text']
                        rich.print(f"[bold]Text Preview:[/bold] {text_preview}")
                    
                    for name in score_names:
                        value = result.get(f'{name}_value')
                        explanation = result.get(f'{name}_explanation')
                        cost = result.get(f'{name}_cost')
                        trace = result.get(f'{name}_trace')
                        
                        rich.print(f"\n[bold cyan]{name} Score:[/bold cyan]")
                        rich.print(f"  [bold]Value:[/bold] {value}")
                        if explanation:
                            rich.print(f"  [bold]Explanation:[/bold] {explanation}")
                        if cost:
                            rich.print(f"  [bold]Cost:[/bold] {cost}")
                        if trace:
                            rich.print(f"  [bold]Trace:[/bold] {trace}")
                    
                    # Also log the truncated version for debugging
                    truncated_result = {
                        k: f"{str(v)[:80]}..." if isinstance(v, str) and len(str(v)) > 80 
                        else v
                        for k, v in result.items()
                    }
                    logging.info(f"Prediction result: {truncated_result}")
        else:
            if format != 'json':
                rich.print("[yellow]No prediction results to display.[/yellow]")
            else:
                print("[]")  # Empty JSON array for no results
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

def output_excel(results, score_names, scorecard_identifier):
    df = pd.DataFrame(results)
    
    logging.info(f"Available DataFrame columns: {df.columns.tolist()}")
    
    columns = ['item_id', 'text']
    for name in score_names:
        columns.extend([
            f'{name}_value',
            f'{name}_explanation',
            f'{name}_cost',
            f'{name}_trace'
        ])
    if len(score_names) > 1:
        columns.append('match?')
    
    logging.info(f"Requested columns: {columns}")
    existing_columns = [col for col in columns if col in df.columns]
    logging.info(f"Found columns: {existing_columns}")
    
    df = df[existing_columns]
    
    filename = f"{scorecard_identifier}_predictions.xlsx"
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

def select_sample(scorecard_class, score_name, item_identifier, fresh):
    """Select an item from the Plexus API using flexible identifier resolution."""
    from plexus.cli.client_utils import create_client
    from plexus.dashboard.api.models.item import Item
    from plexus.cli.reports.utils import resolve_account_id_for_command
    
    # Create API client
    client = create_client()
    account_id = resolve_account_id_for_command(client, None)
    
    if item_identifier:
        # Use the flexible item identifier resolution
        item_id = memoized_resolve_item_identifier(client, item_identifier, account_id)
        if not item_id:
            raise ValueError(f"No item found matching identifier: {item_identifier}")
        
        # Get the item
        try:
            item = Item.get_by_id(item_id, client)
            logging.info(f"Found item {item_id} from identifier '{item_identifier}'")
            
            # Create a pandas-like row structure for compatibility
            sample_data = {
                'text': item.text or '',
                'item_id': item.id,
                'metadata': json.dumps({
                    "item_id": item.id,
                    "account_key": os.getenv('PLEXUS_ACCOUNT_KEY', 'call-criteria'),
                    "scorecard_key": scorecard_class.properties.get('key'),
                    "score_name": score_name
                })
            }
            
            # Convert to DataFrame-like structure for compatibility
            import pandas as pd
            sample_row = pd.DataFrame([sample_data])
            
            return sample_row, item.id
            
        except Exception as e:
            logging.error(f"Error retrieving item {item_id}: {e}")
            raise ValueError(f"Could not retrieve item {item_id}: {e}")
    else:
        # Get the most recent item for the account
        query = f"""
        query ListItemByAccountIdAndCreatedAt($accountId: String!) {{
            listItemByAccountIdAndCreatedAt(accountId: $accountId, sortDirection: DESC, limit: 1) {{
                items {{
                    {Item.fields()}
                }}
            }}
        }}
        """
        
        response = client.execute(query, {'accountId': account_id})
        items = response.get('listItemByAccountIdAndCreatedAt', {}).get('items', [])
        
        if not items:
            raise ValueError("No items found in the account")
        
        item_data = items[0]
        item = Item.from_dict(item_data, client)
        
        logging.info(f"Selected most recent item {item.id} from API")
        
        # Create a pandas-like row structure for compatibility
        sample_data = {
            'text': item.text or '',
            'item_id': item.id,
            'metadata': json.dumps({
                "item_id": item.id,
                "account_key": os.getenv('PLEXUS_ACCOUNT_KEY', 'call-criteria'),
                "scorecard_key": scorecard_class.properties.get('key'),
                "score_name": score_name
            })
        }
        
        # Convert to DataFrame-like structure for compatibility
        import pandas as pd
        sample_row = pd.DataFrame([sample_data])
        
        return sample_row, item.id

async def predict_score(score_name, scorecard_class, sample_row, used_item_id):
    """Predict a single score."""
    score_instance = None  # Initialize outside try block
    try:
        # Create score instance
        score_input = create_score_input(
            sample_row=sample_row, 
            item_id=used_item_id, 
            scorecard_class=scorecard_class,
            score_name=score_name
        )
        
        # Run prediction
        try:
            result = await predict_score_impl(
                scorecard_class=scorecard_class,
                score_name=score_name,
                item_id=used_item_id,
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
    item_id,
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

def handle_exception(loop, context, scorecard_identifier=None, score_identifier=None):
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
        print(f"3. Run the same command with --item {exception.thread_id}")
        print("\nExample:")
        print(f"  plexus predict --scorecard {scorecard_identifier}", end="")
        if score_identifier:
            print(f" --score {score_identifier}", end="")
        print(f" --item {exception.thread_id}")
        print("=" * 80 + "\n")
        
        # Stop the event loop gracefully
        loop.stop()
    else:
        logging.error(f"Unhandled exception in event loop: {message}")
        logging.error(f"Exception: {exception}")
        loop.default_exception_handler(context)
        loop.stop()

def get_scorecard_class(scorecard_identifier: str):
    """Get the scorecard class from the registry using flexible identifier resolution."""
    from plexus.cli.client_utils import create_client
    
    # First try to resolve the scorecard identifier to get the actual scorecard details
    client = create_client()
    scorecard_id = memoized_resolve_scorecard_identifier(client, scorecard_identifier)
    
    if scorecard_id:
        # Get the scorecard details to get the key which is used for registry lookup
        query = f"""
        query GetScorecard {{
            getScorecard(id: "{scorecard_id}") {{
                id
                name
                key
            }}
        }}
        """
        
        try:
            result = client.execute(query)
            scorecard_data = result.get('getScorecard', {})
            scorecard_key = scorecard_data.get('key')
            scorecard_name = scorecard_data.get('name')
            
            if scorecard_key:
                # Load scorecards and try to get by key
                Scorecard.load_and_register_scorecards('scorecards/')
                scorecard_class = scorecard_registry.get(scorecard_key)
                if scorecard_class is not None:
                    logging.info(f"Found scorecard class for key '{scorecard_key}' (name: '{scorecard_name}')")
                    return scorecard_class
                
                # If key didn't work, try by name as fallback
                scorecard_class = scorecard_registry.get(scorecard_name)
                if scorecard_class is not None:
                    logging.info(f"Found scorecard class for name '{scorecard_name}' (key: '{scorecard_key}')")
                    return scorecard_class
        except Exception as e:
            logging.warning(f"Error getting scorecard details: {e}")
    
    # Fallback: try direct registry lookup with the original identifier
    Scorecard.load_and_register_scorecards('scorecards/')
    scorecard_class = scorecard_registry.get(scorecard_identifier)
    if scorecard_class is not None:
        logging.info(f"Found scorecard class for identifier '{scorecard_identifier}' (direct registry lookup)")
        return scorecard_class
    
    logging.error(f"Scorecard with identifier '{scorecard_identifier}' not found in registry.")
    raise ValueError(f"Scorecard with identifier '{scorecard_identifier}' not found in registry.")

def create_score_input(sample_row, item_id, scorecard_class, score_name):
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
        if 'item_id' not in metadata:
            metadata['item_id'] = str(item_id)
        return score_input_class(text=text, metadata=metadata)
    else:
        metadata = {"item_id": str(item_id)}
        return score_input_class(text="", metadata=metadata)