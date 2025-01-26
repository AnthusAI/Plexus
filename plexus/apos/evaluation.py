"""
Extended evaluation functionality for APOS.
"""
import os
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import mlflow
import random
import asyncio
from dataclasses import asdict
from tenacity import retry, stop_after_attempt, wait_exponential

from plexus.Evaluation import AccuracyEvaluation
from plexus.apos.models import (
    OptimizationState,
    IterationResult,
    MismatchAnalysis,
    PromptChange,
    SynthesisResult
)
from plexus.apos.config import APOSConfig, load_config
from plexus.dashboard.api.models.evaluation import Evaluation as DashboardEvaluation
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.dashboard.api.models.account import Account
from plexus.dashboard.api.models.scorecard import Scorecard as DashboardScorecard
from langchain_openai import ChatOpenAI
from plexus.apos.analyzer import MismatchAnalyzer
from plexus.apos.pattern_analyzer import PatternAnalyzer


logger = logging.getLogger('plexus.apos.evaluation')


class APOSEvaluation(AccuracyEvaluation):
    """
    Extended AccuracyEvaluation class for automated prompt optimization.
    
    This class extends the base AccuracyEvaluation to add:
    1. Detailed mismatch tracking and analysis
    2. Result persistence
    3. Iteration comparison
    4. History tracking
    """
    
    def __init__(self, *, override_folder=None, labeled_samples=None, labeled_samples_filename=None, score_id=None, **kwargs):
        # Extract config from kwargs since base class doesn't use it
        self.config = kwargs.pop('config', None) or load_config()
        self.config.setup_logging()
        
        # Store original sample size request and override config if specified
        self.requested_sample_size = kwargs.get('number_of_texts_to_sample', 100)
        if self.requested_sample_size:
            # Command line argument takes precedence over config
            self.config.analysis.samples_per_iteration = self.requested_sample_size
        
        # Store all samples and create fixed evaluation set
        self.all_labeled_samples = labeled_samples
        if labeled_samples and self.config.analysis.samples_per_iteration:
            random.seed(42)  # Use fixed seed for reproducibility
            sample_size = min(len(labeled_samples), self.config.analysis.samples_per_iteration)
            self.evaluation_samples = random.sample(labeled_samples, sample_size)
            random.seed()  # Reset seed
            # Override number_of_texts_to_sample with samples_per_iteration
            kwargs['number_of_texts_to_sample'] = sample_size
            kwargs['labeled_samples'] = self.evaluation_samples
        else:
            self.evaluation_samples = labeled_samples
            kwargs['labeled_samples'] = labeled_samples

        # Initialize our own attributes
        self.scorecard_name = kwargs.get('scorecard_name')
        self.override_folder = override_folder
        self.override_data = self.load_override_data() if self.override_folder else {}
        self.labeled_samples = labeled_samples
        self.labeled_samples_filename = labeled_samples_filename
        self.score_id = score_id
        self.results_queue = asyncio.Queue()
        self.metrics_tasks = {}  # Dictionary to track metrics computation tasks per score
        self.should_stop = False
        self.completed_scores = set()  # Track which scores have completed all their results
        
        # Initialize remaining attributes from base class first
        super().__init__(**kwargs)
        
        # Initialize dashboard client without creating experiment
        try:
            logging.info("Initializing Plexus Dashboard client...")
            self.dashboard_client = PlexusDashboardClient.for_account(kwargs.get('account_key', 'call-criteria'))
            
            # Look up account using default key
            account_key = kwargs.get('account_key', 'call-criteria')
            logging.info(f"Looking up account with key: {account_key}")
            account = Account.get_by_key(account_key, self.dashboard_client)
            logging.info(f"Found account: {account.name} ({account.id})")
            
            # Store the account ID
            self.account_id = account.id
            
            # Look up scorecard using available identifiers
            scorecard = kwargs.get('scorecard')
            logging.info(f"Looking up scorecard with name: {scorecard.name}")
            if hasattr(scorecard, 'key'):
                logging.info(f"Using scorecard key: {scorecard.key}")
                dashboard_scorecard = DashboardScorecard.get_by_key(scorecard.key, self.dashboard_client)
            elif hasattr(scorecard, 'id'):
                logging.info(f"Using scorecard ID: {scorecard.id}")
                dashboard_scorecard = DashboardScorecard.get_by_id(scorecard.id, self.dashboard_client)
            else:
                logging.info(f"Looking up scorecard by name: {scorecard.name}")
                dashboard_scorecard = DashboardScorecard.get_by_name(scorecard.name, self.dashboard_client)
            logging.info(f"Found scorecard: {dashboard_scorecard.name} ({dashboard_scorecard.id})")
            
            # Store the scorecard ID
            self.scorecard_id = dashboard_scorecard.id

            # Look up score ID if we have a subset of score names
            if self.subset_of_score_names and len(self.subset_of_score_names) == 1:
                score_name = self.subset_of_score_names[0]
                logging.info(f"Looking up score with name: {score_name}")
                try:
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
                    
                    # Find the first score with matching name
                    matching_score = None
                    scorecard_data = result.get('getScorecard', {})
                    sections = scorecard_data.get('sections', {}).get('items', [])
                    
                    for section in sections:
                        scores = section.get('scores', {}).get('items', [])
                        if scores:  # If we have any scores
                            matching_score = scores[0]  # Take the first one since GraphQL already filtered
                            break
                    
                    if matching_score:
                        self.score_id = matching_score['id']
                        logging.info(f"Found score: {matching_score['name']} ({self.score_id})")
                    else:
                        logging.warning(f"Could not find score with name: {score_name} in scorecard: {dashboard_scorecard.id}")
                except Exception as e:
                    logging.error(f"Error looking up score: {e}")

        except Exception as e:
            logging.error(f"Failed to initialize dashboard client: {str(e)}", exc_info=True)
            self.dashboard_client = None
            self.experiment_id = None
        
        # Create state tracking
        self.state = OptimizationState(
            scorecard_name=self.scorecard_name,
            score_name=self.subset_of_score_names[0] if self.subset_of_score_names else "all",
            target_accuracy=self.config.optimization.target_accuracy,
            max_iterations=self.config.optimization.max_iterations
        )
        
        # Track current prompt changes
        self.current_prompt_changes = []
        
        # Ensure persistence directory exists
        os.makedirs(self.config.persistence_path, exist_ok=True)
        
        # Initialize analyzers
        self.mismatch_analyzer = MismatchAnalyzer()
        self.pattern_analyzer = PatternAnalyzer()
        self.history_dir = "optimization_history"
        self.current_iteration = 0
        self.iteration_dir = None
        
        logger.info(f"Initialized APOS evaluation for scorecard '{self.scorecard_name}' with {self.config.analysis.samples_per_iteration} samples per iteration")

    def reset_state(self) -> None:
        """Reset evaluation state for a new iteration."""
        # Store current prompts before reset
        current_prompts = self.get_current_prompts()
        if current_prompts:
            logger.info("\nStoring current prompts before reset:")
            for score_name, prompts in current_prompts.items():
                logger.info(f"\nScore '{score_name}':")
                logger.info(f"System Message: {prompts['system_message']}")
                logger.info(f"User Message: {prompts['user_message']}")
        
        # Reset base class state variables
        self.total_correct = 0
        self.total_questions = 0
        self.all_results = []
        self.mismatches = []
        self.results_by_score = {}
        self.processed_items_by_score = {}
        self.processed_items = 0
        
        # Reset our own state variables
        self.results_queue = asyncio.Queue()
        self.metrics_tasks = {}
        self.should_stop = False
        self.completed_scores = set()
        
        # Reset sample size to configured value
        if self.config.analysis.samples_per_iteration:
            self.number_of_texts_to_sample = self.config.analysis.samples_per_iteration
        else:
            self.number_of_texts_to_sample = self.requested_sample_size
        
        # Use the same evaluation samples for each iteration
        self.labeled_samples = self.evaluation_samples
        
        # Clear experiment ID to ensure new dashboard record for each iteration
        self.experiment_id = None
        self.started_at = None
        
        # Restore prompts after reset - this ensures optimized prompts are preserved
        if current_prompts:
            logger.info("\nRestoring prompts after reset:")
            self.set_prompts(current_prompts)
            restored_prompts = self.get_current_prompts()
            for score_name, prompts in restored_prompts.items():
                logger.info(f"\nScore '{score_name}':")
                logger.info(f"System Message: {prompts['system_message']}")
                logger.info(f"User Message: {prompts['user_message']}")
        
        logger.info(f"Reset evaluation state for new iteration with {self.number_of_texts_to_sample} samples")

    async def _analyze_and_synthesize(self) -> Tuple[List[MismatchAnalysis], SynthesisResult]:
        """
        Analyze mismatches individually and synthesize patterns.
        
        Returns:
            Tuple of (analyzed mismatches, synthesis results)
        """
        # First analyze each mismatch individually
        analyzed_mismatches = await self._analyze_mismatches()
        
        # Then analyze patterns across all mismatches
        synthesis_result = await self.pattern_analyzer.analyze_patterns(analyzed_mismatches)
        
        # Save both individual analyses and synthesis results
        self._persist_mismatch_analyses(analyzed_mismatches)
        self._persist_synthesis_results(synthesis_result)
        
        return analyzed_mismatches, synthesis_result
        
    def _persist_mismatch_analyses(self, analyses: List[MismatchAnalysis]) -> None:
        """Save mismatch analyses to disk."""
        if not self.iteration_dir:
            self.iteration_dir = os.path.join(self.history_dir, f"iteration_{self.current_iteration}")
            os.makedirs(self.iteration_dir, exist_ok=True)
            
        output_path = os.path.join(self.iteration_dir, "mismatches.json")
        with open(output_path, 'w') as f:
            json.dump([asdict(m) for m in analyses], f, indent=4)
        logger.info(f"Saved {len(analyses)} mismatch analyses to {output_path}")
        
    def _persist_synthesis_results(self, synthesis: SynthesisResult) -> None:
        """Save pattern synthesis results to disk."""
        if not self.iteration_dir:
            self.iteration_dir = os.path.join(self.history_dir, f"iteration_{self.current_iteration}")
            os.makedirs(self.iteration_dir, exist_ok=True)
            
        output_path = os.path.join(self.iteration_dir, "patterns.json")
        with open(output_path, 'w') as f:
            json.dump(asdict(synthesis), f, indent=4)
        logger.info(f"Saved pattern synthesis results to {output_path}")

    def _load_best_prompts(self) -> Optional[Dict[str, Dict[str, Any]]]:
        """Load the best performing prompts from previous iterations."""
        try:
            best_accuracy = 0.0
            best_prompts = None
            
            # Check each iteration directory for prompts and accuracy
            for iteration_dir in sorted(Path(self.history_dir).glob("iteration_*")):
                result_path = iteration_dir / "result.json"
                prompts_path = iteration_dir / "current_prompts.json"
                
                if result_path.exists() and prompts_path.exists():
                    # Load accuracy from result
                    with open(result_path) as f:
                        result = json.load(f)
                        accuracy = result.get('accuracy', 0.0)
                    
                    # If this iteration had better accuracy, load its prompts
                    if accuracy > best_accuracy:
                        with open(prompts_path) as f:
                            prompts = json.load(f)
                            best_accuracy = accuracy
                            best_prompts = prompts
                            logger.info(f"Found better prompts in {iteration_dir} with accuracy {accuracy:.1%}")
            
            return best_prompts
            
        except Exception as e:
            logger.error(f"Error loading best prompts: {e}")
            return None

    async def run(self) -> IterationResult:
        """Run the evaluation process."""
        try:
            # Store current prompts before reset
            current_prompts = self.get_current_prompts()
            if current_prompts:
                logger.info("\nCurrent prompts before reset:")
                for score_name, prompts in current_prompts.items():
                    logger.info(f"\nScore '{score_name}':")
                    logger.info(f"System Message: {prompts['system_message'][:100]}...")
                    logger.info(f"User Message: {prompts['user_message'][:100]}...")
            
            # Reset state at the start of each run
            self.reset_state()
            
            # Restore current prompts - these take precedence over saved prompts
            if current_prompts:
                logger.info("\nRestoring current prompts after reset")
                self.set_prompts(current_prompts)
            # Only load saved prompts if we don't have current ones
            elif self.current_iteration > 0:
                best_prompts = self._load_best_prompts()
                if best_prompts:
                    logger.info("\nApplying best prompts from previous iterations")
                    self.set_prompts(best_prompts)
            
            # Create iteration directory
            self.current_iteration += 1
            self.iteration_dir = os.path.join(self.history_dir, f"iteration_{self.current_iteration}")
            os.makedirs(self.iteration_dir, exist_ok=True)
            
            # Set report folder path in base class
            report_folder_path = os.path.join(self.iteration_dir, f"iteration_{self.current_iteration}")
            os.makedirs(report_folder_path, exist_ok=True)
            
            # Create new evaluation in dashboard for this iteration
            if self.dashboard_client:
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
                    "totalItems": self.requested_sample_size,
                    "processedItems": 0,
                    "parameters": json.dumps({
                        "sampling_method": self.sampling_method,
                        "sample_size": self.requested_sample_size,
                        "iteration": self.current_iteration
                    }),
                    "startedAt": started_at.isoformat().replace('+00:00', 'Z'),
                    "estimatedRemainingSeconds": self.requested_sample_size
                }
                
                response = DashboardEvaluation.create(
                    client=self.dashboard_client,
                    **experiment_params
                )
                self.experiment_id = response.id
                self.started_at = started_at
                logger.info(f"Created new evaluation for iteration {self.current_iteration}: {self.experiment_id}")
            
            # Start new MLflow run for this iteration
            mlflow.end_run()  # End previous run if any
            mlflow.start_run(run_name=f"iteration_{self.current_iteration}")
            
            # Run base evaluation with the report folder path
            self.report_folder_path = report_folder_path
            await super()._async_run()
            
            # Create initial result object
            result = IterationResult(
                iteration=self.current_iteration,
                accuracy=self.total_correct / self.total_questions if self.total_questions > 0 else 0.0,
                mismatches=self.mismatches,
                prompt_changes=self.current_prompt_changes,
                metrics={},
                metadata={}
            )
            
            # Analyze mismatches and synthesize patterns
            analyzed_mismatches, synthesis_result = await self._analyze_and_synthesize()
            
            # Update result with analyses
            result.mismatch_analyses = analyzed_mismatches
            result.pattern_synthesis = synthesis_result
            
            # Persist results including current prompts
            self._persist_results(result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error running APOS evaluation: {e}")
            raise

    async def _analyze_mismatches(self) -> List[MismatchAnalysis]:
        """
        Analyze mismatches individually to understand why they occurred.
        
        Returns:
            List of analyzed mismatches
        """
        logger.info(f"Analyzing {len(self.mismatches)} mismatches individually")
        
        # Convert raw mismatches to MismatchAnalysis objects
        mismatch_analyses = []
        for mismatch in self.mismatches:
            analysis = MismatchAnalysis(
                transcript_id=mismatch["form_id"],
                question_name=mismatch["question"],
                transcript_text=mismatch["transcript"],
                model_answer=mismatch["predicted"],
                ground_truth=mismatch["ground_truth"],
                original_explanation=mismatch["explanation"] if mismatch["explanation"] else ""
            )
            mismatch_analyses.append(analysis)
            
        # Analyze each mismatch individually
        analyzed_mismatches = await self.mismatch_analyzer.analyze_mismatches(mismatch_analyses)
        
        # Save the analyses
        self._persist_mismatch_analyses(analyzed_mismatches)
        
        return analyzed_mismatches
        
    def _get_metrics(self) -> Dict[str, float]:
        """Get evaluation metrics."""
        return {
            'accuracy': self.total_correct / self.total_questions if self.total_questions > 0 else 0.0,
            'total_questions': self.total_questions,
            'total_correct': self.total_correct
        }

    def _persist_results(self, result: IterationResult) -> None:
        """Persist iteration results to disk."""
        iteration_dir = Path(self.config.persistence_path) / f"iteration_{result.iteration}"
        os.makedirs(iteration_dir, exist_ok=True)
        
        # Save iteration result
        result_path = iteration_dir / "result.json"
        with open(result_path, 'w') as f:
            json.dump({
                'iteration': result.iteration,
                'accuracy': result.accuracy,
                'timestamp': result.timestamp.isoformat(),
                'metrics': result.metrics,
                'metadata': result.metadata
            }, f, indent=2)
        
        # Save mismatches - handle dictionary format
        mismatches_path = iteration_dir / "mismatches.json"
        with open(mismatches_path, 'w') as f:
            json.dump([{
                'transcript_id': m.get('form_id'),
                'question_name': m.get('question'),
                'ground_truth': m.get('ground_truth'),
                'model_answer': m.get('predicted'),
                'explanation': m.get('explanation', ''),
                'metadata': m.get('metadata', {})
            } for m in result.mismatches], f, indent=2)
        
        # Save prompt changes
        changes_path = iteration_dir / "prompt_changes.json"
        with open(changes_path, 'w') as f:
            json.dump([{
                'component': c.component,
                'old_text': c.old_text,
                'new_text': c.new_text,
                'rationale': c.rationale,
                'timestamp': c.timestamp.isoformat() if hasattr(c, 'timestamp') else None,
                'metadata': c.metadata if hasattr(c, 'metadata') else {}
            } for c in result.prompt_changes], f, indent=2)
            
        # Also save current prompts for this iteration
        prompts_path = iteration_dir / "current_prompts.json"
        with open(prompts_path, 'w') as f:
            json.dump(self.get_current_prompts(), f, indent=2)
            
        logger.info(f"Persisted iteration {result.iteration} results to {iteration_dir}")

    def get_current_prompts(self) -> Dict[str, Dict[str, Any]]:
        """Get the current prompts being used for evaluation."""
        prompts = {}
        for score in self.scorecard.scores:
            if not self.subset_of_score_names or score['name'] in self.subset_of_score_names:
                # Extract prompts from graph configuration
                if 'graph' in score and score['graph']:
                    # Get first node's prompts
                    node = score['graph'][0]
                    prompts[score['name']] = {
                        'system_message': node.get('system_message', ''),
                        'user_message': node.get('user_message', '')
                    }
                else:
                    # Fallback to direct score prompts if no graph
                    prompts[score['name']] = {
                        'system_message': score.get('system_message', ''),
                        'user_message': score.get('user_message', '')
                    }
        return prompts

    def set_prompts(self, prompts: Dict[str, Dict[str, Any]]) -> None:
        """Set new prompts for evaluation.
        
        Args:
            prompts: Dictionary mapping score names to their prompt configurations
        """
        for score_name, prompt_config in prompts.items():
            score = next((s for s in self.scorecard.scores if s['name'] == score_name), None)
            if score and 'graph' in score and score['graph']:
                # Update first node's prompts
                node = score['graph'][0]
                node['system_message'] = prompt_config.get('system_message', node.get('system_message', ''))
                node['user_message'] = prompt_config.get('user_message', node.get('user_message', ''))
                
                # Log the actual prompt content
                logger.info(f"\nUpdated prompts for score '{score_name}':")
                logger.info(f"System Message: {node['system_message'][:100]}...")
                logger.info(f"User Message: {node['user_message'][:100]}...")
            elif score:
                # Fallback to updating direct score prompts if no graph
                score['system_message'] = prompt_config.get('system_message', score.get('system_message', ''))
                score['user_message'] = prompt_config.get('user_message', score.get('user_message', ''))
                
                # Log the actual prompt content
                logger.info(f"\nUpdated prompts for score '{score_name}':")
                logger.info(f"System Message: {score['system_message'][:100]}...")
                logger.info(f"User Message: {score['user_message'][:100]}...")

    def apply_prompt_changes(self, changes: List[PromptChange]) -> None:
        """Apply a list of prompt changes.
        
        Args:
            changes: List of PromptChange objects to apply
        """
        logger.info(f"\nApplying {len(changes)} prompt changes:")
        current_prompts = self.get_current_prompts()
        
        # Log current prompts before changes
        logger.info("\nCurrent prompts before changes:")
        for score_name, prompts in current_prompts.items():
            logger.info(f"\nScore '{score_name}':")
            logger.info(f"System Message: {prompts['system_message']}")
            logger.info(f"User Message: {prompts['user_message']}")
        
        # Store old prompts to set in PromptChange objects
        for change in changes:
            score_name = change.metadata.get('score_name')
            if score_name not in current_prompts:
                logger.warning(f"Cannot apply change to unknown score: {score_name}")
                continue
                
            prompt_config = current_prompts[score_name]
            component = change.component.lower()
            
            # Store the old text before applying change
            if component == 'system_message':
                change.old_text = prompt_config.get('system_message', '')
                prompt_config['system_message'] = change.new_text
                logger.info(f"\nScore '{score_name}' - System Message Change:")
                logger.info(f"Old: {change.old_text}")
                logger.info(f"New: {change.new_text}")
            elif component == 'user_message':
                change.old_text = prompt_config.get('user_message', '')
                prompt_config['user_message'] = change.new_text
                logger.info(f"\nScore '{score_name}' - User Message Change:")
                logger.info(f"Old: {change.old_text}")
                logger.info(f"New: {change.new_text}")
            else:
                logger.warning(f"Unknown prompt component: {component}")
                continue
                
        # Store changes for the iteration result
        self.current_prompt_changes.extend(changes)
                
        # Apply the changes
        self.set_prompts(current_prompts)
        
        # Log final prompts after changes
        logger.info("\nFinal prompts after changes:")
        final_prompts = self.get_current_prompts()
        for score_name, prompts in final_prompts.items():
            logger.info(f"\nScore '{score_name}':")
            logger.info(f"System Message: {prompts['system_message']}")
            logger.info(f"User Message: {prompts['user_message']}")

    async def _async_run(self):
        """Run the base evaluation."""
        try:
            result = await super()._async_run()
            return result
        finally:
            pass