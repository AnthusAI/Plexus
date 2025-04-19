"""
Evaluation node for running prompt evaluations and collecting mismatches.
"""
import os
import json
import logging
import random
import asyncio
import mlflow
import importlib
import copy
from typing import Dict, Any, Callable, List
from datetime import datetime, timezone
from decimal import Decimal

from plexus.Evaluation import AccuracyEvaluation
from plexus.apos.nodes.base import APOSNode
from plexus.apos.graph_state import APOSState
from plexus.apos.models import (
    IterationResult,
    OptimizationStatus
)

logger = logging.getLogger('plexus.apos.nodes.evaluation')


class ExtendedAccuracyEvaluation(AccuracyEvaluation):
    """Extended AccuracyEvaluation with prompt management."""
    
    def __init__(self, *args, **kwargs):
        # Make sure override_folder is provided with a default value of None if not in kwargs
        if 'override_folder' not in kwargs:
            kwargs['override_folder'] = None
        # Ensure account_id is set if not provided
        if 'account_id' not in kwargs and 'account_key' in kwargs:
            kwargs['account_id'] = kwargs['account_key']
        super().__init__(*args, **kwargs)
        self.prompts = {}
        self.system_message = None
        self.user_message = None
        self.experiment_id = None  # Initialize experiment_id attribute
    
    def set_prompts(self, prompts: Dict[str, Dict[str, str]]) -> None:
        """
        Set prompts for evaluation.
        
        Args:
            prompts: Dictionary mapping score names to their prompts
                    Each prompt dict should have 'system_message' and 'user_message'
        """
        logger.info("Setting prompts in ExtendedAccuracyEvaluation")
        logger.info(f"Current system message length: {len(self.system_message) if self.system_message else 0}")
        logger.info(f"Current user message length: {len(self.user_message) if self.user_message else 0}")
        
        self.prompts = prompts
        
        # Set the first prompt's messages as the instance's messages
        if prompts:
            first_score = next(iter(prompts.values()))
            self.system_message = first_score.get('system_message')
            self.user_message = first_score.get('user_message')
            logger.info(f"New system message length: {len(self.system_message) if self.system_message else 0}")
            logger.info(f"New user message length: {len(self.user_message) if self.user_message else 0}")
            
        logger.info(f"Set prompts for scores: {list(prompts.keys())}")
    
    async def _async_run(self) -> Dict[str, Any]:
        """Override to use the set prompts."""
        # Initialize started_at for elapsed time calculations
        self.started_at = datetime.now(timezone.utc)
        
        # Set up experiment_id from evaluation_id like parent class does
        if hasattr(self, 'evaluation_id') and self.evaluation_id:
            self.experiment_id = self.evaluation_id
            logger.info(f"Using existing evaluation ID: {self.experiment_id}")
        else:
            # If no evaluation_id, create a new one
            import uuid
            self.experiment_id = str(uuid.uuid4())
            logger.info(f"Generated new evaluation ID: {self.experiment_id}")
        
        # Make sure we have the crucial fields
        self.account_id = getattr(self, 'account_id', 'call-criteria')
        
        # Import needed modules but catch import errors gracefully
        try:
            from plexus.dashboard.api.client import PlexusDashboardClient
            from plexus.dashboard.api.models.evaluation import Evaluation as DashboardEvaluation
            
            # Use for_account method like parent class
            account_key = getattr(self, 'account_key', 'call-criteria')
            self.dashboard_client = PlexusDashboardClient.for_account(account_key)
            logger.info(f"Initialized dashboard client for account: {account_key}")
            
            # Create evaluation record using the high-level API
            try:
                # Add the required Float fields
                now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
                
                # Use the Evaluation model's create method with required fields
                DashboardEvaluation.create(
                    client=self.dashboard_client,
                    type='ACCURACY',
                    accountId=self.account_id,
                    id=self.experiment_id, 
                    status='RUNNING',
                    scorecardId=getattr(self, 'scorecard_id', None),
                    scoreId=getattr(self, 'score_id', None),
                    taskId=getattr(self, 'task_id', None),
                    accuracy=0.0,  # Required non-null Float
                    totalItems=self.number_of_texts_to_sample,  # Required non-null Integer
                    processedItems=0,  # Required non-null Integer
                    startedAt=now  # Required timestamp
                )
                logger.info(f"Created evaluation record with ID: {self.experiment_id}")
            except Exception as create_error:
                logger.error(f"Error creating evaluation record: {create_error}")
                
        except ImportError as e:
            logger.warning(f"Could not import dashboard modules: {e}")
            self.dashboard_client = None
        except Exception as e:
            logger.error(f"Dashboard client initialization error: {e}")
            self.dashboard_client = None
        
        if not self.prompts:
            raise ValueError("No prompts set for evaluation")
        
        # Use the prompts in the evaluation
        for score_name, prompt in self.prompts.items():
            # If subset_of_score_names is None or empty, apply to all scores
            if not self.subset_of_score_names or score_name in self.subset_of_score_names:
                # Find the score in the scorecard's scores
                score_config = next((score for score in self.scorecard.scores 
                                 if score['name'] == score_name), None)
                if score_config:
                    # Set the prompts directly in the score config
                    score_config['system_message'] = prompt['system_message']
                    score_config['user_message'] = prompt['user_message']
                    logger.info(f"Set prompts for score: {score_name}")
                else:
                    logger.warning(f"Score {score_name} not found in scorecard")
        
        try:
            # Create a dummy tracker class if needed
            class DummyTracker:
                def __init__(self):
                    self.current_stage = type('obj', (object,), {'status_message': ''})
                
                def update(self, current_items=0):
                    pass
            
            # Import pandas for dataframe handling
            import pandas as pd
            
            # Load the labeled samples
            if self.labeled_samples:
                df = pd.DataFrame(self.labeled_samples)
            else:
                df = pd.read_csv(self.labeled_samples_filename)

            # Adjust the sample size if necessary
            self.number_of_texts_to_sample = min(len(df), self.requested_sample_size)
            logger.info(f"Adjusted sample size from {self.requested_sample_size} to {self.number_of_texts_to_sample} based on available data")

            # Sample rows based on the sampling method
            if self.sampling_method == 'random':
                selected_sample_rows = df.sample(n=self.number_of_texts_to_sample, random_state=self.random_seed)
            elif self.sampling_method == 'sequential':
                selected_sample_rows = df.head(self.number_of_texts_to_sample)
            else:
                selected_sample_rows = df

            # Create a dummy tracker
            tracker = DummyTracker()

            # Process all scores concurrently
            score_tasks = []
            for score_name in self.score_names():
                task = asyncio.create_task(self.score_all_texts_for_score(selected_sample_rows, score_name, tracker))
                score_tasks.append(task)

            all_results = await asyncio.gather(*score_tasks)
            self.all_results = [result for score_results in all_results for result in score_results if not isinstance(result, Exception)]

            # Calculate metrics from the results
            metrics = self.calculate_metrics(self.all_results)

            # Collect mismatches from results - similar to parent class approach
            self.mismatches = []  # Clear any existing mismatches
            self.total_correct = 0
            self.total_questions = 0
            
            # Count correct answers and collect mismatches
            for result in self.all_results:
                form_id = result.get('form_id', '')
                for question in self.score_names():
                    score_result = next((r for r in result['results'].values() 
                                       if hasattr(r, 'parameters') and r.parameters.name == question), None)
                    if not score_result:
                        continue
                        
                    score_value = str(score_result.value).lower() if score_result else None
                    human_label = str(score_result.metadata.get('human_label', '')).lower() if hasattr(score_result, 'metadata') else None
                    
                    # Count correct vs incorrect
                    is_match = 1 if hasattr(score_result, 'metadata') and score_result.metadata.get('correct', False) else 0
                    self.total_correct += is_match
                    self.total_questions += 1
                    
                    # Collect mismatches (incorrect answers)
                    if not is_match and len(self.mismatches) < self.max_mismatches_to_report:
                        mismatch_data = {
                            'form_id': form_id,
                            'question': question,
                            'predicted': score_value,
                            'ground_truth': human_label,
                            'explanation': score_result.metadata.get('explanation', '') if hasattr(score_result, 'metadata') else '',
                            'transcript': score_result.metadata.get('text', '') if hasattr(score_result, 'metadata') else ''
                        }
                        # Only include if we have either transcript or explanation
                        if mismatch_data['transcript'] or mismatch_data['explanation']:
                            self.mismatches.append(mismatch_data)
            
            logger.info(f"Collected {len(self.mismatches)} mismatches from evaluation")

            # Update dashboard with final metrics 
            if self.dashboard_client and self.experiment_id:
                try:
                    from plexus.dashboard.api.models.evaluation import Evaluation as DashboardEvaluation
                    
                    # Get the evaluation instance
                    eval_instance = DashboardEvaluation.get_by_id(self.experiment_id, self.dashboard_client)
                    
                    # Update with proper metrics
                    eval_instance.update(
                        status='COMPLETED',
                        accuracy=metrics.get('accuracy', 0) * 100,
                        totalItems=self.number_of_texts_to_sample,
                        processedItems=self.number_of_texts_to_sample
                    )
                    logger.info(f"Updated dashboard evaluation {self.experiment_id} with metrics")
                except Exception as e:
                    logger.error(f"Error updating dashboard evaluation: {e}")

            if hasattr(self, 'progress_callback') and self.progress_callback:
                self.progress_callback(self.number_of_texts_to_sample)

            return metrics
        except Exception as e:
            logger.error(f"Error in _async_run: {e}", exc_info=True)
            raise e


