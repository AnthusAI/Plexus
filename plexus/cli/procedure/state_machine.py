"""
Procedure State Machine

Defines the state machine for Procedure workflow using python-statemachine library.
This provides clean, validated state transitions and prevents invalid state changes.
"""
from __future__ import annotations

import logging
from typing import Optional, TYPE_CHECKING

from statemachine import StateMachine, State

if TYPE_CHECKING:
    from plexus.dashboard.api.models.procedure import Procedure

logger = logging.getLogger(__name__)


class ProcedureStateMachine(StateMachine):
    """
    State machine for Procedure workflow.

    States:
        - start: Initial state when procedure is created
        - evaluation: Running initial evaluation to gather metrics
        - hypothesis: Analyzing evaluation results and generating hypotheses
        - test: Testing hypothesis by generating and evaluating score version
        - insights: Analyzing test results and generating insights
        - completed: All work finished successfully
        - error: Procedure encountered an error

    Transitions:
        - begin: start → evaluation (start initial evaluation)
        - analyze: evaluation → hypothesis (begin hypothesis generation)
        - start_testing: hypothesis → test (begin testing hypothesis)
        - analyze_results: test → insights (analyze test results)
        - continue_iteration: insights → hypothesis (loop back for next round)
        - finish_from_insights: insights → completed (insights complete, no more iterations)
        - finish_from_hypothesis: hypothesis → completed (decided no testing needed)
        - fail_*: any state → error (error occurred)
        - retry_from_error: error → evaluation (retry after error)
        - restart_from_error: error → start (full restart after error)
    """

    # Define states
    start = State(initial=True, value="start")
    evaluation = State(value="evaluation")
    hypothesis = State(value="hypothesis")
    test = State(value="test")
    insights = State(value="insights")
    completed = State(final=True, value="completed")
    error = State(value="error")

    # Define transitions
    begin = start.to(evaluation)
    analyze = evaluation.to(hypothesis)
    start_testing = hypothesis.to(test)
    analyze_results = test.to(insights)
    continue_iteration = insights.to(hypothesis)  # NEW: Loop back for next round
    finish_from_insights = insights.to(completed)
    finish_from_hypothesis = hypothesis.to(completed)

    # Error transitions from any state
    fail_from_start = start.to(error)
    fail_from_evaluation = evaluation.to(error)
    fail_from_hypothesis = hypothesis.to(error)
    fail_from_test = test.to(error)
    fail_from_insights = insights.to(error)
    
    # Recovery transitions
    retry_from_error = error.to(evaluation)
    restart_from_error = error.to(start)
    
    def __init__(self, procedure_id: str, current_state: Optional[str] = None, client=None):
        """
        Initialize state machine for a procedure.

        Args:
            procedure_id: The procedure ID
            current_state: The current state (if resuming), or None for new procedure
            client: Optional PlexusDashboardClient for updating TaskStages
        """
        self.procedure_id = procedure_id
        self.client = client

        # Initialize the state machine first (required before accessing states)
        if current_state and current_state in ['start', 'evaluation', 'hypothesis', 'test', 'insights', 'completed', 'error']:
            super().__init__(start_value=current_state)
        elif current_state:
            logger.warning(f"Unknown state '{current_state}', defaulting to 'start'")
            super().__init__()
        else:
            super().__init__()
    
    # Transition callbacks
    def on_begin(self):
        """Called when transitioning start → evaluation"""
        logger.info(f"Procedure {self.procedure_id}: Starting initial evaluation")
        logger.info(f"  [DEBUG] on_begin: self.client = {self.client}")
        # Mark "start" stage as completed and "evaluation" stage as running
        self._update_task_stages("start", "COMPLETED")
        self._update_task_stages("evaluation", "RUNNING")

    def on_analyze(self):
        """Called when transitioning evaluation → hypothesis"""
        logger.info(f"Procedure {self.procedure_id}: Analyzing evaluation results and generating hypotheses")
        # Mark "evaluation" stage as completed and "hypothesis" stage as running
        self._update_task_stages("evaluation", "COMPLETED")
        self._update_task_stages("hypothesis", "RUNNING")

    def on_start_testing(self):
        """Called when transitioning hypothesis → test"""
        logger.info(f"Procedure {self.procedure_id}: Starting hypothesis testing")
        # Mark "hypothesis" stage as completed and "test" stage as running
        self._update_task_stages("hypothesis", "COMPLETED")
        self._update_task_stages("test", "RUNNING")

    def on_analyze_results(self):
        """Called when transitioning test → insights"""
        logger.info(f"Procedure {self.procedure_id}: Analyzing test results and generating insights")
        # Mark "test" stage as completed and "insights" stage as running
        self._update_task_stages("test", "COMPLETED")
        self._update_task_stages("insights", "RUNNING")

    def on_continue_iteration(self):
        """Called when transitioning insights → hypothesis (looping back for next round)"""
        logger.info(f"Procedure {self.procedure_id}: Insights complete, starting next hypothesis round")
        # Mark "insights" stage as completed and "hypothesis" stage as running again
        self._update_task_stages("insights", "COMPLETED")
        self._update_task_stages("hypothesis", "RUNNING")

    def on_finish_from_insights(self):
        """Called when transitioning insights → completed"""
        logger.info(f"Procedure {self.procedure_id}: Insights complete, marking procedure complete")
        # Mark "insights" stage as completed
        self._update_task_stages("insights", "COMPLETED")

    def on_finish_from_hypothesis(self):
        """Called when transitioning hypothesis → completed"""
        logger.info(f"Procedure {self.procedure_id}: Hypothesis phase complete, no code generation needed")
        # Mark "hypothesis" stage as completed
        self._update_task_stages("hypothesis", "COMPLETED")

    def on_enter_error(self):
        """Called when entering error state"""
        logger.error(f"Procedure {self.procedure_id}: Entered error state")
        # Mark current stage as failed
        current = self.current_state.value if hasattr(self.current_state, 'value') else str(self.current_state)
        self._update_task_stages(current, "FAILED")

    def on_retry_from_error(self):
        """Called when transitioning error → evaluation"""
        logger.info(f"Procedure {self.procedure_id}: Retrying from error, restarting evaluation")
        # Mark "evaluation" stage as running
        self._update_task_stages("evaluation", "RUNNING")

    def on_restart_from_error(self):
        """Called when transitioning error → start"""
        logger.info(f"Procedure {self.procedure_id}: Restarting from error")
        # Mark "start" stage as running
        self._update_task_stages("start", "RUNNING")

    def _update_task_stages(self, stage_name: str, new_status: str) -> None:
        """
        Update TaskStage status for a given stage name.

        Args:
            stage_name: The name of the stage (matches state names)
            new_status: The new status (PENDING, RUNNING, COMPLETED, FAILED)
        """
        if not self.client:
            logger.warning(f"⚠️  No client available to update TaskStage for {stage_name}")
            return

        try:
            from plexus.dashboard.api.models.task import Task
            from plexus.dashboard.api.models.task_stage import TaskStage
            from datetime import datetime, timezone

            logger.info(f"🔄 Starting TaskStage update: {stage_name} → {new_status}")

            # Find the Task for this procedure using GSI on accountId
            from plexus.dashboard.api.models.procedure import Procedure
            from datetime import datetime, timezone, timedelta

            logger.info(f"  Step 1: Fetching procedure {self.procedure_id}")
            procedure = Procedure.get_by_id(self.procedure_id, self.client)

            logger.info(f"  Step 2: Querying tasks using accountId GSI")
            # Use listTaskByAccountIdAndUpdatedAt which is indexed
            query = """
            query ListTaskByAccountIdAndUpdatedAt($accountId: String!, $updatedAt: ModelStringKeyConditionInput, $limit: Int, $nextToken: String) {
                listTaskByAccountIdAndUpdatedAt(accountId: $accountId, updatedAt: $updatedAt, limit: $limit, nextToken: $nextToken) {
                    items {
                        id
                        target
                    }
                    nextToken
                }
            }
            """

            # Query ALL tasks for this account (no date filter to avoid GSI lag issues)
            very_old_date = "2000-01-01T00:00:00.000Z"

            tasks = []
            next_token = None
            target_patterns = [f"procedure/run/{self.procedure_id}", f"procedure/{self.procedure_id}"]

            while True:
                variables = {
                    "accountId": procedure.accountId,
                    "updatedAt": {"ge": very_old_date},  # Get all tasks
                    "limit": 1000
                }
                if next_token:
                    variables["nextToken"] = next_token

                result = self.client.execute(query, variables)
                page_tasks = result.get('listTaskByAccountIdAndUpdatedAt', {}).get('items', [])

                # Check this page for matching tasks
                for task in page_tasks:
                    if any(pattern in task['target'] for pattern in target_patterns):
                        tasks.append(task)

                # If we found our task, stop scanning
                if tasks:
                    break

                next_token = result.get('listTaskByAccountIdAndUpdatedAt', {}).get('nextToken')
                if not next_token:
                    break

            logger.info(f"  Found {len(tasks)} tasks matching procedure ID '{self.procedure_id}'")

            if not tasks:
                logger.error(f"❌ No task found for procedure {self.procedure_id}")
                return

            # Prefer "procedure/run/{id}" format over "procedure/{id}"
            task_id = None
            for task_data in tasks:
                if task_data['target'] == f"procedure/run/{self.procedure_id}":
                    task_id = task_data['id']
                    break
            if not task_id and tasks:
                task_id = tasks[0]['id']

            logger.info(f"  Step 3: Found task {task_id}")

            # Get the TaskStage by name
            stage_query = """
            query GetTask($id: ID!) {
                getTask(id: $id) {
                    stages {
                        items {
                            id
                            name
                            status
                        }
                    }
                }
            }
            """

            logger.info(f"  Step 4: Fetching TaskStages for task {task_id}")
            result = self.client.execute(stage_query, {"id": task_id})
            stages = result.get('getTask', {}).get('stages', {}).get('items', [])
            logger.info(f"  Found {len(stages)} stages: {[s['name'] for s in stages]}")

            matching_stage = None
            for stage in stages:
                # Match by name (case-insensitive)
                if stage['name'].lower() == stage_name.lower():
                    matching_stage = stage
                    break

            if not matching_stage:
                logger.error(f"❌ No TaskStage found with name '{stage_name}' for task {task_id}")
                logger.error(f"   Available stages: {[s['name'] for s in stages]}")
                return

            logger.info(f"  Step 5: Found matching stage {matching_stage['id']} (current status: {matching_stage['status']})")

            # Get the TaskStage object and update it
            task_stage = TaskStage.get_by_id(matching_stage['id'], self.client)

            update_kwargs = {"status": new_status}

            # Set timestamps based on status
            if new_status == "RUNNING" and not task_stage.startedAt:
                update_kwargs["startedAt"] = datetime.now(timezone.utc)
            elif new_status in ["COMPLETED", "FAILED"]:
                update_kwargs["completedAt"] = datetime.now(timezone.utc)

            logger.info(f"  Step 6: Updating TaskStage with: {update_kwargs}")
            task_stage.update(**update_kwargs)
            logger.info(f"✅ Updated TaskStage '{stage_name}' to {new_status}")

        except Exception as e:
            logger.error(f"❌ Failed to update TaskStage '{stage_name}': {e}")
            import traceback
            traceback.print_exc()
            # Re-raise to make failures visible
            raise
    
    @property
    def state_value(self) -> str:
        """Get the current state value as a string"""
        return self.current_state.value


