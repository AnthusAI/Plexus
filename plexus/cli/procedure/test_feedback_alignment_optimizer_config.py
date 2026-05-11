from pathlib import Path
from datetime import datetime, timezone

import yaml

from plexus.cli.procedure.procedures import _optimizer_feedback_window


OPTIMIZER_YAML_PATH = (
    Path(__file__).resolve().parents[2] / "procedures" / "feedback_alignment_optimizer.yaml"
)
OPTIMIZER_DOCS_DIR = (
    Path(__file__).resolve().parents[3] / "documentation" / "agent" / "evaluation-feedback"
)
OPTIMIZER_SKILL_PATH = (
    Path(__file__).resolve().parents[3] / "skills" / "score-optimizer" / "SKILL.md"
)


def _load_optimizer_config():
    with OPTIMIZER_YAML_PATH.open() as f:
        return yaml.safe_load(f)


def _read_optimizer_doc(filename):
    return (OPTIMIZER_DOCS_DIR / filename).read_text(encoding="utf-8")


def _build_optimizer_scheduler():
    from lupa import LuaRuntime

    config = _load_optimizer_config()
    code = config["code"]
    start = code.index("local function escalation_rank(mode)")
    end = code.index("local function cookbook_key_for_slot(slot)")
    block = code[start:end]
    lua = LuaRuntime(unpack_returned_tuples=True)
    schedule = lua.execute(
        block
        + """
return function(opts)
  local slots, mode, counts = build_protected_hypothesis_slots(opts)
  return {slots = slots, mode = mode, counts = counts}
end
"""
    )
    return lua, schedule


def _lua_list(lua_table):
    return [lua_table[i] for i in range(1, len(lua_table) + 1)]


def _schedule_slots(num_candidates=3, cycle=1, consecutive_stagnant_cycles=0):
    lua, schedule = _build_optimizer_scheduler()
    result = schedule(
        lua.table_from(
            {
                "num_candidates": num_candidates,
                "cycle": cycle,
                "consecutive_stagnant_cycles": consecutive_stagnant_cycles,
            }
        )
    )
    return _lua_list(result["slots"]), result["mode"], result["counts"]


def test_optimizer_skill_documents_three_phase_rubric_memory_sop():
    skill = OPTIMIZER_SKILL_PATH.read_text(encoding="utf-8")

    assert "Three-Phase Rubric-Memory SOP" in skill
    assert "python -m plexus.cli rubric-memory recent" in skill
    assert "--include-rubric-memory" in skill
    assert "Phase 1" in skill
    assert "Phase 2" in skill
    assert "Phase 3" in skill


def test_optimizer_yaml_defines_dedicated_reporting_agents():
    config = _load_optimizer_config()
    agents = config["agents"]

    assert agents["hypothesis_planner"]["model"] == "gpt-5.4-mini"
    assert agents["code_editor"]["model"] == "gpt-5-mini"
    assert agents["code_editor"]["disable_streaming"] is True

    assert agents["cycle_analyst"]["model"] == "gpt-5-mini"
    assert agents["cycle_analyst"]["max_tokens"] == 16000
    assert agents["cycle_analyst"]["verbosity"] == "low"

    assert agents["report_writer"]["model"] == "gpt-5-mini"
    assert agents["report_writer"]["max_tokens"] == 16000
    assert agents["report_writer"]["verbosity"] == "low"

    assert agents["reviewer"]["model"] == "gpt-5.4-mini"
    assert agents["early_stop_advisor"]["model"] == "gpt-5.4-mini"
    assert agents["early_stop_advisor"]["temperature"] == 1


def test_optimizer_yaml_routes_report_generation_to_reporting_agents():
    config = _load_optimizer_config()
    code = config["code"]

    assert 'run_required_report_phase(\n        cycle_analyst,' in code
    assert 'run_required_report_phase(\n          report_writer,' in code
    assert 'safe_agent_call(agent, agent_name, marked_prompt, nil)' in code
    assert "report_writer.history:add({role = \"system\", content = full_ctx})" in code
    assert "Write a complete technical analysis" not in code


def test_optimizer_yaml_uses_central_agent_steering_not_mailbox_polling():
    config = _load_optimizer_config()
    code = config["code"]

    assert "Phase 4: Mailbox check" not in code
    assert "last_mailbox_check" not in code
    assert "[User guidance injected mid-run]" not in code


def test_optimizer_yaml_uses_dedicated_hypothesis_planner_and_agent_model_overrides():
    config = _load_optimizer_config()
    code = config["code"]
    params = config["params"]

    assert params["agent_models"]["type"] == "object"
    assert "hypothesis_planner" in config["agents"]
    assert "hypothesis_planner.clear_history()" in code
    assert 'safe_agent_call(hypothesis_planner, "hypothesis_planner"' in code
    assert "local response = hypothesis_planner.output or \"\"" in code


