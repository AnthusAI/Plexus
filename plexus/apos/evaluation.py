"""
Extended evaluation functionality for APOS.
"""
import os
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import mlflow
import random
import asyncio

from plexus.Evaluation import AccuracyEvaluation
from plexus.apos.models import (
    OptimizationState,
    IterationResult,
    MismatchAnalysis,
    PromptChange
)
from plexus.apos.config import APOSConfig, load_config
from plexus.dashboard.api.models.evaluation import Evaluation as DashboardEvaluation
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.dashboard.api.models.account import Account
from plexus.dashboard.api.models.scorecard import Scorecard as DashboardScorecard


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
        
        # Store all samples and create fixed evaluation set
        self.all_labeled_samples = labeled_samples
        if labeled_samples and self.config.analysis.samples_per_iteration:
            random.seed(42)  # Use fixed seed for reproducibility
            self.evaluation_samples = random.sample(labeled_samples, self.config.analysis.samples_per_iteration)
            random.seed()  # Reset seed
            kwargs['labeled_samples'] = self.evaluation_samples
            kwargs['number_of_texts_to_sample'] = len(self.evaluation_samples)  # Override to use all evaluation samples
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
        
        logger.info(f"Initialized APOS evaluation for scorecard '{self.scorecard_name}' with {self.config.analysis.samples_per_iteration} samples per iteration")

    def reset_state(self) -> None:
        """Reset evaluation state for a new iteration."""
        # Reset base class state
        self.total_correct = 0
        self.total_questions = 0
        self.all_results = []
        self.mismatches = []
        self.results_by_score = {}
        self.processed_items_by_score = {}
        self.processed_items = 0
        self.completed_scores = set()
        self.metrics_tasks = {}
        self.current_prompt_changes = []  # Reset prompt changes
        
        # Use the same evaluation samples for each iteration
        self.labeled_samples = self.evaluation_samples
        
        logger.info("Reset evaluation state for new iteration")

    async def run(self) -> IterationResult:
        """Run a single evaluation iteration."""
        try:
            # Start iteration
            self.state.status = "in_progress"
            iteration = self.state.current_iteration + 1
            
            # Reset state for new iteration
            self.reset_state()
            
            # Set unique run ID for MLFlow artifacts
            self.run_id = f"iteration_{iteration}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            mlflow.start_run(run_name=self.run_id, nested=True)
            
            logger.info(f"Starting iteration {iteration} with run ID: {self.run_id}")
            
            try:
                # Only create a new dashboard experiment for iterations after the first one
                if self.state.current_iteration > 0:
                    started_at = datetime.now(timezone.utc)
                    experiment_params = {
                        "type": "accuracy",
                        "accountId": self.account_id,
                        "scorecardId": self.scorecard_id,
                        "status": "RUNNING",
                        "accuracy": 0.0,
                        "totalItems": self.number_of_texts_to_sample,
                        "processedItems": 0,
                        "parameters": json.dumps({
                            "sampling_method": self.sampling_method,
                            "sample_size": self.number_of_texts_to_sample,
                            "iteration": iteration,
                            "score_name": self.subset_of_score_names[0] if self.subset_of_score_names else None
                        }),
                        "estimatedRemainingSeconds": self.number_of_texts_to_sample
                    }
                    
                    # Add score ID if available
                    if self.score_id:
                        experiment_params["scoreId"] = self.score_id

                    response = DashboardEvaluation.create(
                        client=self.dashboard_client,
                        **experiment_params
                    )
                    self.experiment_id = response.id
                    self.started_at = started_at
                
                # Run base evaluation
                await super().run()
                
                # Create mismatch analyses
                mismatches = self._analyze_mismatches()
                
                # Create iteration result
                result = IterationResult(
                    iteration=iteration,
                    accuracy=self.total_correct / self.total_questions if self.total_questions > 0 else 0.0,
                    mismatches=mismatches,
                    prompt_changes=self.current_prompt_changes.copy(),  # Include current changes
                    metrics=self._get_metrics()
                )
                
                # Update state
                self.state.add_iteration_result(result)
                
                # Persist results
                self._persist_results(result)
                
                # Update final metrics
                if self.dashboard_client and self.experiment_id:
                    metrics = self.calculate_metrics(self.all_results)
                    await self.log_to_dashboard(
                        metrics,
                        status="COMPLETED"
                    )
                
                logger.info(f"Completed iteration {iteration} with accuracy {result.accuracy:.2%}")
                return result
            finally:
                mlflow.end_run()
            
        except Exception as e:
            logger.error(f"Error during iteration {self.state.current_iteration + 1}: {e}")
            raise

    def _analyze_mismatches(self) -> List[MismatchAnalysis]:
        """Analyze mismatches from the evaluation."""
        analyses = []
        
        for mismatch in self.mismatches:
            analysis = MismatchAnalysis(
                transcript_id=mismatch['form_id'],
                question_name=mismatch['question'],
                ground_truth=mismatch['ground_truth'],
                model_answer=mismatch['predicted'],
                transcript_text=mismatch['transcript'],
                analysis=mismatch['explanation'] if mismatch['explanation'] else "",
                error_category=None,  # Will be filled by analyzer
                root_cause=None,  # Will be filled by analyzer
                confidence=0.0  # Will be filled by analyzer
            )
            analyses.append(analysis)
            
        logger.info(f"Created {len(analyses)} mismatch analyses")
        return analyses

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
        
        # Save mismatches
        mismatches_path = iteration_dir / "mismatches.json"
        with open(mismatches_path, 'w') as f:
            json.dump([{
                'transcript_id': m.transcript_id,
                'question_name': m.question_name,
                'ground_truth': m.ground_truth,
                'model_answer': m.model_answer,
                'analysis': m.analysis,
                'error_category': m.error_category,
                'root_cause': m.root_cause,
                'confidence': m.confidence,
                'metadata': m.metadata
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
                        'user_message': node.get('user_message', ''),
                        'few_shot_examples': node.get('examples', [])
                    }
                else:
                    # Fallback to direct score prompts if no graph
                    prompts[score['name']] = {
                        'system_message': score.get('system_message', ''),
                        'user_message': score.get('user_message', ''),
                        'few_shot_examples': score.get('few_shot_examples', [])
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
                if 'examples' not in node:
                    node['examples'] = []
                node['examples'] = prompt_config.get('few_shot_examples', node['examples'])
            elif score:
                # Fallback to updating direct score prompts if no graph
                score['system_message'] = prompt_config.get('system_message', score.get('system_message', ''))
                score['user_message'] = prompt_config.get('user_message', score.get('user_message', ''))
                score['few_shot_examples'] = prompt_config.get('few_shot_examples', score.get('few_shot_examples', []))
        
        logger.info(f"Updated prompts for {len(prompts)} scores")

    def apply_prompt_changes(self, changes: List[PromptChange]) -> None:
        """Apply a list of prompt changes.
        
        Args:
            changes: List of PromptChange objects to apply
        """
        current_prompts = self.get_current_prompts()
        
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
            elif component == 'user_message':
                change.old_text = prompt_config.get('user_message', '')
                prompt_config['user_message'] = change.new_text
            elif component == 'few_shot_examples':
                change.old_text = str(prompt_config.get('few_shot_examples', []))
                prompt_config['few_shot_examples'] = change.new_text
            else:
                logger.warning(f"Unknown prompt component: {component}")
                continue
                
        # Store changes for the iteration result
        self.current_prompt_changes.extend(changes)
                
        self.set_prompts(current_prompts)
        logger.info(f"Applied {len(changes)} prompt changes")

    async def score_all_texts_for_score(self, selected_sample_rows, score_name):
        """Score all texts for a specific score concurrently"""
        if score_name not in self.results_by_score:
            self.results_by_score[score_name] = []
        if score_name not in self.processed_items_by_score:
            self.processed_items_by_score[score_name] = 0

        tasks = []
        total_rows = len(selected_sample_rows)
        for idx, (_, row) in enumerate(selected_sample_rows.iterrows()):
            task = asyncio.create_task(self.score_text(row, score_name))
            tasks.append(task)
        
        for task in asyncio.as_completed(tasks):
            try:
                result = await task
                if result:
                    self.results_by_score[score_name].append(result)
                    self.processed_items_by_score[score_name] += 1
                    self.processed_items = sum(self.processed_items_by_score.values())
                    # Start metrics task if needed
                    is_final_result = self.processed_items_by_score[score_name] == total_rows
                    await self.maybe_start_metrics_task(score_name, is_final_result)
            except Exception as e:
                logger.error(f"Error scoring text for {score_name}: {e}")
        
        return self.results_by_score[score_name]

    async def maybe_start_metrics_task(self, score_name: str, is_final_result: bool = False):
        """Start a metrics computation task if one isn't running, or if this is the final result"""
        if is_final_result:
            # For final results, always compute metrics
            self.completed_scores.add(score_name)
            if score_name in self.metrics_tasks:
                task = self.metrics_tasks[score_name]
                if not task.done():
                    task.cancel()
            self.metrics_tasks[score_name] = asyncio.create_task(self.continuous_metrics_computation(score_name))
        elif score_name not in self.metrics_tasks or self.metrics_tasks[score_name].done():
            # Start new task if none exists or previous one is done
            self.metrics_tasks[score_name] = asyncio.create_task(self.continuous_metrics_computation(score_name))

    async def continuous_metrics_computation(self, score_name: str):
        """Background task that continuously computes and posts metrics for a specific score"""
        last_processed_count = 0
        while not self.should_stop:
            try:
                # Check if we have any new results for this score
                current_count = len(self.results_by_score.get(score_name, []))
                if current_count > 0 and current_count != last_processed_count:
                    # Combine results from all scores for metrics calculation
                    combined_results = []
                    for score, results in self.results_by_score.items():
                        combined_results.extend(results)
                    
                    metrics = self.calculate_metrics(combined_results)
                    # If this is the final update (score is complete), mark it as completed
                    status = "COMPLETED" if score_name in self.completed_scores else "RUNNING"
                    
                    # Create a task for the API call and shield it from cancellation
                    api_task = asyncio.shield(self.log_to_dashboard(metrics, status=status))
                    try:
                        await api_task
                        last_processed_count = current_count
                    except asyncio.CancelledError:
                        # If we're cancelled, still wait for the API call to finish
                        logger.info("Metrics task cancelled, ensuring API call completes")
                        try:
                            await api_task
                        except asyncio.CancelledError:
                            pass  # Ignore any additional cancellations
                        logger.info("API call completed after cancellation")
                        return  # Exit the task
                
                # Wait a bit before checking again
                await asyncio.sleep(.1)
            except asyncio.CancelledError:
                logger.info(f"Metrics computation for {score_name} cancelled")
                return  # Exit gracefully
            except Exception as e:
                logger.error(f"Error in continuous metrics computation for {score_name}: {e}")
                await asyncio.sleep(5)  # Wait longer on error 