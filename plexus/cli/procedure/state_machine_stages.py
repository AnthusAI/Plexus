"""
Extract TaskStage configuration from Procedure state machines.

This module provides functions to convert state machine definitions into
TaskStage configurations that can be used with the Task progress tracking system.
"""
from __future__ import annotations

from typing import Dict, List
from plexus.cli.shared.task_progress_tracker import StageConfig


def get_stages_from_state_machine() -> Dict[str, StageConfig]:
    """
    Get TaskStage configurations from the procedure state machine.
    
    Currently returns hard-coded stages from ProcedureStateMachine.
    In the future, this will parse the state machine from YAML configuration.
    
    Returns:
        Dictionary mapping stage names to StageConfig objects
    """
    # Import the state machine to get the states
    from .state_machine import ProcedureStateMachine
    
    # For now, hardcode the stages based on the state machine
    # States: start, evaluation, hypothesis, test, insights, completed, error
    # We only create stages for the workflow states, not terminal states
    stages = {
        "Start": StageConfig(
            order=1,
            status_message="Procedure created, ready to run"
        ),
        "Evaluation": StageConfig(
            order=2,
            status_message="Running initial evaluation"
        ),
        "Hypothesis": StageConfig(
            order=3,
            status_message="Analyzing results and generating hypotheses"
        ),
        "Test": StageConfig(
            order=4,
            status_message="Testing hypothesis with score version"
        ),
        "Insights": StageConfig(
            order=5,
            status_message="Analyzing test results and generating insights"
        ),
    }
    
    # Note: 'completed' and 'error' are terminal states handled by Task status,
    # not as separate stages
    
    return stages


def get_stage_names_from_state_machine() -> List[str]:
    """
    Get the ordered list of stage names from the state machine.
    
    Returns:
        List of stage names in order
    """
    stages = get_stages_from_state_machine()
    # Sort by order
    sorted_stages = sorted(stages.items(), key=lambda x: x[1].order)
    return [name for name, _ in sorted_stages]


def parse_state_machine_from_yaml(yaml_code: str) -> Dict[str, StageConfig]:
    """
    Parse state machine configuration from YAML and return TaskStage configs.
    
    This is a placeholder for future functionality where procedures can define
    custom state machines in their YAML configuration.
    
    Args:
        yaml_code: The YAML configuration containing state machine definition
        
    Returns:
        Dictionary mapping stage names to StageConfig objects
        
    TODO: Implement YAML parsing for custom state machines
    """
    # For now, return the hardcoded stages
    # Future: Parse YAML for custom state machine definition
    return get_stages_from_state_machine()