def test_optimizer_yaml_protects_structural_lane_from_rubric_candidate_cap():
    config = _load_optimizer_config()
    code = config["code"]

    assert "local function cap_rubric_hypothesis_slots(slots, requested_count)" in code
    assert "local function build_protected_hypothesis_slots(opts)" in code
    assert "num_candidates caps only the three normal rubric lanes" in code
    assert "hyp_slots = cap_hypothesis_slots" not in code
    assert "Generating %s hypotheses" in code
    assert "Hypothesis slots scheduled: %s" in code

    slots, mode, counts = _schedule_slots(num_candidates=3, cycle=1)
    assert slots == ["recent_incremental", "recent_bold", "regression_fix", "structural"]
    assert mode == "normal"
    assert counts["rubric"] == 3
    assert counts["structural"] == 1

    slots, _mode, counts = _schedule_slots(num_candidates=2, cycle=1)
    assert slots == ["recent_incremental", "recent_bold", "structural"]
    assert counts["rubric"] == 2
    assert counts["structural"] == 1

    slots, _mode, counts = _schedule_slots(num_candidates=1, cycle=1)
    assert slots == ["recent_incremental", "structural"]
    assert counts["rubric"] == 1
    assert counts["structural"] == 1


def test_optimizer_yaml_adds_plateau_lanes_on_top_of_protected_lanes():
    slots, mode, counts = _schedule_slots(
        num_candidates=3,
        cycle=1,
        consecutive_stagnant_cycles=3,
    )
    assert slots == [
        "recent_incremental",
        "recent_bold",
        "regression_fix",
        "structural",
        "reframe",
    ]
    assert mode == "escalate"
    assert counts["rubric"] == 3
    assert counts["structural"] == 1
    assert counts["plateau"] == 1

    slots, mode, counts = _schedule_slots(
        num_candidates=3,
        cycle=1,
        consecutive_stagnant_cycles=6,
    )
    assert slots == [
        "recent_incremental",
        "recent_bold",
        "regression_fix",
        "structural",
        "reframe",
        "full_rewrite",
    ]
    assert mode == "ultra_creative"
    assert counts["plateau"] == 2


def test_optimizer_yaml_adds_creative_hypothesis_after_third_cycle():
    config = _load_optimizer_config()
    code = config["code"]
    creative_doc = _read_optimizer_doc("optimizer-cookbook-creative.md")

    assert "local function should_add_creative_hypothesis(cycle_number)" in code
    assert ">= 4" in code
    assert "creative_slots = {\"creative\"}" in code
    assert "OBJECTIVE: Creative hypothesis (cycle 4+ cookbook lane)" in code
    assert "Do NOT let it displace rubric-oriented hypotheses" in code
    assert "Use the creative cookbook injected above" in code
    assert "Repeat the operative prompt instructions 3x" in creative_doc
    assert "Polish" in creative_doc

    slots, _mode, counts = _schedule_slots(num_candidates=3, cycle=4)
    assert slots == [
        "recent_incremental",
        "recent_bold",
        "regression_fix",
        "structural",
        "creative",
    ]
    assert counts["creative"] == 1


def test_optimizer_yaml_uses_lane_specific_cookbooks():
    config = _load_optimizer_config()
    code = config["code"]

    assert 'load_optimizer_cookbook("optimizer-cookbook-normal")' in code
    assert 'load_optimizer_cookbook("optimizer-cookbook-structural")' in code
    assert 'load_optimizer_cookbook("optimizer-cookbook-creative")' in code
    assert "local function cookbook_key_for_slot(slot)" in code
    assert 'if slot == "creative" then' in code
    assert 'if slot == "mechanical_repair" or slot == "structural" or slot == "reframe" or slot == "full_rewrite" then' in code
    assert "slot = slot_name" in code
    assert "Lane-specific cookbooks are injected per hypothesis slot" in code


def test_optimizer_normal_cookbook_emphasizes_rubric_policy_before_mechanics():
    normal_doc = _read_optimizer_doc("optimizer-cookbook-normal.md")

    assert "Missing Policy" in normal_doc
    assert "Ambiguous Criterion" in normal_doc
    assert "Feedback-Direction Targeting" in normal_doc
    assert "Guidelines -> Prompt Alignment" in normal_doc
    assert "Do not spend a normal slot on mechanics alone" in normal_doc
    assert "Repeat the operative prompt instructions 3x" not in normal_doc
    assert "Repeat the whole prompt" not in normal_doc
    assert "Polish" not in normal_doc


def test_optimizer_structural_cookbook_includes_late_prompt_shape_lane():
    structural_doc = _read_optimizer_doc("optimizer-cookbook-structural.md")

    assert "C4. Prompt-Shape / Attention-Structure Transformations" in structural_doc
    assert "lightweight alternative to CoT" in structural_doc
    assert "Repeat the decisive question/rule" in structural_doc
    assert "reorder label definitions or valid_classes" in structural_doc
    assert "C5. Full Rewrite" in structural_doc
    assert "Model Swap" in structural_doc
    assert "Input Source" in structural_doc
    assert "Extractor Node" in structural_doc
    assert "Repeat the operative prompt instructions 3x" not in structural_doc
    assert "Polish" not in structural_doc


