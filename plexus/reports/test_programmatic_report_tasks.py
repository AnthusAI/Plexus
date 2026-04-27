from unittest.mock import MagicMock, patch

from plexus.reports.service import (
    _wait_for_programmatic_task_result,
    run_programmatic_block_and_persist,
    run_block_cached,
)


@patch("plexus.reports.service._check_db_cache")
@patch("plexus.reports.service._find_matching_programmatic_task")
@patch("plexus.reports.service._create_programmatic_report_task")
def test_run_block_cached_background_queues_durable_task(
    mock_create_task,
    mock_find_matching_task,
    mock_check_db_cache,
):
    mock_check_db_cache.return_value = None
    mock_find_matching_task.return_value = None
    queued_task = MagicMock()
    queued_task.id = "task-123"
    mock_create_task.return_value = queued_task

    output, log_output, was_cached = run_block_cached(
        block_class="AcceptanceRate",
        block_config={"scorecard": "sc-1"},
        account_id="acct-1",
        client=MagicMock(),
        cache_key="cache-key",
        background=True,
    )

    assert output == {
        "status": "dispatched",
        "cache_key": "cache-key",
        "task_id": "task-123",
    }
    assert log_output is None
    assert was_cached is False
    mock_create_task.assert_called_once()


@patch("plexus.reports.service._check_db_cache")
@patch("plexus.reports.service._find_matching_programmatic_task")
def test_run_block_cached_background_dedupes_inflight_task(
    mock_find_matching_task,
    mock_check_db_cache,
):
    mock_check_db_cache.return_value = None
    existing_task = MagicMock()
    existing_task.id = "task-456"
    mock_find_matching_task.return_value = existing_task

    output, log_output, was_cached = run_block_cached(
        block_class="AcceptanceRate",
        block_config={"scorecard": "sc-1"},
        account_id="acct-1",
        client=MagicMock(),
        cache_key="cache-key",
        background=True,
    )

    assert output == {
        "status": "already_dispatched",
        "cache_key": "cache-key",
        "task_id": "task-456",
    }
    assert log_output is None
    assert was_cached is False


@patch("plexus.reports.service.run_programmatic_block_and_persist")
@patch("plexus.reports.service._wait_for_programmatic_task_result")
@patch("plexus.reports.service._find_matching_programmatic_task")
@patch("plexus.reports.service._check_db_cache")
def test_run_block_cached_foreground_waits_for_existing_task(
    mock_check_db_cache,
    mock_find_matching_task,
    mock_wait_for_task,
    mock_run_and_persist,
):
    mock_check_db_cache.return_value = None
    existing_task = MagicMock()
    existing_task.id = "task-789"
    mock_find_matching_task.return_value = existing_task
    mock_wait_for_task.return_value = ({"summary": {"total_items": 4}}, None, True)

    output, log_output, was_cached = run_block_cached(
        block_class="AcceptanceRate",
        block_config={"scorecard": "sc-1"},
        account_id="acct-1",
        client=MagicMock(),
        cache_key="cache-key",
        background=False,
    )

    assert output == {"summary": {"total_items": 4}}
    assert log_output is None
    assert was_cached is True
    mock_wait_for_task.assert_called_once()
    mock_run_and_persist.assert_not_called()


@patch("plexus.reports.service.time.monotonic", side_effect=[0.0, 0.1])
@patch("plexus.reports.service.time.sleep", return_value=None)
@patch("plexus.reports.service.Task.get_by_id")
@patch("plexus.reports.service._find_report_by_task_id")
def test_wait_for_programmatic_task_result_surfaces_failure(
    mock_find_report_by_task_id,
    mock_task_get_by_id,
    _mock_sleep,
    _mock_monotonic,
):
    queued_task = MagicMock()
    queued_task.id = "task-111"

    mock_find_report_by_task_id.return_value = None

    failed_task = MagicMock()
    failed_task.status = "FAILED"
    failed_task.dispatchStatus = "DISPATCHED"
    failed_task.errorMessage = "Task crashed"
    failed_task.stderr = "stacktrace"
    mock_task_get_by_id.return_value = failed_task

    output, log_output, was_cached = _wait_for_programmatic_task_result(
        task=queued_task,
        cache_key="cache-key",
        account_id="acct-1",
        client=MagicMock(),
        timeout_seconds=1,
    )

    assert output is None
    assert "Task crashed" in log_output
    assert "stacktrace" in log_output
    assert was_cached is False


@patch("plexus.reports.service.time.monotonic", side_effect=[0.0, 0.1])
@patch("plexus.reports.service.Task.get_by_id")
@patch("plexus.reports.service._find_report_by_task_id")
@patch("plexus.reports.service._load_programmatic_report_result")
def test_wait_for_programmatic_task_result_surfaces_persisted_report_failure(
    mock_load_programmatic_report_result,
    mock_find_report_by_task_id,
    mock_task_get_by_id,
    _mock_monotonic,
):
    queued_task = MagicMock()
    queued_task.id = "task-222"

    report = MagicMock()
    mock_find_report_by_task_id.return_value = report
    mock_load_programmatic_report_result.return_value = (None, "Score not found")

    refreshed_task = MagicMock()
    refreshed_task.status = "COMPLETED"
    refreshed_task.dispatchStatus = "COMPLETED"
    refreshed_task.errorMessage = None
    refreshed_task.stderr = None
    mock_task_get_by_id.return_value = refreshed_task

    output, log_output, was_cached = _wait_for_programmatic_task_result(
        task=queued_task,
        cache_key="cache-key",
        account_id="acct-1",
        client=MagicMock(),
        timeout_seconds=1,
    )

    assert output is None
    assert log_output == "Score not found"
    assert was_cached is False


@patch("plexus.reports.service._persist_block_result")
@patch("plexus.reports.service._instantiate_and_run_block")
def test_run_programmatic_block_and_persist_uses_concise_failure_message(
    mock_instantiate_and_run_block,
    mock_persist_block_result,
):
    mock_instantiate_and_run_block.return_value = (
        None,
        "Error running block FeedbackContradictions (FeedbackContradictions): Score not found\nDetails:\ntraceback",
        None,
    )

    output, log_output = run_programmatic_block_and_persist(
        cache_key="cache-key",
        block_class="FeedbackContradictions",
        block_config={"scorecard": "sc-1"},
        account_id="acct-1",
        client=MagicMock(),
    )

    assert output is None
    assert "Details:\ntraceback" in log_output
    assert mock_persist_block_result.call_args.kwargs["success"] is False
    assert (
        mock_persist_block_result.call_args.kwargs["error_message"]
        == "Error running block FeedbackContradictions (FeedbackContradictions): Score not found"
    )
