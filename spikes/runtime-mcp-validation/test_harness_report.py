"""Focused tests for runtime MCP spike harness/report guardrails."""

from __future__ import annotations

import csv

import pytest

import harness
from harness import (
    assert_planned_cost_within_cap,
    assert_readiness_run_succeeded,
    cost_usd,
    execute_lua,
    extract_lua,
    classify_failure,
    create_plexus_module,
    load_tasks,
    normalize_provider_usage,
    parse_model_ids,
    to_jsonable,
)
from report import SummaryRow, summarize


def summary_row(
    *,
    task_id: str,
    model_id: str,
    succeeded_first_try: bool = True,
) -> SummaryRow:
    return SummaryRow(
        task_id=task_id,
        model_id=model_id,
        succeeded_first_try=succeeded_first_try,
        attempts_used=1,
        total_input_tokens=10,
        total_output_tokens=10,
        tool_definition_tokens=5,
        latency_ms=1,
        total_cost_usd=0.001,
        failure_classification="" if succeeded_first_try else "language",
    )


def test_parse_model_ids_rejects_duplicates() -> None:
    with pytest.raises(SystemExit) as exc_info:
        parse_model_ids(None, "stub-oracle,stub-oracle")

    assert "duplicate" in str(exc_info.value).lower()


def test_parse_model_ids_rejects_model_and_models_together() -> None:
    with pytest.raises(SystemExit) as exc_info:
        parse_model_ids("stub-oracle", "openai:gpt-example")

    assert "either --model or --models" in str(exc_info.value)


def test_cost_plan_refuses_over_cap_before_provider_calls() -> None:
    with pytest.raises(SystemExit) as exc_info:
        assert_planned_cost_within_cap(
            model_ids=["openai:gpt-example"],
            task_count=1,
            max_total_cost_usd=0.10,
            estimated_real_call_cost_usd=0.20,
        )

    assert "exceeds cap" in str(exc_info.value)


def test_cost_plan_ignores_stub_oracle_calls() -> None:
    plan = assert_planned_cost_within_cap(
        model_ids=["stub-oracle"],
        task_count=15,
        max_total_cost_usd=0.10,
        estimated_real_call_cost_usd=0.20,
    )

    assert plan["real_call_count"] == 0
    assert plan["estimated_cost_usd"] == 0.0


