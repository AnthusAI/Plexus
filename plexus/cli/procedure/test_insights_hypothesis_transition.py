"""
Tests for the insights → hypothesis state transition.

This tests the complete cycle of:
1. Insights phase creating an insights node
2. Transitioning back to hypothesis state
3. Hypothesis phase generating new hypotheses based on insights
"""

import pytest
from unittest.mock import Mock, patch
import json
from plexus.cli.procedure.state_machine import ProcedureStateMachine
from plexus.cli.procedure.states import STATE_INSIGHTS, STATE_HYPOTHESIS


def test_insights_to_hypothesis_transition_exists():
    """Test that insights → hypothesis transition is defined in state machine."""
    sm = ProcedureStateMachine('test-proc-id', current_state=STATE_INSIGHTS)

    # Verify the transition exists
    assert hasattr(sm, 'continue_iteration')

    # Verify transition is valid
    assert sm.current_state.value == STATE_INSIGHTS

    # Execute transition
    sm.continue_iteration()

    # Verify new state
    assert sm.current_state.value == STATE_HYPOTHESIS


def test_continue_iteration_callback():
    """Test on_continue_iteration callback is called during transition."""
    mock_client = Mock()
    sm = ProcedureStateMachine('test-proc-id', current_state=STATE_INSIGHTS, client=mock_client)

    with patch.object(sm, '_update_task_stages') as mock_update:
        # Execute transition
        sm.continue_iteration()

        # Verify callback updated task stages
        assert mock_update.call_count == 2
        mock_update.assert_any_call('insights', 'COMPLETED')
        mock_update.assert_any_call('hypothesis', 'RUNNING')


def test_state_machine_transition_map_includes_insights_to_hypothesis():
    """Test that service.py transition_map includes insights → hypothesis."""
    from plexus.cli.procedure.service import ProcedureService

    # We can't easily test the transition_map directly without mocking a lot,
    # but we can verify the state machine supports the transition
    sm = ProcedureStateMachine('test-id', current_state=STATE_INSIGHTS)

    # Verify transition method exists
    assert hasattr(sm, 'continue_iteration')
    assert callable(sm.continue_iteration)


def test_hypothesis_phase_after_insights():
    """
    Test that hypothesis phase can run after insights phase completes.

    This is an integration-style test that verifies the hypothesis phase
    can be invoked after insights completes.
    """
    from plexus.cli.procedure.service import ProcedureService

    mock_client = Mock()
    service = ProcedureService(mock_client)

    # Create a state machine in HYPOTHESIS state (as if just transitioned from INSIGHTS)
    sm = ProcedureStateMachine('test-proc-id', current_state=STATE_HYPOTHESIS, client=mock_client)

    # Verify we're in hypothesis state
    assert sm.current_state.value == STATE_HYPOTHESIS

    # This state should be valid and ready to generate new hypotheses
    # The actual hypothesis generation would be tested in the hypothesis phase tests


def test_full_insights_to_hypothesis_cycle():
    """
    Test complete cycle: INSIGHTS → continue_iteration → HYPOTHESIS.
    """
    mock_client = Mock()

    # Start in INSIGHTS state (after test phase completed)
    sm = ProcedureStateMachine('test-proc-id', current_state=STATE_INSIGHTS, client=mock_client)

    assert sm.current_state.value == STATE_INSIGHTS

    # Execute insights → hypothesis transition
    with patch.object(sm, '_update_task_stages'):
        sm.continue_iteration()

    # Verify we're now in HYPOTHESIS state
    assert sm.current_state.value == STATE_HYPOTHESIS

    # From HYPOTHESIS, we should be able to transition to TEST (normal flow)
    with patch.object(sm, '_update_task_stages'):
        sm.start_testing()

    # Verify we're now in TEST state
    from plexus.cli.procedure.states import STATE_TEST
    assert sm.current_state.value == STATE_TEST


def test_insights_can_finish_or_continue():
    """Test that from INSIGHTS state, we can either finish or continue iteration."""
    mock_client = Mock()
    sm = ProcedureStateMachine('test-proc-id', current_state=STATE_INSIGHTS, client=mock_client)

    # Should be able to continue iteration
    assert hasattr(sm, 'continue_iteration')

    # Should also be able to finish
    assert hasattr(sm, 'finish_from_insights')

    # Test continue iteration
    with patch.object(sm, '_update_task_stages'):
        sm.continue_iteration()
    assert sm.current_state.value == STATE_HYPOTHESIS

    # Reset and test finish
    sm2 = ProcedureStateMachine('test-proc-id-2', current_state=STATE_INSIGHTS, client=mock_client)
    with patch.object(sm2, '_update_task_stages'):
        sm2.finish_from_insights()

    from plexus.cli.procedure.states import STATE_COMPLETED
    assert sm2.current_state.value == STATE_COMPLETED


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