def test_optimizer_creative_cookbook_is_isolated_to_creative_lane():
    config = _load_optimizer_config()
    code = config["code"]
    normal_doc = _read_optimizer_doc("optimizer-cookbook-normal.md")
    structural_doc = _read_optimizer_doc("optimizer-cookbook-structural.md")
    creative_doc = _read_optimizer_doc("optimizer-cookbook-creative.md")

    assert "Repeat the operative prompt instructions 3x" in creative_doc
    assert "Polish" in creative_doc
    assert "Transcript First, Instruction Last" in creative_doc
    assert "Repeat the operative prompt instructions 3x" not in normal_doc
    assert "Repeat the operative prompt instructions 3x" not in structural_doc
    assert "Translate the operative prompt or rubric instructions to Polish" not in code
    assert "Repeat the whole prompt twice" not in code


def test_optimizer_yaml_passes_code_editor_context_inline_without_history_injection():
    config = _load_optimizer_config()
    code = config["code"]

    assert "code_editor.history:add" not in code
    assert "=== CURRENT score_config.yaml (the file you are editing) ===" in code
    assert "The current file content is included above in this message." in code
    assert "local synthesis_context_parts = {}" in code
    assert "=== CURRENT score_config.yaml (starting from %s" in code
    assert "Recovered from %s context window error: cleared history, rebuilt inline context" in code


def test_optimizer_yaml_deduplicates_submitted_candidate_records():
    config = _load_optimizer_config()
    code = config["code"]

    assert "local submitted_version_keys = {}" in code
    assert "local submitted_version_ids = {}" in code
    assert "local function record_submitted_version(entry)" in code
    assert "Skipping duplicate submitted version record" in code
    assert "Skipping duplicate submitted candidate version" in code
    assert code.count("table.insert(submitted_versions") == 1


def test_optimizer_yaml_skips_invalid_synthesis_strategy_selection():
    config = _load_optimizer_config()
    code = config["code"]

    assert "if best_sv_score <= -999 then" in code
    assert "no viable synthesis strategy" in code
    assert "Strategy selection skipped" in code
    assert "No viable synthesis strategy selected" in code


def test_optimizer_yaml_ignores_code_editor_prose_after_terminal_tools():
    config = _load_optimizer_config()
    code = config["code"]

    assert 'Tool.last_call("submit_score_version") or Tool.last_call("done")' in code
    assert "Ignoring agent prose after terminal tool call" in code
    assert code.count("Ignoring agent prose after terminal tool call") == 2


def test_optimizer_yaml_handles_semantically_unchanged_submit_errors():
    config = _load_optimizer_config()
    code = config["code"]

    assert "semantically unchanged" in code
    assert "Formatting/comment-only changes do not count" in code


def test_optimizer_startup_requests_retrieval_only_rubric_memory():
    config = _load_optimizer_config()
    code = config["code"]

    assert '"plexus_rubric_memory_evidence_pack"' in code
    assert "synthesize = false" in code


def test_optimizer_startup_requests_recent_rubric_memory():
    config = _load_optimizer_config()
    code = config["code"]

    assert '"plexus_rubric_memory_recent_entries"' in code
    assert "active_rubric_memory_score_version_id = has_text(params.start_version) and params.start_version or nil" in code
    assert "score_version_id = active_rubric_memory_score_version_id" in code
    assert "=== RECENT RUBRIC MEMORY ===" in code
    assert "recent_rubric_memory_briefing = recent_result.markdown_context" in code
    assert 'State.set("recent_rubric_memory_context", recent_result)' in code


def test_optimizer_sme_gate_refreshes_rubric_memory_for_active_version():
    config = _load_optimizer_config()
    code = config["code"]

    assert "ensure_rubric_memory_context_for_version" in code
    assert "rubric_memory_context_score_version" in code
    assert 'topic_hint = purpose or "Optimizer rubric-memory active-version context"' in code
    assert 'State.set("rubric_memory_context_score_version_id", score_version_id)' in code
    assert "gate_rubric_memory_context = ensure_rubric_memory_context_for_version" in code
    assert "rubric_memory_context = gate_rubric_memory_context" in code


def test_optimizer_contradictions_reports_use_active_score_version_cache_key():
    config = _load_optimizer_config()
    code = config["code"]

    assert "contradictions_score_version_id =" in code
    assert "final_contradictions_score_version_id =" in code
    assert "score_version_id = contradictions_score_version_id" in code
    assert "score_version_id = final_contradictions_score_version_id" in code
    assert '" / " .. tostring(contradictions_score_version_id)' in code
    assert '" / " .. tostring(final_contradictions_score_version_id)' in code


