# Runtime MCP Validation Task Set

These task definitions support Kanbus task `plx-7041b9`, under the gating spike
epic `plx-f978d2`.

The spike measures whether frontier models can use one `execute_tactus` MCP tool
to write Plexus-flavored Tactus code against a stubbed `plexus` module. The task
set intentionally covers ordinary reads, single predictions, multi-step Plexus
workflows, long-running operations, budget discipline, error handling, HITL, docs
discovery, datasets, reports, and procedure introspection.

## File Contract

Each YAML file contains:

- `id`: stable task id used by the harness.
- `name`: human-readable task name.
- `prompt`: user request sent to the model.
- `expected_outcome`: structured success criteria for the harness.
- `coverage_tags`: categories covered by the task.
- `required_apis`: `plexus.*` functions expected or likely to be useful.
- `forbidden_apis`: functions that should not be called for budget/safety reasons.
- `max_attempts_for_first_try_pass`: always `1` for first-try scoring.
- `fixture_notes`: guidance for the stub fixture author.
- Async contract: any prompt that asks for `async = true` must also require an
  explicit `budget` object with `usd`, `wallclock_seconds`, `depth`, and
  `tool_calls`.

The harness should treat `expected_outcome.kind` as the primary checker selector
and should record all API calls so `required_apis` / `forbidden_apis` assertions
can be evaluated.

## Task Index

| File | Focus |
|---|---|
| `01_list_scorecards_find_compliance.yaml` | Basic scorecard/score discovery |
| `02_inspect_score_recent_evaluations.yaml` | Score champion + recent eval metrics |
| `03_predict_single_item.yaml` | Single prediction and cost reporting |
| `04_false_negative_feedback_summary.yaml` | Feedback pattern summarization without raw transcript dumping |
| `05_compare_two_evaluations.yaml` | Evaluation comparison and metric reasoning |
| `06_run_streaming_feedback_evaluation.yaml` | Synchronous long-running evaluation with streaming |
| `07_start_async_evaluation_and_return_handle.yaml` | Async evaluation handle behavior |
| `08_tight_budget_feedback_triage.yaml` | Tight-budget aggregate triage, avoiding expensive calls |
| `09_choose_cheaper_score_before_llm.yaml` | Cost ladder: cheap score before LLM score |
| `10_missing_item_error_handling.yaml` | Structured missing-item error handling |
| `11_set_champion_requires_hitl.yaml` | Destructive champion mutation triggers HITL |
| `12_discover_dataset_docs_then_build.yaml` | Docs discovery before dataset build |
| `13_discover_report_run_docs.yaml` | Docs discovery before report run |
| `14_build_and_check_associated_dataset.yaml` | Dataset build + association check |
| `15_inspect_procedure_and_chat_messages.yaml` | Procedure and chat-message introspection |

## Coverage Matrix

| Coverage Area | Task IDs |
|---|---|
| Read-only listing/info/details | `list_scorecards_find_compliance`, `inspect_score_recent_evaluations`, `inspect_procedure_and_chat_messages` |
| Single-item prediction | `predict_single_item` |
| Multi-step composition | `false_negative_feedback_summary`, `compare_two_evaluations`, `build_and_check_associated_dataset`, `inspect_procedure_and_chat_messages` |
| Long-running operation + streaming | `run_streaming_feedback_evaluation`, `start_async_evaluation_and_return_handle`, `discover_report_run_docs` |
| Budget-aware decisions | `tight_budget_feedback_triage`, `choose_cheaper_score_before_llm`, `run_streaming_feedback_evaluation` |
| Error handling | `missing_item_error_handling` |
| HITL-by-default | `set_champion_requires_hitl` |
| Docs discovery | `discover_dataset_docs_then_build`, `discover_report_run_docs` |
| Datasets | `discover_dataset_docs_then_build`, `build_and_check_associated_dataset` |
| Reports | `discover_report_run_docs` |
| Procedures | `inspect_procedure_and_chat_messages` |
