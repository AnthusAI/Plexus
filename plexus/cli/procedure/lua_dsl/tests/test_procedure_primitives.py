"""
Tests for Procedure Primitive - Sub-procedure invocation and orchestration.

Comprehensive tests covering all 10 methods:
1. run() - synchronous execution
2. spawn() - asynchronous execution
3. wait() - wait for completion with/without timeout
4. status() - check task status
5. cancel() - cancel running task
6. inject() - inject message to running task
7. wait_any() - race pattern (first completion)
8. wait_all() - fan-in pattern (all complete)
9. is_complete() - boolean completion check
10. all_complete() - check all tasks complete
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from plexus.cli.procedure.lua_dsl.primitives.procedure import ProcedurePrimitive


class TestProcedurePrimitiveSetup:
    """Test fixture setup and initialization."""

    @pytest.fixture
    def mock_client(self):
        """Create mock PlexusDashboardClient."""
        client = Mock()
        client.execute = Mock()
        return client

    @pytest.fixture
    def mock_mcp_server(self):
        """Create mock MCP server."""
        return Mock()

    @pytest.fixture
    def mock_lua_sandbox(self):
        """Create mock Lua sandbox for table construction."""
        sandbox = Mock()
        sandbox.lua = Mock()
        sandbox.lua.table = Mock(side_effect=lambda: {})
        return sandbox

    @pytest.fixture
    def procedure_primitive(self, mock_client, mock_mcp_server):
        """Create ProcedurePrimitive for testing."""
        return ProcedurePrimitive(
            client=mock_client,
            account_id='test-account-123',
            parent_procedure_id='parent-proc-456',
            mcp_server=mock_mcp_server,
            openai_api_key='test-key-789'
        )

    @pytest.fixture
    def procedure_primitive_with_lua(self, mock_client, mock_mcp_server, mock_lua_sandbox):
        """Create ProcedurePrimitive with Lua sandbox."""
        return ProcedurePrimitive(
            client=mock_client,
            account_id='test-account-123',
            parent_procedure_id='parent-proc-456',
            mcp_server=mock_mcp_server,
            openai_api_key='test-key-789',
            lua_sandbox=mock_lua_sandbox
        )

    def test_initialization(self, procedure_primitive):
        """Test ProcedurePrimitive initialization."""
        assert procedure_primitive.account_id == 'test-account-123'
        assert procedure_primitive.parent_procedure_id == 'parent-proc-456'
        assert procedure_primitive._spawned_procedures == {}

    def test_repr(self, procedure_primitive):
        """Test string representation."""
        repr_str = repr(procedure_primitive)
        assert 'ProcedurePrimitive' in repr_str
        assert 'parent-proc-456' in repr_str
        assert 'spawned=0' in repr_str


class TestProcedureRun:
    """Test synchronous procedure execution with Procedure.run()."""

    @pytest.fixture
    def mock_client(self):
        """Create mock client."""
        return Mock()

    @pytest.fixture
    def mock_mcp_server(self):
        """Create mock MCP server."""
        return Mock()

    @pytest.fixture
    def mock_procedure(self):
        """Create mock Procedure object."""
        procedure = Mock()
        procedure.id = 'sub-proc-123'
        procedure.code = 'name: "Test"\nsteps:\n  - log: "Hello"'
        return procedure

    @pytest.fixture
    def procedure_primitive(self, mock_client, mock_mcp_server):
        """Create ProcedurePrimitive."""
        return ProcedurePrimitive(
            client=mock_client,
            account_id='test-account',
            parent_procedure_id='parent-proc',
            mcp_server=mock_mcp_server
        )

    @patch('plexus.dashboard.api.models.procedure.Procedure')
    @patch('plexus.cli.procedure.lua_dsl.runtime.LuaDSLRuntime')
    @patch('plexus.cli.procedure.lua_dsl.primitives.procedure.asyncio.run')
    def test_run_executes_synchronously(
        self,
        mock_asyncio_run,
        mock_runtime_class,
        mock_procedure_class,
        procedure_primitive,
        mock_procedure
    ):
        """Test that run() executes sub-procedure synchronously."""
        # Setup mocks
        mock_procedure_class.get_by_id.return_value = mock_procedure
        mock_runtime = Mock()
        mock_runtime_class.return_value = mock_runtime
        mock_asyncio_run.return_value = {'success': True, 'result': 'done'}

        # Execute
        result = procedure_primitive.run('sub-proc-123', {'param': 'value'})

        # Verify
        mock_procedure_class.get_by_id.assert_called_once_with('sub-proc-123', procedure_primitive.client)
        mock_runtime_class.assert_called_once()
        assert result == {'success': True, 'result': 'done'}

    @patch('plexus.dashboard.api.models.procedure.Procedure')
    def test_run_with_no_params(self, mock_procedure_class, procedure_primitive, mock_procedure):
        """Test run() with no parameters."""
        mock_procedure_class.get_by_id.return_value = mock_procedure

        with patch('plexus.cli.procedure.lua_dsl.runtime.LuaDSLRuntime') as mock_runtime_class:
            with patch('plexus.cli.procedure.lua_dsl.primitives.procedure.asyncio.run') as mock_asyncio_run:
                mock_asyncio_run.return_value = {'success': True}

                result = procedure_primitive.run('sub-proc-123')

                assert result == {'success': True}

    @patch('plexus.dashboard.api.models.procedure.Procedure')
    def test_run_raises_on_procedure_not_found(self, mock_procedure_class, procedure_primitive):
        """Test run() raises RuntimeError when procedure not found."""
        mock_procedure_class.get_by_id.side_effect = ValueError("Could not find Procedure with ID test-proc")

        with pytest.raises(RuntimeError, match="Failed to run sub-procedure"):
            procedure_primitive.run('test-proc')

    @patch('plexus.dashboard.api.models.procedure.Procedure')
    @patch('plexus.cli.procedure.lua_dsl.runtime.LuaDSLRuntime')
    @patch('plexus.cli.procedure.lua_dsl.primitives.procedure.asyncio.run')
    def test_run_raises_on_execution_error(
        self,
        mock_asyncio_run,
        mock_runtime_class,
        mock_procedure_class,
        procedure_primitive,
        mock_procedure
    ):
        """Test run() raises RuntimeError on execution failure."""
        mock_procedure_class.get_by_id.return_value = mock_procedure
        mock_asyncio_run.side_effect = Exception("Execution failed")

        with pytest.raises(RuntimeError, match="Failed to run sub-procedure"):
            procedure_primitive.run('sub-proc-123')

    @patch('plexus.dashboard.api.models.procedure.Procedure')
    @patch('plexus.cli.procedure.lua_dsl.runtime.LuaDSLRuntime')
    @patch('plexus.cli.procedure.lua_dsl.primitives.procedure.asyncio.run')
    def test_run_with_lua_table_params(
        self,
        mock_asyncio_run,
        mock_runtime_class,
        mock_procedure_class,
        procedure_primitive,
        mock_procedure
    ):
        """Test run() converts Lua table parameters to Python dict."""
        from lupa import LuaRuntime
        lua = LuaRuntime(unpack_returned_tuples=True)

        # Create Lua table
        lua_table = lua.eval('{name = "test", value = 42}')

        mock_procedure_class.get_by_id.return_value = mock_procedure
        mock_asyncio_run.return_value = {'success': True}

        result = procedure_primitive.run('sub-proc-123', lua_table)

        # Verify Lua table was converted
        assert result == {'success': True}

    def test_run_returns_lua_table_when_sandbox_present(self, mock_client, mock_mcp_server):
        """Test run() returns Lua table when lua_sandbox is provided."""
        mock_lua_sandbox = Mock()
        mock_lua_sandbox.lua.table = Mock(return_value={})

        prim = ProcedurePrimitive(
            client=mock_client,
            account_id='test-account',
            parent_procedure_id='parent-proc',
            mcp_server=mock_mcp_server,
            lua_sandbox=mock_lua_sandbox
        )

        mock_procedure = Mock()
        mock_procedure.code = 'test'

        with patch('plexus.dashboard.api.models.procedure.Procedure') as mock_proc_class:
            with patch('plexus.cli.procedure.lua_dsl.runtime.LuaDSLRuntime'):
                with patch('plexus.cli.procedure.lua_dsl.primitives.procedure.asyncio.run') as mock_run:
                    mock_proc_class.get_by_id.return_value = mock_procedure
                    mock_run.return_value = {'key': 'value'}

                    result = prim.run('sub-proc-123')

                    # Verify Lua table creation was called
                    mock_lua_sandbox.lua.table.assert_called()


class TestProcedureSpawn:
    """Test asynchronous procedure spawning with Procedure.spawn()."""

    @pytest.fixture
    def mock_client(self):
        """Create mock client."""
        return Mock()

    @pytest.fixture
    def mock_mcp_server(self):
        """Create mock MCP server."""
        return Mock()

    @pytest.fixture
    def procedure_primitive(self, mock_client, mock_mcp_server):
        """Create ProcedurePrimitive."""
        return ProcedurePrimitive(
            client=mock_client,
            account_id='test-account',
            parent_procedure_id='parent-proc',
            mcp_server=mock_mcp_server
        )

    @patch('plexus.dashboard.api.models.procedure.Procedure')
    @patch('plexus.cli.procedure.lua_dsl.primitives.procedure.asyncio.get_running_loop')
    def test_spawn_creates_task(self, mock_get_loop, mock_procedure_class, procedure_primitive):
        """Test spawn() creates an asyncio task."""
        mock_procedure = Mock()
        mock_procedure.code = 'test'
        mock_procedure_class.get_by_id.return_value = mock_procedure

        # Mock event loop
        mock_loop = Mock()
        mock_task = Mock()
        mock_loop.create_task.return_value = mock_task
        mock_get_loop.return_value = mock_loop

        # Spawn procedure
        task_id = procedure_primitive.spawn('sub-proc-123', {'param': 'value'})

        # Verify task was spawned
        assert task_id in procedure_primitive._spawned_procedures
        task_info = procedure_primitive._spawned_procedures[task_id]
        assert task_info['procedure_id'] == 'sub-proc-123'
        assert task_info['params'] == {'param': 'value'}
        assert task_info['status'] == 'RUNNING'
        assert task_info['task'] == mock_task
        assert 'message_queue' in task_info

    @patch('plexus.dashboard.api.models.procedure.Procedure')
    @patch('plexus.cli.procedure.lua_dsl.primitives.procedure.asyncio.get_running_loop')
    def test_spawn_returns_task_id(self, mock_get_loop, mock_procedure_class, procedure_primitive):
        """Test spawn() returns a valid task ID."""
        mock_procedure = Mock()
        mock_procedure.code = 'test'
        mock_procedure_class.get_by_id.return_value = mock_procedure

        mock_loop = Mock()
        mock_loop.create_task.return_value = Mock()
        mock_get_loop.return_value = mock_loop

        task_id = procedure_primitive.spawn('sub-proc-123')

        assert isinstance(task_id, str)
        assert len(task_id) > 0

    @patch('plexus.dashboard.api.models.procedure.Procedure')
    @patch('plexus.cli.procedure.lua_dsl.primitives.procedure.asyncio.get_running_loop')
    def test_spawn_without_event_loop(self, mock_get_loop, mock_procedure_class, procedure_primitive):
        """Test spawn() when not in async context."""
        mock_procedure = Mock()
        mock_procedure.code = 'test'
        mock_procedure_class.get_by_id.return_value = mock_procedure

        # Simulate no event loop
        mock_get_loop.side_effect = RuntimeError("No running event loop")

        task_id = procedure_primitive.spawn('sub-proc-123')

        # Should still create task info with PENDING status
        task_info = procedure_primitive._spawned_procedures[task_id]
        assert task_info['status'] == 'PENDING'
        assert task_info['task'] is None
        assert task_info['coroutine'] is not None

    @patch('plexus.dashboard.api.models.procedure.Procedure')
    def test_spawn_raises_on_procedure_not_found(self, mock_procedure_class, procedure_primitive):
        """Test spawn() raises RuntimeError when procedure not found."""
        mock_procedure_class.get_by_id.side_effect = ValueError("Not found")

        with pytest.raises(RuntimeError, match="Failed to spawn sub-procedure"):
            procedure_primitive.spawn('invalid-proc')

    @patch('plexus.dashboard.api.models.procedure.Procedure')
    @patch('plexus.cli.procedure.lua_dsl.primitives.procedure.asyncio.get_running_loop')
    def test_spawn_multiple_procedures(self, mock_get_loop, mock_procedure_class, procedure_primitive):
        """Test spawning multiple procedures."""
        mock_procedure = Mock()
        mock_procedure.code = 'test'
        mock_procedure_class.get_by_id.return_value = mock_procedure

        mock_loop = Mock()
        mock_loop.create_task.return_value = Mock()
        mock_get_loop.return_value = mock_loop

        task_id1 = procedure_primitive.spawn('proc-1')
        task_id2 = procedure_primitive.spawn('proc-2')
        task_id3 = procedure_primitive.spawn('proc-3')

        assert len(procedure_primitive._spawned_procedures) == 3
        assert task_id1 != task_id2 != task_id3


class TestProcedureWait:
    """Test waiting for procedure completion with Procedure.wait()."""

    @pytest.fixture
    def procedure_primitive(self):
        """Create ProcedurePrimitive with mock dependencies."""
        return ProcedurePrimitive(
            client=Mock(),
            account_id='test-account',
            parent_procedure_id='parent-proc',
            mcp_server=Mock()
        )

    def test_wait_raises_on_invalid_task_id(self, procedure_primitive):
        """Test wait() raises RuntimeError for invalid task ID."""
        with pytest.raises(RuntimeError, match="Task .* not found"):
            procedure_primitive.wait('invalid-task-id')

    def test_wait_returns_cached_result_if_already_completed(self, procedure_primitive):
        """Test wait() returns cached result if task already completed."""
        task_id = 'test-task-123'
        procedure_primitive._spawned_procedures[task_id] = {
            'status': 'COMPLETED',
            'result': {'success': True, 'data': 'cached'}
        }

        result = procedure_primitive.wait(task_id)

        assert result == {'success': True, 'data': 'cached'}

    @patch('plexus.cli.procedure.lua_dsl.primitives.procedure.asyncio.run')
    def test_wait_with_asyncio_task(self, mock_asyncio_run, procedure_primitive):
        """Test wait() waits for asyncio task to complete."""
        mock_task = Mock()
        mock_task.done.return_value = False
        mock_asyncio_run.return_value = {'success': True, 'result': 'completed'}

        task_id = 'test-task-123'
        procedure_primitive._spawned_procedures[task_id] = {
            'status': 'RUNNING',
            'task': mock_task,
            'result': None
        }

        result = procedure_primitive.wait(task_id)

        assert result == {'success': True, 'result': 'completed'}
        assert procedure_primitive._spawned_procedures[task_id]['status'] == 'COMPLETED'

    @patch('plexus.cli.procedure.lua_dsl.primitives.procedure.asyncio.run')
    def test_wait_with_timeout(self, mock_asyncio_run, procedure_primitive):
        """Test wait() with timeout parameter."""
        mock_task = Mock()
        mock_asyncio_run.side_effect = asyncio.TimeoutError()

        task_id = 'test-task-123'
        procedure_primitive._spawned_procedures[task_id] = {
            'status': 'RUNNING',
            'task': mock_task
        }

        with pytest.raises(TimeoutError, match="timed out after"):
            procedure_primitive.wait(task_id, timeout=5.0)

        assert procedure_primitive._spawned_procedures[task_id]['status'] == 'TIMEOUT'

    @patch('plexus.cli.procedure.lua_dsl.primitives.procedure.asyncio.run')
    def test_wait_with_task_failure(self, mock_asyncio_run, procedure_primitive):
        """Test wait() handles task execution failure."""
        mock_task = Mock()
        mock_asyncio_run.side_effect = Exception("Task execution failed")

        task_id = 'test-task-123'
        procedure_primitive._spawned_procedures[task_id] = {
            'status': 'RUNNING',
            'task': mock_task
        }

        with pytest.raises(RuntimeError, match="Task .* failed"):
            procedure_primitive.wait(task_id)

        assert procedure_primitive._spawned_procedures[task_id]['status'] == 'FAILED'

    def test_wait_without_task_object(self, procedure_primitive):
        """Test wait() when task has no asyncio task object."""
        task_id = 'test-task-123'
        procedure_primitive._spawned_procedures[task_id] = {
            'status': 'PENDING',
            'task': None
        }

        result = procedure_primitive.wait(task_id)

        assert result['success'] is False
        assert 'no event loop available' in result['error']


class TestProcedureStatus:
    """Test checking procedure status with Procedure.status()."""

    @pytest.fixture
    def procedure_primitive(self):
        """Create ProcedurePrimitive."""
        return ProcedurePrimitive(
            client=Mock(),
            account_id='test-account',
            parent_procedure_id='parent-proc',
            mcp_server=Mock()
        )

    def test_status_raises_on_invalid_task_id(self, procedure_primitive):
        """Test status() raises RuntimeError for invalid task ID."""
        with pytest.raises(RuntimeError, match="Task .* not found"):
            procedure_primitive.status('invalid-task-id')

    def test_status_returns_running(self, procedure_primitive):
        """Test status() returns RUNNING for active task."""
        mock_task = Mock()
        mock_task.done.return_value = False

        task_id = 'test-task-123'
        procedure_primitive._spawned_procedures[task_id] = {
            'status': 'RUNNING',
            'task': mock_task
        }

        status = procedure_primitive.status(task_id)

        assert status == 'RUNNING'

    def test_status_returns_completed(self, procedure_primitive):
        """Test status() returns COMPLETED for finished task."""
        mock_task = Mock()
        mock_task.done.return_value = True
        mock_task.cancelled.return_value = False
        mock_task.exception.return_value = None
        mock_task.result.return_value = {'success': True}

        task_id = 'test-task-123'
        procedure_primitive._spawned_procedures[task_id] = {
            'status': 'RUNNING',
            'task': mock_task
        }

        status = procedure_primitive.status(task_id)

        assert status == 'COMPLETED'
        assert procedure_primitive._spawned_procedures[task_id]['result'] == {'success': True}

    def test_status_returns_cancelled(self, procedure_primitive):
        """Test status() returns CANCELLED for cancelled task."""
        mock_task = Mock()
        mock_task.done.return_value = True
        mock_task.cancelled.return_value = True

        task_id = 'test-task-123'
        procedure_primitive._spawned_procedures[task_id] = {
            'status': 'RUNNING',
            'task': mock_task
        }

        status = procedure_primitive.status(task_id)

        assert status == 'CANCELLED'

    def test_status_returns_failed(self, procedure_primitive):
        """Test status() returns FAILED for task with exception."""
        mock_task = Mock()
        mock_task.done.return_value = True
        mock_task.cancelled.return_value = False
        mock_task.exception.return_value = Exception("Task failed")

        task_id = 'test-task-123'
        procedure_primitive._spawned_procedures[task_id] = {
            'status': 'RUNNING',
            'task': mock_task
        }

        status = procedure_primitive.status(task_id)

        assert status == 'FAILED'
        assert 'Task failed' in procedure_primitive._spawned_procedures[task_id]['error']

    def test_status_without_task_object(self, procedure_primitive):
        """Test status() returns stored status when no task object."""
        task_id = 'test-task-123'
        procedure_primitive._spawned_procedures[task_id] = {
            'status': 'PENDING',
            'task': None
        }

        status = procedure_primitive.status(task_id)

        assert status == 'PENDING'


class TestProcedureCancel:
    """Test cancelling procedures with Procedure.cancel()."""

    @pytest.fixture
    def procedure_primitive(self):
        """Create ProcedurePrimitive."""
        return ProcedurePrimitive(
            client=Mock(),
            account_id='test-account',
            parent_procedure_id='parent-proc',
            mcp_server=Mock()
        )

    def test_cancel_raises_on_invalid_task_id(self, procedure_primitive):
        """Test cancel() raises RuntimeError for invalid task ID."""
        with pytest.raises(RuntimeError, match="Task .* not found"):
            procedure_primitive.cancel('invalid-task-id')

    def test_cancel_running_task(self, procedure_primitive):
        """Test cancel() successfully cancels running task."""
        mock_task = Mock()
        mock_task.done.return_value = False
        mock_task.cancel.return_value = True

        task_id = 'test-task-123'
        procedure_primitive._spawned_procedures[task_id] = {
            'status': 'RUNNING',
            'task': mock_task
        }

        result = procedure_primitive.cancel(task_id)

        assert result is True
        assert procedure_primitive._spawned_procedures[task_id]['status'] == 'CANCELLED'
        mock_task.cancel.assert_called_once()

    def test_cancel_already_completed_task(self, procedure_primitive):
        """Test cancel() returns False for already completed task."""
        task_id = 'test-task-123'
        procedure_primitive._spawned_procedures[task_id] = {
            'status': 'COMPLETED',
            'task': Mock()
        }

        result = procedure_primitive.cancel(task_id)

        assert result is False

    def test_cancel_already_failed_task(self, procedure_primitive):
        """Test cancel() returns False for already failed task."""
        task_id = 'test-task-123'
        procedure_primitive._spawned_procedures[task_id] = {
            'status': 'FAILED',
            'task': Mock()
        }

        result = procedure_primitive.cancel(task_id)

        assert result is False

    def test_cancel_already_cancelled_task(self, procedure_primitive):
        """Test cancel() returns False for already cancelled task."""
        task_id = 'test-task-123'
        procedure_primitive._spawned_procedures[task_id] = {
            'status': 'CANCELLED',
            'task': Mock()
        }

        result = procedure_primitive.cancel(task_id)

        assert result is False

    def test_cancel_task_that_failed_to_cancel(self, procedure_primitive):
        """Test cancel() when asyncio task cancel fails."""
        mock_task = Mock()
        mock_task.done.return_value = False
        mock_task.cancel.return_value = False

        task_id = 'test-task-123'
        procedure_primitive._spawned_procedures[task_id] = {
            'status': 'RUNNING',
            'task': mock_task
        }

        result = procedure_primitive.cancel(task_id)

        assert result is False

    def test_cancel_without_task_object(self, procedure_primitive):
        """Test cancel() marks task as cancelled when no task object."""
        task_id = 'test-task-123'
        procedure_primitive._spawned_procedures[task_id] = {
            'status': 'PENDING',
            'task': None
        }

        result = procedure_primitive.cancel(task_id)

        assert result is True
        assert procedure_primitive._spawned_procedures[task_id]['status'] == 'CANCELLED'


class TestProcedureInject:
    """Test injecting messages with Procedure.inject()."""

    @pytest.fixture
    def procedure_primitive(self):
        """Create ProcedurePrimitive."""
        return ProcedurePrimitive(
            client=Mock(),
            account_id='test-account',
            parent_procedure_id='parent-proc',
            mcp_server=Mock()
        )

    def test_inject_raises_on_invalid_task_id(self, procedure_primitive):
        """Test inject() raises RuntimeError for invalid task ID."""
        with pytest.raises(RuntimeError, match="Task .* not found"):
            procedure_primitive.inject('invalid-task-id', 'message')

    def test_inject_to_running_task(self, procedure_primitive):
        """Test inject() successfully injects message to running task."""
        task_id = 'test-task-123'
        message_queue = asyncio.Queue(maxsize=100)

        procedure_primitive._spawned_procedures[task_id] = {
            'status': 'RUNNING',
            'task': Mock(),
            'message_queue': message_queue
        }

        result = procedure_primitive.inject(task_id, 'Test message')

        assert result is True
        assert message_queue.qsize() == 1

    def test_inject_to_pending_task(self, procedure_primitive):
        """Test inject() can inject to pending task."""
        task_id = 'test-task-123'
        message_queue = asyncio.Queue(maxsize=100)

        procedure_primitive._spawned_procedures[task_id] = {
            'status': 'PENDING',
            'task': None,
            'message_queue': message_queue
        }

        result = procedure_primitive.inject(task_id, 'Test message')

        assert result is True

    def test_inject_to_completed_task_fails(self, procedure_primitive):
        """Test inject() returns False for completed task."""
        task_id = 'test-task-123'
        procedure_primitive._spawned_procedures[task_id] = {
            'status': 'COMPLETED',
            'task': Mock(),
            'message_queue': asyncio.Queue()
        }

        result = procedure_primitive.inject(task_id, 'message')

        assert result is False

    def test_inject_creates_queue_if_missing(self, procedure_primitive):
        """Test inject() creates message queue if not present."""
        task_id = 'test-task-123'
        procedure_primitive._spawned_procedures[task_id] = {
            'status': 'RUNNING',
            'task': Mock()
        }

        result = procedure_primitive.inject(task_id, 'message')

        assert result is True
        assert 'message_queue' in procedure_primitive._spawned_procedures[task_id]

    def test_inject_handles_full_queue(self, procedure_primitive):
        """Test inject() returns False when queue is full."""
        task_id = 'test-task-123'
        message_queue = asyncio.Queue(maxsize=1)
        message_queue.put_nowait({'type': 'existing'})

        procedure_primitive._spawned_procedures[task_id] = {
            'status': 'RUNNING',
            'task': Mock(),
            'message_queue': message_queue
        }

        result = procedure_primitive.inject(task_id, 'message')

        assert result is False


class TestProcedureWaitAny:
    """Test race pattern with Procedure.wait_any()."""

    @pytest.fixture
    def procedure_primitive(self):
        """Create ProcedurePrimitive."""
        return ProcedurePrimitive(
            client=Mock(),
            account_id='test-account',
            parent_procedure_id='parent-proc',
            mcp_server=Mock()
        )

    def test_wait_any_raises_on_empty_handles(self, procedure_primitive):
        """Test wait_any() raises RuntimeError for empty handle list."""
        with pytest.raises(RuntimeError, match="No handles provided"):
            procedure_primitive.wait_any([])

    def test_wait_any_raises_on_invalid_handle(self, procedure_primitive):
        """Test wait_any() raises RuntimeError for invalid handle."""
        with pytest.raises(RuntimeError, match="Task .* not found"):
            procedure_primitive.wait_any(['invalid-handle'])

    def test_wait_any_returns_already_completed_task(self, procedure_primitive):
        """Test wait_any() returns immediately if task already completed."""
        task_id1 = 'task-1'
        task_id2 = 'task-2'

        procedure_primitive._spawned_procedures[task_id1] = {
            'status': 'COMPLETED',
            'result': {'success': True, 'data': 'first'}
        }
        procedure_primitive._spawned_procedures[task_id2] = {
            'status': 'RUNNING',
            'task': Mock()
        }

        handle, result = procedure_primitive.wait_any([task_id1, task_id2])

        assert handle == task_id1
        assert result == {'success': True, 'data': 'first'}

    @patch('plexus.cli.procedure.lua_dsl.primitives.procedure.asyncio.run')
    def test_wait_any_waits_for_first_completion(self, mock_asyncio_run, procedure_primitive):
        """Test wait_any() waits for first task to complete."""
        task_id1 = 'task-1'
        task_id2 = 'task-2'

        mock_task1 = Mock()
        mock_task2 = Mock()
        mock_task1.done.return_value = False
        mock_task2.done.return_value = False
        mock_task1.result.return_value = {'success': True, 'winner': 'task1'}

        procedure_primitive._spawned_procedures[task_id1] = {
            'status': 'RUNNING',
            'task': mock_task1
        }
        procedure_primitive._spawned_procedures[task_id2] = {
            'status': 'RUNNING',
            'task': mock_task2
        }

        # Mock asyncio.wait to return task1 as done
        mock_asyncio_run.return_value = (set([mock_task1]), set([mock_task2]))

        handle, result = procedure_primitive.wait_any([task_id1, task_id2])

        assert handle == task_id1
        assert result == {'success': True, 'winner': 'task1'}

    @patch('plexus.cli.procedure.lua_dsl.primitives.procedure.asyncio.run')
    def test_wait_any_with_timeout(self, mock_asyncio_run, procedure_primitive):
        """Test wait_any() raises TimeoutError on timeout."""
        task_id = 'task-1'
        mock_task = Mock()
        mock_task.done.return_value = False

        procedure_primitive._spawned_procedures[task_id] = {
            'status': 'RUNNING',
            'task': mock_task
        }

        # Mock asyncio.wait to return empty done set (timeout)
        mock_asyncio_run.return_value = (set(), set([mock_task]))

        with pytest.raises(TimeoutError, match="No tasks completed within"):
            procedure_primitive.wait_any([task_id], timeout=5.0)

    def test_wait_any_with_all_completed(self, procedure_primitive):
        """Test wait_any() returns first when all already completed."""
        task_id1 = 'task-1'
        task_id2 = 'task-2'

        procedure_primitive._spawned_procedures[task_id1] = {
            'status': 'COMPLETED',
            'result': {'data': 'first'}
        }
        procedure_primitive._spawned_procedures[task_id2] = {
            'status': 'COMPLETED',
            'result': {'data': 'second'}
        }

        handle, result = procedure_primitive.wait_any([task_id1, task_id2])

        assert handle == task_id1
        assert result == {'data': 'first'}


class TestProcedureWaitAll:
    """Test fan-in pattern with Procedure.wait_all()."""

    @pytest.fixture
    def procedure_primitive(self):
        """Create ProcedurePrimitive."""
        return ProcedurePrimitive(
            client=Mock(),
            account_id='test-account',
            parent_procedure_id='parent-proc',
            mcp_server=Mock()
        )

    def test_wait_all_raises_on_empty_handles(self, procedure_primitive):
        """Test wait_all() raises RuntimeError for empty handle list."""
        with pytest.raises(RuntimeError, match="No handles provided"):
            procedure_primitive.wait_all([])

    def test_wait_all_raises_on_invalid_handle(self, procedure_primitive):
        """Test wait_all() raises RuntimeError for invalid handle."""
        with pytest.raises(RuntimeError, match="Task .* not found"):
            procedure_primitive.wait_all(['invalid-handle'])

    def test_wait_all_returns_all_completed(self, procedure_primitive):
        """Test wait_all() returns all results when already completed."""
        task_id1 = 'task-1'
        task_id2 = 'task-2'

        procedure_primitive._spawned_procedures[task_id1] = {
            'status': 'COMPLETED',
            'result': {'data': 'first'}
        }
        procedure_primitive._spawned_procedures[task_id2] = {
            'status': 'COMPLETED',
            'result': {'data': 'second'}
        }

        results = procedure_primitive.wait_all([task_id1, task_id2])

        assert results[task_id1] == {'data': 'first'}
        assert results[task_id2] == {'data': 'second'}

    @patch('plexus.cli.procedure.lua_dsl.primitives.procedure.asyncio.run')
    def test_wait_all_waits_for_all_tasks(self, mock_asyncio_run, procedure_primitive):
        """Test wait_all() waits for all tasks to complete."""
        task_id1 = 'task-1'
        task_id2 = 'task-2'

        mock_task1 = Mock()
        mock_task2 = Mock()
        mock_task1.done.return_value = False
        mock_task2.done.return_value = False
        mock_task1.result.return_value = {'result': 'first'}
        mock_task2.result.return_value = {'result': 'second'}

        procedure_primitive._spawned_procedures[task_id1] = {
            'status': 'RUNNING',
            'task': mock_task1
        }
        procedure_primitive._spawned_procedures[task_id2] = {
            'status': 'RUNNING',
            'task': mock_task2
        }

        # Mock asyncio.wait to return all as done
        mock_asyncio_run.return_value = (set([mock_task1, mock_task2]), set())

        results = procedure_primitive.wait_all([task_id1, task_id2])

        assert results[task_id1] == {'result': 'first'}
        assert results[task_id2] == {'result': 'second'}

    @patch('plexus.cli.procedure.lua_dsl.primitives.procedure.asyncio.run')
    def test_wait_all_handles_task_failure(self, mock_asyncio_run, procedure_primitive):
        """Test wait_all() handles task failures gracefully."""
        task_id1 = 'task-1'
        task_id2 = 'task-2'

        mock_task1 = Mock()
        mock_task2 = Mock()
        # Set done() to False so tasks get added to pending_tasks dict
        mock_task1.done.return_value = False
        mock_task2.done.return_value = False
        mock_task1.result.return_value = {'success': True}
        mock_task2.result.side_effect = Exception("Task failed")

        procedure_primitive._spawned_procedures[task_id1] = {
            'status': 'RUNNING',
            'task': mock_task1
        }
        procedure_primitive._spawned_procedures[task_id2] = {
            'status': 'RUNNING',
            'task': mock_task2
        }

        mock_asyncio_run.return_value = (set([mock_task1, mock_task2]), set())

        results = procedure_primitive.wait_all([task_id1, task_id2])

        assert results[task_id1] == {'success': True}
        assert results[task_id2]['success'] is False
        assert 'Task failed' in results[task_id2]['error']

    @patch('plexus.cli.procedure.lua_dsl.primitives.procedure.asyncio.run')
    def test_wait_all_with_timeout(self, mock_asyncio_run, procedure_primitive):
        """Test wait_all() handles timeout with partial results."""
        task_id1 = 'task-1'
        task_id2 = 'task-2'

        mock_task1 = Mock()
        mock_task2 = Mock()
        # Set done() to False so tasks get added to pending_tasks dict
        mock_task1.done.return_value = False
        mock_task2.done.return_value = False
        mock_task1.result.return_value = {'success': True}

        procedure_primitive._spawned_procedures[task_id1] = {
            'status': 'RUNNING',
            'task': mock_task1
        }
        procedure_primitive._spawned_procedures[task_id2] = {
            'status': 'RUNNING',
            'task': mock_task2
        }

        # Mock timeout: task1 done, task2 pending
        mock_asyncio_run.return_value = (set([mock_task1]), set([mock_task2]))

        results = procedure_primitive.wait_all([task_id1, task_id2], timeout=5.0)

        assert results[task_id1] == {'success': True}
        assert results[task_id2]['status'] == 'TIMEOUT'

    def test_wait_all_with_mixed_states(self, procedure_primitive):
        """Test wait_all() with tasks in different states."""
        task_id1 = 'task-1'
        task_id2 = 'task-2'
        task_id3 = 'task-3'

        mock_task = Mock()
        mock_task.done.return_value = False
        mock_task.result.return_value = {'result': 'third'}

        procedure_primitive._spawned_procedures[task_id1] = {
            'status': 'COMPLETED',
            'result': {'result': 'first'}
        }
        procedure_primitive._spawned_procedures[task_id2] = {
            'status': 'FAILED',
            'result': {'success': False}
        }
        procedure_primitive._spawned_procedures[task_id3] = {
            'status': 'RUNNING',
            'task': mock_task
        }

        with patch('plexus.cli.procedure.lua_dsl.primitives.procedure.asyncio.run') as mock_run:
            mock_run.return_value = (set([mock_task]), set())

            results = procedure_primitive.wait_all([task_id1, task_id2, task_id3])

            assert len(results) == 3
            assert results[task_id1] == {'result': 'first'}
            assert results[task_id2] == {'success': False}
            assert results[task_id3] == {'result': 'third'}


class TestProcedureIsComplete:
    """Test checking single task completion with Procedure.is_complete()."""

    @pytest.fixture
    def procedure_primitive(self):
        """Create ProcedurePrimitive."""
        return ProcedurePrimitive(
            client=Mock(),
            account_id='test-account',
            parent_procedure_id='parent-proc',
            mcp_server=Mock()
        )

    def test_is_complete_raises_on_invalid_handle(self, procedure_primitive):
        """Test is_complete() raises RuntimeError for invalid handle."""
        with pytest.raises(RuntimeError, match="Task .* not found"):
            procedure_primitive.is_complete('invalid-handle')

    def test_is_complete_returns_true_for_completed(self, procedure_primitive):
        """Test is_complete() returns True for completed task."""
        task_id = 'task-1'
        procedure_primitive._spawned_procedures[task_id] = {
            'status': 'COMPLETED',
            'task': Mock()
        }

        assert procedure_primitive.is_complete(task_id) is True

    def test_is_complete_returns_true_for_failed(self, procedure_primitive):
        """Test is_complete() returns True for failed task."""
        task_id = 'task-1'
        procedure_primitive._spawned_procedures[task_id] = {
            'status': 'FAILED',
            'task': Mock()
        }

        assert procedure_primitive.is_complete(task_id) is True

    def test_is_complete_returns_true_for_cancelled(self, procedure_primitive):
        """Test is_complete() returns True for cancelled task."""
        task_id = 'task-1'
        procedure_primitive._spawned_procedures[task_id] = {
            'status': 'CANCELLED',
            'task': Mock()
        }

        assert procedure_primitive.is_complete(task_id) is True

    def test_is_complete_returns_true_for_timeout(self, procedure_primitive):
        """Test is_complete() returns True for timeout status."""
        task_id = 'task-1'
        procedure_primitive._spawned_procedures[task_id] = {
            'status': 'TIMEOUT',
            'task': Mock()
        }

        assert procedure_primitive.is_complete(task_id) is True

    def test_is_complete_returns_false_for_running(self, procedure_primitive):
        """Test is_complete() returns False for running task."""
        mock_task = Mock()
        mock_task.done.return_value = False

        task_id = 'task-1'
        procedure_primitive._spawned_procedures[task_id] = {
            'status': 'RUNNING',
            'task': mock_task
        }

        assert procedure_primitive.is_complete(task_id) is False

    def test_is_complete_returns_false_for_pending(self, procedure_primitive):
        """Test is_complete() returns False for pending task."""
        task_id = 'task-1'
        procedure_primitive._spawned_procedures[task_id] = {
            'status': 'PENDING',
            'task': None
        }

        assert procedure_primitive.is_complete(task_id) is False

    def test_is_complete_updates_status_from_task(self, procedure_primitive):
        """Test is_complete() updates status by calling status()."""
        mock_task = Mock()
        mock_task.done.return_value = True
        mock_task.cancelled.return_value = False
        mock_task.exception.return_value = None
        mock_task.result.return_value = {'success': True}

        task_id = 'task-1'
        procedure_primitive._spawned_procedures[task_id] = {
            'status': 'RUNNING',
            'task': mock_task
        }

        # First call updates status
        result = procedure_primitive.is_complete(task_id)

        assert result is True
        assert procedure_primitive._spawned_procedures[task_id]['status'] == 'COMPLETED'


class TestProcedureAllComplete:
    """Test checking all tasks complete with Procedure.all_complete()."""

    @pytest.fixture
    def procedure_primitive(self):
        """Create ProcedurePrimitive."""
        return ProcedurePrimitive(
            client=Mock(),
            account_id='test-account',
            parent_procedure_id='parent-proc',
            mcp_server=Mock()
        )

    def test_all_complete_returns_true_for_empty_list(self, procedure_primitive):
        """Test all_complete() returns True for empty list."""
        assert procedure_primitive.all_complete([]) is True

    def test_all_complete_returns_true_when_all_done(self, procedure_primitive):
        """Test all_complete() returns True when all tasks complete."""
        task_id1 = 'task-1'
        task_id2 = 'task-2'
        task_id3 = 'task-3'

        procedure_primitive._spawned_procedures[task_id1] = {
            'status': 'COMPLETED',
            'task': Mock()
        }
        procedure_primitive._spawned_procedures[task_id2] = {
            'status': 'FAILED',
            'task': Mock()
        }
        procedure_primitive._spawned_procedures[task_id3] = {
            'status': 'CANCELLED',
            'task': Mock()
        }

        assert procedure_primitive.all_complete([task_id1, task_id2, task_id3]) is True

    def test_all_complete_returns_false_when_any_running(self, procedure_primitive):
        """Test all_complete() returns False when any task still running."""
        task_id1 = 'task-1'
        task_id2 = 'task-2'

        mock_task = Mock()
        mock_task.done.return_value = False

        procedure_primitive._spawned_procedures[task_id1] = {
            'status': 'COMPLETED',
            'task': Mock()
        }
        procedure_primitive._spawned_procedures[task_id2] = {
            'status': 'RUNNING',
            'task': mock_task
        }

        assert procedure_primitive.all_complete([task_id1, task_id2]) is False

    def test_all_complete_with_single_task(self, procedure_primitive):
        """Test all_complete() with single task."""
        task_id = 'task-1'
        procedure_primitive._spawned_procedures[task_id] = {
            'status': 'COMPLETED',
            'task': Mock()
        }

        assert procedure_primitive.all_complete([task_id]) is True

    def test_all_complete_checks_all_handles(self, procedure_primitive):
        """Test all_complete() checks all provided handles."""
        task_ids = [f'task-{i}' for i in range(5)]

        # All complete except last one
        for i, task_id in enumerate(task_ids):
            if i < 4:
                procedure_primitive._spawned_procedures[task_id] = {
                    'status': 'COMPLETED',
                    'task': Mock()
                }
            else:
                mock_task = Mock()
                mock_task.done.return_value = False
                procedure_primitive._spawned_procedures[task_id] = {
                    'status': 'RUNNING',
                    'task': mock_task
                }

        assert procedure_primitive.all_complete(task_ids) is False


class TestLuaTableConversion:
    """Test Lua table conversion helpers."""

    @pytest.fixture
    def procedure_primitive(self):
        """Create ProcedurePrimitive."""
        return ProcedurePrimitive(
            client=Mock(),
            account_id='test-account',
            parent_procedure_id='parent-proc',
            mcp_server=Mock()
        )

    @pytest.fixture
    def procedure_primitive_with_lua(self):
        """Create ProcedurePrimitive with Lua sandbox."""
        mock_lua_sandbox = Mock()
        mock_lua_sandbox.lua.table = Mock(return_value={})

        return ProcedurePrimitive(
            client=Mock(),
            account_id='test-account',
            parent_procedure_id='parent-proc',
            mcp_server=Mock(),
            lua_sandbox=mock_lua_sandbox
        )

    def test_lua_to_python_with_dict(self, procedure_primitive):
        """Test _lua_to_python converts Lua table to Python dict."""
        from lupa import LuaRuntime
        lua = LuaRuntime(unpack_returned_tuples=True)

        lua_table = lua.eval('{name = "test", value = 42, nested = {key = "val"}}')

        result = procedure_primitive._lua_to_python(lua_table)

        assert isinstance(result, dict)
        assert result['name'] == 'test'
        assert result['value'] == 42
        assert result['nested']['key'] == 'val'

    def test_lua_to_python_with_array(self, procedure_primitive):
        """Test _lua_to_python converts Lua array to Python list."""
        from lupa import LuaRuntime
        lua = LuaRuntime(unpack_returned_tuples=True)

        lua_array = lua.eval('{1, 2, 3, 4, 5}')

        result = procedure_primitive._lua_to_python(lua_array)

        assert isinstance(result, list)
        assert result == [1, 2, 3, 4, 5]

    def test_lua_to_python_with_non_table(self, procedure_primitive):
        """Test _lua_to_python passes through non-table values."""
        assert procedure_primitive._lua_to_python(42) == 42
        assert procedure_primitive._lua_to_python("string") == "string"
        assert procedure_primitive._lua_to_python(None) is None

    def test_python_to_lua_without_sandbox(self, procedure_primitive):
        """Test _python_to_lua returns unchanged when no sandbox."""
        data = {'key': 'value'}
        result = procedure_primitive._python_to_lua(data)
        assert result == data

    def test_python_to_lua_with_dict(self, procedure_primitive_with_lua):
        """Test _python_to_lua converts Python dict to Lua table."""
        data = {'key': 'value', 'num': 42}

        result = procedure_primitive_with_lua._python_to_lua(data)

        # Verify table creation was called
        procedure_primitive_with_lua.lua_sandbox.lua.table.assert_called()

    def test_python_to_lua_with_list(self, procedure_primitive_with_lua):
        """Test _python_to_lua converts Python list to Lua array."""
        data = [1, 2, 3, 4, 5]

        result = procedure_primitive_with_lua._python_to_lua(data)

        # Verify table creation was called for array
        procedure_primitive_with_lua.lua_sandbox.lua.table.assert_called()

    def test_python_to_lua_with_nested_structures(self, procedure_primitive_with_lua):
        """Test _python_to_lua handles nested structures."""
        data = {
            'outer': {
                'inner': [1, 2, 3],
                'name': 'test'
            },
            'items': ['a', 'b', 'c']
        }

        result = procedure_primitive_with_lua._python_to_lua(data)

        # Multiple table creations for nested structures
        assert procedure_primitive_with_lua.lua_sandbox.lua.table.call_count > 1


class TestProcedureEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.fixture
    def procedure_primitive(self):
        """Create ProcedurePrimitive."""
        return ProcedurePrimitive(
            client=Mock(),
            account_id='test-account',
            parent_procedure_id='parent-proc',
            mcp_server=Mock()
        )

    def test_multiple_waits_on_same_task(self, procedure_primitive):
        """Test calling wait() multiple times on same completed task."""
        task_id = 'task-1'
        procedure_primitive._spawned_procedures[task_id] = {
            'status': 'COMPLETED',
            'result': {'data': 'cached'}
        }

        result1 = procedure_primitive.wait(task_id)
        result2 = procedure_primitive.wait(task_id)

        assert result1 == result2 == {'data': 'cached'}

    def test_status_after_cancel(self, procedure_primitive):
        """Test status() after cancelling a task."""
        mock_task = Mock()
        mock_task.done.return_value = False
        mock_task.cancel.return_value = True

        task_id = 'task-1'
        procedure_primitive._spawned_procedures[task_id] = {
            'status': 'RUNNING',
            'task': mock_task
        }

        procedure_primitive.cancel(task_id)
        status = procedure_primitive.status(task_id)

        assert status == 'CANCELLED'

    def test_inject_after_cancel(self, procedure_primitive):
        """Test inject() fails after task is cancelled."""
        task_id = 'task-1'
        procedure_primitive._spawned_procedures[task_id] = {
            'status': 'CANCELLED',
            'task': Mock(),
            'message_queue': asyncio.Queue()
        }

        result = procedure_primitive.inject(task_id, 'message')

        assert result is False

    def test_concurrent_spawns(self, procedure_primitive):
        """Test spawning multiple procedures creates unique task IDs."""
        with patch('plexus.dashboard.api.models.procedure.Procedure') as mock_proc:
            mock_proc.get_by_id.return_value = Mock(code='test')
            with patch('plexus.cli.procedure.lua_dsl.primitives.procedure.asyncio.get_running_loop') as mock_loop:
                mock_loop.return_value.create_task.return_value = Mock()

                task_ids = set()
                for i in range(10):
                    task_id = procedure_primitive.spawn(f'proc-{i}')
                    task_ids.add(task_id)

                # All task IDs should be unique
                assert len(task_ids) == 10

    def test_wait_any_with_lua_table_handles(self, procedure_primitive):
        """Test wait_any() converts Lua table of handles to Python list."""
        from lupa import LuaRuntime
        lua = LuaRuntime(unpack_returned_tuples=True)

        task_id1 = 'task-1'
        task_id2 = 'task-2'

        procedure_primitive._spawned_procedures[task_id1] = {
            'status': 'COMPLETED',
            'result': {'data': 'first'}
        }
        procedure_primitive._spawned_procedures[task_id2] = {
            'status': 'RUNNING',
            'task': Mock()
        }

        # Create Lua array of handles
        lua.execute(f'''
            handles = {{"{task_id1}", "{task_id2}"}}
        ''')
        lua_handles = lua.globals().handles

        handle, result = procedure_primitive.wait_any(lua_handles)

        assert handle == task_id1

    def test_wait_all_with_lua_table_handles(self, procedure_primitive):
        """Test wait_all() converts Lua table of handles to Python list."""
        from lupa import LuaRuntime
        lua = LuaRuntime(unpack_returned_tuples=True)

        task_id1 = 'task-1'
        task_id2 = 'task-2'

        procedure_primitive._spawned_procedures[task_id1] = {
            'status': 'COMPLETED',
            'result': {'data': 'first'}
        }
        procedure_primitive._spawned_procedures[task_id2] = {
            'status': 'COMPLETED',
            'result': {'data': 'second'}
        }

        lua.execute(f'''
            handles = {{"{task_id1}", "{task_id2}"}}
        ''')
        lua_handles = lua.globals().handles

        results = procedure_primitive.wait_all(lua_handles)

        assert len(results) == 2