def test_optimizer_yaml_treats_interruption_as_terminal_not_retryable():
    config = _load_optimizer_config()
    code = config["code"]

    assert 'return "interrupted"' in code
    assert 'if err_type == "interrupted" then' in code
    assert "error(tostring(err))" in code
    assert 'if classify_error(slot_err) == "interrupted" then' in code
    assert 'if classify_error(cycle_err) == "interrupted" then' in code


def test_optimizer_yaml_records_sample_size_diagnostics():
    config = _load_optimizer_config()
    code = config["code"]

    assert 'State.get("sample_size_diagnostics")' in code
    assert 'State.set("sample_size_diagnostics", sample_size_diagnostics)' in code
    assert "requested_max_samples = min_dataset_rows" in code
    assert "available_rows = selected_row_count" in code


def test_optimizer_yaml_requires_requested_rows_for_cached_regression_dataset():
    config = _load_optimizer_config()
    code = config["code"]

    assert "local dataset_size_adequate = dataset_rows >= min_dataset_rows" in code
    assert "dataset_source_exhausted and dataset_rows >= min_acceptable" in code
    assert "dataset_requested_max_items >= min_dataset_rows" in code
    assert "dataset_check.row_count >= min_acceptable" not in code
    assert "build_source_exhausted" in code
    assert "unbal_source_exhausted" in code
    assert "qualifying_found" in code


def test_optimizer_yaml_bounds_report_context_and_output_shapes():
    config = _load_optimizer_config()
    code = config["code"]

    assert "Keep the entire report under 450 words." in code
    assert "Exactly 4 bullets, one sentence each." in code
    assert "Exactly 3 short subsections. Each must be exactly 2 sentences." in code
    assert "HARD LIMIT: max 3 agenda items. Under 200 words total." in code
    assert 'trunc(history_text, 2000)' in code
    assert 'trunc(ins.analysis, 800)' in code
    assert 'render_items("FALSE POSITIVES (predicted YES, should be NO)", fp_items, 2)' in code
    assert 'render_items("FALSE NEGATIVES (predicted NO, should be YES)", fn_items, 2)' in code
    assert 'render_items("OTHER MISCLASSIFICATIONS", other_items, 1)' in code


def test_optimizer_yaml_uses_required_report_phase_helper_for_all_report_llm_calls():
    config = _load_optimizer_config()
    code = config["code"]

    assert "local function run_required_report_phase" in code
    assert "report_generation_status" in code
    assert "Report phase %s started" in code
    assert "Report phase %s succeeded" in code
    assert "report_generation_failed:" in code
    for phase_id in [
        "cycle_executive_analysis",
        "cycle_lab_report",
        "cycle_sme_agenda",
        "accumulated_lessons",
        "procedure_summary",
        "end_executive_summary",
        "end_lab_report",
        "end_sme_agenda",
    ]:
        assert f'"{phase_id}"' in code
    assert code.count("run_required_report_phase(") >= 9


def test_optimizer_yaml_preprocessing_guidance_starts_with_broad_relevant_windows():
    structural_doc = _read_optimizer_doc("optimizer-cookbook-structural.md")

    assert "RelevantWindowsTranscriptFilter" in structural_doc
    assert "Start with broad sentence windows" in structural_doc
    assert "prev_count=5" in structural_doc
    assert "next_count=8" in structural_doc
    assert "Avoid first attempts with one-word windows" in structural_doc


def test_optimizer_yaml_marks_report_failures_as_terminal_without_losing_cycle_state():
    config = _load_optimizer_config()
    code = config["code"]

    assert 'stop_reason = "report_generation_failed"' in code
    assert 'if string.find(tostring(cycle_err), "report_generation_failed", 1, true) then' in code
    assert 'if stop_reason ~= "report_generation_failed" then' in code
    assert 'error("report_generation_failed:" .. phase .. ": " .. tostring(err))' in code
    assert 'State.set("iterations", iterations)' in code


def test_optimizer_yaml_final_reports_do_not_block_optimizer_completion():
    config = _load_optimizer_config()
    code = config["code"]

    assert 'State.set("optimization_complete", true)' in code
    assert 'State.set("optimizer_result_summary", final_run_summary)' in code
    assert 'State.set("final_report_dispatch", {' in code
    assert "local function run_nonblocking_final_report_phase" in code
    assert 'if string.sub(phase, 1, 4) == "end_" then' in code
    assert "return run_nonblocking_final_report_phase(phase, agent_name, prompt)" in code
    assert 'status = "skipped_nonblocking"' in code
    assert 'mode = "nonblocking_deterministic"' in code
    assert "Final LLM report generation is not run inline with optimizer completion." in code
    assert "Final reports will not block completion." in code
    assert "Main unresolved signal" in code
    assert "FOR YOUR NEXT MEETING" in code
    assert "SME agenda deferred" not in code
    assert "final report deferred" not in code


def test_optimizer_yaml_adds_report_phase_markers_for_context_capture():
    config = _load_optimizer_config()
    code = config["code"]

    assert "local function report_phase_marker" in code
    assert "=== OPTIMIZER REPORT PHASE: " in code
    assert "local marked_prompt = marker .." in code
    assert "turn_label = marker" in code


