"""
Stage configurations for different types of operations.

This module provides predefined stage configurations for different operation types
like evaluations, predictions, etc. Each configuration defines the stages, their
order, and their properties.
"""

from typing import Dict
from plexus.cli.task_progress_tracker import StageConfig


def get_evaluation_stage_configs(total_items: int = 0) -> Dict[str, StageConfig]:
    """Get stage configuration for evaluation operations.
    
    Args:
        total_items: Total number of items to process (for Processing stage)
        
    Returns:
        Dictionary mapping stage names to StageConfig objects
    """
    return {
        "Setup": StageConfig(
            order=1,
            status_message="Setting up evaluation..."
        ),
        "Processing": StageConfig(
            order=2,
            total_items=total_items,
            status_message="Starting processing..."
        ),
        "Finalizing": StageConfig(
            order=3,
            status_message="Starting finalization..."
        )
    }


def get_prediction_stage_configs(total_items: int = 1) -> Dict[str, StageConfig]:
    """Get stage configuration for prediction operations.
    
    Args:
        total_items: Total number of items to process (for Predicting stage)
        
    Returns:
        Dictionary mapping stage names to StageConfig objects
    """
    return {
        "Querying": StageConfig(
            order=1,
            status_message="Looking up Score configuration and Item..."
        ),
        "Predicting": StageConfig(
            order=2,
            total_items=total_items,
            status_message="Running prediction..."
        ),
        "Archiving": StageConfig(
            order=3,
            status_message="Posting results to API..."
        )
    }


def get_stage_configs_for_operation_type(operation_type: str, total_items: int = 0) -> Dict[str, StageConfig]:
    """Get stage configuration for a specific operation type.
    
    Args:
        operation_type: Type of operation ('evaluation', 'prediction', etc.)
        total_items: Total number of items to process
        
    Returns:
        Dictionary mapping stage names to StageConfig objects
        
    Raises:
        ValueError: If operation_type is not recognized
    """
    if operation_type.lower() in ['evaluation', 'evaluate', 'accuracy']:
        return get_evaluation_stage_configs(total_items)
    elif operation_type.lower() in ['prediction', 'predict']:
        return get_prediction_stage_configs(total_items)
    else:
        raise ValueError(f"Unknown operation type: {operation_type}")


# Legacy aliases for backward compatibility
def get_evaluation_stages(total_items: int = 0) -> Dict[str, StageConfig]:
    """Legacy alias for get_evaluation_stage_configs."""
    return get_evaluation_stage_configs(total_items)


def get_prediction_stages(total_items: int = 1) -> Dict[str, StageConfig]:
    """Legacy alias for get_prediction_stage_configs."""
    return get_prediction_stage_configs(total_items)