def write_summary(path, rows) -> None:
    fields = [
        "task_id",
        "model_id",
        "succeeded_first_try",
        "attempts_used",
        "total_input_tokens",
        "total_output_tokens",
        "tool_definition_tokens",
        "latency_ms",
        "total_cost_usd",
        "failure_classification",
    ]
    path.parent.mkdir(parents=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def readiness_row(model_id: str, succeeded: bool) -> dict[str, object]:
    return {
        "task_id": "predict_single_item",
        "model_id": model_id,
        "succeeded_first_try": str(succeeded).lower(),
        "attempts_used": 1,
        "total_input_tokens": 10,
        "total_output_tokens": 10,
        "tool_definition_tokens": 5,
        "latency_ms": 1,
        "total_cost_usd": "0.001",
        "failure_classification": "",
    }


def test_readiness_run_requires_run_id() -> None:
    with pytest.raises(SystemExit) as exc_info:
        assert_readiness_run_succeeded(None)

    assert "readiness-run-id" in str(exc_info.value)


def test_readiness_run_rejects_missing_summary(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(harness, "RESULTS_DIR", tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        assert_readiness_run_succeeded("missing-run")

    assert "summary not found" in str(exc_info.value).lower()


def test_readiness_run_rejects_stub_only_success(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(harness, "RESULTS_DIR", tmp_path)
    write_summary(
        tmp_path / "stub-run" / "summary.csv",
        [readiness_row("stub-oracle", True)],
    )

    with pytest.raises(SystemExit) as exc_info:
        assert_readiness_run_succeeded("stub-run")

    assert "no successful real-provider" in str(exc_info.value)


def test_readiness_run_accepts_successful_real_result(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(harness, "RESULTS_DIR", tmp_path)
    write_summary(
        tmp_path / "real-run" / "summary.csv",
        [readiness_row("openai:gpt-example", True)],
    )

    assert_readiness_run_succeeded("real-run")


def test_predict_single_item_prompt_matches_required_contract() -> None:
    task = next(task for task in load_tasks() if task.id == "predict_single_item")
    prompt = task.prompt

    for api_name in task.required_apis:
        assert api_name in prompt

    for field_name in [
        "item_id",
        "score_id",
        "score_version_id",
        "predicted_value",
        "explanation",
        "cost",
    ]:
        assert field_name in prompt


def expected_prompt_terms(task: harness.SpikeTask) -> set[str]:
    expected = task.expected_outcome
    kind = expected["kind"]
    terms: set[str] = set()

    if kind == "exact_fields":
        for key in expected["fields"]:
            if key.endswith("_present"):
                terms.add(key[:-8])
            elif key == "cost_present":
                terms.add("cost")
            else:
                terms.add(key)
    elif kind == "contains_fields":
        fields = expected["fields"]
        for key, value in fields.items():
            if key == "evaluations_count":
                terms.add("evaluations")
            elif key == "chat_messages_count":
                terms.add("chat_messages")
            elif key == "includes_metrics":
                terms.update(value)
            elif key == "includes_regression_assessment":
                terms.add("regression")
            elif key == "status_one_of":
                terms.add("status")
            else:
                terms.add(key)
    elif kind == "structured_summary":
        terms.add("patterns")
        terms.update(expected["constraints"]["each_pattern_has"])
    elif kind == "streaming_operation":
        for key in expected["final_fields"]:
            terms.add(key[:-8] if key.endswith("_present") else key)
        terms.update(expected["stream_requirements"]["fields_per_event"])
    elif kind == "async_handle":
        terms.update(
            {
                "handle_id",
                "status",
                "check_later_with",
                "budget",
                "usd",
                "wallclock_seconds",
                "depth",
                "tool_calls",
            }
        )
    elif kind == "budget_aware":
        for key in expected["fields"]:
            if key == "answer_present":
                terms.add("answer")
            elif key == "evidence_uses_counts_or_alignment":
                terms.add("alignment")
            elif key == "predicted_value_present":
                terms.add("predicted_value")
            elif key == "cost_less_than_usd":
                terms.add("cost")
            elif key in {"did_not_call", "budget_remaining_nonnegative"}:
                continue
            else:
                terms.add(key)
    elif kind == "structured_error":
        terms.update({"error", "code", "retryable"})
    elif kind == "hitl_required":
        terms.update(expected["fields"])
    elif kind == "docs_discovery_then_action":
        for key in expected["fields"]:
            if key == "docs_requested":
                continue
            terms.add(key[:-8] if key.endswith("_present") else key)
    else:
        raise AssertionError(f"unsupported expected kind in test: {kind}")

    return terms


def test_all_task_prompts_name_required_apis_and_output_contract_terms() -> None:
    for task in load_tasks():
        for api_name in task.required_apis:
            assert api_name in task.prompt, f"{task.id} prompt omits {api_name}"
        for term in expected_prompt_terms(task):
            assert term in task.prompt, f"{task.id} prompt omits {term}"


def test_budget_calls_are_not_required_apis_for_any_task() -> None:
    for task in load_tasks():
        assert "plexus.budget.remaining" not in task.required_apis, (
            f"{task.id} should not require explicit plexus.budget.remaining; "
            "budget enforcement is ambient runtime behavior."
        )


def test_streaming_evaluation_task_no_longer_demands_explicit_budget_call() -> None:
    task = next(task for task in load_tasks() if task.id == "run_streaming_feedback_evaluation")
    assert "plexus.budget.remaining" not in task.required_apis
    assert task.required_apis == ["plexus.evaluation.run"]


def test_helper_bindings_cover_spike_api_catalog() -> None:
    plexus = create_plexus_module()
    catalog = plexus.api.list()
    helpers = {helper_name for helper_name, _, _ in harness.HELPER_BINDINGS}

    expected_helpers = {
        f"{namespace.removeprefix('plexus.')}_{method}"
        for namespace, methods in catalog.items()
        for method in methods
        if namespace not in {"plexus.budget", "plexus.cost"}
    }

    assert len(helpers) == len([binding[0] for binding in harness.HELPER_BINDINGS])
    assert expected_helpers <= helpers


def test_boot_prompt_names_canonical_helper_contract() -> None:
    boot_prompt = harness.BOOT_PROMPT.read_text()
    for term in (
        "namespace_method",
        "scorecards_list",
        "score_set_champion",
        "evaluation_info",
        "handle_status",
        "docs_get",
        "api_list",
    ):
        assert term in boot_prompt


def test_false_negative_summary_prompt_names_fixture_fields_for_grouping() -> None:
    task = next(task for task in load_tasks() if task.id == "false_negative_feedback_summary")
    for term in ("item_id", "pattern", "comment"):
        assert term in task.prompt, f"{task.id} prompt omits {term}"


def test_async_tasks_require_explicit_budget_contract_in_prompt() -> None:
    for task in load_tasks():
        if "async = true" not in task.prompt:
            continue
        for term in ("budget", "usd", "wallclock_seconds", "depth", "tool_calls"):
            assert term in task.prompt, f"{task.id} prompt omits async budget term: {term}"


def test_structured_summary_rejects_empty_representative_item_id() -> None:
    task = next(task for task in load_tasks() if task.id == "false_negative_feedback_summary")
    result = harness.check_expected(
        task,
        final_value={
            "patterns": [
                {"label": "a", "example_count": 4, "representative_item_id": ""},
                {"label": "b", "example_count": 3, "representative_item_id": "item_1102"},
                {"label": "c", "example_count": 2, "representative_item_id": "item_1103"},
            ]
        },
        api_calls=["plexus.feedback.find", "plexus.feedback.alignment", "plexus.item.info"],
        stream_events=[],
    )
    assert result["passed"] is False
    assert "pattern has empty representative_item_id" in result["details"]


def test_extract_accepts_tactus_fenced_blocks() -> None:
    assert extract_lua("```tactus\nevaluate{ item_count = 1 }\n```") == (
        "evaluate{ item_count = 1 }"
    )


def test_repair_loop_recovers_from_first_attempt_syntax_error(monkeypatch) -> None:
    pytest.importorskip("lupa")
    task = next(task for task in load_tasks() if task.id == "run_streaming_feedback_evaluation")

    attempts: list[str] = []

    def fake_call_model(model_id: str, prompt: str) -> tuple[str, list[dict[str, object]]]:
        attempts.append(prompt)
        if len(attempts) == 1:
            text = "this is not valid lua syntax @@@"
        else:
            text = "evaluate{ score_id = \"score_compliance_tone\", item_count = 200 }\n"
        transcript = [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": text, "usage": None},
        ]
        return text, transcript

    monkeypatch.setattr(harness, "call_model", fake_call_model)

    result = harness.run_task(task, "openai:gpt-stub", repair_attempts=1)

    assert len(attempts) == 2
    assert result.attempts_used == 2
    assert result.succeeded_first_try is False
    assert result.check_results["passed"] is True
    assert result.failure_classification is None
    assert "plexus.evaluation.run" in result.api_calls


def test_repair_loop_preserves_first_try_passed_when_first_attempt_succeeds(monkeypatch) -> None:
    pytest.importorskip("lupa")
    task = next(task for task in load_tasks() if task.id == "run_streaming_feedback_evaluation")

    def fake_call_model(model_id: str, prompt: str) -> tuple[str, list[dict[str, object]]]:
        text = "evaluate{ score_id = \"score_compliance_tone\", item_count = 200 }\n"
        transcript = [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": text, "usage": None},
        ]
        return text, transcript

    monkeypatch.setattr(harness, "call_model", fake_call_model)

    result = harness.run_task(task, "openai:gpt-stub", repair_attempts=1)

    assert result.attempts_used == 1
    assert result.succeeded_first_try is True
    assert result.check_results["passed"] is True


def test_structured_error_task_counts_as_first_try_pass_when_check_passes(monkeypatch) -> None:
    pytest.importorskip("lupa")
    task = next(task for task in load_tasks() if task.id == "missing_item_error_handling")

    def fake_call_model(model_id: str, prompt: str) -> tuple[str, list[dict[str, object]]]:
        text = (
            "predict{ score_id = \"score_compliance_tone\", "
            "item_id = \"item_does_not_exist\" }\n"
        )
        transcript = [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": text, "usage": None},
        ]
        return text, transcript

    monkeypatch.setattr(harness, "call_model", fake_call_model)

    result = harness.run_task(task, "openai:gpt-stub", repair_attempts=0)

    assert result.check_results["passed"] is True
    assert result.succeeded_first_try is True
    assert result.errors_per_attempt
    assert result.errors_per_attempt[0]["code"] == "ITEM_NOT_FOUND"


def test_repair_loop_disabled_when_repair_attempts_zero(monkeypatch) -> None:
    pytest.importorskip("lupa")
    task = next(task for task in load_tasks() if task.id == "run_streaming_feedback_evaluation")

    attempts: list[str] = []

    def fake_call_model(model_id: str, prompt: str) -> tuple[str, list[dict[str, object]]]:
        attempts.append(prompt)
        text = "this is not valid lua syntax @@@"
        transcript = [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": text, "usage": None},
        ]
        return text, transcript

    monkeypatch.setattr(harness, "call_model", fake_call_model)

    result = harness.run_task(task, "openai:gpt-stub", repair_attempts=0)

    assert len(attempts) == 1
    assert result.attempts_used == 1
    assert result.succeeded_first_try is False
    assert result.failure_classification == "language"


def test_evaluate_helper_returns_runtime_captured_value_without_require_or_return() -> None:
    pytest.importorskip("lupa")
    plexus = create_plexus_module()

    value = execute_lua(
        """
evaluate{
  score_id = "score_compliance_tone",
  item_count = 200,
}
""",
        plexus,
    )

    assert isinstance(value, dict)
    assert value["score_id"] == "score_compliance_tone"
    assert value["processed_items"] == 200
    assert value["final_ac1"] is not None
    assert value["total_cost"] is not None
    api_calls = [entry["api"] for entry in plexus.call_log()]
    assert "plexus.evaluation.run" in api_calls
    assert "plexus.budget.remaining" not in api_calls
    assert any(event.get("event") == "progress" for event in plexus.stream_events())


def test_explicit_return_overrides_runtime_capture() -> None:
    pytest.importorskip("lupa")
    plexus = create_plexus_module()

    value = execute_lua(
        """
local prediction = predict{
  score_id = "score_compliance_tone",
  item_id = "item_1007",
}
return {
  item_id = prediction.item_id,
  predicted_value = prediction.value,
}
""",
        plexus,
    )

    assert value == {
        "item_id": "item_1007",
        "predicted_value": "No",
    }


def test_runtime_records_budget_spend_without_explicit_budget_call() -> None:
    pytest.importorskip("lupa")
    plexus = create_plexus_module()

    execute_lua(
        """
evaluate{
  score_id = "score_compliance_tone",
  item_count = 200,
}
""",
        plexus,
    )

    api_calls = [entry["api"] for entry in plexus.call_log()]
    assert "plexus.budget.remaining" not in api_calls
    spent = plexus.budget.remaining()["usd_spent"]
    assert spent > 0
    assert any(
        event.get("operation", "").startswith("plexus.evaluation.run")
        for event in plexus.budget_events()
    )


def test_helper_aliases_map_to_expected_namespace_methods() -> None:
    pytest.importorskip("lupa")
    plexus = create_plexus_module()

    execute_lua(
        """
score{ id = "score_compliance_tone" }
item{ id = "item_1007" }
predict{ score_id = "score_compliance_tone", item_id = "item_1007" }
feedback{ score_id = "score_compliance_tone", kind = "FN", approved = true }
dataset{ score_id = "score_compliance_tone", window_days = 14 }
procedure{ id = "proc_alignment_optimizer" }
""",
        plexus,
    )

    api_calls = [entry["api"] for entry in plexus.call_log()]
    for expected in [
        "plexus.score.info",
        "plexus.item.info",
        "plexus.score.predict",
        "plexus.feedback.find",
        "plexus.dataset.build_from_feedback_window",
        "plexus.procedure.info",
    ]:
        assert expected in api_calls, f"missing {expected} in {api_calls}"


def test_canonical_helper_aliases_map_to_expected_namespace_methods() -> None:
    pytest.importorskip("lupa")
    plexus = create_plexus_module()

    execute_lua(
        """
scorecards_list{ account = "Acme Health" }
score_info{ id = "score_compliance_tone" }
item_last{}
feedback_alignment{ score_id = "score_compliance_tone" }
evaluation_info{ id = "eval_compliance_candidate" }
report_configurations_list{}
procedure_chat_sessions{ procedure_id = "proc_alignment_optimizer" }
docs_get{ key = "reports" }
api_list{}
""",
        plexus,
    )

    api_calls = [entry["api"] for entry in plexus.call_log()]
    for expected in [
        "plexus.scorecards.list",
        "plexus.score.info",
        "plexus.item.last",
        "plexus.feedback.alignment",
        "plexus.evaluation.info",
        "plexus.report.configurations_list",
        "plexus.procedure.chat_sessions",
        "plexus.docs.get",
        "plexus.api.list",
    ]:
        assert expected in api_calls, f"missing {expected} in {api_calls}"


def test_explicit_require_plexus_still_works_for_back_compat() -> None:
    pytest.importorskip("lupa")
    plexus = create_plexus_module()

    value = execute_lua(
        """
local plexus = require("plexus")
return plexus.score.info{ id = "score_compliance_tone" }.id
""",
        plexus,
    )

    assert value == "score_compliance_tone"


def test_async_evaluation_accepts_nested_lua_table_args() -> None:
    pytest.importorskip("lupa")
    plexus = create_plexus_module()

    value = execute_lua(
        """
local plexus = require("plexus")
local handle = plexus.evaluation.run{
  score_id = "Compliance Tone",
  item_count = 1000,
  filter = {
    feedback_status = "approved",
  },
  async = true,
  budget = {
    usd = 0.5,
    wallclock_seconds = 1800,
    depth = 1,
    tool_calls = 10,
  },
}
local status = plexus.handle.status{ id = handle.id }
return {
  handle_id = handle.id,
  status = status.status,
  check_later_with = "plexus.handle.status",
}
""",
        plexus,
    )

    assert value == {
        "handle_id": "handle_eval_stub_compliance_tone_1000",
        "status": "running",
        "check_later_with": "plexus.handle.status",
    }


def test_normalize_provider_usage_supports_anthropic_shape() -> None:
    usage = normalize_provider_usage(
        [{"role": "assistant", "usage": {"input_tokens": 123, "output_tokens": 45}}]
    )

    assert usage == {"input_tokens": 123, "output_tokens": 45, "total_tokens": None}


def test_normalize_provider_usage_supports_litellm_shape() -> None:
    usage = normalize_provider_usage(
        [
            {
                "role": "assistant",
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 25,
                    "total_tokens": 125,
                },
            }
        ]
    )

    assert usage == {"input_tokens": 100, "output_tokens": 25, "total_tokens": 125}


def test_normalize_provider_usage_derives_missing_output_from_total() -> None:
    usage = normalize_provider_usage(
        [{"role": "assistant", "usage": {"input_tokens": 80, "total_tokens": 120}}]
    )

    assert usage == {"input_tokens": 80, "output_tokens": 40, "total_tokens": 120}


def test_to_jsonable_converts_structured_stub_errors() -> None:
    value = to_jsonable(
        {
            "status": "handled",
            "error": harness.PlexusStubError(
                "ITEM_NOT_FOUND",
                "No item found for 'missing'",
                retryable=False,
            ),
        }
    )

    assert value == {
        "status": "handled",
        "error": {
            "code": "ITEM_NOT_FOUND",
            "message": "No item found for 'missing'",
            "retryable": False,
            "details": {},
        },
    }


def test_cost_usd_supports_structured_cost_payloads() -> None:
    assert cost_usd({"usd": 0.0004}) == 0.0004
    assert cost_usd({"usd_spent": 0.001}) == 0.001
    assert cost_usd("unknown") == 999.0


def test_classify_failure_keeps_stub_failures_separate() -> None:
    classification = classify_failure(
        model_id="stub-oracle",
        errors=[],
        check_results={"passed": False, "details": ["wrong processed_items"]},
    )

    assert classification == "harness_or_fixture"


def test_classify_failure_detects_lua_language_error() -> None:
    classification = classify_failure(
        model_id="openai:gpt-example",
        errors=[{"code": "LuaSyntaxError", "message": "unexpected symbol"}],
        check_results={"passed": False, "details": []},
    )

    assert classification == "language"


def test_classify_failure_detects_api_design_error() -> None:
    classification = classify_failure(
        model_id="openai:gpt-example",
        errors=[{"code": "MODULE_NOT_FOUND", "message": "No module named 'foo'"}],
        check_results={"passed": False, "details": []},
    )

    assert classification == "api_design"


def test_classify_failure_detects_provider_request_error() -> None:
    classification = classify_failure(
        model_id="openai:gpt-example",
        errors=[
            {
                "code": "BadRequestError",
                "message": "The requested model 'gpt-example' does not exist.",
            }
        ],
        check_results={"passed": False, "details": ["missing required APIs"]},
    )

    assert classification == "provider_error"


def test_classify_failure_detects_boot_prompt_gap() -> None:
    classification = classify_failure(
        model_id="openai:gpt-example",
        errors=[],
        check_results={"passed": False, "details": ["missing required APIs: ['plexus.docs.get']"]},
    )

    assert classification == "boot_prompt"


def test_classify_failure_detects_fundamental_wrong_answer() -> None:
    classification = classify_failure(
        model_id="openai:gpt-example",
        errors=[],
        check_results={"passed": False, "details": ["wrong processed_items"]},
    )

    assert classification == "fundamental"


def test_report_gate_requires_complete_real_model_task_coverage() -> None:
    rows = [
        summary_row(task_id="predict_single_item", model_id=model_id)
        for model_id in ["real-a", "real-b", "real-c", "real-d"]
    ]

    summary = summarize(rows, details=[])

    assert summary["real_model_count"] == 4
    assert summary["complete_real_model_count"] == 0
    assert summary["decision_ready"] is False
    assert summary["gate_passed"] is False


def test_report_gate_counts_complete_real_model_results() -> None:
    task_ids = [task.id for task in load_tasks()]
    rows = [
        summary_row(task_id=task_id, model_id=model_id)
        for model_id in ["real-a", "real-b", "real-c", "real-d"]
        for task_id in task_ids
    ]

    summary = summarize(rows, details=[])

    assert summary["complete_real_model_count"] == 4
    assert summary["decision_ready"] is True
    assert summary["gate_passed"] is True


def test_report_summarizes_streaming_events() -> None:
    summary = summarize(
        [summary_row(task_id="run_streaming_feedback_evaluation", model_id="stub-oracle")],
        details=[
            {
                "task_id": "run_streaming_feedback_evaluation",
                "model_id": "stub-oracle",
                "stream_events": [
                    {"event": "started"},
                    {"event": "progress"},
                    {"event": "progress"},
                    {"event": "completed"},
                ],
            }
        ],
    )

    assert summary["stream_event_count"] == 4
    assert summary["stream_summaries"] == [
        {
            "task_id": "run_streaming_feedback_evaluation",
            "model_id": "stub-oracle",
            "stream_event_count": 4,
            "event_types": ["completed", "progress", "started"],
        }
    ]