def test_optimizer_yaml_uses_shared_score_version_test_tool():
    config = _load_optimizer_config()
    code = config["code"]

    assert 'call_plexus_tool, "plexus_score_test"' in code
    assert 'version              = candidate_id' in code
    assert 'samples              = 3' in code


def test_optimizer_yaml_routes_unresolved_placeholders_to_mechanical_repair_lane():
    config = _load_optimizer_config()
    code = config["code"]

    assert 'failure_code=unresolved_prompt_placeholders' in code
    assert '"mechanical_repair"' in code
    assert "OBJECTIVE: Mechanical prompt-rendering repair" in code
    assert "Do not target recurrence, RCA topics, model behavior, or rubric semantics" in code
    assert "{{ metadata.disposition }}" in code
    assert "mechanical_prompt_failure = mechanical_prompt_failure" in code
    assert "Mechanical prompt-rendering preflight failed; scheduling repair lane" in code
    assert "MECHANICAL PROMPT RENDERING FAILURE" in code
    assert "Repair placeholder syntax or metadata interpolation before attempting rubric tuning." in code
    assert 'skip_reason = "mechanical_repair_failed"' in code
    assert 'stop_reason = "mechanical_failure"' in code
    assert 'State.set("mechanical_prompt_failure_unresolved", true)' in code
    assert "Mechanical prompt repair did not produce a smoke-test-clean version; stopping before rubric optimization." in code


def test_optimizer_yaml_protects_mechanically_clean_prompt_lines_after_repair():
    config = _load_optimizer_config()
    code = config["code"]

    assert "local function contains_legacy_xcc_placeholders(text)" in code
    assert "local function build_mechanical_integrity_guard_text(code_text, start_label)" in code
    assert "The starting YAML (%s) is already mechanically clean for legacy placeholder syntax." in code
    assert "Any candidate that reintroduces `{xcc:` will be rejected before evaluation." in code
    assert 'local protect_mechanical_prompt_lines = not has_text(mechanical_prompt_failure)' in code
    assert 'and not contains_legacy_xcc_placeholders(current_code)' in code
    assert 'build_mechanical_integrity_guard_text(current_code, "current base version")' in code
    assert 'build_mechanical_integrity_guard_text(start_code, start_label)' in code
    assert 'build_legacy_placeholder_guard_failure(candidate_id, submitted_file_content)' in code


def test_optimizer_yaml_strategy_b_uses_clean_starting_point_when_baseline_is_mechanically_dirty():
    config = _load_optimizer_config()
    code = config["code"]

    assert "local strategy_b_start_code = current_code" in code
    assert 'if contains_legacy_xcc_placeholders(current_code) and not contains_legacy_xcc_placeholders(synth_start_code) then' in code
    assert 'strategy_b_start_code = synth_start_code' in code
    assert 'strategy_b_start_label = "MECHANICALLY CLEAN STARTING POINT (" .. synth_start_label .. ")"' in code
    assert 'diag("Strategy B switching from mechanically dirty baseline to smoke-test-clean starting point")' in code
    assert 'run_synthesis_react(table.concat(strategy_b_parts, "\\n"), strategy_b_start_code, strategy_b_start_label, strategy_b_parent_version_id, 10, "Strategy-B")' in code


def test_optimizer_yaml_defines_safe_encode_for_score_test_failure_details():
    config = _load_optimizer_config()
    code = config["code"]

    assert "local function safe_encode(value)" in code
    assert "return Json.encode(value)" in code
    assert "if test_result.failures and #test_result.failures > 0 then" in code
    assert 'safe_encode(test_result.failures)' in code
    assert 'safe_encode(test_result.predictions)' in code


def test_optimizer_yaml_gates_sme_questions_with_rubric_memory():
    config = _load_optimizer_config()
    code = config["code"]
    tools = config["agents"]["code_editor"]["tools"]
    system_prompt = config["agents"]["code_editor"]["system_prompt"]

    assert "plexus_rubric_memory_recent_entries" in tools
    assert "plexus_rubric_memory_sme_question_gate" in tools
    assert "Before concluding that SME input is needed, check rubric memory." in system_prompt
    assert "Begin policy-sensitive work by reviewing recent rubric memory" in system_prompt
    assert "local function gate_sme_agenda" in code
    assert '"plexus_rubric_memory_sme_question_gate"' in code
    assert '"cycle_" .. tostring(cycle) .. "_sme_agenda"' in code
    assert '"end_of_run_sme_agenda"' in code
    assert 'State.set("sme_agenda_raw"' in code
    assert 'State.set("sme_agenda_gated"' in code
    assert 'State.set("sme_question_gate_diagnostics"' in code