class EvaluationNode(APOSNode):
    """Node for evaluating prompts and collecting mismatches."""
    
    def __init__(self, config):
        """Initialize the evaluation node."""
        # Initialize APOSNode first
        APOSNode.__init__(self, config)
        
        # Initialize evaluation instance as None - will be created when needed
        self.evaluation = None
        
        # Call setup
        self._setup_node()
    
    def _setup_node(self) -> None:
        """Set up evaluation components."""
        self.evaluation_cache = {}  # Cache evaluation results
        self.iteration_dir = None
        self.current_iteration = 0
        self.total_correct = 0
        self.total_questions = 0
        self.mismatches = []
        self.evaluation = None
        
        # Initialize base evaluation state
        self.all_results = []
        self.results_by_score = {}
        self.processed_items_by_score = {}
        self.processed_items = 0
        
        # Sample management
        self.all_labeled_samples = None
        self.evaluation_samples = None
        self.labeled_samples = None
        self.labeled_samples_filename = None
        
        # Queue and task management
        self.results_queue = asyncio.Queue()
        self.metrics_tasks = {}
        self.completed_scores = set()
        
        # Override management
        self.override_folder = None
        self.override_data = {}
        
        # History tracking
        self.history_dir = "optimization_history"
        
        # Ensure persistence directory exists
        os.makedirs(self.config.persistence_path, exist_ok=True)
        
        logger.info("Initialized evaluation node")
    
    def _convert_mismatches(self, raw_mismatches: List[Any]) -> List[Dict[str, Any]]:
        """Convert raw mismatches to the format expected by APOSState."""
        converted_mismatches = []
        for m in raw_mismatches:
            # Initialize metadata
            metadata = {}
            
            # Handle both dictionary and object formats
            if isinstance(m, dict):
                # Get form_id from direct attribute or metadata
                form_id = m.get('form_id')
                if not form_id:
                    # Try to get form_id from metadata
                    raw_metadata = m.get('metadata', {})
                    if isinstance(raw_metadata, str):
                        try:
                            metadata = json.loads(raw_metadata)
                        except:
                            metadata = {}
                    else:
                        metadata = raw_metadata
                    form_id = metadata.get('form_id', '')
                
                mismatch = {
                    'form_id': form_id,
                    'question_name': m.get('question') or m.get('question_name') or '',
                    'model_answer': m.get('predicted') or m.get('model_answer') or '',
                    'transcript_text': m.get('transcript', ''),
                    'original_explanation': m.get('explanation', ''),
                    'ground_truth': m.get('ground_truth') or '',
                    'metadata': metadata
                }
            else:
                # Get form_id from direct attribute or metadata
                form_id = getattr(m, 'form_id', None)
                if not form_id:
                    # Try to get form_id from metadata
                    raw_metadata = getattr(m, 'metadata', {})
                    if isinstance(raw_metadata, str):
                        try:
                            metadata = json.loads(raw_metadata)
                        except:
                            metadata = {}
                    else:
                        metadata = raw_metadata
                    form_id = metadata.get('form_id', '')
                
                mismatch = {
                    'form_id': form_id,
                    'question_name': getattr(m, 'question_name', '') or '',
                    'model_answer': getattr(m, 'model_answer', '') or getattr(m, 'predicted', '') or '',
                    'transcript_text': getattr(m, 'transcript_text', '') or getattr(m, 'transcript', ''),
                    'original_explanation': getattr(m, 'original_explanation', '') or getattr(m, 'explanation', ''),
                    'ground_truth': getattr(m, 'ground_truth', '') or '',
                    'metadata': metadata
                }
            converted_mismatches.append(mismatch)
        return converted_mismatches

    def _create_evaluation(
        self,
        scorecard: Any,
        score_name: str,
        system_message: str,
        user_message: str
    ) -> None:
        """Set up evaluation with current state."""
        # Get score config and update with new prompts
        score_config = next((score for score in scorecard.scores 
                           if score['name'] == score_name), None)
        if not score_config:
            raise ValueError(f"Score '{score_name}' not found in scorecard.")
        
        logger.info(f"Found score config for {score_name}")
        
        # Create a deep copy of the score config to avoid modifying the original
        score_config = copy.deepcopy(score_config)
        
        # Update the prompts in the score config
        if 'graph' in score_config and score_config['graph']:
            # Update first node's prompts
            score_config['graph'][0]['system_message'] = system_message
            score_config['graph'][0]['user_message'] = user_message
            logger.info("Updated prompts in score graph configuration")
        else:
            # Update direct score prompts
            score_config['system_message'] = system_message
            score_config['user_message'] = user_message
            logger.info("Updated prompts in score configuration")
        
        # Get score class and create instance
        score_class_name = score_config['class']
        score_module_path = f'plexus.scores.{score_class_name}'
        logger.info(f"Loading score class {score_class_name} from {score_module_path}")
        
        score_module = importlib.import_module(score_module_path)
        score_class = getattr(score_module, score_class_name)
        
        # Create score instance with updated config
        score_config['scorecard_name'] = scorecard.name
        score_config['score_name'] = score_name
        logger.info("Creating score instance with updated prompts")
        score_instance = score_class(**score_config)
        
        # Get label field information
        label_score_name = score_config.get('label_score_name', score_name)
        label_field = score_config.get('label_field', None)
        
        logger.info(f"Using label_score_name: {label_score_name}, label_field: {label_field}")
        
        # Load and process data
        logger.info("Loading and processing data")
        score_instance.load_data(data=score_config['data'])
        score_instance.process_data()
        
        # Get samples and ensure form_ids are preserved
        logger.info("Converting dataframe to samples")
        df = score_instance.dataframe
        
        # Log the dataframe columns for debugging
        logger.info(f"DataFrame columns: {df.columns.tolist()}")
        
        # Ensure form_id is in the dataframe
        if 'form_id' not in df.columns:
            # Try to get form_id from metadata if it exists
            if 'metadata' in df.columns:
                def extract_form_id(metadata):
                    if isinstance(metadata, str):
                        try:
                            metadata = json.loads(metadata)
                        except:
                            return None
                    return metadata.get('form_id')
                df['form_id'] = df['metadata'].apply(extract_form_id)
            
            # If still no form_id, use f_id if available
            if 'form_id' not in df.columns and 'f_id' in df.columns:
                df['form_id'] = df['f_id']
            
            # If still no form_id, use index as last resort
            if 'form_id' not in df.columns:
                logger.warning("No form_id found in data, using index as form_id")
                df['form_id'] = df.index.astype(str)
        
        # Convert to records while preserving ALL columns
        df_dict = df.to_dict('records')
        samples = []
        for record in df_dict:
            # First, create the base sample structure
            sample = {
                'text': record.get('text', ''),
                'content_id': record.get('content_id', ''),
                'form_id': record.get('form_id', ''),
                'Session ID': record.get('Session ID', ''),
                'columns': {}
            }
            
            # Process metadata
            metadata = record.get('metadata', {})
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except:
                    metadata = {}
            sample['columns']['metadata'] = metadata
            
            # Add form_id to columns
            sample['columns']['form_id'] = sample['form_id']
            
            # Handle the label field specifically
            label_value = None
            combined_field = None  # Initialize outside the if block
            
            # Try different possible formats for the label field
            if label_field:
                combined_field = f"{label_score_name} {label_field}"  # e.g., "Non-Qualified Reason comment"
                if combined_field in record:
                    label_value = record[combined_field]
                    logger.info(f"Found label in combined field: {combined_field}")
                elif label_field in record:
                    label_value = record[label_field]
                    logger.info(f"Found label in direct field: {label_field}")
            
            # If we found a label value, add it in all necessary formats
            if label_value is not None:
                # Add as the score name for direct access
                sample[label_score_name] = label_value
                # Add as standard label format
                sample[f"{label_score_name}_label"] = label_value
                # Add to columns
                sample['columns'][f"{label_score_name}_label"] = label_value
                sample['columns'][label_score_name] = label_value
                logger.info(f"Added label value: {label_value} for {label_score_name}")
            
            # Copy ALL remaining fields to both top level and columns
            for key, value in record.items():
                if key not in ['text', 'content_id', 'form_id', 'metadata', 'Session ID']:
                    # Keep certain fields at top level
                    if (key.endswith('_label') or 
                        key == label_score_name or 
                        (combined_field and key == combined_field)):  # Check if combined_field exists
                        sample[key] = value
                    # Add everything to columns
                    sample['columns'][key] = value
            
            samples.append(sample)
            
            # Debug log for each sample
            logger.info(f"Created sample with keys: {list(sample.keys())}")
            logger.info(f"Sample columns: {list(sample['columns'].keys())}")
        
        logger.info(f"Got {len(samples)} total samples with columns: {list(samples[0].keys()) if samples else []}")
        
        # Store all samples and create fixed evaluation set if needed
        if not self.all_labeled_samples:
            self.all_labeled_samples = samples
            
            # Create evaluation samples if we have a sample size
            if samples and self.config.analysis.samples_per_iteration:
                random.seed(42)  # Use fixed seed for reproducibility
                sample_size = min(len(samples), self.config.analysis.samples_per_iteration)
                self.evaluation_samples = random.sample(samples, sample_size)
                random.seed()  # Reset seed
                logger.info(f"Using {len(self.evaluation_samples)} samples for evaluation")
            else:
                self.evaluation_samples = samples
                logger.info(f"Using all {len(samples)} samples for evaluation")

        # Create ExtendedAccuracyEvaluation instance with updated scorecard
        logger.info("Creating evaluation instance with updated prompts")
        self.evaluation = ExtendedAccuracyEvaluation(
            scorecard=scorecard,
            scorecard_name=scorecard.name,
            labeled_samples=self.evaluation_samples,
            number_of_texts_to_sample=len(self.evaluation_samples),
            account_key='call-criteria',
            account_id='call-criteria',  # Set account_id to match account_key
            subset_of_score_names=[score_name],
            max_mismatches_to_report=self.config.optimization.max_mismatches_to_report
        )
        
        # Set prompts in evaluation instance
        logger.info(f"Setting prompts for {score_name}")
        logger.info(f"System message: {system_message[:100]}...")
        logger.info(f"User message: {user_message[:100]}...")
        self.evaluation.set_prompts({
            score_name: {
                "system_message": system_message,
                "user_message": user_message
            }
        })
        
        # Also update the prompts in the scorecard's score configuration
        for score in scorecard.scores:
            if score['name'] == score_name:
                if 'graph' in score and score['graph']:
                    score['graph'][0]['system_message'] = system_message
                    score['graph'][0]['user_message'] = user_message
                else:
                    score['system_message'] = system_message
                    score['user_message'] = user_message
                logger.info("Updated prompts in scorecard configuration")
                break
        
        logger.info("Evaluation setup complete")
                    
    def _save_iteration_results(self, iteration_result: IterationResult) -> None:
        """Save all iteration results to disk in a consistent format."""
        try:
            # Get scorecard and score names from metadata
            scorecard_name = iteration_result.metadata.get("scorecard_name")
            score_name = iteration_result.metadata.get("score_name")
            
            if not scorecard_name or not score_name:
                logger.error("Missing scorecard_name or score_name in metadata")
                return
                
            # Create directory structure
            results_dir = os.path.join(
                self.history_dir,
                scorecard_name,
                score_name,
                f"iteration_{self.current_iteration}"
            )
            os.makedirs(results_dir, exist_ok=True)
            self.iteration_dir = results_dir

            # Save current prompts
            prompts = {
                "system_message": iteration_result.metadata["system_message"],
                "user_message": iteration_result.metadata["user_message"]
            }
            with open(os.path.join(results_dir, "current_prompts.json"), 'w') as f:
                json.dump(prompts, f, indent=2)
            
            # Convert Decimal values to float in metrics
            metrics = {}
            for key, value in iteration_result.metrics.items():
                if isinstance(value, Decimal):
                    metrics[key] = float(value)
                else:
                    metrics[key] = value
            
            # Save main result
            result = {
                "iteration": iteration_result.iteration,
                "accuracy": iteration_result.accuracy,
                "metrics": metrics,
                "metadata": {
                    **iteration_result.metadata,
                    "started_at": iteration_result.metadata.get("started_at"),
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
            }
            with open(os.path.join(results_dir, "result.json"), 'w') as f:
                json.dump(result, f, indent=2)
            
            logger.info(f"Saved all iteration results to {results_dir}")
                
        except Exception as e:
            logger.error(f"Error saving iteration results: {e}")

    def _save_high_accuracy_mark(self, iteration_result: IterationResult, state: APOSState) -> None:
        """Save high accuracy mark if this iteration achieved a new best accuracy."""
        try:
            # Get scorecard and score names from metadata
            scorecard_name = iteration_result.metadata.get("scorecard_name")
            score_name = iteration_result.metadata.get("score_name")
            
            if not scorecard_name or not score_name:
                logger.error("Missing scorecard_name or score_name in metadata")
                return
                
            # Create directory structure
            best_accuracy_dir = os.path.join(
                self.history_dir,
                scorecard_name,
                score_name
            )
            os.makedirs(best_accuracy_dir, exist_ok=True)
            
            # Get current accuracy and previous best accuracy
            current_accuracy = iteration_result.accuracy
            previous_best_accuracy = iteration_result.metadata.get("previous_best_accuracy", 0.0)
            
            # Only save to disk if this was indeed better than the previous best accuracy
            if current_accuracy > previous_best_accuracy:
                logger.info(f"New best accuracy achieved: {current_accuracy:.3f} (previous: {previous_best_accuracy:.3f})")
                
                # Get system and user messages, ensuring proper line breaks
                system_message = iteration_result.metadata.get("system_message", "")
                user_message = iteration_result.metadata.get("user_message", "")
                
                # Make sure line breaks are preserved
                system_lines = []
                for line in system_message.splitlines():
                    system_lines.append(f"      {line}")
                
                user_lines = []
                for line in user_message.splitlines():
                    user_lines.append(f"      {line}")
                
                # Create YAML content with proper indentation and line breaks
                yaml_content = [
                    f"accuracy: {current_accuracy}",
                    f"iteration: {iteration_result.iteration}",
                    "prompts:",
                    f"  {score_name}:",
                    "    system_message: |",
                ]
                yaml_content.extend(system_lines)
                yaml_content.append("    user_message: |")
                yaml_content.extend(user_lines)
                yaml_content.append(f"score_name: {score_name}")
                yaml_content.append(f"scorecard_name: {scorecard_name}")
                
                # Join with proper line endings and write to file
                best_accuracy_file = os.path.join(best_accuracy_dir, "best_accuracy.yaml")
                with open(best_accuracy_file, 'w', newline='\n') as f:
                    f.write('\n'.join(yaml_content))
                    
                logger.info(f"Saved new best accuracy mark to {best_accuracy_file}")
                
        except Exception as e:
            logger.error(f"Error saving high accuracy mark: {e}")
        
    async def cleanup(self) -> None:
        """Clean up resources."""
        try:
            # End MLFlow run if active - only if evaluation exists and has experiment_id
            if self.evaluation and hasattr(self.evaluation, 'experiment_id') and self.evaluation.experiment_id:
                try:
                    mlflow.end_run()
                except:
                    pass
            
            # Clear queues
            while not self.results_queue.empty():
                try:
                    await self.results_queue.get_nowait()
                except:
                    pass
            
            # Cancel any pending tasks
            for task in self.metrics_tasks.values():
                try:
                    task.cancel()
                except:
                    pass
                    
            logger.info("Cleaned up evaluation resources")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    async def evaluate_prompts(self, state: APOSState) -> Dict[str, Any]:
        """Run evaluation and collect mismatches."""
        try:
            # Get scorecard from metadata
            scorecard = state.metadata.get("scorecard")
            if not scorecard:
                raise ValueError("No scorecard found in state metadata")
            
            # Set scorecard name and score name in metadata
            state.metadata["scorecard_name"] = scorecard.name
            state.metadata["score_name"] = state.score_name
            logger.info(f"Set metadata - scorecard_name: {scorecard.name}, score_name: {state.score_name}")
            
            # Get current iteration from state
            self.current_iteration = state.current_iteration
            
            # Create iteration directory with new structure
            iteration_dir = os.path.join(
                "optimization_history",
                scorecard.name,
                state.score_name,
                f"iteration_{self.current_iteration}"
            )
            os.makedirs(iteration_dir, exist_ok=True)
            state.metadata["iteration_dir"] = iteration_dir
            logger.info(f"Created iteration directory: {iteration_dir}")

            # Store original prompts for comparison
            original_system = state.system_message
            original_user = state.user_message

            # Apply any optimized prompts from previous iteration
            if state.optimization_result:
                logger.info("Found optimization result from previous iteration")
                logger.info(f"Original system message length: {len(original_system)}")
                logger.info(f"Original user message length: {len(original_user)}")
                
                # Get prompt changes
                prompt_changes = state.optimization_result
                if hasattr(state.optimization_result, 'prompt_changes'):
                    prompt_changes = state.optimization_result.prompt_changes
                
                # Apply each change
                for change in prompt_changes:
                    if isinstance(change, dict):
                        component = change.get('component')
                        new_text = change.get('new_text')
                    else:
                        component = change.component
                        new_text = change.new_text

                    if component == "system_message" and new_text and new_text != original_system:
                        logger.info("Applying system message change:")
                        logger.info(f"Old length: {len(original_system)}")
                        logger.info(f"New length: {len(new_text)}")
                        state.system_message = new_text
                    elif component == "user_message" and new_text and new_text != original_user:
                        logger.info("Applying user message change:")
                        logger.info(f"Old length: {len(original_user)}")
                        logger.info(f"New length: {len(new_text)}")
                        state.user_message = new_text

                # Log final prompt state
                logger.info("Final prompt state after changes:")
                logger.info(f"System message length: {len(state.system_message)}")
                logger.info(f"User message length: {len(state.user_message)}")
                logger.info(f"System message changed: {original_system != state.system_message}")
                logger.info(f"User message changed: {original_user != state.user_message}")

            # Create evaluation instance with current prompts
            self._create_evaluation(
                scorecard=scorecard,
                score_name=state.score_name,
                system_message=state.system_message,
                user_message=state.user_message
            )
            
            # Set prompts in evaluation instance
            self.evaluation.set_prompts({
                state.score_name: {
                    'system_message': state.system_message,
                    'user_message': state.user_message
                }
            })
            
            # Run evaluation
            logger.info(f"Running evaluation for {state.score_name}")
            logger.info(f"Using system message length: {len(state.system_message)}")
            logger.info(f"Using user message length: {len(state.user_message)}")
            await self.evaluation._async_run()
            
            # Get evaluation results
            accuracy = self.evaluation.total_correct / self.evaluation.total_questions if self.evaluation.total_questions > 0 else 0
            
            # Get accumulated costs from the scorecard
            expenses = self.evaluation.scorecard.get_accumulated_costs()
            
            # Calculate cost per call from total cost and number of calls
            cost_per_call = expenses['total_cost'] / expenses['llm_calls'] if expenses['llm_calls'] > 0 else Decimal('0')
            
            # Store previous best accuracy for comparison
            previous_best_accuracy = state.best_accuracy
            
            # Get mismatches from evaluation and convert them
            raw_mismatches = self.evaluation.mismatches or []
            converted_mismatches = self._convert_mismatches(raw_mismatches)
            logger.info(f"Found {len(converted_mismatches)} mismatches")
            
            # Create iteration result with converted mismatches and costs
            iteration_result = IterationResult(
                iteration=state.current_iteration,
                accuracy=accuracy,
                mismatches=converted_mismatches,
                prompt_changes=state.optimization_result if state.optimization_result else [],
                metrics={
                    "accuracy": accuracy,
                    "total_cost": expenses['total_cost'],
                    "cost_per_call": float(cost_per_call),  # Convert Decimal to float for serialization
                    "total_calls": expenses['llm_calls'],
                    "input_cost": expenses['input_cost'],
                    "output_cost": expenses['output_cost'],
                    "prompt_tokens": expenses['prompt_tokens'],
                    "completion_tokens": expenses['completion_tokens'],
                    "cached_tokens": expenses['cached_tokens']
                },
                metadata={
                    "system_message": state.system_message,
                    "user_message": state.user_message,
                    "started_at": self.evaluation.started_at.isoformat() if self.evaluation.started_at else None,
                    "experiment_id": self.evaluation.experiment_id,
                    "iteration_dir": iteration_dir,
                    "scorecard_name": scorecard.name,
                    "score_name": state.score_name,
                    "previous_best_accuracy": previous_best_accuracy  # Store for comparison
                }
            )
            
            # Add to history and update state's best accuracy
            state.add_iteration_result(iteration_result)
            
            # Save initial results
            self._save_iteration_results(iteration_result)
            
            # Save high accuracy mark if needed
            self._save_high_accuracy_mark(iteration_result, state)
            
            # Update state with results
            state.current_accuracy = accuracy
            state.mismatches = converted_mismatches
            state.metadata["iteration_dir"] = iteration_dir
            
            # Return just the state dict
            return state.dict()
            
        except Exception as e:
            logger.error(f"Error in evaluation node: {e}")
            state.status = OptimizationStatus.FAILED
            state.metadata["error"] = str(e)
            return state.dict()
        finally:
            # Clean up resources
            await self.cleanup()
            logger.info("Cleaned up evaluation resources")

    def get_node_handler(self) -> Callable[[APOSState], Dict[str, Any]]:
        """Get the handler function for this node."""
        return self.evaluate_prompts 