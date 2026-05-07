from plexus.cli.shared.CommandTasks import _should_append_task_id_arg


def test_should_not_append_task_id_to_procedure_run_command():
    assert _should_append_task_id_arg(["procedure", "run", "proc-1"]) is False


def test_should_not_append_task_id_to_programmatic_report_block_command():
    assert (
        _should_append_task_id_arg(
            ["feedback", "report", "run-programmatic-block", "--payload-base64", "abc123"]
        )
        is False
    )


def test_should_append_task_id_to_evaluation_command():
    assert _should_append_task_id_arg(["evaluate", "accuracy", "--scorecard", "Card"]) is True
