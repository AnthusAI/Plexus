"""
Tests for Step and Checkpoint primitives.

Tests checkpointed operations and checkpoint management.
"""

import pytest
from unittest.mock import Mock, MagicMock
from plexus.cli.procedure.lua_dsl.primitives.step import StepPrimitive, CheckpointPrimitive


class TestStepPrimitive:
    """Test Step.run() primitive for checkpointed operations."""

    @pytest.fixture
    def mock_execution_context(self):
        """Create mock execution context."""
        context = Mock()
        context.step_run = Mock(return_value='result')
        context.checkpoint_exists = Mock(return_value=False)
        context.checkpoint_get = Mock(return_value=None)
        return context

    @pytest.fixture
    def step_primitive(self, mock_execution_context):
        """Create StepPrimitive for testing."""
        return StepPrimitive(mock_execution_context)

    def test_run_delegates_to_execution_context(self, step_primitive, mock_execution_context):
        """Test that Step.run() delegates to execution context."""
        mock_fn = Mock(return_value='test_result')

        result = step_primitive.run('test_step', mock_fn)

        # Should delegate to context
        mock_execution_context.step_run.assert_called_once_with('test_step', mock_fn)
        assert result == 'result'

    def test_run_with_successful_execution(self, step_primitive, mock_execution_context):
        """Test successful step execution."""
        def test_function():
            return {'status': 'success', 'data': 42}

        mock_execution_context.step_run.return_value = {'status': 'success', 'data': 42}

        result = step_primitive.run('compute_result', test_function)

        assert result == {'status': 'success', 'data': 42}

    def test_run_with_exception_propagates(self, step_primitive, mock_execution_context):
        """Test that exceptions from execution context propagate."""
        mock_execution_context.step_run.side_effect = RuntimeError('Step failed')

        with pytest.raises(RuntimeError, match='Step failed'):
            step_primitive.run('failing_step', lambda: None)

    def test_run_with_complex_return_value(self, step_primitive, mock_execution_context):
        """Test step with complex return value."""
        complex_result = {
            'metrics': {'accuracy': 0.95, 'f1': 0.92},
            'config': {'model': 'gpt-4', 'temperature': 0.7},
            'timestamp': '2024-01-01T00:00:00Z'
        }

        mock_execution_context.step_run.return_value = complex_result

        result = step_primitive.run('evaluate_model', lambda: complex_result)

        assert result == complex_result
        assert result['metrics']['accuracy'] == 0.95


class TestCheckpointPrimitive:
    """Test Checkpoint management primitive."""

    @pytest.fixture
    def mock_execution_context(self):
        """Create mock execution context."""
        context = Mock()
        context.checkpoint_clear_all = Mock()
        context.checkpoint_clear_after = Mock()
        context.checkpoint_exists = Mock(return_value=True)
        context.checkpoint_get = Mock(return_value={'cached': 'data'})
        return context

    @pytest.fixture
    def checkpoint_primitive(self, mock_execution_context):
        """Create CheckpointPrimitive for testing."""
        return CheckpointPrimitive(mock_execution_context)

    def test_clear_all(self, checkpoint_primitive, mock_execution_context):
        """Test Checkpoint.clear_all() clears all checkpoints."""
        checkpoint_primitive.clear_all()

        mock_execution_context.checkpoint_clear_all.assert_called_once()

    def test_clear_after(self, checkpoint_primitive, mock_execution_context):
        """Test Checkpoint.clear_after() clears from specified step."""
        checkpoint_primitive.clear_after('step_name')

        mock_execution_context.checkpoint_clear_after.assert_called_once_with('step_name')

    def test_exists_returns_true_for_existing(self, checkpoint_primitive, mock_execution_context):
        """Test Checkpoint.exists() returns True for existing checkpoint."""
        mock_execution_context.checkpoint_exists.return_value = True

        result = checkpoint_primitive.exists('existing_step')

        assert result is True
        mock_execution_context.checkpoint_exists.assert_called_once_with('existing_step')

    def test_exists_returns_false_for_missing(self, checkpoint_primitive, mock_execution_context):
        """Test Checkpoint.exists() returns False for missing checkpoint."""
        mock_execution_context.checkpoint_exists.return_value = False

        result = checkpoint_primitive.exists('missing_step')

        assert result is False
        mock_execution_context.checkpoint_exists.assert_called_once_with('missing_step')

    def test_get_returns_cached_value(self, checkpoint_primitive, mock_execution_context):
        """Test Checkpoint.get() returns cached value."""
        mock_execution_context.checkpoint_get.return_value = {'result': 'cached'}

        result = checkpoint_primitive.get('step_name')

        assert result == {'result': 'cached'}
        mock_execution_context.checkpoint_get.assert_called_once_with('step_name')

    def test_get_returns_none_for_missing(self, checkpoint_primitive, mock_execution_context):
        """Test Checkpoint.get() returns None for missing checkpoint."""
        mock_execution_context.checkpoint_get.return_value = None

        result = checkpoint_primitive.get('missing_step')

        assert result is None


