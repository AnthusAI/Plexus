"""
Script to run automated evaluation optimization.
"""
import logging
import asyncio
import os
from typing import Optional, List, Dict, Any
from pathlib import Path
import json

from plexus.apos.evaluation import APOSEvaluation
from plexus.apos.optimizer import PromptOptimizer
from plexus.apos.config import APOSConfig, load_config
from plexus.Scorecard import Scorecard
from plexus.Registries import scorecard_registry
from plexus.apos.samples import get_samples


logger = logging.getLogger('plexus.apos.optimize')


async def optimize_evaluation(
    scorecard_name: str,
    score_name: Optional[str] = None,
    config_path: Optional[str] = None
) -> None:
    """
    Run an automated optimization cycle for a scorecard evaluation.
    
    Args:
        scorecard_name: Name of the scorecard to optimize
        score_name: Optional specific score to focus on
        config_path: Optional path to configuration file
    """
    try:
        # Load configuration
        config = load_config(config_path)
        logger.info(f"Starting optimization for scorecard '{scorecard_name}'")
        
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
        
        # Initialize components
        evaluation = APOSEvaluation(
            config=config,
            scorecard=scorecard,
            scorecard_name=scorecard_name,
            subset_of_score_names=[score_name] if score_name else None,
            labeled_samples=samples
        )
        optimizer = PromptOptimizer(config=config)
        
        # Track best accuracy and prompts
        best_accuracy = 0.0
        best_prompts = evaluation.get_current_prompts()  # Initialize with current prompts
        consecutive_no_improvement = 0  # Track consecutive iterations without improvement
        
        # Run optimization loop
        iteration = 0
        
        # Initial evaluation
        result = await evaluation.run()
        current_accuracy = result.accuracy
        logger.info(f"Initial accuracy: {current_accuracy:.1%}")
        
        # Update best accuracy
        if current_accuracy > best_accuracy:
            best_accuracy = current_accuracy
            best_prompts = evaluation.get_current_prompts()
            logger.info(f"New best accuracy achieved: {best_accuracy:.1%}")
        
        while iteration < config.optimization.max_iterations:
            iteration += 1
            logger.info(f"\n=== Starting Iteration {iteration} ===")
            
            # Check if target accuracy reached
            if current_accuracy >= config.optimization.target_accuracy:
                logger.info(f"Target accuracy {config.optimization.target_accuracy:.1%} reached!")
                break
                
            # Check if we've hit max iterations
            if iteration == config.optimization.max_iterations:
                logger.info(f"Reached maximum iterations ({config.optimization.max_iterations})")
                break
                
            # Only proceed with optimization if accuracy is not perfect
            if current_accuracy < 1.0 and result.mismatches:
                # Generate prompt improvements directly from mismatches
                logger.info("Generating prompt improvements...")
                optimized_changes = optimizer.optimize_prompt(score_name, result.mismatches)
                
                # Validate and collect changes
                prompt_changes = []
                for component, change in optimized_changes.items():
                    if optimizer.validate_change(change):
                        prompt_changes.append(change)
                        logger.info(f"Generated improvement for {component}")
                    else:
                        logger.warning(f"Skipping invalid change for {component}")
                
                # Apply changes and evaluate
                if prompt_changes:
                    logger.info(f"Applying {len(prompt_changes)} prompt improvements...")
                    evaluation.apply_prompt_changes(prompt_changes)
                    
                    # Run evaluation with new prompts
                    result = await evaluation.run()
                    result.prompt_changes.extend(prompt_changes)  # Add the changes to the result
                    
                    # Log the improvement (or regression)
                    improvement = result.accuracy - current_accuracy
                    logger.info(f"Accuracy change: {improvement:.1%}")
                    
                    # Update current accuracy
                    current_accuracy = result.accuracy
                    
                    # Update best if improved
                    if current_accuracy > best_accuracy:
                        best_accuracy = current_accuracy
                        best_prompts = evaluation.get_current_prompts()
                        consecutive_no_improvement = 0  # Reset counter on improvement
                        logger.info(f"New best accuracy achieved: {best_accuracy:.1%}")
                    else:
                        consecutive_no_improvement += 1
                        logger.info(f"No improvement for {consecutive_no_improvement} consecutive iterations")
                    
                    # Only break if we've had multiple iterations without improvement
                    if consecutive_no_improvement >= 3:
                        logger.info("No improvement for 3 consecutive iterations")
                        break
                else:
                    logger.info("No valid prompt improvements generated")
                    break
            else:
                logger.info("Perfect accuracy achieved or no mismatches to fix")
                break
        
        # Restore best prompts at the end if current accuracy is worse
        if best_accuracy > current_accuracy:
            logger.info("Restoring best performing prompts...")
            evaluation.set_prompts(best_prompts)
        
        # Log final results
        logger.info("\n=== Optimization Complete ===")
        logger.info(f"Best accuracy achieved: {best_accuracy:.1%}")
        logger.info(f"Total iterations: {iteration}")
        
        # Save optimized prompts
        output_dir = Path(config.persistence_path) / scorecard_name
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{score_name}_optimized_prompts.json"
        
        # Use the best prompts we tracked during optimization
        final_prompts = {
            'system_message': best_prompts.get(score_name, {}).get('system_message', ''),
            'user_message': best_prompts.get(score_name, {}).get('user_message', '')
        }
        
        with open(output_file, 'w') as f:
            json.dump({score_name: final_prompts}, f, indent=2)
        logger.info(f"Optimized prompts saved to: {output_file}")
        logger.info(f"Final prompts: {final_prompts}")  # Log the prompts being saved
        
    except Exception as e:
        logger.error(f"Error during optimization: {e}")
        raise


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run automated evaluation optimization")
    parser.add_argument("scorecard", help="Name of scorecard to optimize")
    parser.add_argument("--score", help="Specific score to optimize")
    parser.add_argument("--config", help="Path to configuration file")
    
    args = parser.parse_args()
    
    asyncio.run(optimize_evaluation(
        scorecard_name=args.scorecard,
        score_name=args.score,
        config_path=args.config
    )) 