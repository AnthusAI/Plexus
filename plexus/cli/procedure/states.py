"""
Procedure State Constants

Defines the valid states for a Procedure's workflow.

NOTE: State transitions are now managed by the ProcedureStateMachine class
in state_machine.py. These constants are kept for backwards compatibility
and convenience, but validation should use the state machine.
"""
from __future__ import annotations

# Procedure workflow states
STATE_START = "start"
STATE_EVALUATION = "evaluation"
STATE_HYPOTHESIS = "hypothesis"
STATE_TEST = "test"
STATE_INSIGHTS = "insights"
STATE_COMPLETED = "completed"
STATE_ERROR = "error"

# All valid states (kept for backwards compatibility)
VALID_STATES = [
    STATE_START,
    STATE_EVALUATION,
    STATE_HYPOTHESIS,
    STATE_TEST,
    STATE_INSIGHTS,
    STATE_COMPLETED,
    STATE_ERROR
]


def is_valid_state(state: str) -> bool:
    """
    Check if a state string is valid.
    
    Note: For new code, prefer using ProcedureStateMachine for validation.
    """
    return state in VALID_STATES


def is_valid_transition(from_state: str | None, to_state: str) -> bool:
    """
    Check if a state transition is valid.
    
    Note: This delegates to the state machine for proper validation.
    For new code, use ProcedureStateMachine directly.
    """
    from .state_machine import is_valid_transition as sm_is_valid_transition
    return sm_is_valid_transition(from_state, to_state)


def get_next_states(current_state: str | None) -> list[str]:
    """
    Get the list of valid next states from the current state.
    
    Note: This delegates to the state machine.
    For new code, use ProcedureStateMachine directly.
    """
    from .state_machine import get_valid_transitions
    return get_valid_transitions(current_state)

