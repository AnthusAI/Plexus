from pathlib import Path

import yaml


OPTIMIZER_YAML_PATH = (
    Path(__file__).resolve().parents[2] / "procedures" / "feedback_alignment_optimizer.yaml"
)


def _load_optimizer_config():
    with OPTIMIZER_YAML_PATH.open() as f:
        return yaml.safe_load(f)


def _split_top_level_lua_args(args_text: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    in_string = False
    quote = ""
    escaped = False

    for ch in args_text:
        if in_string:
            buf.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                in_string = False
            continue

        if ch in ('"', "'"):
            in_string = True
            quote = ch
            buf.append(ch)
            continue

        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)

        if ch == "," and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)

    if buf:
        parts.append("".join(buf).strip())

    return parts


def _find_unbound_string_format_placeholders(lua_code: str) -> list[tuple[int, str]]:
    needle = "string.format("
    findings: list[tuple[int, str]] = []
    i = 0

    while True:
        start = lua_code.find(needle, i)
        if start == -1:
            break
        j = start + len(needle)
        depth = 1
        in_string = False
        quote = ""
        escaped = False

        while j < len(lua_code) and depth > 0:
            ch = lua_code[j]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == quote:
                    in_string = False
            else:
                if ch in ('"', "'"):
                    in_string = True
                    quote = ch
                elif ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
            j += 1

        args_text = lua_code[start + len(needle): j - 1]
        args = _split_top_level_lua_args(args_text)
        if len(args) == 1 and "%" in args[0]:
            line = lua_code[:start].count("\n") + 1
            findings.append((line, args[0]))

        i = j

    return findings


def test_optimizer_yaml_defines_dedicated_reporting_agents():
    config = _load_optimizer_config()
    agents = config["agents"]

    assert agents["code_editor"]["model"] == "gpt-5.4"

    assert agents["cycle_analyst"]["model"] == "gpt-5.4"
    assert agents["cycle_analyst"]["max_tokens"] == 1200
    assert agents["cycle_analyst"]["verbosity"] == "low"

    assert agents["report_writer"]["model"] == "gpt-5.2"
    assert agents["report_writer"]["max_tokens"] == 900
    assert agents["report_writer"]["verbosity"] == "low"


def test_optimizer_yaml_routes_report_generation_to_reporting_agents():
    config = _load_optimizer_config()
    code = config["code"]

    assert 'safe_agent_call(cycle_analyst, "cycle_analyst"' in code
    assert 'safe_agent_call(report_writer, "report_writer"' in code
    assert "report_writer.history:add({role = \"system\", content = full_ctx})" in code
    assert "Write a complete technical analysis" not in code


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


def test_optimizer_yaml_runs_contradictions_directly_without_background_dispatch():
    config = _load_optimizer_config()
    code = config["code"]

    assert "local bg = opts.background or false" not in code
    assert 'background = true' not in code
    assert 'background = false' not in code
    assert "dispatched in background" not in code
    assert "consume results later" not in code
    assert 'pcall(refresh_known_contradictions, 0, {ttl_hours = 48})' in code
    assert 'cache_key = "FeedbackContradictions (expanded): " .. scorecard_name .. " / " .. score_name' in code


def test_optimizer_yaml_uses_plateau_escalation_without_plateau_stop():
    config = _load_optimizer_config()
    code = config["code"]

    assert 'local plateau_mode = State.get("plateau_mode") == true' in code
    assert 'plateau_slots = {"recent_incremental", "structural", "aggressive_rebuild", "regression_fix"}' in code
    assert 'effective_candidates = math.min(base_candidates + 1, 4)' in code
    assert 'Plateau detected after %d stagnant cycles; escalating search breadth and structural exploration.' in code
    assert "improvement_plateau" not in code
    assert "early_stopped" not in code
    assert "stopping (improvement plateau)" not in code


def test_optimizer_yaml_classifies_blocked_cycle_outcomes_explicitly():
    config = _load_optimizer_config()
    code = config["code"]

    assert 'local function classify_cycle_outcome(iter)' in code
    assert 'return "blocked_cannot_improve"' in code
    assert 'return "blocked_mechanical"' in code
    assert 'return "blocked_cycle_error"' in code
    assert 'outcome = blocked_outcome' in code
    assert 'outcome = "blocked_mechanical"' in code
    assert 'outcome = "blocked_cycle_error"' in code
    assert 'blocked_reason = blocked_message' in code
    assert 'pcall(call_plexus_tool, "plexus_set_stage_status"' in code
    assert 'Running: %d accepted, %d carried (neutral), %d rejected, %d blocked(cannot_improve), %d blocked(mechanical), %d blocked(cycle_error)' in code


def test_optimizer_yaml_treats_str_replace_mismatch_as_edit_failure():
    config = _load_optimizer_config()
    code = config["code"]

    assert 'local function is_editor_error_result(edit_result)' in code
    assert "doesn't exactly match the file content" in code
    assert "no match found for old_str" in code
    assert 'is_editor_error_result(edit_result)' in code


def test_optimizer_yaml_uses_line_based_editor_protocol():
    config = _load_optimizer_config()
    code = config["code"]

    assert "command='replace_lines'" in code
    assert "use view with view_range to get numbered lines for replace_lines" in code
    assert "copy your old_str EXACTLY" not in code
    assert "Use the numbered lines you just viewed and call str_replace_editor with command='replace_lines'" in code


def test_optimizer_yaml_updates_stage_status_for_live_cycle_subphases():
    config = _load_optimizer_config()
    code = config["code"]

    assert 'local function set_stage_status(message)' in code
    assert 'Cycle %d: editing hypothesis %d/%d (%s)' in code
    assert 'Cycle %d: smoke testing candidate version %s' in code
    assert 'Cycle %d: evaluating %d submitted candidate version(s)' in code


def test_optimizer_yaml_has_no_unbound_string_format_placeholders():
    config = _load_optimizer_config()
    code = config["code"]

    findings = _find_unbound_string_format_placeholders(code)
    assert findings == [], f"Unbound string.format placeholders found: {findings}"
