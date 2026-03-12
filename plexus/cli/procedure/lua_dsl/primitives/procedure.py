"""
Procedure Primitive - Sub-procedure invocation and orchestration.

Provides:
- Procedure.run(procedure_id, params) - Execute sub-procedure synchronously
- Procedure.spawn(procedure_id, params) - Launch sub-procedure asynchronously
- Procedure.wait(procedure_id) - Wait for sub-procedure completion
- Procedure.status(procedure_id) - Check sub-procedure status
- Procedure.cancel(procedure_id) - Cancel running sub-procedure
"""

import logging
import asyncio
import time
from typing import Dict, Any, Optional
from lupa import lua_type

logger = logging.getLogger(__name__)


class ProcedurePrimitive:
    """
    Handles sub-procedure invocation and orchestration.

    Enables workflows to:
    - Execute sub-procedures synchronously or asynchronously
    - Monitor sub-procedure status
    - Cancel running sub-procedures
    - Build hierarchical workflow compositions
    """

    def __init__(self, client, account_id: str, parent_procedure_id: str, mcp_server, openai_api_key: Optional[str] = None, lua_sandbox=None):
        """
        Initialize Procedure primitive.

        Args:
            client: PlexusDashboardClient instance
            account_id: Account ID for procedure operations
            parent_procedure_id: ID of the parent procedure
            mcp_server: MCP server for tool access
            openai_api_key: Optional OpenAI API key
            lua_sandbox: Optional LuaSandbox for Lua table construction
        """
        self.client = client
        self.account_id = account_id
        self.parent_procedure_id = parent_procedure_id
        self.mcp_server = mcp_server
        self.openai_api_key = openai_api_key
        self.lua_sandbox = lua_sandbox

        # Track spawned procedures
        self._spawned_procedures: Dict[str, Dict[str, Any]] = {}

        logger.debug(f"ProcedurePrimitive initialized for parent {parent_procedure_id}")

    def run(self, procedure_id: str, params: Optional[Any] = None) -> Any:
        """
        Execute a sub-procedure synchronously and wait for completion.

        Args:
            procedure_id: ID of the procedure to execute
            params: Optional parameters to pass to the procedure

        Returns:
            Result from the sub-procedure

        Raises:
            RuntimeError: If procedure execution fails

        Example (Lua):
            local result = Procedure.run("score-analysis-proc", {
                scorecard = "compliance",
                days = 7
            })
            Log.info("Sub-procedure complete", {status = result.status})
        """
        logger.info(f"Running sub-procedure {procedure_id} synchronously")

        try:
            # Convert Lua params to Python dict
            python_params = self._lua_to_python(params) if params else {}

            # Get procedure by ID
            from plexus.dashboard.api.models.procedure import Procedure
            procedure = Procedure.get_by_id(procedure_id, self.client)

            # Create new runtime for sub-procedure (automatically gets isolated chat session)
            from plexus.cli.procedure.lua_dsl.runtime import LuaDSLRuntime

            sub_runtime = LuaDSLRuntime(
                procedure_id=procedure_id,
                client=self.client,
                mcp_server=self.mcp_server,
                openai_api_key=self.openai_api_key
            )

            # Execute synchronously (blocks until complete)
            result = asyncio.run(sub_runtime.execute(
                yaml_config=procedure.code,
                context=python_params
            ))

            logger.info(f"Sub-procedure {procedure_id} completed with success: {result.get('success')}")

            # Convert result to Lua table if needed
            if self.lua_sandbox:
                return self._python_to_lua(result)
            else:
                return result

        except Exception as e:
            error_msg = f"Failed to run sub-procedure {procedure_id}: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

    def spawn(self, procedure_id: str, params: Optional[Any] = None) -> str:
        """
        Launch a sub-procedure asynchronously without waiting.

        Args:
            procedure_id: ID of the procedure to execute
            params: Optional parameters to pass to the procedure

        Returns:
            Task ID or execution identifier for the spawned procedure

        Example (Lua):
            local task_id = Procedure.spawn("data-processing", {
                input_file = "/tmp/data.json"
            })
            Log.info("Spawned sub-procedure", {task_id = task_id})

            -- Continue with other work...

            -- Later, wait for completion
            local result = Procedure.wait(task_id)
        """
        logger.info(f"Spawning sub-procedure {procedure_id} asynchronously")

        try:
            # Convert Lua params to Python dict
            python_params = self._lua_to_python(params) if params else {}

            # Get procedure by ID
            from plexus.dashboard.api.models.procedure import Procedure
            procedure = Procedure.get_by_id(procedure_id, self.client)

            # Generate a task ID
            import uuid
            task_id = str(uuid.uuid4())

            # Create async coroutine for sub-procedure execution
            async def run_sub_procedure():
                """Execute sub-procedure with isolated chat session."""
                from plexus.cli.procedure.lua_dsl.runtime import LuaDSLRuntime

                sub_runtime = LuaDSLRuntime(
                    procedure_id=procedure_id,
                    client=self.client,
                    mcp_server=self.mcp_server,
                    openai_api_key=self.openai_api_key
                )

                return await sub_runtime.execute(
                    yaml_config=procedure.code,
                    context=python_params
                )

            # Check if we're in an async context and create task
            try:
                loop = asyncio.get_running_loop()
                task = loop.create_task(run_sub_procedure())
                logger.info(f"Created asyncio task for sub-procedure {procedure_id}")
            except RuntimeError:
                # Not in async context - need to handle this case
                logger.warning(f"Not in async context - cannot spawn truly async task for {procedure_id}")
                # Fall back to storing just the coroutine for later execution
                task = None

            # Store spawn info with task
            self._spawned_procedures[task_id] = {
                'procedure_id': procedure_id,
                'params': python_params,
                'status': 'RUNNING' if task else 'PENDING',
                'started_at': time.time(),
                'task': task,  # Store asyncio.Task object
                'coroutine': run_sub_procedure if not task else None,  # Store coroutine if no event loop
                'result': None,
                'error': None,
                'message_queue': asyncio.Queue(maxsize=100)  # Message queue for inject()
            }

            logger.info(f"Spawned sub-procedure {procedure_id} with task_id {task_id}")
            return task_id

        except Exception as e:
            error_msg = f"Failed to spawn sub-procedure {procedure_id}: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

    def wait(self, task_id: str, timeout: Optional[float] = None) -> Any:
        """
        Wait for a spawned sub-procedure to complete.

        Args:
            task_id: Task ID returned by spawn()
            timeout: Optional timeout in seconds (None = wait forever)

        Returns:
            Result from the sub-procedure

        Raises:
            RuntimeError: If task not found or execution fails
            TimeoutError: If timeout exceeded

        Example (Lua):
            local task_id = Procedure.spawn("analysis", {data = data})

            -- Do other work...

            local result = Procedure.wait(task_id, 60)  -- Wait up to 60 seconds
            Log.info("Analysis complete", {result = result})
        """
        logger.info(f"Waiting for sub-procedure task {task_id}")

        if task_id not in self._spawned_procedures:
            error_msg = f"Task {task_id} not found"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        task_info = self._spawned_procedures[task_id]
        task = task_info.get('task')

        # If task already completed, return cached result
        if task_info['status'] == 'COMPLETED':
            logger.info(f"Task {task_id} already completed")
            result = task_info.get('result', {})
            if self.lua_sandbox:
                return self._python_to_lua(result)
            else:
                return result

        # If we have an asyncio task, wait for it
        if task:
            try:
                # Run the async task synchronously (Lua is synchronous)
                # asyncio.run() will raise RuntimeError if already in async context,
                # which is expected and handled
                if timeout:
                    result = asyncio.run(asyncio.wait_for(task, timeout=timeout))
                else:
                    result = asyncio.run(task)

                # Update task info
                task_info['status'] = 'COMPLETED'
                task_info['result'] = result
                task_info['completed_at'] = time.time()

                logger.info(f"Task {task_id} completed successfully")

                if self.lua_sandbox:
                    return self._python_to_lua(result)
                else:
                    return result

            except asyncio.TimeoutError:
                error_msg = f"Task {task_id} timed out after {timeout} seconds"
                logger.error(error_msg)
                task_info['status'] = 'TIMEOUT'
                raise TimeoutError(error_msg)
            except Exception as e:
                error_msg = f"Task {task_id} failed: {e}"
                logger.error(error_msg)
                task_info['status'] = 'FAILED'
                task_info['error'] = str(e)
                raise RuntimeError(error_msg)
        else:
            # No task object - either PENDING or fallback mode
            logger.warning(f"Task {task_id} has no asyncio task object - cannot wait")
            result = {
                'success': False,
                'error': 'Task not executing (no event loop available)',
                'task_id': task_id
            }
            if self.lua_sandbox:
                return self._python_to_lua(result)
            else:
                return result

    def status(self, task_id: str) -> str:
        """
        Check the status of a spawned sub-procedure.

        Args:
            task_id: Task ID returned by spawn()

        Returns:
            Status string: 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED', 'PENDING'

        Raises:
            RuntimeError: If task not found

        Example (Lua):
            local task_id = Procedure.spawn("long-running", {})

            while Procedure.status(task_id) == "RUNNING" do
                Log.info("Still running...")
                Sleep(5)
            end

            Log.info("Task finished", {status = Procedure.status(task_id)})
        """
        logger.debug(f"Checking status for task {task_id}")

        if task_id not in self._spawned_procedures:
            error_msg = f"Task {task_id} not found"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        task_info = self._spawned_procedures[task_id]
        task = task_info.get('task')

        # If we have an asyncio task, check its actual state
        if task:
            if task.done():
                if task.cancelled():
                    task_info['status'] = 'CANCELLED'
                elif task.exception():
                    task_info['status'] = 'FAILED'
                    task_info['error'] = str(task.exception())
                else:
                    task_info['status'] = 'COMPLETED'
                    # Cache result if not already cached
                    if not task_info.get('result'):
                        try:
                            task_info['result'] = task.result()
                        except Exception as e:
                            logger.warning(f"Failed to get result from completed task: {e}")
            # else: still RUNNING

        status = task_info['status']
        logger.debug(f"Task {task_id} status: {status}")
        return status

    def cancel(self, task_id: str) -> bool:
        """
        Cancel a running sub-procedure.

        Args:
            task_id: Task ID returned by spawn()

        Returns:
            True if cancelled successfully, False if already completed

        Raises:
            RuntimeError: If task not found

        Example (Lua):
            local task_id = Procedure.spawn("slow-task", {})

            -- Cancel if taking too long
            Sleep(10)
            if Procedure.status(task_id) == "RUNNING" then
                Procedure.cancel(task_id)
                Log.info("Task cancelled")
            end
        """
        logger.info(f"Cancelling task {task_id}")

        if task_id not in self._spawned_procedures:
            error_msg = f"Task {task_id} not found"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        task_info = self._spawned_procedures[task_id]
        task = task_info.get('task')

        # Check if task is already finished
        if task_info['status'] in ['COMPLETED', 'FAILED', 'CANCELLED']:
            logger.warning(f"Task {task_id} already finished with status {task_info['status']}")
            return False

        # If we have an asyncio task, cancel it
        if task:
            if task.done():
                logger.warning(f"Task {task_id} already completed")
                return False

            # Cancel the asyncio task
            cancelled = task.cancel()

            if cancelled:
                task_info['status'] = 'CANCELLED'
                task_info['cancelled_at'] = time.time()
                logger.info(f"Task {task_id} cancelled successfully")
                return True
            else:
                logger.warning(f"Failed to cancel task {task_id}")
                return False
        else:
            # No task object - just mark as cancelled
            task_info['status'] = 'CANCELLED'
            task_info['cancelled_at'] = time.time()
            logger.info(f"Task {task_id} marked as CANCELLED (no asyncio task)")
            return True

    def _lua_to_python(self, value: Any) -> Any:
        """Recursively convert Lua tables to Python dicts/lists."""
        if lua_type(value) == 'table':
            result = {}
            is_array = True
            keys = []

            for k, v in value.items():
                keys.append(k)
                result[k] = self._lua_to_python(v)
                if not isinstance(k, int) or k < 1:
                    is_array = False

            # Check if keys are consecutive integers starting at 1
            if is_array and keys:
                keys_sorted = sorted(keys)
                if keys_sorted != list(range(1, len(keys) + 1)):
                    is_array = False

            # Convert to list if it's an array
            if is_array and keys:
                return [result[i] for i in range(1, len(keys) + 1)]
            else:
                return result
        else:
            return value

    def _python_to_lua(self, value: Any):
        """Recursively convert Python dicts/lists to Lua tables."""
        if not self.lua_sandbox:
            return value

        if isinstance(value, dict):
            lua_table = self.lua_sandbox.lua.table()
            for k, v in value.items():
                lua_table[k] = self._python_to_lua(v)
            return lua_table
        elif isinstance(value, (list, tuple)):
            lua_table = self.lua_sandbox.lua.table()
            for i, item in enumerate(value, start=1):
                lua_table[i] = self._python_to_lua(item)
            return lua_table
        else:
            return value

    def inject(self, handle: str, message: str) -> bool:
        """
        Inject a message into a running sub-procedure's queue.

        Args:
            handle: Task ID from spawn()
            message: Message to inject

        Returns:
            True if injected successfully, False otherwise

        Raises:
            RuntimeError: If task not found

        Example (Lua):
            local task = Procedure.spawn("analysis", {})
            Procedure.inject(task, "Focus on security patterns")
        """
        if handle not in self._spawned_procedures:
            raise RuntimeError(f"Task {handle} not found")

        task_info = self._spawned_procedures[handle]

        if task_info['status'] not in ['RUNNING', 'PENDING']:
            logger.warning(f"Cannot inject to task {handle} with status {task_info['status']}")
            return False

        # Get or create message queue
        if 'message_queue' not in task_info:
            task_info['message_queue'] = asyncio.Queue(maxsize=100)

        try:
            task_info['message_queue'].put_nowait({
                'type': 'injected_message',
                'content': message,
                'injected_at': time.time()
            })
            logger.info(f"Injected message to task {handle}: {message[:50]}...")
            return True
        except asyncio.QueueFull:
            logger.warning(f"Message queue full for task {handle}")
            return False

    def wait_any(self, handles: Any, timeout: Optional[float] = None) -> tuple:
        """
        Wait for first sub-procedure to complete.

        Args:
            handles: List of task IDs (Lua table or Python list)
            timeout: Optional timeout in seconds

        Returns:
            Tuple of (completed_handle, result)

        Raises:
            RuntimeError: If no handles or handle not found
            TimeoutError: If timeout exceeded

        Example (Lua):
            local tasks = {
                Procedure.spawn("fast", {}),
                Procedure.spawn("slow", {})
            }
            local winner, result = Procedure.wait_any(tasks, 30)
            Log.info("First complete", {winner = winner})
        """
        handle_list = self._lua_to_python(handles) if handles else []

        if not handle_list:
            raise RuntimeError("No handles provided to wait_any")

        # Validate all handles exist
        for handle in handle_list:
            if handle not in self._spawned_procedures:
                raise RuntimeError(f"Task {handle} not found")

        # Check for already completed tasks
        for handle in handle_list:
            task_info = self._spawned_procedures[handle]
            if task_info['status'] in ['COMPLETED', 'FAILED', 'CANCELLED']:
                result = task_info.get('result', {})
                logger.info(f"Task {handle} already completed")
                return (handle, self._python_to_lua(result) if self.lua_sandbox else result)

        # Gather pending tasks
        pending_tasks = {}
        for handle in handle_list:
            task = self._spawned_procedures[handle].get('task')
            if task and not task.done():
                pending_tasks[task] = handle

        if not pending_tasks:
            # All tasks already done, return first
            handle = handle_list[0]
            result = self._spawned_procedures[handle].get('result', {})
            return (handle, self._python_to_lua(result) if self.lua_sandbox else result)

        # Use asyncio.wait with FIRST_COMPLETED
        try:
            done, pending = asyncio.run(asyncio.wait(
                pending_tasks.keys(),
                timeout=timeout,
                return_when=asyncio.FIRST_COMPLETED
            ))
        except RuntimeError:
            # Not in async context
            done, pending = asyncio.run(asyncio.wait(
                pending_tasks.keys(),
                timeout=timeout,
                return_when=asyncio.FIRST_COMPLETED
            ))

        if not done:
            raise TimeoutError(f"No tasks completed within {timeout} seconds")

        # Process first completed
        completed_task = list(done)[0]
        completed_handle = pending_tasks[completed_task]
        task_info = self._spawned_procedures[completed_handle]

        try:
            result = completed_task.result()
            task_info['status'] = 'COMPLETED'
            task_info['result'] = result
            task_info['completed_at'] = time.time()
            logger.info(f"Task {completed_handle} completed first")
        except Exception as e:
            task_info['status'] = 'FAILED'
            task_info['error'] = str(e)
            result = {'success': False, 'error': str(e)}
            logger.error(f"Task {completed_handle} failed: {e}")

        return (completed_handle, self._python_to_lua(result) if self.lua_sandbox else result)

    def wait_all(self, handles: Any, timeout: Optional[float] = None) -> Any:
        """
        Wait for all sub-procedures to complete.

        Args:
            handles: List of task IDs
            timeout: Optional timeout in seconds

        Returns:
            Dict/Lua table mapping handle -> result

        Example (Lua):
            local tasks = {
                Procedure.spawn("process-1", {}),
                Procedure.spawn("process-2", {})
            }
            local results = Procedure.wait_all(tasks, 120)
            for handle, result in pairs(results) do
                Log.info("Result", {handle = handle, success = result.success})
            end
        """
        handle_list = self._lua_to_python(handles) if handles else []

        if not handle_list:
            raise RuntimeError("No handles provided to wait_all")

        results = {}
        pending_tasks = {}

        # Separate completed from running
        for handle in handle_list:
            if handle not in self._spawned_procedures:
                raise RuntimeError(f"Task {handle} not found")

            task_info = self._spawned_procedures[handle]

            if task_info['status'] in ['COMPLETED', 'FAILED', 'CANCELLED']:
                results[handle] = task_info.get('result', {})
            else:
                task = task_info.get('task')
                if task and not task.done():
                    pending_tasks[task] = handle

        # If all already completed, return results
        if not pending_tasks:
            logger.info("All tasks already completed")
            return self._python_to_lua(results) if self.lua_sandbox else results

        # Wait for all pending
        try:
            done, pending = asyncio.run(asyncio.wait(
                pending_tasks.keys(),
                timeout=timeout,
                return_when=asyncio.ALL_COMPLETED
            ))
        except RuntimeError:
            done, pending = asyncio.run(asyncio.wait(
                pending_tasks.keys(),
                timeout=timeout,
                return_when=asyncio.ALL_COMPLETED
            ))

        # Process completed tasks
        for task in done:
            handle = pending_tasks[task]
            task_info = self._spawned_procedures[handle]

            try:
                result = task.result()
                task_info['status'] = 'COMPLETED'
                task_info['result'] = result
                task_info['completed_at'] = time.time()
                results[handle] = result
                logger.info(f"Task {handle} completed")
            except Exception as e:
                task_info['status'] = 'FAILED'
                task_info['error'] = str(e)
                results[handle] = {'success': False, 'error': str(e)}
                logger.error(f"Task {handle} failed: {e}")

        # Handle timeouts (still pending)
        for task in pending:
            handle = pending_tasks[task]
            task_info = self._spawned_procedures[handle]
            task_info['status'] = 'TIMEOUT'
            results[handle] = {'success': False, 'error': 'Timeout', 'status': 'TIMEOUT'}
            logger.warning(f"Task {handle} timed out")

        return self._python_to_lua(results) if self.lua_sandbox else results

    def is_complete(self, handle: str) -> bool:
        """
        Check if a task has completed (success, failure, or cancellation).

        Args:
            handle: Task ID from spawn()

        Returns:
            True if task is in terminal state, False if still running

        Raises:
            RuntimeError: If task not found

        Example (Lua):
            local task = Procedure.spawn("analysis", {})
            while not Procedure.is_complete(task) do
                Log.info("Still running...")
                Sleep(2)
            end
        """
        if handle not in self._spawned_procedures:
            raise RuntimeError(f"Task {handle} not found")

        # Get current status (updates from asyncio.Task if needed)
        status = self.status(handle)

        terminal_states = ['COMPLETED', 'FAILED', 'CANCELLED', 'TIMEOUT']
        is_done = status in terminal_states

        logger.debug(f"Task {handle} is_complete: {is_done} (status: {status})")
        return is_done

    def all_complete(self, handles: Any) -> bool:
        """
        Check if all tasks have completed.

        Args:
            handles: List of task IDs

        Returns:
            True if all tasks complete, False if any still running

        Example (Lua):
            local batch = {}
            for i = 1, 10 do
                table.insert(batch, Procedure.spawn("item", {id = i}))
            end

            while not Procedure.all_complete(batch) do
                Log.info("Processing batch...")
                Sleep(5)
            end
        """
        handle_list = self._lua_to_python(handles) if handles else []

        if not handle_list:
            return True  # Empty list is vacuously true

        for handle in handle_list:
            if not self.is_complete(handle):
                return False

        logger.debug(f"All {len(handle_list)} tasks complete")
        return True

    def __repr__(self) -> str:
        return f"ProcedurePrimitive(parent={self.parent_procedure_id}, spawned={len(self._spawned_procedures)})"
