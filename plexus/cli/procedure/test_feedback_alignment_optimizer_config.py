from pathlib import Path

import yaml


OPTIMIZER_YAML_PATH = (
    Path(__file__).resolve().parents[2] / "procedures" / "feedback_alignment_optimizer.yaml"
)


def _load_optimizer_config():
    with OPTIMIZER_YAML_PATH.open() as f:
        return yaml.safe_load(f)


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

    assert 'safe_agent_call(cycle_analyst, "cycle_analyst"' in code
    assert 'safe_agent_call(report_writer, "report_writer"' in code
    assert "report_writer.history:add({role = \"system\", content = full_ctx})" in code
    assert "Write a complete technical analysis" not in code


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
    assert "local function record_submitted_version(entry)" in code
    assert "Skipping duplicate submitted version record" in code
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


def test_optimizer_startup_requests_retrieval_only_rubric_memory():
    config = _load_optimizer_config()
    code = config["code"]

    assert '"plexus_rubric_memory_evidence_pack"' in code
    assert "synthesize = false" in code


def test_optimizer_yaml_bounds_report_context_and_output_shapes():
    config = _load_optimizer_config()
    code = config["code"]

    assert "Keep the entire report under 450 words." in code
    assert "Exactly 4 bullets, one sentence each." in code
    assert "Exactly 3 short subsections. Each must be exactly 2 sentences." in code
    assert "HARD LIMIT: max 3 agenda items. Under 150 words total." in code
    assert 'trunc(history_text, 2000)' in code
    assert 'trunc(ins.analysis, 800)' in code
    assert 'render_items("FALSE POSITIVES (predicted YES, should be NO)", fp_items, 2)' in code
    assert 'render_items("FALSE NEGATIVES (predicted NO, should be YES)", fn_items, 2)' in code
    assert 'render_items("OTHER MISCLASSIFICATIONS", other_items, 1)' in code


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

    assert "plexus_rubric_memory_sme_question_gate" in tools
    assert "Before concluding that SME input is needed, check rubric memory." in system_prompt
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
    assert "include_rubric_memory = false" in code
    assert 'pcall(refresh_known_contradictions, 0, {ttl_hours = 48})' in code
    assert 'cache_key = "FeedbackContradictions (expanded): " .. scorecard_name .. " / " .. score_name' in code


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


def test_optimizer_yaml_keeps_bold_lane_and_uses_escalation_advisor():
    config = _load_optimizer_config()
    code = config["code"]

    assert 'done(escalation_mode=\\"escalate\\", reason=...)' in code
    assert 'done(escalation_mode=\\"ultra_creative\\", reason=...)' in code
    assert 'Plateau escalation advisor' in code
    assert 'OBJECTIVE: Reframe the problem (cross-cycle reinterpretation)' in code
    assert 'OBJECTIVE: Full rewrite from a new framing' in code
    assert 'Removing a harmful filter is a valid structural hypothesis.' in code