def test_optimizer_yaml_runs_contradictions_directly_without_background_dispatch():
    config = _load_optimizer_config()
    code = config["code"]

    assert "local bg = opts.background or false" not in code
    assert 'background = true' not in code
    assert 'background = false' not in code
    assert "dispatched in background" not in code
    assert "consume results later" not in code
    assert "include_rubric_memory = false" not in code
    assert "include_rubric_memory = true" in code
    assert 'pcall(refresh_known_contradictions, 0, {ttl_hours = 48})' in code
    assert 'cache_key = "FeedbackContradictions (expanded): " .. scorecard_name .. " / " .. score_name' in code


def test_optimizer_baseline_feedback_runs_score_rubric_consistency_check():
    config = _load_optimizer_config()
    code = config["code"]

    assert "score_rubric_consistency_check = true" in code
    assert 'evaluation_type    = "feedback"' in code


def test_optimizer_yaml_freezes_feedback_window_instead_of_stopping_on_new_feedback():
    config = _load_optimizer_config()
    code = config["code"]
    params = config["params"]

    assert params["feedback_window_start_at"]["type"] == "string"
    assert params["feedback_window_end_at"]["type"] == "string"
    assert 'State.set("feedback_window_start_at", params.feedback_window_start_at)' in code
    assert 'State.set("feedback_window_end_at", params.feedback_window_end_at)' in code
    assert 'feedback_start_at = params.feedback_window_start_at' in code
    assert 'feedback_end_at = params.feedback_window_end_at' in code
    assert 'start_at = params.feedback_window_start_at' in code
    assert 'end_at = params.feedback_window_end_at' in code
    assert '" / " .. tostring(params.feedback_window_start_at) .. " / " .. tostring(params.feedback_window_end_at)' in code
    assert 'State.set("feedback_target_advanced_ignored"' in code
    assert "Continuing against frozen window ending" in code
    assert "feedback_target_changed_restart_required" not in code
    assert "os.time()" not in code
    assert 'os.date("!%Y-%m-%dT%H:%M:%SZ",' not in code


def test_optimizer_cli_computes_frozen_feedback_window():
    start_at, end_at = _optimizer_feedback_window(
        90,
        datetime(2026, 5, 9, 12, 0, 0, tzinfo=timezone.utc),
    )

    assert start_at == "2026-02-08T12:00:00Z"
    assert end_at == "2026-05-09T12:00:00Z"


def test_optimizer_yaml_persists_configured_max_iterations_for_reporting():
    config = _load_optimizer_config()
    code = config["code"]

    assert 'State.set("configured_max_iterations", params.max_iterations)' in code
    assert "configured_max_iterations = params.max_iterations" in code


def test_optimizer_yaml_persists_no_feedback_terminal_summary():
    config = _load_optimizer_config()
    code = config["code"]

    assert 'State.set("stop_reason", "skipped_no_feedback")' in code
    assert 'stop_reason = "skipped_no_feedback"' in code
    assert 'State.set("end_of_run_report", {' in code
    assert 'status = "skipped_no_feedback"' in code


def test_optimizer_yaml_treats_cycle_errors_as_terminal_and_does_not_extend_iteration_cap():
    config = _load_optimizer_config()
    code = config["code"]

    assert "local max_cycles = params.max_iterations" in code
    assert "max_cycles = max_cycles + 1" not in code
    assert '"ERROR in cycle %d: %s — stopping run"' in code
    assert 'stop_reason = "error"' in code
    assert 'error("Cycle " .. tostring(cycle) .. " failed: " .. tostring(cycle_err))' in code


def test_optimizer_yaml_avoids_double_counting_after_cycle_record_and_formats_cycle_prompt_with_cycle_number():
    config = _load_optimizer_config()
    code = config["code"]

    assert "local cycle_recorded = false" in code
    assert "if not cycle_recorded then" in code
    assert "cycle_recorded = true" in code
    assert 'Analyze Cycle %d and produce exactly four sections in this order:\\n"' in code
    assert '.. "- No long paragraphs anywhere\\n",' in code
    assert "cycle))" in code


def test_optimizer_yaml_never_promotes_champion_and_reports_manual_follow_up():
    config = _load_optimizer_config()
    code = config["code"]

    assert "plexus_score_set_champion" not in code
    assert "Promoting winning version" not in code
    assert "Champion promoted:" not in code
    assert "Manual promotion is required; the optimizer never promotes champion automatically." in code
    assert "Winning version remains the current champion" in code
    assert "No promotion was performed." in code
    assert "winning_version_id = last_accepted_version_id" in code


def test_optimizer_yaml_rejects_non_completed_evaluation_handles():
    config = _load_optimizer_config()
    code = config["code"]

    assert "local eval_status = string.upper(tostring(eval_data.status or waited.status or \"\"))" in code
    assert 'if eval_status ~= "COMPLETED" then' in code
    assert "local eval_error = eval_data.error_message or eval_data.errorMessage" in code
    assert '" error_message=" .. tostring(eval_error)' in code
    assert '"Evaluation did not complete: status=" .. tostring(eval_data.status or waited.status)' in code
    assert "score_version_id = eval_result.score_version_id or eval_result.scoreVersionId" in code


