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
        super().__init__(*args, **kwargs)
        self.prompts = {}
        self.system_message = None
        self.user_message = None
    
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
        
        return await super()._async_run()


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
        
        # Get score class
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
        
        # Load and process data
        logger.info("Loading and processing data")
        score_instance.load_data(data=score_config['data'])
        score_instance.process_data()
        
        # Get samples and ensure form_ids are preserved
        logger.info("Converting dataframe to samples")
        df = score_instance.dataframe
        
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
                df['form_id'] = df.index.astype(str)  # Convert index to string for consistency
        
        # Convert to records while preserving form_id and ensuring proper structure
        df_dict = df.to_dict('records')
        samples = []
        for record in df_dict:
            # Ensure form_id is included in both top level and columns
            form_id = record.get('form_id', '')
            metadata = record.get('metadata', {})
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except:
                    metadata = {}
            
            # Create properly structured sample with evaluation fields at top level
            sample = {
                'text': record.get('text', ''),
                'content_id': record.get('content_id', ''),
                'form_id': form_id,
                'Session ID': record.get('Session ID', ''),
                'columns': {
                    'form_id': form_id,
                    'metadata': metadata
                }
            }
            
            # Add any additional columns that might be needed for evaluation
            for key, value in record.items():
                if key not in ['text', 'content_id', 'form_id', 'metadata', 'Session ID']:
                    # Keep label fields at top level for evaluation
                    if key.endswith('_label') or key in score_config.get('scores', [{'name': score_name}])[0]['name']:
                        sample[key] = value
                    # Everything else goes in columns
                    sample['columns'][key] = value
            
            samples.append(sample)
            
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
                # Get system and user messages, replacing escaped newlines with actual newlines
                system_message = iteration_result.metadata.get("system_message", "").replace('\\n', '\n')
                user_message = iteration_result.metadata.get("user_message", "").replace('\\n', '\n')
                
                # Create YAML content manually to ensure proper formatting
                yaml_content = f"""accuracy: {current_accuracy}
iteration: {iteration_result.iteration}
prompts:
  {score_name}:
    system_message: |
{os.linesep.join(f'      {line}' for line in system_message.splitlines())}
    user_message: |
{os.linesep.join(f'      {line}' for line in user_message.splitlines())}
score_name: {score_name}
scorecard_name: {scorecard_name}
"""
                
                # Write the YAML content directly
                best_accuracy_file = os.path.join(best_accuracy_dir, "best_accuracy.yaml")
                with open(best_accuracy_file, 'w') as f:
                    f.write(yaml_content)
                    
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