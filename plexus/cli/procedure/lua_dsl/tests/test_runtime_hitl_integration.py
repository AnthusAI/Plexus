"""
Simple tests verifying runtime exception handling for HITL.

Tests that ProcedureWaitingForHuman is properly caught and formatted.
"""

import pytest
from plexus.cli.procedure.lua_dsl.execution_context import ProcedureWaitingForHuman


class TestRuntimeProcedureWaitingForHumanHandling:
    """Test that runtime handles ProcedureWaitingForHuman exception."""

    def test_exception_contains_required_fields(self):
        """Test ProcedureWaitingForHuman has required fields."""
        exc = ProcedureWaitingForHuman(
            procedure_id='proc-123',
            pending_message_id='msg-456'
        )

        assert exc.procedure_id == 'proc-123'
        assert exc.pending_message_id == 'msg-456'
        assert 'proc-123' in str(exc)
        assert 'msg-456' in str(exc)

    def test_exception_is_catchable(self):
        """Test that exception can be caught and handled."""
        try:
            raise ProcedureWaitingForHuman(
                procedure_id='test-proc',
                pending_message_id='test-msg'
            )
        except ProcedureWaitingForHuman as e:
            assert e.procedure_id == 'test-proc'
            assert e.pending_message_id == 'test-msg'
        else:
            pytest.fail("Exception should have been raised and caught")
