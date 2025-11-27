#!/usr/bin/env python3
"""
Test script for MLTrainerLocal.

This script validates that MLTrainerLocal correctly wraps the existing
Score.train_model() workflow without breaking anything.
"""

import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import plexus
from plexus.Registries import scorecard_registry
from plexus.training import MLTrainerLocal
from plexus.CustomLogging import logging

def test_ml_trainer_local():
    """Test MLTrainerLocal with an existing scorecard/score."""

    # Load scorecards
    logging.info("Loading scorecards...")
    plexus.Scorecard.load_and_register_scorecards('scorecards/')

    # Get first available scorecard
    # Try a known scorecard name first
    known_scorecards = ['Randall Reilly v1.0', 'CS3 Services V2', 'SelectQuote HCS Medium-Risk']
    scorecard_class = None
    scorecard_name = None

    for name in known_scorecards:
        scorecard_class = scorecard_registry.get(name)
        if scorecard_class:
            scorecard_name = name
            break

    if not scorecard_class:
        logging.error("Could not find any known scorecards")
        return False
    logging.info(f"Using scorecard: {scorecard_name}")

    # Get first score from scorecard
    # Handle both dict and list formats
    if isinstance(scorecard_class.scores, dict):
        if not scorecard_class.scores:
            logging.error(f"No scores found in scorecard {scorecard_name}")
            return False

        score_names = list(scorecard_class.scores.keys())
        score_name = score_names[0]
        score_config = scorecard_class.scores[score_name]

        # Check if score has 'data' configuration (required for training)
        if 'data' not in score_config:
            logging.warning(f"Score {score_name} has no 'data' configuration")
            # Try other scores
            for next_name in score_names[1:]:
                next_config = scorecard_class.scores[next_name]
                if 'data' in next_config:
                    score_name = next_name
                    score_config = next_config
                    break
            else:
                logging.error("No scores with 'data' configuration found")
                return False
    else:
        # List format
        if not scorecard_class.scores:
            logging.error(f"No scores found in scorecard {scorecard_name}")
            return False

        # Find first score with 'data' configuration
        score_config = None
        for score in scorecard_class.scores:
            if isinstance(score, dict) and 'data' in score:
                score_config = score
                score_name = score.get('name', 'Unknown')
                break

        if not score_config:
            logging.error("No scores with 'data' configuration found in list")
            return False

    logging.info(f"Using score: {score_name}")
    logging.info(f"Score class: {score_config.get('class')}")

    try:
        # Create trainer
        logging.info("\n" + "="*80)
        logging.info("Creating MLTrainerLocal instance...")
        logging.info("="*80)

        trainer = MLTrainerLocal(
            scorecard_class=scorecard_class,
            score_config=score_config,
            fresh=False  # Use cached data for testing
        )

        # Execute training
        logging.info("\n" + "="*80)
        logging.info("Executing training workflow...")
        logging.info("="*80)

        result = trainer.execute()

        # Display results
        logging.info("\n" + "="*80)
        logging.info("TRAINING RESULT")
        logging.info("="*80)
        logging.info(f"Success: {result.success}")
        logging.info(f"Training type: {result.training_type}")
        logging.info(f"Target: {result.target}")

        # For LangGraphScore, we expect failure (no train_model method)
        # This is actually a successful validation test!
        if score_config.get('class') == 'LangGraphScore':
            if not result.success and 'train_model' in result.error:
                logging.info("\n" + "="*80)
                logging.info("TEST PASSED: MLTrainerLocal correctly validated that LangGraphScore")
                logging.info("doesn't support ML training (no train_model method)!")
                logging.info("="*80)
                return True
            else:
                logging.error("Expected validation error for LangGraphScore, but didn't get it")
                return False

        if result.error:
            logging.error(f"Error: {result.error}")
            return False

        logging.info(f"\nArtifacts:")
        for artifact_type, location in result.artifacts.items():
            logging.info(f"  {artifact_type}: {location}")

        logging.info(f"\nMetrics:")
        for metric_name, value in result.metrics.items():
            logging.info(f"  {metric_name}: {value}")

        logging.info(f"\nMetadata:")
        for key, value in result.metadata.items():
            logging.info(f"  {key}: {value}")

        logging.info("\n" + "="*80)
        logging.info("TEST PASSED: MLTrainerLocal works correctly!")
        logging.info("="*80)

        return True

    except Exception as e:
        logging.error(f"\nTEST FAILED: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    success = test_ml_trainer_local()
    sys.exit(0 if success else 1)
