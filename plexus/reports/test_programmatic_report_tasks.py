from unittest.mock import MagicMock, patch

from plexus.reports.service import (
    _wait_for_programmatic_task_result,
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
