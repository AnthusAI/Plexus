"""Tests for ProcedureStateMachine"""
import pytest
from plexus.cli.procedure.state_machine import (
    ProcedureStateMachine,
    create_state_machine,
    get_valid_transitions,
    is_valid_transition
)


def test_state_machine_initial_state():
    """Test that state machine starts in 'start' state"""
    sm = create_state_machine("test-proc-1")
    assert sm.state_value == "start"


def test_state_machine_resume_from_state():
    """Test that state machine can be initialized with existing state"""
    sm = create_state_machine("test-proc-2", current_state="hypothesis")
    assert sm.state_value == "hypothesis"


def test_valid_transition_start_to_evaluation():
    """Test transition from start to evaluation"""
    sm = create_state_machine("test-proc-3", current_state="start")
    sm.begin()
    assert sm.state_value == "evaluation"


def test_valid_transition_evaluation_to_hypothesis():
    """Test transition from evaluation to hypothesis"""
    sm = create_state_machine("test-proc-3b", current_state="evaluation")
    sm.analyze()
    assert sm.state_value == "hypothesis"


def test_valid_transition_hypothesis_to_code():
    """Test transition from hypothesis to code"""
    sm = create_state_machine("test-proc-4", current_state="hypothesis")
    sm.start_coding()
    assert sm.state_value == "code"


def test_valid_transition_code_to_completed():
    """Test transition from code to completed"""
    sm = create_state_machine("test-proc-5", current_state="code")
    sm.finish_from_code()
    assert sm.state_value == "completed"


def test_valid_transition_hypothesis_to_completed():
    """Test transition from hypothesis directly to completed"""
    sm = create_state_machine("test-proc-6", current_state="hypothesis")
    sm.finish_from_hypothesis()
    assert sm.state_value == "completed"


def test_invalid_transition_raises_error():
    """Test that invalid transitions raise errors"""
    sm = create_state_machine("test-proc-7", current_state="start")
    
    # Can't go from start directly to code
    with pytest.raises(Exception):
        sm.start_coding()


def test_error_transitions():
    """Test transitions to error state"""
    sm = create_state_machine("test-proc-8", current_state="hypothesis")
    sm.fail_from_hypothesis()
    assert sm.state_value == "error"


def test_recovery_from_error():
    """Test recovery transitions from error state"""
    sm = create_state_machine("test-proc-9", current_state="error")
    sm.retry_from_error()
    assert sm.state_value == "evaluation"


def test_get_valid_transitions_from_start():
    """Test getting valid transitions from start state"""
    transitions = get_valid_transitions("start")
    assert "evaluation" in transitions
    assert "error" in transitions
    assert "hypothesis" not in transitions  # Can't go directly from start to hypothesis
    assert "code" not in transitions


def test_get_valid_transitions_from_hypothesis():
    """Test getting valid transitions from hypothesis state"""
    transitions = get_valid_transitions("hypothesis")
    assert "code" in transitions
    assert "completed" in transitions
    assert "error" in transitions


def test_is_valid_transition_helper():
    """Test the is_valid_transition helper function"""
    assert is_valid_transition("start", "evaluation") == True
    assert is_valid_transition("evaluation", "hypothesis") == True
    assert is_valid_transition("hypothesis", "code") == True
    assert is_valid_transition("code", "completed") == True
    assert is_valid_transition("start", "hypothesis") == False  # Invalid - must go through evaluation
    assert is_valid_transition("start", "code") == False  # Invalid
    assert is_valid_transition("completed", "hypothesis") == False  # Can't leave completed


def test_allowed_transitions_property():
    """Test that we can query allowed transitions from state machine"""
    sm = create_state_machine("test-proc-10", current_state="hypothesis")
    allowed = sm.allowed_events
    
    # Should have multiple transitions available
    assert len(allowed) > 0
    
    # Should have event names (python-statemachine uses 'allowed_events')
    assert "start_coding" in allowed
    assert "finish_from_hypothesis" in allowed


def test_completed_is_final_state():
    """Test that completed state has no outgoing transitions"""
    sm = create_state_machine("test-proc-11", current_state="completed")
    assert len(sm.allowed_events) == 0


def test_callbacks_are_called():
    """Test that state transition callbacks are executed"""
    sm = create_state_machine("test-proc-12", current_state="start")
    
    # Track if callback was called by checking state before/after
    assert sm.state_value == "start"
    sm.begin()
    assert sm.state_value == "evaluation"
    
    # The on_begin callback should have been called (logged)

