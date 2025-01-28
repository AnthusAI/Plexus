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
from plexus.apos.pattern_analyzer import PatternAnalyzer
from plexus.dashboard.api.models.evaluation import Evaluation as DashboardEvaluation

logger = logging.getLogger('plexus.apos.nodes.evaluation')


class ExtendedAccuracyEvaluation(AccuracyEvaluation):
    """Extended AccuracyEvaluation with prompt management."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.prompts = {}
    
    def set_prompts(self, prompts: Dict[str, Dict[str, str]]) -> None:
        """
        Set prompts for evaluation.
        
        Args:
            prompts: Dictionary mapping score names to their prompts
                    Each prompt dict should have 'system_message' and 'user_message'
        """
        self.prompts = prompts
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
        # Initialize base evaluation state
        self.total_correct = 0
        self.total_questions = 0
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
        self.current_iteration = 0
        self.iteration_dir = None
        
        # Experiment tracking
        self.experiment_id = None
        self.started_at = None
        self.scorecard_id = None
        self.score_id = None
        self.account_id = None
        
        # Initialize pattern analyzer
        self.pattern_analyzer = PatternAnalyzer(config=self.config)
        
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
    
    def _prepare_samples(self, labeled_samples: List[Any]) -> List[Any]:
        """Prepare evaluation samples with fixed seed."""
        if not labeled_samples:
            logger.warning("No labeled samples provided")
            return []
            
        # Store all samples first
        self.all_labeled_samples = labeled_samples
        
        # Use fixed seed for reproducibility
        random.seed(42)
        sample_size = min(len(labeled_samples), self.config.analysis.samples_per_iteration)
        samples = random.sample(labeled_samples, sample_size)
        random.seed()  # Reset seed
        
        logger.info(f"Prepared {len(samples)} samples for evaluation")
        
        # Store evaluation samples
        self.evaluation_samples = samples
        self.labeled_samples = samples  # This is used by the evaluation
        
        return samples
    
    def _reset_state(self) -> None:
        """Reset evaluation state for a new iteration."""
        # Store values we want to preserve
        old_samples = self.evaluation_samples
        old_all_samples = self.all_labeled_samples
        old_samples_filename = self.labeled_samples_filename
        old_override_folder = self.override_folder
        old_override_data = self.override_data
        
        # Reset base evaluation state
        self.total_correct = 0
        self.total_questions = 0
        self.all_results = []
        self.results_by_score = {}
        self.processed_items_by_score = {}
        self.processed_items = 0
        
        # Reset queue and tasks
        self.results_queue = asyncio.Queue()
        self.metrics_tasks = {}
        self.completed_scores = set()
        
        # Clear experiment ID for new iteration
        self.experiment_id = None
        self.started_at = None
        
        # Restore preserved values
        self.evaluation_samples = old_samples
        self.all_labeled_samples = old_all_samples
        self.labeled_samples = self.evaluation_samples  # Use same samples for each iteration
        self.labeled_samples_filename = old_samples_filename
        self.override_folder = old_override_folder
        self.override_data = old_override_data
        
        logger.info("Reset evaluation state for new iteration")
    
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
        
        # Get score config
        score_config = next((score for score in scorecard.scores 
                           if score['name'] == score_name), None)
        if not score_config:
            raise ValueError(f"Score '{score_name}' not found in scorecard.")
        
        logger.info(f"Found score config for {score_name}")
        
        # Get samples using score config
        score_class_name = score_config['class']
        score_module_path = f'plexus.scores.{score_class_name}'
        logger.info(f"Loading score class {score_class_name} from {score_module_path}")
        
        score_module = importlib.import_module(score_module_path)
        score_class = getattr(score_module, score_class_name)
        
        # Create score instance
        score_config['scorecard_name'] = scorecard.name
        score_config['score_name'] = score_name
        logger.info("Creating score instance")
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
        
        # Create ExtendedAccuracyEvaluation instance
        self.evaluation = ExtendedAccuracyEvaluation(
            scorecard=scorecard,
            scorecard_name=scorecard.name,
            labeled_samples=self.evaluation_samples,
            number_of_texts_to_sample=len(self.evaluation_samples),
            account_key='call-criteria',
            score_id=self.score_id,
            subset_of_score_names=[score_name]
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
        
        logger.info("Evaluation setup complete")
    
    def _apply_prompt_changes(self, state: APOSState) -> Dict[str, Any]:
        """Apply any pending prompt changes to the state."""
        if not state.optimization_result:
            return state.dict()
            
        logger.info("Applying prompt changes from optimization")
        
        # Get the prompt changes
        changes = state.optimization_result.prompt_changes
        if not changes:
            return state.dict()
            
        # Apply each change
        state_updates = state.dict()
        for change in changes:
            if change.system_message:
                logger.info("Applying system message change")
                state_updates["system_message"] = change.system_message
            if change.user_message:
                logger.info("Applying user message change")
                state_updates["user_message"] = change.user_message
                
        return state_updates
    
    def _should_continue_evaluation(self, state: APOSState) -> bool:
        """Check if evaluation should continue."""
        # Check if we've reached target accuracy
        if state.current_accuracy >= state.target_accuracy:
            logger.info(f"Target accuracy {state.target_accuracy} reached")
            return False
            
        # Check if we've hit max iterations
        if state.current_iteration >= state.max_iterations:
            logger.info(f"Maximum iterations {state.max_iterations} reached")
            return False
            
        # Check if we've hit max retries
        if state.retry_count >= state.max_retries:
            logger.info(f"Maximum retries {state.max_retries} reached")
            return False
            
        return True
    
    def _handle_evaluation_error(self, error: Exception, state: APOSState) -> Dict[str, Any]:
        """Handle evaluation errors."""
        logger.error(f"Error during evaluation: {str(error)}")
        
        state_updates = state.dict()
        state_updates["retry_count"] = state.retry_count + 1
        
        if state_updates["retry_count"] >= state.max_retries:
            logger.error("Max retries reached, marking as failed")
            state_updates["status"] = OptimizationStatus.FAILED
            state_updates["error"] = str(error)
            
        return state_updates
    
    def load_override_data(self) -> Dict[str, Any]:
        """Load override data from the override folder."""
        if not self.override_folder:
            return {}
            
        try:
            logger.info(f"Loading override data from {self.override_folder}")
            override_file = os.path.join(self.override_folder, "overrides.json")
            if os.path.exists(override_file):
                with open(override_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading override data: {e}")
        return {}
    
    def _setup_iteration_directory(self) -> None:
        """Set up directory for current iteration results."""
        # Use the iteration number from the instance
        self.iteration_dir = os.path.join(
            self.config.persistence_path,
            self.history_dir,
            f"iteration_{self.current_iteration}"
        )
        os.makedirs(self.iteration_dir, exist_ok=True)
        logger.info(f"Created iteration directory: {self.iteration_dir}")
        
        # Create initial JSON files
        files_to_create = [
            "current_prompts.json",
            "mismatches.json",
            "patterns.json",
            "prompt_changes.json",
            "result.json"
        ]
        
        for filename in files_to_create:
            filepath = os.path.join(self.iteration_dir, filename)
            if not os.path.exists(filepath):
                with open(filepath, 'w') as f:
                    json.dump({}, f, indent=2)
                logger.debug(f"Created {filename}")
                
    def _save_mismatches(self, mismatches: List[Any], iteration_dir: Path) -> None:
        """Save mismatches to disk in a consistent format."""
        mismatches_path = iteration_dir / "mismatches.json"
        formatted_mismatches = []
        
        for m in mismatches:
            # Handle both dictionary and object formats
            if isinstance(m, dict):
                mismatch = {
                    'form_id': m.get('form_id'),
                    'question_name': m.get('question'),
                    'ground_truth': m.get('ground_truth'),
                    'model_answer': m.get('predicted'),
                    'explanation': m.get('explanation', ''),
                    'metadata': m.get('metadata', {})
                }
            else:
                mismatch = {
                    'form_id': getattr(m, 'transcript_id', None) or getattr(m, 'form_id', None),
                    'question_name': getattr(m, 'question_name', None),
                    'ground_truth': getattr(m, 'ground_truth', None),
                    'model_answer': getattr(m, 'model_answer', None),
                    'explanation': getattr(m, 'original_explanation', '') or getattr(m, 'explanation', ''),
                    'metadata': getattr(m, 'metadata', {})
                }
            formatted_mismatches.append(mismatch)
            
        with open(mismatches_path, 'w') as f:
            json.dump(formatted_mismatches, f, indent=2)
        logger.info(f"Saved {len(formatted_mismatches)} mismatches to {mismatches_path}")

    def _save_iteration_results(self, iteration_result: IterationResult) -> None:
        """Save all iteration results to disk in a consistent format."""
        try:
            if not self.iteration_dir:
                self.iteration_dir = os.path.join(self.history_dir, f"iteration_{self.current_iteration}")
                os.makedirs(self.iteration_dir, exist_ok=True)

            # Save current prompts
            prompts = {
                "system_message": iteration_result.metadata["system_message"],
                "user_message": iteration_result.metadata["user_message"]
            }
            with open(os.path.join(self.iteration_dir, "current_prompts.json"), 'w') as f:
                json.dump(prompts, f, indent=2)
            
            # Save mismatches
            self._save_mismatches(iteration_result.mismatches, Path(self.iteration_dir))
        
        # Save prompt changes
            changes = []
            for c in iteration_result.prompt_changes:
                if isinstance(c, dict):
                    changes.append({
                        "component": c.get("component", ""),
                        "old_text": c.get("old_text", ""),
                        "new_text": c.get("new_text", ""),
                        "rationale": c.get("rationale", "")
                    })
                else:
                    changes.append({
                        "component": c.component,
                        "old_text": c.old_text,
                        "new_text": c.new_text,
                        "rationale": c.rationale
                    })
            with open(os.path.join(self.iteration_dir, "prompt_changes.json"), 'w') as f:
                json.dump(changes, f, indent=2)
            
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
            with open(os.path.join(self.iteration_dir, "result.json"), 'w') as f:
                json.dump(result, f, indent=2)
            
            logger.info(f"Saved all iteration results to {self.iteration_dir}")
                
        except Exception as e:
            logger.error(f"Error saving iteration results: {e}")

    # Remove redundant methods
    def _persist_results(self, result: IterationResult) -> None:
        """Redirect to _save_iteration_results for consistency."""
        self._save_iteration_results(result)
        
    def _persist_synthesis_results(self, synthesis: SynthesisResult) -> None:
        """Save pattern synthesis results to disk."""
        if not self.iteration_dir:
            self.iteration_dir = os.path.join(self.history_dir, f"iteration_{self.current_iteration}")
            os.makedirs(self.iteration_dir, exist_ok=True)
            
        output_path = os.path.join(self.iteration_dir, "patterns.json")
        with open(output_path, 'w') as f:
            json.dump({
                'common_issues': synthesis.common_issues,
                'summary': synthesis.summary
            }, f, indent=4)
        logger.info(f"Saved pattern synthesis results to {output_path}")
    
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
            
            # Set up MLFlow run
            try:
                self._setup_mlflow_run(state.scorecard_name)
            except Exception as e:
                logger.error(f"Error setting up MLFlow run: {e}")
            
            # Get current iteration from state
            self.current_iteration = state.current_iteration
            
            # Create iteration directory
            self._setup_iteration_directory()
            
            # Check for optimized prompts from previous iteration
            current_system = state.system_message
            current_user = state.user_message
            
            # Safely get prompt changes if they exist
            prompt_changes = []
            if state.optimization_result is not None:
                logger.info("Found optimization result from previous iteration")
                
                # Handle dictionary format with prompt_improvement and prompt_changes
                if isinstance(state.optimization_result, dict):
                    prompt_improvement = state.optimization_result.get('prompt_improvement')
                    if prompt_improvement:
                        logger.info("Using prompt improvement from optimization result")
                        current_system = prompt_improvement.system_message
                        current_user = prompt_improvement.user_message
                        prompt_changes = state.optimization_result.get('prompt_changes', [])
                        
                        logger.info("Applying optimized system message:")
                        logger.info(f"Old: {state.system_message[:100]}...")
                        logger.info(f"New: {current_system[:100]}...")
                        logger.info("Applying optimized user message:")
                        logger.info(f"Old: {state.user_message[:100]}...")
                        logger.info(f"New: {current_user[:100]}...")
                
                # Handle list of PromptChange objects
                elif isinstance(state.optimization_result, list):
                    for change in state.optimization_result:
                        if change.component == "system_message":
                            current_system = change.new_text
                            logger.info("Applying optimized system message:")
                            logger.info(f"Old: {state.system_message[:100]}...")
                            logger.info(f"New: {current_system[:100]}...")
                        elif change.component == "user_message":
                            current_user = change.new_text
                            logger.info("Applying optimized user message:")
                            logger.info(f"Old: {state.user_message[:100]}...")
                            logger.info(f"New: {current_user[:100]}...")
                    prompt_changes = state.optimization_result
                
                # Handle single PromptChange object
                elif hasattr(state.optimization_result, 'component'):
                    change = state.optimization_result
                    if change.component == "system_message":
                        current_system = change.new_text
                        logger.info("Applying optimized system message:")
                        logger.info(f"Old: {state.system_message[:100]}...")
                        logger.info(f"New: {current_system[:100]}...")
                    elif change.component == "user_message":
                        current_user = change.new_text
                        logger.info("Applying optimized user message:")
                        logger.info(f"Old: {state.user_message[:100]}...")
                        logger.info(f"New: {current_user[:100]}...")
                    prompt_changes = [change]
            
            # Update state with new prompts before evaluation
            state.system_message = current_system
            state.user_message = current_user
            logger.info("Updated state with new prompts")
            
            # Create evaluation instance with current prompts
            self._create_evaluation(
                scorecard=scorecard,
                score_name=state.score_name,
                system_message=current_system,
                user_message=current_user
            )
            
            # Run evaluation
            logger.info(f"Running evaluation for {state.score_name}")
            await self.evaluation._async_run()
            
            # Get evaluation results
            accuracy = self.evaluation.total_correct / self.evaluation.total_questions if self.evaluation.total_questions > 0 else 0
            
            # Get mismatches from evaluation and convert them
            raw_mismatches = self.evaluation.mismatches or []
            converted_mismatches = self._convert_mismatches(raw_mismatches)
            logger.info(f"Found {len(converted_mismatches)} mismatches")
            
            # Create iteration result with converted mismatches
            iteration_result = IterationResult(
                iteration=state.current_iteration,
                accuracy=accuracy,
                mismatches=converted_mismatches,
                prompt_changes=prompt_changes,
                metrics={"accuracy": accuracy},
                metadata={
                    "system_message": current_system,
                    "user_message": current_user,
                    "started_at": self.started_at.isoformat() if self.started_at else None,
                    "experiment_id": self.experiment_id,
                    "iteration_dir": self.iteration_dir
                }
            )
            
            # Add to history
            state.add_iteration_result(iteration_result)
            
            # Save initial results
            self._save_iteration_results(iteration_result)
            
            # Update state with results and new prompts
            state.current_accuracy = accuracy
            state.mismatches = converted_mismatches
            state.metadata["iteration_dir"] = self.iteration_dir
            
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