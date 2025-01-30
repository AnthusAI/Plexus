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
from typing import Dict, Any, Callable, Optional, List, Tuple
from datetime import datetime, timezone
from pathlib import Path
from tenacity import retry, stop_after_attempt, wait_exponential

from plexus.Evaluation import AccuracyEvaluation
from plexus.apos.nodes.base import APOSNode
from plexus.apos.graph_state import APOSState
from plexus.apos.models import (
    IterationResult,
    OptimizationStatus,
    SynthesisResult,
    EvaluationResult,
    PromptChange
)
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.dashboard.api.models.account import Account
from plexus.dashboard.api.models.scorecard import Scorecard as DashboardScorecard
from plexus.dashboard.api.models.evaluation import Evaluation as DashboardEvaluation

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
        self.started_at = None
        self.experiment_id = None
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
        
        # Experiment tracking
        self.scorecard_id = None
        self.score_id = None
        self.account_id = None
        
        # Initialize dashboard client
        self._setup_dashboard_client()
        
        # Ensure persistence directory exists
        os.makedirs(self.config.persistence_path, exist_ok=True)
        
        logger.info("Initialized evaluation node with caching and dashboard integration")
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _setup_dashboard_client(self) -> None:
        """Initialize the Plexus Dashboard client."""
        try:
            logger.info("Initializing Plexus Dashboard client...")
            self.dashboard_client = PlexusDashboardClient.for_account('call-criteria')
            
            # Look up account
            logger.info("Looking up account")
            account = Account.get_by_key('call-criteria', self.dashboard_client)
            logger.info(f"Found account: {account.name} ({account.id})")
            self.account_id = account.id
            
        except Exception as e:
            logger.error(f"Failed to initialize dashboard client: {str(e)}")
            self.dashboard_client = None
            self.experiment_id = None
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _setup_scorecard(self, scorecard_name: str, score_name: Optional[str] = None) -> None:
        """Set up scorecard and score IDs."""
        if not self.dashboard_client:
            return
            
        try:
            # Look up scorecard using available identifiers
            logger.info(f"Looking up scorecard: {scorecard_name}")
            try:
                # Try by key first
                dashboard_scorecard = DashboardScorecard.get_by_key(scorecard_name, self.dashboard_client)
                logger.info("Found scorecard by key")
            except:
                try:
                    # Try by ID next
                    dashboard_scorecard = DashboardScorecard.get_by_id(scorecard_name, self.dashboard_client)
                    logger.info("Found scorecard by ID")
                except:
                    # Finally try by name
                    dashboard_scorecard = DashboardScorecard.get_by_name(scorecard_name, self.dashboard_client)
                    logger.info("Found scorecard by name")
                    
            logger.info(f"Found scorecard: {dashboard_scorecard.name} ({dashboard_scorecard.id})")
            self.scorecard_id = dashboard_scorecard.id
            
            # Look up score if specified
            if score_name:
                logger.info(f"Looking up score: {score_name}")
                query = """
                query GetScoreFromScorecard($scorecardId: ID!, $name: String!) {
                    getScorecard(id: $scorecardId) {
                        sections {
                            items {
                                scores(filter: {name: {eq: $name}}) {
                                    items {
                                        id
                                        name
                                    }
                                }
                            }
                        }
                    }
                }
                """
                variables = {
                    "scorecardId": dashboard_scorecard.id,
                    "name": score_name
                }
                result = self.dashboard_client.execute(query, variables)
                
                # Find matching score
                scorecard_data = result.get('getScorecard', {})
                sections = scorecard_data.get('sections', {}).get('items', [])
                
                for section in sections:
                    scores = section.get('scores', {}).get('items', [])
                    if scores:
                        self.score_id = scores[0]['id']
                        logger.info(f"Found score: {scores[0]['name']} ({self.score_id})")
                        break
                        
        except Exception as e:
            logger.error(f"Error setting up scorecard: {e}")
        
    def _create_evaluation(
        self,
        scorecard: Any,
        score_name: str,
        system_message: str,
        user_message: str
    ) -> None:
        """Set up evaluation with current state."""
        # Set up scorecard if needed
        if not self.scorecard_id:
            self._setup_scorecard(scorecard.name, score_name)
        
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
        
        # Get samples
        logger.info("Converting dataframe to samples")
        samples = score_instance.dataframe.to_dict('records')
        logger.info(f"Got {len(samples)} total samples")
        
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
            score_id=self.score_id,
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
            
            # Save main result
            result = {
                "iteration": iteration_result.iteration,
                "accuracy": iteration_result.accuracy,
                "metrics": iteration_result.metrics,
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
        
    def _setup_mlflow_run(self, scorecard_name: str) -> None:
        """Set up MLFlow run for tracking."""
        try:
            # End any existing run
            try:
                mlflow.end_run()
            except:
                pass
                
            mlflow.set_experiment(f"apos_{scorecard_name}")
            run = mlflow.start_run(nested=True)  # Allow nested runs
            self.experiment_id = run.info.run_id
            logger.info(f"Started MLFlow run: {self.experiment_id}")
        except Exception as e:
            logger.error(f"Error setting up MLFlow run: {e}")
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _create_dashboard_evaluation(self) -> None:
        """Create a dashboard evaluation record."""
        if not self.dashboard_client:
            return
            
        try:
            started_at = datetime.now(timezone.utc)
            experiment_params = {
                "type": "accuracy",
                "accountId": self.account_id,
                "scorecardId": self.scorecard_id,
                "scoreId": self.score_id,
                "status": "RUNNING",
                "accuracy": 0.0,
                "createdAt": started_at.isoformat().replace('+00:00', 'Z'),
                "updatedAt": started_at.isoformat().replace('+00:00', 'Z'),
                "totalItems": len(self.evaluation_samples) if self.evaluation_samples else 0,
                "processedItems": 0,
                "parameters": json.dumps({
                    "sampling_method": "random",
                    "sample_size": self.config.analysis.samples_per_iteration,
                    "iteration": self.current_iteration
                }),
                "startedAt": started_at.isoformat().replace('+00:00', 'Z'),
                "estimatedRemainingSeconds": len(self.evaluation_samples) if self.evaluation_samples else 0
            }
            
            response = DashboardEvaluation.create(
                client=self.dashboard_client,
                **experiment_params
            )
            self.experiment_id = response.id
            self.started_at = started_at
            logger.info(f"Created new evaluation for iteration {self.current_iteration}: {self.experiment_id}")
            
        except Exception as e:
            logger.error(f"Error creating dashboard evaluation: {e}")
    
    async def cleanup(self) -> None:
        """Clean up resources."""
        try:
            # End MLFlow run if active
            if self.experiment_id:
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
    
    def _convert_mismatches(self, raw_mismatches: List[Any]) -> List[Dict[str, Any]]:
        """Convert raw mismatches to the format expected by APOSState."""
        converted_mismatches = []
        for m in raw_mismatches:
            # Handle both dictionary and object formats
            if isinstance(m, dict):
                # Get transcript_id with fallback to empty string to avoid None
                transcript_id = m.get('form_id') or m.get('transcript_id') or ''
                mismatch = {
                    'transcript_id': transcript_id,
                    'question_name': m.get('question') or m.get('question_name') or '',
                    'model_answer': m.get('predicted') or m.get('model_answer') or '',
                    'transcript_text': m.get('transcript', ''),  # Default to empty string if not present
                    'original_explanation': m.get('explanation', ''),  # Default to empty string if not present
                    'ground_truth': m.get('ground_truth') or '',
                    'metadata': m.get('metadata', {})
                }
            else:
                # Get transcript_id with fallback to empty string to avoid None
                transcript_id = getattr(m, 'transcript_id', '') or getattr(m, 'form_id', '') or ''
                mismatch = {
                    'transcript_id': transcript_id,
                    'question_name': getattr(m, 'question_name', '') or '',
                    'model_answer': getattr(m, 'model_answer', '') or getattr(m, 'predicted', '') or '',
                    'transcript_text': getattr(m, 'transcript_text', '') or getattr(m, 'transcript', ''),
                    'original_explanation': getattr(m, 'original_explanation', '') or getattr(m, 'explanation', ''),
                    'ground_truth': getattr(m, 'ground_truth', '') or '',
                    'metadata': getattr(m, 'metadata', {})
                }
            converted_mismatches.append(mismatch)
        return converted_mismatches

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
            
            # Set up MLFlow run
            try:
                self._setup_mlflow_run(state.scorecard_name)
            except Exception as e:
                logger.error(f"Error setting up MLFlow run: {e}")
            
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
            
            # Store previous best accuracy for comparison
            previous_best_accuracy = state.best_accuracy
            
            # Get mismatches from evaluation and convert them
            raw_mismatches = self.evaluation.mismatches or []
            converted_mismatches = self._convert_mismatches(raw_mismatches)
            logger.info(f"Found {len(converted_mismatches)} mismatches")
            
            # Create iteration result with converted mismatches
            iteration_result = IterationResult(
                iteration=state.current_iteration,
                accuracy=accuracy,
                mismatches=converted_mismatches,
                prompt_changes=state.optimization_result if state.optimization_result else [],
                metrics={"accuracy": accuracy},
                metadata={
                    "system_message": state.system_message,
                    "user_message": state.user_message,
                    "started_at": self.started_at.isoformat() if self.started_at else None,
                    "experiment_id": self.experiment_id,
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