class TestStepPrimitiveIntegration:
    """Integration tests for Step primitive with real checkpoint logic."""

    def test_step_checkpoints_expensive_operation(self):
        """Test that Step.run() checkpoints expensive operations."""
        from plexus.cli.procedure.lua_dsl.execution_context import LocalExecutionContext
        from unittest.mock import Mock
        import json

        # Setup mock services
        mock_graphql = Mock()
        mock_graphql.query.return_value = {
            'getProcedure': {
                'id': 'proc-123',
                'metadata': json.dumps({'checkpoints': {}})
            }
        }
        mock_graphql.mutate.return_value = {}

        mock_recorder = Mock()
        mock_recorder.session_id = 'session-456'

        # Create real execution context
        context = LocalExecutionContext(
            procedure_id='proc-123',
            session_id='session-456',
            graphql_service=mock_graphql,
            chat_recorder=mock_recorder
        )

        step = StepPrimitive(context)

        # Track execution count
        execution_count = {'count': 0}

        def expensive_operation():
            execution_count['count'] += 1
            return {'result': execution_count['count']}

        # First execution
        result1 = step.run('expensive_op', expensive_operation)
        assert result1 == {'result': 1}
        assert execution_count['count'] == 1

        # Second execution (should use checkpoint)
        result2 = step.run('expensive_op', expensive_operation)
        assert result2 == {'result': 1}  # Same result
        assert execution_count['count'] == 1  # NOT re-executed

    def test_checkpoint_clear_allows_reexecution(self):
        """Test that clearing checkpoints allows re-execution."""
        from plexus.cli.procedure.lua_dsl.execution_context import LocalExecutionContext
        from unittest.mock import Mock
        import json

        # Setup mock services
        mock_graphql = Mock()
        mock_graphql.query.return_value = {
            'getProcedure': {
                'id': 'proc-123',
                'metadata': json.dumps({'checkpoints': {}})
            }
        }
        mock_graphql.mutate.return_value = {}

        mock_recorder = Mock()
        mock_recorder.session_id = 'session-456'

        # Create context
        context = LocalExecutionContext(
            procedure_id='proc-123',
            session_id='session-456',
            graphql_service=mock_graphql,
            chat_recorder=mock_recorder
        )

        step = StepPrimitive(context)
        checkpoint = CheckpointPrimitive(context)

        execution_count = {'count': 0}

        def test_operation():
            execution_count['count'] += 1
            return execution_count['count']

        # First execution
        result1 = step.run('test_op', test_operation)
        assert result1 == 1

        # Verify checkpoint exists
        assert checkpoint.exists('test_op')
        assert checkpoint.get('test_op') == 1

        # Clear checkpoints
        checkpoint.clear_all()

        # Should not exist after clear
        assert not checkpoint.exists('test_op')
        assert checkpoint.get('test_op') is None

        # Re-execution should run again
        result2 = step.run('test_op', test_operation)
        assert result2 == 2  # New execution
        assert execution_count['count'] == 2