def test_optimizer_yaml_skips_scores_with_no_recent_feedback_baseline():
    config = _load_optimizer_config()
    code = config["code"]

    assert "local function is_no_feedback_baseline_error(err)" in code
    assert '"no qualifying feedback"' in code
    assert '"no labeled samples"' in code
    assert '"dataset not found"' in code
    assert 'status = "skipped_no_feedback"' in code
    assert "No qualifying recent feedback is available for " in code


def test_optimizer_yaml_fails_fast_on_infrastructure_submit_errors():
    config = _load_optimizer_config()
    code = config["code"]

    assert "local function is_non_recoverable_submit_error(err)" in code
    assert '"graphql query failed"' in code
    assert '"invalid value"' in code
    assert '"missing api"' in code
    assert '"semantically unchanged"' in code
    assert 'error("submit_score_version infrastructure error: " .. tostring(submit_result.error))' in code
    assert code.count("is_non_recoverable_submit_error(submit_result.error)") >= 2


def test_optimizer_yaml_marks_one_cycle_runs_as_verification_only():
    config = _load_optimizer_config()
    code = config["code"]

    assert "Single-cycle verification run: this will validate one optimization cycle only and will not perform champion promotion." in code
    assert 'local completion_mode = params.max_iterations == 1 and "Verification complete" or "Optimization complete"' in code


def test_optimizer_yaml_runs_diagnostic_synthesis_when_no_hypothesis_has_positive_signal():
    config = _load_optimizer_config()
    code = config["code"]

    assert "if #succeeded == 0 and not any_partial_positive then" in code
    assert "Running diagnostic synthesis despite 0 successes and no positive hypothesis signal" in code
    assert "All %d hypotheses regressed; synthesis must start from baseline and treat failed edits as negative evidence" in code
    assert "Start from BASELINE, not from any failed hypothesis code." in code
    assert "no_successful_hypotheses_no_positive_signal" not in code


def test_optimizer_yaml_records_visible_synthesis_decision_when_no_version_is_evaluated():
    config = _load_optimizer_config()
    code = config["code"]

    assert "local synthesis_decision_log = nil" in code
    assert 'build_synthesis_decision_log(\n          "not_evaluated"' in code
    assert '"no_synthesis_version_and_no_successful_hypothesis"' in code
    assert "synthesis_decision_log = build_synthesis_decision_log" in code
    assert "dual_synthesis = synthesis_decision_log" in code
    assert "Cycle %d — No synthesis version was evaluated; recorded synthesis decision artifact" in code


def test_optimizer_yaml_uses_safe_tool_call_arg_helper_instead_of_direct_args_dereferences():
    config = _load_optimizer_config()
    code = config["code"]

    assert "local function tool_call_arg(call, key, default)" in code
    assert ".args.command" not in code
    assert ".args.reason" not in code
    assert ".args.version_note" not in code
    assert ".args.old_str" not in code
    assert ".args.new_str" not in code


def test_optimizer_yaml_uses_utf8_safe_truncation_without_byte_slicing():
    config = _load_optimizer_config()
    code = config["code"]

    assert "local function trunc(s, maxlen)" in code
    assert "local str = utf8_clean(tostring(s))" in code
    assert "return utf8_clean(string.sub(str, 1, maxlen))" in code
    assert "string.char(string.byte(str, i))" not in code


def test_optimizer_yaml_rebaselines_continuations_when_feedback_target_advanced():
    config = _load_optimizer_config()
    code = config["code"]

    assert "local continuation_rebaseline = false" in code
    assert "Continuation detected newer feedback target" in code
    assert "if not is_continuation or continuation_rebaseline then" in code
    assert 'if not is_continuation then' in code
    assert 'State.set("iterations", {})' in code


def test_optimizer_yaml_escalates_plateaus_instead_of_stopping_or_shrinking():
    config = _load_optimizer_config()
    code = config["code"]

    assert 'stop_reason = "improvement_plateau"' not in code
    assert 'stop_reason = "early_stopped"' not in code
    assert "Conservatism mode" not in code
    assert "ULTRA-CONSERVATIVE" not in code
    assert 'hyp_slots = {"recent_incremental"}' not in code
    assert 'hyp_slots = {"recent_incremental", "structural"}' not in code
    assert 'plateau_slots = {"reframe"}' in code
    assert 'plateau_slots = {"reframe", "full_rewrite"}' in code
    assert 'The run is stuck. Search harder instead of shrinking the hypothesis set.' in code
    assert 'Recent cycles are flat. Broaden search instead of reducing ambition.' in code


