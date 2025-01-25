"""
Script to run automated evaluation optimization.
"""
import logging
import asyncio
import os
from typing import Optional, List, Dict, Any
from pathlib import Path
import json
import pandas as pd

from plexus.apos.evaluation import APOSEvaluation
from plexus.apos.optimizer import PromptOptimizer
from plexus.apos.config import APOSConfig, load_config
from plexus.Scorecard import Scorecard
from plexus.Registries import scorecard_registry
from plexus.apos.samples import get_samples
from plexus.apos.models import MismatchAnalysis


logger = logging.getLogger('plexus.apos.optimize')


async def optimize_evaluation(
    scorecard_name: str,
    score_name: str = None,
    config: APOSConfig = None,
    override_folder: str = None,
    number_of_samples: int = None,
    **kwargs
) -> None:
    """
    Run the automated prompt optimization process.
    
    Args:
        scorecard_name: Name of scorecard to optimize
        score_name: Optional specific score to optimize
        config: Optional APOS configuration
        override_folder: Optional folder containing override data
        number_of_samples: Optional number of samples to use
    """
    try:
        # Load scorecard
        Scorecard.load_and_register_scorecards('scorecards/')
        scorecard_class = scorecard_registry.get(scorecard_name)
        if scorecard_class is None:
            raise ValueError(f"Scorecard with name '{scorecard_name}' not found.")
            
        scorecard = scorecard_class(scorecard=scorecard_name)
        logger.info(f"Loaded scorecard: {scorecard_class.name}")
        
        # Get score config and samples
        score_config = next((score for score in scorecard.scores 
                        if score['name'] == score_name), None)
        if not score_config:
            raise ValueError(f"Score '{score_name}' not found in scorecard.")
            
        samples = get_samples(scorecard, score_name, score_config)
        
        # Load config if not provided
        if config is None:
            config = load_config()
        
        # Initialize optimizer
        optimizer = PromptOptimizer(config=config)
        
        # Initialize evaluation
        evaluation = APOSEvaluation(
            scorecard=scorecard,
            scorecard_name=scorecard_name,
            labeled_samples=samples,
            subset_of_score_names=[score_name],
            config=config,
            number_of_texts_to_sample=number_of_samples,
            override_folder=override_folder
        )
        
        # Run initial evaluation to get baseline
        result = await evaluation.run()
        initial_accuracy = result.accuracy
        logger.info(f"Initial accuracy: {initial_accuracy:.1%}")
        
        # Track best accuracy and prompts
        best_accuracy = initial_accuracy
        best_prompts = evaluation.get_current_prompts()
        best_iteration = 0
        logger.info(f"New best accuracy achieved: {best_accuracy:.1%}")
        
        # Create output directory for best prompts
        output_dir = Path(f"optimization_history/{scorecard_name}")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Main optimization loop
        iteration = 1
        while (
            iteration <= evaluation.config.optimization.max_iterations and
            best_accuracy < evaluation.config.optimization.target_accuracy
        ):
            logger.info(f"\n=== Starting Iteration {iteration} ===")
            
            try:
                logger.info("Generating prompt improvements...")
                
                # Convert raw mismatches to MismatchAnalysis objects
                mismatch_analyses = []
                for mismatch in result.mismatches:
                    analysis = MismatchAnalysis(
                        transcript_id=mismatch["form_id"],
                        question_name=mismatch["question"],
                        transcript_text=mismatch["transcript"],
                        model_answer=mismatch["predicted"],
                        ground_truth=mismatch["ground_truth"],
                        original_explanation=mismatch["explanation"] if mismatch["explanation"] else ""
                    )
                    mismatch_analyses.append(analysis)
                
                # Optimize prompts for each score
                for score_name in evaluation.subset_of_score_names or []:
                    logger.info(f"Optimizing prompts for score: {score_name}")
                    
                    # Get current prompts
                    current_prompts = evaluation.get_current_prompts()
                    logger.info("Current prompts loaded:")
                    logger.info(f"System message: {current_prompts[score_name]['system_message']}")
                    logger.info(f"User message: {current_prompts[score_name]['user_message']}")
                    
                    # Generate improvements
                    optimized_changes = optimizer.optimize_prompt(score_name, mismatch_analyses, evaluation)
                    
                    # Convert dict of changes to list
                    changes_list = list(optimized_changes.values())
                    
                    # Apply changes
                    evaluation.apply_prompt_changes(changes_list)
                
                # Run evaluation with new prompts
                result = await evaluation.run()
                
                # Update best accuracy and prompts if improved
                if result.accuracy > best_accuracy:
                    best_accuracy = result.accuracy
                    best_prompts = evaluation.get_current_prompts()
                    best_iteration = iteration
                    logger.info(f"New best accuracy achieved: {best_accuracy:.1%} at iteration {iteration}")
                    
                    # Save best prompts to file
                    output_file = output_dir / f"{score_name}_optimized_prompts.json"
                    with open(output_file, 'w') as f:
                        json.dump({
                            'accuracy': best_accuracy,
                            'iteration': iteration,
                            'prompts': best_prompts,
                            'score_name': score_name,
                            'scorecard_name': scorecard_name
                        }, f, indent=2)
                    logger.info(f"Saved best prompts to {output_file}")
                
                iteration += 1
                
            except Exception as e:
                logger.error(f"Error during optimization: {e}")
                raise
        
        # Log final results
        logger.info("\n=== Optimization Complete ===")
        logger.info(f"Initial accuracy: {initial_accuracy:.1%}")
        logger.info(f"Best accuracy: {best_accuracy:.1%} (achieved at iteration {best_iteration})")
        logger.info(f"Best prompts saved to optimization_history/{scorecard_name}/{score_name}_optimized_prompts.json")
        
    except Exception as e:
        logger.error(f"Error running optimization: {e}")
        raise


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run automated evaluation optimization")
    parser.add_argument("scorecard", help="Name of scorecard to optimize")
    parser.add_argument("--score", help="Specific score to optimize")
    parser.add_argument("--config", help="Path to configuration file")
    parser.add_argument("--override-folder", help="Optional folder containing override data")
    parser.add_argument("--number-of-samples", type=int, help="Number of samples to use")
    
    args = parser.parse_args()
    
    asyncio.run(optimize_evaluation(
        scorecard_name=args.scorecard,
        score_name=args.score,
        config=load_config(args.config) if args.config else None,
        override_folder=args.override_folder,
        number_of_samples=args.number_of_samples
    )) 