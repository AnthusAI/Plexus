"""
Extended evaluation functionality for APOS.
"""
import os
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import pandas as pd
import mlflow
import random

from plexus.Evaluation import AccuracyEvaluation
from plexus.apos.models import (
    OptimizationState,
    IterationResult,
    MismatchAnalysis,
    PromptChange
)
from plexus.apos.config import APOSConfig, load_config


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
    
    def __init__(self, config: Optional[APOSConfig] = None, labeled_samples: Optional[List[Dict[str, Any]]] = None, **kwargs):
        self.config = config or load_config()
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
        
        # Pass labeled_samples directly to parent class
        super().__init__(**kwargs)
        
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

    def load_iteration_result(self, iteration: int) -> Optional[IterationResult]:
        """Load results for a specific iteration."""
        iteration_dir = Path(self.config.persistence_path) / f"iteration_{iteration}"
        if not iteration_dir.exists():
            logger.warning(f"No results found for iteration {iteration}")
            return None
            
        try:
            # Load main result
            with open(iteration_dir / "result.json") as f:
                result_data = json.load(f)
                
            # Load mismatches
            with open(iteration_dir / "mismatches.json") as f:
                mismatches_data = json.load(f)
                
            # Load prompt changes
            with open(iteration_dir / "prompt_changes.json") as f:
                changes_data = json.load(f)
                
            # Reconstruct objects
            mismatches = [MismatchAnalysis(**m) for m in mismatches_data]
            changes = [PromptChange(**c) for c in changes_data]
            
            return IterationResult(
                iteration=result_data['iteration'],
                accuracy=result_data['accuracy'],
                mismatches=mismatches,
                prompt_changes=changes,
                metrics=result_data['metrics'],
                metadata=result_data['metadata']
            )
            
        except Exception as e:
            logger.error(f"Error loading iteration {iteration} results: {e}")
            return None

    def get_improvement_trend(self) -> List[float]:
        """Get the accuracy improvement trend across iterations."""
        improvements = []
        prev_result = None
        
        for result in self.state.history:
            improvement = result.get_improvement(prev_result)
            improvements.append(improvement)
            prev_result = result
            
        return improvements

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

    def generate_excel_report(self, report_folder_path, results, selected_sample_rows):
        """Override parent's generate_excel_report to include iteration number in filename."""
        records = []
        score_names = self.score_names()
        all_score_names = "_".join(score_names).replace(" ", "_")
        filename_safe_score_names = "".join(c for c in all_score_names if c.isalnum() or c in "_-")
        
        # Include iteration number in filename
        iteration_suffix = f"_iteration_{self.state.current_iteration + 1}"
        
        for result in results:
            for question in score_names:
                score_result = next((r for r in result['results'].values() if r.parameters.name == question), None)
                if score_result:
                    records.append({
                        'report_id': result['session_id'],
                        'form_id': result['form_id'],
                        'question_name': question,
                        'human_label': score_result.metadata['human_label'],
                        'human_explanation': score_result.metadata['human_explanation'],
                        'predicted_answer': score_result.value,
                        'match': score_result.metadata['correct'],
                        'explanation': score_result.explanation,
                        'original_text': score_result.metadata['text'],
                    })

        df_records = pd.DataFrame(records)
        excel_file_path = f"{report_folder_path}/Evaluation Report for {filename_safe_score_names}{iteration_suffix}.xlsx"
        df_records.to_excel(excel_file_path, index=False)
        mlflow.log_artifact(excel_file_path)

        logger.info(f"Excel report generated at {excel_file_path}") 