# Convenience functions for common operations
def create_state_machine(procedure_id: str, current_state: Optional[str] = None, client=None) -> ProcedureStateMachine:
    """
    Create a state machine for a procedure.

    Args:
        procedure_id: The procedure ID
        current_state: The current state (if resuming), or None for new procedure
        client: Optional PlexusDashboardClient for TaskStage updates

    Returns:
        ProcedureStateMachine instance
    """
    return ProcedureStateMachine(procedure_id=procedure_id, current_state=current_state, client=client)


def get_valid_transitions(current_state: Optional[str]) -> list[str]:
    """
    Get list of valid transitions from a given state.
    
    Args:
        current_state: The current state value
        
    Returns:
        List of valid next state values
    """
    # Create multiple temp state machines and try each event to see where it leads
    transitions = []
    sm = ProcedureStateMachine(procedure_id="temp", current_state=current_state or "start")
    
    for event_name in sm.allowed_events:
        # Create a fresh state machine for each test
        test_sm = ProcedureStateMachine(procedure_id="temp", current_state=current_state or "start")
        try:
            # Execute the event
            getattr(test_sm, event_name)()
            # Get the resulting state
            result_state = test_sm.state_value
            if result_state not in transitions:
                transitions.append(result_state)
        except Exception:
            # Event failed, skip it
            pass
    
    return transitions


def is_valid_transition(from_state: Optional[str], to_state: str) -> bool:
    """
    Check if a state transition is valid.
    
    Args:
        from_state: The current state (or None for initial state)
        to_state: The target state
        
    Returns:
        True if transition is valid, False otherwise
    """
    valid_next_states = get_valid_transitions(from_state)
    return to_state in valid_next_states