def test_optimizer_yaml_flags_repeated_strongly_harmful_hypothesis_territory_without_erasing_lane():
    config = _load_optimizer_config()
    code = config["code"]

    assert "local HYPOTHESIS_REPEAT_STOPWORDS" in code
    assert "hypothesis_repeats_strongly_harmful_prior" in code
    assert "fb_d < -0.05 or acc_d < -0.05" in code
    assert "overlaps strongly harmful cycle" in code
    assert "flagged as repeated harmful territory" in code
    assert "preserving lane and steering edit away from prior failure" in code
    assert "Preserve this protected lane, but avoid copying the failed policy family, wording family, or evidence rule." in code
    assert "blocked for harmful repeat, retrying with hard exclusion" not in code


def test_optimizer_yaml_keeps_bold_lane_and_uses_escalation_advisor():
    config = _load_optimizer_config()
    code = config["code"]
    structural_doc = _read_optimizer_doc("optimizer-cookbook-structural.md")

    assert 'done(escalation_mode=\\"escalate\\", reason=...)' in code
    assert 'done(escalation_mode=\\"ultra_creative\\", reason=...)' in code
    assert 'Plateau escalation advisor' in code
    assert 'OBJECTIVE: Reframe the problem (cross-cycle reinterpretation)' in code
    assert 'OBJECTIVE: Full rewrite from a new framing' in code
    assert 'Remove or relax a processor that is suppressing reviewer-relevant evidence.' in structural_doc


def test_optimizer_yaml_builds_agent_recurrence_context_with_emerging_items():
    config = _load_optimizer_config()
    code = config["code"]

    assert "local function build_recurrence_agent_context(tracker, cycle, max_items)" in code
    assert "local function build_recurrence_agent_rows(tracker, cycle, max_items)" in code
    assert "RECURRENT MISCLASSIFICATION CONTEXT FOR OPTIMIZER AGENTS" in code
    assert "Treat EMERGING items below as early warning examples" in code
    assert "RECURRENCE_PATTERN_PRIORITY = {" in code
    assert "EMERGING = 5" in code
    assert "#per_cycle >= 2 or wrong >= 2 or (wrong >= 1 and correct >= 1)" in code
    assert 'local is_early_warning = (entry.pattern == "EMERGING" and wrong >= 1)' in code
    assert "has_repeat_history or is_early_warning" in code
    assert "pattern=%s%s" in code


def test_optimizer_yaml_injects_agent_recurrence_context_into_reasoning_paths():
    config = _load_optimizer_config()
    code = config["code"]

    assert "local recurrence_agent_context = build_recurrence_agent_context(State.get(\"item_recurrence\") or {}, cycle, 12)" in code
    assert code.count("build_recurrence_agent_context(State.get(\"item_recurrence\") or {}, cycle, 12)") >= 7
    assert 'notify_recurrence_context_injected("hypothesis"' in code
    assert 'notify_recurrence_context_injected("editor"' in code
    assert 'notify_recurrence_context_injected("synthesis"' in code
    assert 'notify_recurrence_context_injected("reviewer"' in code
    assert "cycle_recurrence_agent_context = build_recurrence_agent_context(ir, cycle, 12) or \"\"" in code
    assert "Escalation guidance: if these items are still recurring" in code


def test_optimizer_yaml_logs_auditable_recurrence_context_fingerprint():
    config = _load_optimizer_config()
    code = config["code"]

    assert "local function build_recurrence_context_audit(tracker, cycle, max_items)" in code
    assert "local function notify_recurrence_context_injected(context_label, tracker, cycle)" in code
    assert "target=%s %s; top3=[%s]" in code
    assert "wrong=%dx correct=%dx label=%s model=%s trajectory=%s" in code
    assert 'State.set("last_recurrence_context_audit"' in code
    assert "Injected recurrent misclassification context: %s" in code
    assert 'notify_recurrence_context_injected("planning"' in code
    assert 'notify_recurrence_context_injected("hypothesis"' in code
    assert 'notify_recurrence_context_injected("editor"' in code
    assert 'notify_recurrence_context_injected("synthesis"' in code
    assert 'notify_recurrence_context_injected("strategy_b"' in code
    assert 'notify_recurrence_context_injected("reviewer"' in code


def test_optimizer_yaml_hypotheses_must_account_for_recurrence_targets():
    config = _load_optimizer_config()
    code = config["code"]

    assert "Your description MUST name the recurrence target pattern/item group" in code
    assert "no recurrence target" in code
    assert "feedback-focused hypothesis this cycle must target its top recurrence group" in code
    assert "For OSCILLATING items, prefer narrow predicates" in code
    assert "If recurrent misclassification context is present, your edit must either target the named recurrence group" in code


def test_optimizer_yaml_records_recurrence_for_failed_no_synthesis_cycles():
    config = _load_optimizer_config()
    code = config["code"]

    assert "local function record_cycle_item_recurrence(cycle, item_classifications, cycle_context, notify_public)" in code
    assert "record_cycle_item_recurrence(cycle, fb_item_class" in code
    assert "failed_fb_item_class" in code
    assert "record_cycle_item_recurrence(cycle, failed_fb_item_class" in code
    assert "Cycle %d - Repeat Misclassification Tracker: no repeat or transition-history items yet." in code
