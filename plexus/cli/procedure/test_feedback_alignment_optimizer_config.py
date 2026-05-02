from pathlib import Path

import yaml


OPTIMIZER_YAML_PATH = (
    Path(__file__).resolve().parents[2] / "procedures" / "feedback_alignment_optimizer.yaml"
)
OPTIMIZER_SKILL_PATH = (
    Path(__file__).resolve().parents[3] / "skills" / "plexus-score-optimizer" / "SKILL.md"
)


def _load_optimizer_config():
    with OPTIMIZER_YAML_PATH.open() as f:
        return yaml.safe_load(f)


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


def test_optimizer_yaml_caps_hypothesis_slots_by_requested_num_candidates():
    config = _load_optimizer_config()
    code = config["code"]

    assert "local function cap_hypothesis_slots(slots, requested_count)" in code
    assert "hyp_slots = cap_hypothesis_slots(hyp_slots, params.num_candidates)" in code
    assert "for i = 1, cap do" in code
    assert "Generating %d/%d requested hypotheses" in code
    assert "else\n      hyp_slots =" not in code


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
    config = _load_optimizer_config()
    code = config["code"]

    assert "RelevantWindowsTranscriptFilter" in code
    assert "start with broad sentence windows" in code
    assert "prev_count=5 and next_count=8" in code
    assert "Do not start with prev_count=1/next_count=1 word windows" in code


def test_optimizer_yaml_marks_report_failures_as_terminal_without_losing_cycle_state():
    config = _load_optimizer_config()
    code = config["code"]

    assert 'stop_reason = "report_generation_failed"' in code
    assert 'if string.find(tostring(cycle_err), "report_generation_failed", 1, true) then' in code
    assert 'if stop_reason ~= "report_generation_failed" then' in code
    assert 'error("report_generation_failed:" .. phase .. ": " .. tostring(err))' in code
    assert 'State.set("iterations", iterations)' in code


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


def test_optimizer_yaml_marks_one_cycle_runs_as_verification_only():
    config = _load_optimizer_config()
    code = config["code"]

    assert "Single-cycle verification run: this will validate one optimization cycle only and will not perform champion promotion." in code
    assert 'local completion_mode = params.max_iterations == 1 and "Verification complete" or "Optimization complete"' in code


def test_optimizer_yaml_skips_synthesis_when_no_hypothesis_has_positive_signal():
    config = _load_optimizer_config()
    code = config["code"]

    assert "if #succeeded == 0 and not any_partial_positive then" in code
    assert "no_successful_hypotheses_no_positive_signal" in code
    assert "no hypotheses succeeded and no positive signal was found" in code


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
    assert 'table.insert(slots, "reframe")' in code
    assert 'table.insert(slots, "full_rewrite")' in code
    assert 'The run is stuck. Search harder instead of shrinking the hypothesis set.' in code
    assert 'Recent cycles are flat. Broaden search instead of reducing ambition.' in code


def test_optimizer_yaml_rejects_repeated_strongly_harmful_hypothesis_territory():
    config = _load_optimizer_config()
    code = config["code"]

    assert "local HYPOTHESIS_REPEAT_STOPWORDS" in code
    assert "hypothesis_repeats_strongly_harmful_prior" in code
    assert "fb_d < -0.05 or acc_d < -0.05" in code
    assert "overlaps strongly harmful cycle" in code
    assert "rejected as repeated harmful territory" in code
    assert "blocked for harmful repeat, retrying with hard exclusion" in code
    assert "Do not target the same policy family, wording family, or evidence rule." in code


def test_optimizer_yaml_keeps_bold_lane_and_uses_escalation_advisor():
    config = _load_optimizer_config()
    code = config["code"]

    assert 'done(escalation_mode=\\"escalate\\", reason=...)' in code
    assert 'done(escalation_mode=\\"ultra_creative\\", reason=...)' in code
    assert 'Plateau escalation advisor' in code
    assert 'OBJECTIVE: Reframe the problem (cross-cycle reinterpretation)' in code
    assert 'OBJECTIVE: Full rewrite from a new framing' in code
    assert 'Removing a harmful filter is a valid structural hypothesis.' in code
