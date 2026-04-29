"""Validation harness for the runtime MCP spike.

This first version is intentionally provider-neutral. It can run all curated
tasks against a deterministic `stub-oracle` adapter that exercises the
fixture-backed PlexusModule and the result checkers. Real model adapters should
produce the same AttemptResult shape after calling the eventual `execute_tactus`
tool.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

import yaml

from plexus_module_stub import PlexusModule, PlexusStubError, create_plexus_module


ROOT = Path(__file__).resolve().parent
TASKS_DIR = ROOT / "tasks"
RESULTS_DIR = ROOT / "results"
BOOT_PROMPT = ROOT / "boot_prompt.md"
BOOT_PROMPT_TOKEN_LIMIT = 2000
DEFAULT_MAX_TOTAL_COST_USD = 50.0
DEFAULT_ESTIMATED_REAL_CALL_COST_USD = 0.20


@dataclass
class SpikeTask:
    id: str
    name: str
    prompt: str
    expected_outcome: dict[str, Any]
    coverage_tags: list[str]
    required_apis: list[str]
    forbidden_apis: list[str] = field(default_factory=list)
    max_attempts_for_first_try_pass: int = 1
    fixture_notes: str = ""


@dataclass
class AttemptResult:
    task_id: str
    model_id: str
    succeeded_first_try: bool
    attempts_used: int
    total_input_tokens: int
    total_output_tokens: int
    tool_definition_tokens: int
    latency_ms: int
    total_cost_usd: float
    generated_tactus_per_attempt: list[str]
    errors_per_attempt: list[dict[str, Any]]
    failure_classification: str | None
    full_transcript: list[dict[str, Any]]
    final_value: dict[str, Any] | list[Any] | None
    api_calls: list[str]
    stream_events: list[dict[str, Any]]
    check_results: dict[str, Any]


def estimate_tokens(text: str) -> int:
    try:
        import tiktoken

        encoder = tiktoken.get_encoding("cl100k_base")
        return len(encoder.encode(text))
    except Exception:
        return max(len(text) // 4, 1)


def normalize_provider_usage(transcript: list[dict[str, Any]]) -> dict[str, int | None]:
    """Extract provider-reported token usage from a model transcript."""

    input_tokens = 0
    output_tokens = 0
    total_tokens = 0
    saw_input = False
    saw_output = False
    saw_total = False

    for message in transcript:
        usage = message.get("usage")
        if not usage:
            continue
        if hasattr(usage, "model_dump"):
            usage = usage.model_dump()
        if not isinstance(usage, dict):
            continue

        message_input = usage.get("input_tokens") or usage.get("prompt_tokens")
        message_output = usage.get("output_tokens") or usage.get("completion_tokens")
        message_total = usage.get("total_tokens")

        if message_total is not None and message_input is not None and message_output is None:
            message_output = max(message_total - message_input, 0)
        if message_total is not None and message_output is not None and message_input is None:
            message_input = max(message_total - message_output, 0)

        if message_input is not None:
            input_tokens += int(message_input)
            saw_input = True
        if message_output is not None:
            output_tokens += int(message_output)
            saw_output = True
        if message_total is not None:
            total_tokens += int(message_total)
            saw_total = True

    return {
        "input_tokens": input_tokens if saw_input else None,
        "output_tokens": output_tokens if saw_output else None,
        "total_tokens": total_tokens if saw_total else None,
    }


def validate_boot_prompt(path: Path = BOOT_PROMPT) -> int:
    if not path.exists():
        raise ValueError(f"boot prompt not found: {path}")
    token_count = estimate_tokens(path.read_text())
    if token_count > BOOT_PROMPT_TOKEN_LIMIT:
        raise ValueError(
            f"boot prompt is {token_count} tokens; limit is {BOOT_PROMPT_TOKEN_LIMIT}"
        )
    return token_count


def load_tasks(tasks_dir: Path = TASKS_DIR) -> list[SpikeTask]:
    tasks: list[SpikeTask] = []
    for path in sorted(tasks_dir.glob("*.yaml")):
        data = yaml.safe_load(path.read_text())
        tasks.append(
            SpikeTask(
                id=data["id"],
                name=data["name"],
                prompt=data["prompt"],
                expected_outcome=data["expected_outcome"],
                coverage_tags=data["coverage_tags"],
                required_apis=data["required_apis"],
                forbidden_apis=data.get("forbidden_apis", []),
                max_attempts_for_first_try_pass=data.get(
                    "max_attempts_for_first_try_pass", 1
                ),
                fixture_notes=data.get("fixture_notes", ""),
            )
        )
    return tasks


def validate_tasks(tasks: list[SpikeTask]) -> None:
    ids: set[str] = set()
    for task in tasks:
        if task.id in ids:
            raise ValueError(f"duplicate task id: {task.id}")
        ids.add(task.id)
        if task.max_attempts_for_first_try_pass != 1:
            raise ValueError(f"{task.id}: max_attempts_for_first_try_pass must be 1")
        if not task.coverage_tags:
            raise ValueError(f"{task.id}: coverage_tags is empty")
        if not task.required_apis:
            raise ValueError(f"{task.id}: required_apis is empty")


def fields_present(value: dict[str, Any], fields: list[str]) -> bool:
    return all(field in value and value[field] is not None for field in fields)


def cost_usd(value: Any, default: float = 999.0) -> float:
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, dict):
        for key in ("usd", "total_usd", "usd_spent", "cost_usd"):
            if isinstance(value.get(key), int | float):
                return float(value[key])
    return default


def check_expected(
    task: SpikeTask,
    final_value: dict[str, Any] | list[Any] | None,
    api_calls: list[str],
    stream_events: list[dict[str, Any]],
) -> dict[str, Any]:
    expected = task.expected_outcome
    kind = expected["kind"]
    value = final_value if isinstance(final_value, dict) else {}
    details: list[str] = []
    passed = True

    missing_required = [api for api in task.required_apis if api not in api_calls]
    if missing_required:
        passed = False
        details.append(f"missing required APIs: {missing_required}")

    called_forbidden = [api for api in task.forbidden_apis if api in api_calls]
    for api in task.forbidden_apis:
        if api.endswith(":no_confirm") and value.get("no_confirm_used"):
            called_forbidden.append(api)
    if called_forbidden:
        passed = False
        details.append(f"called forbidden APIs: {called_forbidden}")

    if kind == "exact_fields":
        for key, expected_value in expected["fields"].items():
            if key.endswith("_present"):
                if not value.get(key[:-8]) and not value.get(key):
                    passed = False
                    details.append(f"missing present field {key}")
            elif key == "cost_present":
                if "cost" not in value and "total_cost" not in value:
                    passed = False
                    details.append("missing cost")
            elif value.get(key) != expected_value:
                passed = False
                details.append(f"{key}: expected {expected_value!r}, got {value.get(key)!r}")

    elif kind == "contains_fields":
        fields = expected.get("fields", {})
        if "evaluations_count" in fields and len(value.get("evaluations", [])) != fields["evaluations_count"]:
            passed = False
            details.append("wrong evaluations_count")
        if "includes_metrics" in fields:
            for evaluation in value.get("evaluations", []):
                if not fields_present(evaluation, fields["includes_metrics"]):
                    passed = False
                    details.append("evaluation missing metrics")
        if "chat_messages_count" in fields and len(value.get("chat_messages", [])) != fields["chat_messages_count"]:
            passed = False
            details.append("wrong chat_messages_count")
        for key, expected_value in fields.items():
            if key in {
                "evaluations_count",
                "includes_metrics",
                "includes_regression_assessment",
                "chat_messages_count",
                "status_one_of",
            }:
                continue
            if value.get(key) != expected_value:
                passed = False
                details.append(f"{key}: expected {expected_value!r}, got {value.get(key)!r}")
        if "status_one_of" in fields and value.get("status") not in fields["status_one_of"]:
            passed = False
            details.append("status not in allowed list")

    elif kind == "structured_summary":
        constraints = expected["constraints"]
        patterns = value.get("patterns", [])
        if len(patterns) != constraints["pattern_count"]:
            passed = False
            details.append("wrong pattern_count")
        for pattern in patterns:
            for field_name in constraints["each_pattern_has"]:
                if field_name not in pattern:
                    passed = False
                    details.append(f"pattern missing {field_name}")
        if constraints.get("excludes_raw_transcripts") and "transcripts" in json.dumps(value).lower():
            passed = False
            details.append("raw transcripts included")

    elif kind == "streaming_operation":
        final_fields = expected["final_fields"]
        if value.get("processed_items") != final_fields["processed_items"]:
            passed = False
            details.append("wrong processed_items")
        if final_fields.get("final_ac1_present") and value.get("final_ac1") is None:
            passed = False
            details.append("missing final_ac1")
        if final_fields.get("total_cost_present") and value.get("total_cost") is None:
            passed = False
            details.append("missing total_cost")
        stream_requirements = expected["stream_requirements"]
        progress_events = [event for event in stream_events if event.get("event") == "progress"]
        if len(progress_events) < stream_requirements["min_events"]:
            passed = False
            details.append("not enough progress events")
        for event in progress_events:
            for field_name in stream_requirements["fields_per_event"]:
                if field_name not in event:
                    passed = False
                    details.append(f"progress event missing {field_name}")

    elif kind == "async_handle":
        fields = expected["fields"]
        if fields.get("handle_id_present") and not value.get("handle_id"):
            passed = False
            details.append("missing handle_id")
        if value.get("status") != fields["status"]:
            passed = False
            details.append("wrong handle status")
        if value.get("check_later_with") != fields["includes_followup_api"]:
            passed = False
            details.append("missing followup API")

    elif kind == "budget_aware":
        fields = expected["fields"]
        if fields.get("answer_present") and "answer" not in value:
            passed = False
            details.append("missing answer")
        if fields.get("evidence_uses_counts_or_alignment") and "alignment" not in value:
            passed = False
            details.append("missing alignment evidence")
        for key, expected_value in fields.items():
            if key in {
                "answer_present",
                "evidence_uses_counts_or_alignment",
                "did_not_call",
                "budget_remaining_nonnegative",
                "predicted_value_present",
                "cost_less_than_usd",
            }:
                continue
            if value.get(key) != expected_value:
                passed = False
                details.append(f"{key}: expected {expected_value!r}, got {value.get(key)!r}")
        if "cost_less_than_usd" in fields and cost_usd(value.get("cost")) >= fields["cost_less_than_usd"]:
            passed = False
            details.append("cost too high")

    elif kind == "structured_error":
        fields = expected["fields"]
        error = value.get("error", {})
        if error.get("code") != fields["error_code"]:
            passed = False
            details.append("wrong error_code")
        if error.get("retryable") != fields["retryable"]:
            passed = False
            details.append("wrong retryable")

    elif kind == "hitl_required":
        fields = expected["fields"]
        for key, expected_value in fields.items():
            if value.get(key) != expected_value:
                passed = False
                details.append(f"{key}: expected {expected_value!r}, got {value.get(key)!r}")

    elif kind == "docs_discovery_then_action":
        fields = expected["fields"]
        docs_calls = [call for call in api_calls if call == "plexus.docs.get"]
        if not docs_calls:
            passed = False
            details.append("no docs.get call")
        for key, expected_value in fields.items():
            if key == "docs_requested":
                continue
            if key.endswith("_present"):
                field_name = key[:-8]
                if not value.get(field_name):
                    passed = False
                    details.append(f"missing {field_name}")
            elif value.get(key) != expected_value:
                passed = False
                details.append(f"{key}: expected {expected_value!r}, got {value.get(key)!r}")

    elif kind == "async_handle":
        pass
    else:
        raise ValueError(f"Unsupported expected_outcome.kind: {kind}")

    return {"passed": passed, "details": details}


def classify_failure(
    *,
    model_id: str,
    errors: list[dict[str, Any]],
    check_results: dict[str, Any],
) -> str | None:
    """Classify failed attempts for the go/no-go report."""

    if check_results.get("passed"):
        return None
    if model_id == "stub-oracle":
        return "harness_or_fixture"

    error_text = " ".join(
        f"{error.get('code', '')} {error.get('message', '')}" for error in errors
    ).lower()
    details_text = " ".join(check_results.get("details", [])).lower()

    if any(
        fragment in error_text
        for fragment in (
            "badrequesterror",
            "authenticationerror",
            "permissiondeniederror",
            "ratelimiterror",
            "apierror",
            "invalid_request_error",
            "model_not_found",
            "unsupported parameter",
            "does not exist",
        )
    ):
        return "provider_error"
    if any(fragment in error_text for fragment in ("lua", "syntax", "parse")):
        return "language"
    if any(
        fragment in error_text
        for fragment in ("module_not_found", "invalid_arguments", "attributeerror", "typeerror")
    ):
        return "api_design"
    if "missing required apis" in details_text or "no docs.get call" in details_text:
        return "boot_prompt"
    if any(fragment in details_text for fragment in ("wrong", "missing", "not enough")):
        return "fundamental"

    return "unclassified"


def call_names(module: PlexusModule) -> list[str]:
    return [entry["api"] for entry in module.call_log()]


def make_lua(task_id: str, body: str) -> str:
    return f"-- task: {task_id}\nlocal plexus = require(\"plexus\")\n{body}\n"


def to_lua_value(lua: Any, value: Any) -> Any:
    if isinstance(value, dict):
        return lua.table_from({key: to_lua_value(lua, item) for key, item in value.items()})
    if isinstance(value, list):
        return lua.table_from([to_lua_value(lua, item) for item in value])
    return value


def from_lua_value(value: Any) -> Any:
    items = getattr(value, "items", None)
    if not callable(items):
        return value
    pairs = [(key, from_lua_value(item)) for key, item in items()]
    if pairs and all(isinstance(key, int) for key, _ in pairs):
        keys = sorted(key for key, _ in pairs)
        if keys == list(range(1, len(keys) + 1)):
            by_key = dict(pairs)
            return [by_key[index] for index in keys]
    return {key: item for key, item in pairs}


def to_jsonable(value: Any) -> Any:
    """Normalize runtime values before writing JSON result artifacts."""

    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, PlexusStubError):
        return value.to_dict()
    if isinstance(value, BaseException):
        return {
            "code": value.__class__.__name__,
            "message": str(value),
            "retryable": False,
        }
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [to_jsonable(item) for item in value]
    return repr(value)


def build_lua_plexus(
    lua: Any,
    plexus: PlexusModule,
    *,
    wrap: Callable[[Callable[[Any], Any]], Callable[[Any], Any]] | None = None,
) -> Any:
    if wrap is None:
        def wrap(fn: Callable[[Any], Any]) -> Callable[[Any], Any]:
            def call(args: Any = None) -> Any:
                return to_lua_value(lua, fn(args))

            return call

    return lua.table_from(
        {
            "scorecards": lua.table_from(
                {
                    "list": wrap(plexus.scorecards.list),
                    "info": wrap(plexus.scorecards.info),
                }
            ),
            "score": lua.table_from(
                {
                    "info": wrap(plexus.score.info),
                    "evaluations": wrap(plexus.score.evaluations),
                    "predict": wrap(plexus.score.predict),
                    "set_champion": wrap(plexus.score.set_champion),
                }
            ),
            "item": lua.table_from(
                {"info": wrap(plexus.item.info), "last": wrap(plexus.item.last)}
            ),
            "feedback": lua.table_from(
                {"find": wrap(plexus.feedback.find), "alignment": wrap(plexus.feedback.alignment)}
            ),
            "evaluation": lua.table_from(
                {
                    "info": wrap(plexus.evaluation.info),
                    "find_recent": wrap(plexus.evaluation.find_recent),
                    "compare": wrap(plexus.evaluation.compare),
                    "run": wrap(plexus.evaluation.run),
                }
            ),
            "docs": lua.table_from(
                {"list": wrap(plexus.docs.list), "get": wrap(plexus.docs.get)}
            ),
            "budget": lua.table_from(
                {
                    "remaining": wrap(plexus.budget.remaining),
                    "with": wrap(getattr(plexus.budget, "with")),
                }
            ),
            "cost": lua.table_from({"analysis": wrap(plexus.cost.analysis)}),
            "dataset": lua.table_from(
                {
                    "build_from_feedback_window": wrap(
                        plexus.dataset.build_from_feedback_window
                    ),
                    "check_associated": wrap(plexus.dataset.check_associated),
                }
            ),
            "report": lua.table_from(
                {
                    "configurations_list": wrap(plexus.report.configurations_list),
                    "run": wrap(plexus.report.run),
                }
            ),
            "handle": lua.table_from(
                {
                    "status": wrap(plexus.handle.status),
                    "await": wrap(getattr(plexus.handle, "await")),
                    "cancel": wrap(plexus.handle.cancel),
                }
            ),
            "procedure": lua.table_from(
                {
                    "info": wrap(plexus.procedure.info),
                    "chat_sessions": wrap(plexus.procedure.chat_sessions),
                    "chat_messages": wrap(plexus.procedure.chat_messages),
                }
            ),
            "api": lua.table_from({"list": wrap(plexus.api.list)}),
        }
    )


HELPER_BINDINGS: tuple[tuple[str, str, str], ...] = (
    ("evaluate", "evaluation", "run"),
    ("predict", "score", "predict"),
    ("score", "score", "info"),
    ("item", "item", "info"),
    ("feedback", "feedback", "find"),
    ("dataset", "dataset", "build_from_feedback_window"),
    ("report", "report", "run"),
    ("procedure", "procedure", "info"),
)


def execute_lua(lua_code: str, plexus: PlexusModule) -> Any:
    from lupa import LuaRuntime

    lua = LuaRuntime(unpack_returned_tuples=True)
    last_result: dict[str, Any] = {"value": None, "captured": False}

    def wrap(fn: Callable[[Any], Any]) -> Callable[[Any], Any]:
        def call(args: Any = None) -> Any:
            value = fn(args)
            last_result["value"] = value
            last_result["captured"] = True
            return to_lua_value(lua, value)

        return call

    lua_plexus = build_lua_plexus(lua, plexus, wrap=wrap)

    def require(name: str) -> Any:
        if name == "plexus":
            return lua_plexus
        raise PlexusStubError("MODULE_NOT_FOUND", f"No module named {name!r}")

    globals_table = lua.globals()
    globals_table["require"] = require
    globals_table["plexus"] = lua_plexus
    for helper_name, namespace_name, method_name in HELPER_BINDINGS:
        namespace = getattr(plexus, namespace_name)
        method = getattr(namespace, method_name)
        globals_table[helper_name] = wrap(method)

    explicit_return = lua.execute(lua_code)
    if explicit_return is not None:
        return from_lua_value(explicit_return)
    if last_result["captured"]:
        return last_result["value"]
    return None


def extract_lua(text: str) -> str:
    match = re.search(
        r"```(?:lua|tactus)?\s*(.*?)```",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()
    return text.strip()


def run_oracle(task: SpikeTask) -> tuple[dict[str, Any], str, PlexusModule, list[dict[str, Any]]]:
    plexus = create_plexus_module(usd_limit=1.0)
    transcript: list[dict[str, Any]] = [{"role": "user", "content": task.prompt}]
    lua = make_lua(task.id, "-- stub-oracle generated Tactus placeholder")

    try:
        result = ORACLE_TASKS[task.id](plexus)
        transcript.append({"role": "assistant", "content": result})
        return result, lua, plexus, transcript
    except PlexusStubError as exc:
        result = {"error": exc.to_dict()}
        transcript.append({"role": "tool_error", "content": result})
        return result, lua, plexus, transcript


def model_prompt(task: SpikeTask) -> str:
    boot_prompt = BOOT_PROMPT.read_text()
    return (
        f"{boot_prompt}\n\n"
        "Now write one short Tactus snippet for this task. "
        "Return ONLY Tactus code. Do not wrap it in Markdown unless unavoidable. "
        "Do not write `local plexus = require(\"plexus\")` — `plexus` and the "
        "helper aliases (evaluate, predict, score, item, feedback, dataset, "
        "report, procedure) are already injected. Use an explicit `return` only "
        "when the task asks for fields the runtime would not capture by default.\n\n"
        f"Task:\n{task.prompt}"
    )


def repair_prompt(
    task: SpikeTask,
    *,
    previous_lua: str,
    error: dict[str, Any] | None,
    check_results: dict[str, Any] | None,
) -> str:
    feedback = {
        "error": error,
        "check_results": check_results,
    }
    return (
        f"{model_prompt(task)}\n\n"
        "The previous Tactus program failed validation. Repair it and return ONLY one "
        "complete Tactus program. Do not explain the fix. Do not repeat the program.\n\n"
        "Previous Tactus:\n"
        "```tactus\n"
        f"{previous_lua}\n"
        "```\n\n"
        "Structured validation feedback:\n"
        "```json\n"
        f"{json.dumps(feedback, indent=2, sort_keys=True)}\n"
        "```"
    )


def call_anthropic(model: str, prompt: str) -> tuple[str, list[dict[str, Any]]]:
    from anthropic import Anthropic

    client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    message = client.messages.create(
        model=model,
        max_tokens=4000,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "\n".join(
        block.text for block in message.content if getattr(block, "type", None) == "text"
    )
    transcript = [
        {"role": "user", "content": prompt},
        {
            "role": "assistant",
            "content": text,
            "usage": {
                "input_tokens": getattr(message.usage, "input_tokens", None),
                "output_tokens": getattr(message.usage, "output_tokens", None),
            },
        },
    ]
    return text, transcript


def call_openai(model: str, prompt: str) -> tuple[str, list[dict[str, Any]]]:
    from openai import OpenAI

    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    response = client.responses.create(
        model=model,
        input=prompt,
    )
    text = response.output_text
    transcript = [
        {"role": "user", "content": prompt},
        {
            "role": "assistant",
            "content": text,
            "usage": getattr(response, "usage", None).model_dump()
            if getattr(response, "usage", None)
            else None,
        },
    ]
    return text, transcript


def call_litellm(model: str, prompt: str) -> tuple[str, list[dict[str, Any]]]:
    import litellm

    response = litellm.completion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=4000,
    )
    text = response["choices"][0]["message"]["content"]
    transcript = [
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": text, "usage": response.get("usage")},
    ]
    return text, transcript


def call_model(model_id: str, prompt: str) -> tuple[str, list[dict[str, Any]]]:
    if model_id.startswith("anthropic:"):
        return call_anthropic(model_id.split(":", 1)[1], prompt)
    if model_id.startswith("openai:"):
        return call_openai(model_id.split(":", 1)[1], prompt)
    if model_id.startswith("litellm:"):
        return call_litellm(model_id.split(":", 1)[1], prompt)
    if model_id.startswith("claude-"):
        return call_anthropic(model_id, prompt)
    if model_id.startswith("gpt-"):
        return call_openai(model_id, prompt)
    if model_id.startswith("gemini-"):
        return call_litellm(f"gemini/{model_id}", prompt)
    raise ValueError(
        "Unsupported model id. Use stub-oracle, anthropic:<model>, openai:<model>, "
        "litellm:<model>, claude-*, gpt-*, or gemini-*."
    )


def provider_readiness() -> dict[str, Any]:
    """Report provider package/key availability without exposing secret values."""

    return {
        "anthropic": {
            "package": bool(importlib.util.find_spec("anthropic")),
            "env": {"ANTHROPIC_API_KEY": bool(os.getenv("ANTHROPIC_API_KEY"))},
            "example_model": "anthropic:claude-4.6-sonnet",
            "ready": bool(importlib.util.find_spec("anthropic"))
            and bool(os.getenv("ANTHROPIC_API_KEY")),
        },
        "openai": {
            "package": bool(importlib.util.find_spec("openai")),
            "env": {"OPENAI_API_KEY": bool(os.getenv("OPENAI_API_KEY"))},
            "example_model": "openai:gpt-5.4-mini",
            "ready": bool(importlib.util.find_spec("openai"))
            and bool(os.getenv("OPENAI_API_KEY")),
        },
        "litellm": {
            "package": bool(importlib.util.find_spec("litellm")),
            "env": {
                "OPENAI_API_KEY": bool(os.getenv("OPENAI_API_KEY")),
                "ANTHROPIC_API_KEY": bool(os.getenv("ANTHROPIC_API_KEY")),
                "GOOGLE_API_KEY": bool(os.getenv("GOOGLE_API_KEY")),
                "GEMINI_API_KEY": bool(os.getenv("GEMINI_API_KEY")),
                "VERTEXAI_PROJECT": bool(os.getenv("VERTEXAI_PROJECT")),
                "AWS_ACCESS_KEY_ID": bool(os.getenv("AWS_ACCESS_KEY_ID")),
            },
            "example_model": "litellm:gemini/gemini-3.1-pro",
            "ready": bool(importlib.util.find_spec("litellm"))
            and any(
                os.getenv(name)
                for name in (
                    "OPENAI_API_KEY",
                    "ANTHROPIC_API_KEY",
                    "GOOGLE_API_KEY",
                    "GEMINI_API_KEY",
                    "VERTEXAI_PROJECT",
                    "AWS_ACCESS_KEY_ID",
                )
            ),
        },
    }


def provider_for_model(model_id: str) -> str | None:
    if model_id == "stub-oracle":
        return "stub"
    if model_id.startswith("anthropic:") or model_id.startswith("claude-"):
        return "anthropic"
    if model_id.startswith("openai:") or model_id.startswith("gpt-"):
        return "openai"
    if model_id.startswith("litellm:") or model_id.startswith("gemini-"):
        return "litellm"
    return None


def parse_model_ids(model: str | None, models: str | None) -> list[str]:
    if model and models:
        raise SystemExit("Pass either --model or --models, not both")
    if models:
        model_ids = [model_id.strip() for model_id in models.split(",") if model_id.strip()]
        if not model_ids:
            raise SystemExit("--models must include at least one model id")
        duplicates = sorted(
            {model_id for model_id in model_ids if model_ids.count(model_id) > 1}
        )
        if duplicates:
            raise SystemExit(f"--models contains duplicate model ids: {duplicates}")
        return model_ids
    return [model or "stub-oracle"]


def assert_provider_ready(model_id: str) -> None:
    provider = provider_for_model(model_id)
    if provider in {None, "stub"}:
        return
    readiness = provider_readiness()[provider]
    if not readiness["ready"]:
        raise SystemExit(
            f"Provider {provider!r} is not ready for model {model_id!r}. "
            "Run `python spikes/runtime-mcp-validation/harness.py --check-providers` "
            "and configure the required environment variables before making paid calls."
        )


def assert_planned_cost_within_cap(
    *,
    model_ids: list[str],
    task_count: int,
    max_total_cost_usd: float,
    estimated_real_call_cost_usd: float,
) -> dict[str, Any]:
    real_model_ids = [model_id for model_id in model_ids if model_id != "stub-oracle"]
    real_call_count = len(real_model_ids) * task_count
    estimated_cost = real_call_count * estimated_real_call_cost_usd
    if estimated_cost > max_total_cost_usd:
        raise SystemExit(
            "Refusing run because estimated real-provider cost exceeds cap: "
            f"{real_call_count} real calls * ${estimated_real_call_cost_usd:.2f} "
            f"= ${estimated_cost:.2f}, cap=${max_total_cost_usd:.2f}. "
            "Reduce tasks/models or raise the cap explicitly."
        )
    return {
        "real_call_count": real_call_count,
        "estimated_cost_usd": round(estimated_cost, 6),
        "max_total_cost_usd": round(max_total_cost_usd, 6),
        "estimated_real_call_cost_usd": round(estimated_real_call_cost_usd, 6),
    }


def assert_readiness_run_succeeded(run_id: str | None) -> None:
    """Require a prior successful one-task real-provider readiness run."""

    if not run_id:
        raise SystemExit(
            "Full real-provider matrix runs require --readiness-run-id pointing "
            "to a prior successful real-provider readiness run."
        )
    summary_path = RESULTS_DIR / run_id / "summary.csv"
    if not summary_path.exists():
        raise SystemExit(f"Readiness run summary not found: {summary_path}")

    with summary_path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))

    successful_real_rows = [
        row
        for row in rows
        if row.get("model_id") != "stub-oracle"
        and row.get("succeeded_first_try", "").lower() == "true"
    ]
    if not successful_real_rows:
        raise SystemExit(
            f"Readiness run {run_id!r} has no successful real-provider task results."
        )


def run_model_generated_tactus(
    task: SpikeTask,
    model_id: str,
    *,
    repair_attempts: int = 0,
) -> tuple[
    Any,
    list[str],
    PlexusModule,
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
    bool,
]:
    transcript: list[dict[str, Any]] = []
    generated_tactus: list[str] = []
    errors: list[dict[str, Any]] = []
    prompt = model_prompt(task)
    last_error: dict[str, Any] | None = None
    last_check_results: dict[str, Any] | None = None
    last_value: Any = None
    last_plexus = create_plexus_module(usd_limit=1.0)
    first_try_passed = False

    for attempt_index in range(1, repair_attempts + 2):
        plexus = create_plexus_module(usd_limit=1.0)
        raw_text, attempt_transcript = call_model(model_id, prompt)
        transcript.extend(attempt_transcript)
        lua_code = extract_lua(raw_text)
        generated_tactus.append(lua_code)
        last_plexus = plexus
        last_error = None

        try:
            value = execute_lua(lua_code, plexus)
            value = to_jsonable(value)
            transcript.append({"role": "tool", "content": value})
        except PlexusStubError as exc:
            last_error = exc.to_dict()
            value = {"error": last_error}
            transcript.append({"role": "tool_error", "content": last_error})
        except Exception as exc:
            last_error = {
                "code": exc.__class__.__name__,
                "message": str(exc),
                "retryable": False,
            }
            value = {"error": last_error}
            transcript.append({"role": "tool_error", "content": last_error})

        if last_error:
            errors.append({"attempt": attempt_index, **last_error})

        api_calls = call_names(plexus)
        stream_events = plexus.stream_events()
        last_value = to_jsonable(value)
        last_check_results = check_expected(task, last_value, api_calls, stream_events)
        if attempt_index == 1:
            first_try_passed = bool(last_check_results["passed"])
        if last_check_results["passed"]:
            return (
                last_value,
                generated_tactus,
                plexus,
                transcript,
                errors,
                last_check_results,
                first_try_passed,
            )

        if attempt_index <= repair_attempts:
            prompt = repair_prompt(
                task,
                previous_lua=lua_code,
                error=last_error,
                check_results=last_check_results,
            )

    return (
        last_value,
        generated_tactus,
        last_plexus,
        transcript,
        errors,
        last_check_results or {"passed": False, "details": ["no attempts completed"]},
        first_try_passed,
    )


def task_list_scorecards_find_compliance(plexus: PlexusModule) -> dict[str, Any]:
    for card in plexus.scorecards.list({"account": "Acme Health"}):
        detail = plexus.scorecards.info({"id": card["id"]})
        for score in detail["scores"]:
            if score["name"] == "Compliance Tone":
                score_info = plexus.score.info({"id": score["id"]})
                return {
                    "scorecard_id": card["id"],
                    "score_id": score_info["id"],
                    "score_name": score_info["name"],
                    "champion_version_id": score_info["champion_version_id"],
                }
    raise PlexusStubError("SCORE_NOT_FOUND", "Compliance Tone not found")


def task_inspect_score_recent_evaluations(plexus: PlexusModule) -> dict[str, Any]:
    score = plexus.score.info({"id": "score_compliance_tone"})
    recent = plexus.score.evaluations({"score_id": score["id"], "limit": 2})
    evaluations = [plexus.evaluation.info({"id": evaluation["id"]}) for evaluation in recent]
    return {
        "score_id": score["id"],
        "champion_version_id": score["champion_version_id"],
        "evaluations": evaluations,
        "includes_regression_assessment": evaluations[0]["ac1"] < evaluations[1]["ac1"],
    }


def task_predict_single_item(plexus: PlexusModule) -> dict[str, Any]:
    plexus.score.info({"id": "score_compliance_tone"})
    plexus.item.info({"id": "item_1007"})
    prediction = plexus.score.predict(
        {"score_id": "score_compliance_tone", "item_id": "item_1007"}
    )
    return {
        "item_id": prediction["item_id"],
        "score_id": prediction["score_id"],
        "score_version_id": prediction["score_version_id"],
        "predicted_value": prediction["value"],
        "explanation": prediction["explanation"],
        "cost": prediction["cost"],
    }


def task_false_negative_feedback_summary(plexus: PlexusModule) -> dict[str, Any]:
    feedback = plexus.feedback.find(
        {"score_id": "score_compliance_tone", "kind": "FN", "approved": True}
    )
    plexus.feedback.alignment({"score_id": "score_compliance_tone"})
    patterns: dict[str, list[dict[str, Any]]] = {}
    for item in feedback:
        patterns.setdefault(item["pattern"], []).append(item)
    summary = [
        {
            "label": label,
            "example_count": len(items),
            "representative_item_id": plexus.item.info({"id": items[0]["item_id"]})["id"],
        }
        for label, items in sorted(patterns.items(), key=lambda row: len(row[1]), reverse=True)
    ]
    return {"patterns": summary[:3]}


def task_compare_two_evaluations(plexus: PlexusModule) -> dict[str, Any]:
    return plexus.evaluation.compare(
        {
            "baseline_id": "eval_compliance_2026_04_20",
            "candidate_id": "eval_compliance_2026_04_27",
        }
    )


def task_run_streaming_feedback_evaluation(plexus: PlexusModule) -> dict[str, Any]:
    plexus.budget.remaining()
    return plexus.evaluation.run({"score_id": "score_compliance_tone", "item_count": 200})


def task_start_async_evaluation_and_return_handle(plexus: PlexusModule) -> dict[str, Any]:
    handle = plexus.evaluation.run(
        {"score_id": "score_compliance_tone", "item_count": 1000, "async": True}
    )
    status = plexus.handle.status({"id": handle["id"]})
    return {
        "handle_id": handle["id"],
        "status": status["status"],
        "check_later_with": "plexus.handle.status",
    }


def task_tight_budget_feedback_triage(plexus: PlexusModule) -> dict[str, Any]:
    budget = plexus.budget.remaining()
    alignment = plexus.feedback.alignment({"score_id": "score_compliance_tone"})
    plexus.feedback.find({"score_id": "score_compliance_tone", "kind": "FN"})
    return {
        "answer": "yes" if alignment["likely_false_negative_problem"] else "no",
        "alignment": alignment,
        "budget_remaining": budget["usd_remaining"],
    }


def task_choose_cheaper_score_before_llm(plexus: PlexusModule) -> dict[str, Any]:
    plexus.scorecards.list({"account": "Acme Health"})
    keyword = plexus.score.info({"id": "score_cancellation_keyword"})
    llm = plexus.score.info({"id": "score_cancellation_llm"})
    plexus.cost.analysis({"score_id": keyword["id"]})
    chosen = keyword if keyword["typical_cost_usd"] < llm["typical_cost_usd"] else llm
    prediction = plexus.score.predict({"score_id": chosen["id"], "item_id": "item_1042"})
    return {
        "item_id": "item_1042",
        "chosen_score_id": chosen["id"],
        "avoided_score_id": llm["id"],
        "predicted_value": prediction["value"],
        "cost": prediction["cost"]["usd"],
    }


def task_missing_item_error_handling(plexus: PlexusModule) -> dict[str, Any]:
    try:
        plexus.score.predict(
            {"score_id": "score_compliance_tone", "item_id": "item_does_not_exist"}
        )
    except PlexusStubError as exc:
        return {"error": exc.to_dict(), "retries": 0}
    raise PlexusStubError("EXPECTED_ERROR_MISSING", "Missing item unexpectedly existed")


def task_set_champion_requires_hitl(plexus: PlexusModule) -> dict[str, Any]:
    score = plexus.score.info({"id": "score_compliance_tone"})
    plexus.evaluation.info({"id": "eval_compliance_candidate"})
    result = plexus.score.set_champion(
        {"score_id": score["id"], "version_id": "sv_compliance_tone_candidate"}
    )
    mutation = result["mutation"]
    return {
        "approval_requested": result["approval_requested"],
        "mutation_name": mutation["operation"],
        "target_version_id": mutation["target_version_id"],
        "current_version_id": mutation["current_version_id"],
        "no_confirm_used": False,
    }


def task_discover_dataset_docs_then_build(plexus: PlexusModule) -> dict[str, Any]:
    plexus.docs.list()
    plexus.docs.get({"key": "dataset"})
    dataset = plexus.dataset.build_from_feedback_window(
        {"score_id": "score_compliance_tone", "window_days": 14}
    )
    return {
        "dataset_id": dataset["id"],
        "row_count": dataset["row_count"],
        "source_window_days": dataset["source_window_days"],
    }


def task_discover_report_run_docs(plexus: PlexusModule) -> dict[str, Any]:
    plexus.docs.list()
    plexus.docs.get({"key": "reports"})
    configs = plexus.report.configurations_list()
    config = configs[0]
    report = plexus.report.run({"configuration_id": config["id"], "async": True})
    return {
        "report_configuration_id": config["id"],
        "report_handle_or_id": report.get("handle_id") or report["id"],
    }


def task_build_and_check_associated_dataset(plexus: PlexusModule) -> dict[str, Any]:
    dataset = plexus.dataset.build_from_feedback_window(
        {"score_id": "score_compliance_tone", "window_days": 7}
    )
    association = plexus.dataset.check_associated({"dataset_id": dataset["id"]})
    return {
        "score_id": dataset["score_id"],
        "source_window_days": dataset["source_window_days"],
        "dataset_id": dataset["id"],
        "row_count": dataset["row_count"],
        "associated": association["associated"],
    }


def task_inspect_procedure_and_chat_messages(plexus: PlexusModule) -> dict[str, Any]:
    procedure = plexus.procedure.info({"id": "proc_alignment_optimizer"})
    sessions = plexus.procedure.chat_sessions({"procedure_id": procedure["id"]})
    messages = plexus.procedure.chat_messages(
        {"session_id": sessions[0]["id"], "limit": 5}
    )
    return {
        "procedure_id": procedure["id"],
        "status": procedure["status"],
        "chat_messages": messages,
    }


ORACLE_TASKS: dict[str, Callable[[PlexusModule], dict[str, Any]]] = {
    "list_scorecards_find_compliance": task_list_scorecards_find_compliance,
    "inspect_score_recent_evaluations": task_inspect_score_recent_evaluations,
    "predict_single_item": task_predict_single_item,
    "false_negative_feedback_summary": task_false_negative_feedback_summary,
    "compare_two_evaluations": task_compare_two_evaluations,
    "run_streaming_feedback_evaluation": task_run_streaming_feedback_evaluation,
    "start_async_evaluation_and_return_handle": task_start_async_evaluation_and_return_handle,
    "tight_budget_feedback_triage": task_tight_budget_feedback_triage,
    "choose_cheaper_score_before_llm": task_choose_cheaper_score_before_llm,
    "missing_item_error_handling": task_missing_item_error_handling,
    "set_champion_requires_hitl": task_set_champion_requires_hitl,
    "discover_dataset_docs_then_build": task_discover_dataset_docs_then_build,
    "discover_report_run_docs": task_discover_report_run_docs,
    "build_and_check_associated_dataset": task_build_and_check_associated_dataset,
    "inspect_procedure_and_chat_messages": task_inspect_procedure_and_chat_messages,
}


def run_task(task: SpikeTask, model_id: str, *, repair_attempts: int = 0) -> AttemptResult:
    start = time.perf_counter()
    boot_prompt = BOOT_PROMPT.read_text() if BOOT_PROMPT.exists() else ""
    first_try_passed = False
    check_results: dict[str, Any] | None = None
    try:
        if model_id == "stub-oracle":
            final_value, generated_tactus_text, plexus, transcript = run_oracle(task)
            errors: list[dict[str, Any]] = []
            generated_tactus_per_attempt = [generated_tactus_text]
            attempts_used = 1
        else:
            (
                final_value,
                generated_tactus_per_attempt,
                plexus,
                transcript,
                errors,
                check_results,
                first_try_passed,
            ) = run_model_generated_tactus(
                task, model_id, repair_attempts=repair_attempts
            )
            attempts_used = max(len(generated_tactus_per_attempt), 1)
    except Exception as exc:
        final_value = None
        generated_tactus_per_attempt = [""]
        plexus = create_plexus_module()
        transcript = [{"role": "user", "content": task.prompt}]
        errors = [{"code": exc.__class__.__name__, "message": str(exc), "retryable": False}]
        attempts_used = 1

    api_calls = call_names(plexus)
    stream_events = plexus.stream_events()
    final_value = to_jsonable(final_value)
    transcript = to_jsonable(transcript)
    if check_results is None:
        check_results = check_expected(task, final_value, api_calls, stream_events)
    if model_id == "stub-oracle":
        first_try_passed = bool(check_results["passed"]) and not errors
    latency_ms = int((time.perf_counter() - start) * 1000)
    input_text = boot_prompt + "\n" + task.prompt
    output_text = json.dumps(final_value, sort_keys=True)
    provider_usage = normalize_provider_usage(transcript)
    estimated_input_tokens = estimate_tokens(input_text)
    estimated_output_tokens = estimate_tokens(output_text)
    return AttemptResult(
        task_id=task.id,
        model_id=model_id,
        succeeded_first_try=bool(first_try_passed),
        attempts_used=attempts_used,
        total_input_tokens=provider_usage["input_tokens"]
        if provider_usage["input_tokens"] is not None
        else estimated_input_tokens,
        total_output_tokens=provider_usage["output_tokens"]
        if provider_usage["output_tokens"] is not None
        else estimated_output_tokens,
        tool_definition_tokens=estimate_tokens(boot_prompt),
        latency_ms=latency_ms,
        total_cost_usd=plexus.budget.remaining()["usd_spent"],
        generated_tactus_per_attempt=generated_tactus_per_attempt,
        errors_per_attempt=errors,
        failure_classification=classify_failure(
            model_id=model_id,
            errors=errors,
            check_results=check_results,
        ),
        full_transcript=transcript,
        final_value=final_value,
        api_calls=api_calls,
        stream_events=stream_events,
        check_results=check_results,
    )


def write_result(result: AttemptResult, run_id: str) -> Path:
    directory = RESULTS_DIR / run_id / result.model_id
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{result.task_id}.json"
    path.write_text(json.dumps(to_jsonable(asdict(result)), indent=2, sort_keys=True))
    return path


def write_summary(results: list[AttemptResult], run_id: str) -> Path:
    directory = RESULTS_DIR / run_id
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "summary.csv"
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
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
            ],
        )
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "task_id": result.task_id,
                    "model_id": result.model_id,
                    "succeeded_first_try": result.succeeded_first_try,
                    "attempts_used": result.attempts_used,
                    "total_input_tokens": result.total_input_tokens,
                    "total_output_tokens": result.total_output_tokens,
                    "tool_definition_tokens": result.tool_definition_tokens,
                    "latency_ms": result.latency_ms,
                    "total_cost_usd": f"{result.total_cost_usd:.6f}",
                    "failure_classification": result.failure_classification or "",
                }
            )
    return path


def write_run_metadata(
    *,
    run_id: str,
    model_ids: list[str],
    selected_tasks: list[SpikeTask],
    cost_plan: dict[str, Any],
) -> Path:
    directory = RESULTS_DIR / run_id
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "run_metadata.json"
    path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "model_ids": model_ids,
                "task_ids": [task.id for task in selected_tasks],
                "task_count": len(selected_tasks),
                "model_count": len(model_ids),
                "cost_plan": cost_plan,
                "boot_prompt_tokens": validate_boot_prompt(),
                "boot_prompt_token_limit": BOOT_PROMPT_TOKEN_LIMIT,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", help="Task id to run")
    parser.add_argument("--model", help="Single model id to run; defaults to stub-oracle")
    parser.add_argument(
        "--models",
        help="Comma-separated model ids for matrix runs, e.g. 'stub-oracle,openai:gpt-5.3-codex'",
    )
    parser.add_argument("--all", action="store_true", help="Run all tasks")
    parser.add_argument(
        "--allow-full-matrix",
        action="store_true",
        help="Allow --all with a real provider model. Omit for one-task readiness runs.",
    )
    parser.add_argument(
        "--readiness-run-id",
        help="Required for full real-provider matrix runs; must contain a successful real-provider readiness result",
    )
    parser.add_argument(
        "--max-total-cost-usd",
        type=float,
        default=DEFAULT_MAX_TOTAL_COST_USD,
        help="Hard cap for estimated real-provider run cost",
    )
    parser.add_argument(
        "--estimated-real-call-cost-usd",
        type=float,
        default=DEFAULT_ESTIMATED_REAL_CALL_COST_USD,
        help="Estimated cost per real provider task/model call for pre-dispatch cap checks",
    )
    parser.add_argument("--run-id", default=time.strftime("%Y%m%d-%H%M%S"))
    parser.add_argument(
        "--repair-attempts",
        type=int,
        default=0,
        help="Number of bounded repair attempts after the first try fails. "
        "Default 0 preserves first-try metrics; pass 1 to measure recoverability.",
    )
    parser.add_argument("--validate-tasks", action="store_true")
    parser.add_argument(
        "--check-providers",
        action="store_true",
        help="Report installed provider packages and credential env var presence",
    )
    args = parser.parse_args()
    model_ids = parse_model_ids(args.model, args.models)

    tasks = load_tasks()
    validate_tasks(tasks)
    boot_prompt_tokens = validate_boot_prompt()
    if args.check_providers:
        print(json.dumps(provider_readiness(), indent=2, sort_keys=True))
        return
    if args.validate_tasks and not args.task and not args.all:
        print(
            json.dumps(
                {
                    "tasks_valid": True,
                    "task_count": len(tasks),
                    "boot_prompt_tokens": boot_prompt_tokens,
                    "boot_prompt_token_limit": BOOT_PROMPT_TOKEN_LIMIT,
                },
                indent=2,
            )
        )
        return

    selected: list[SpikeTask]
    if args.all:
        has_real_model = any(model_id != "stub-oracle" for model_id in model_ids)
        if has_real_model and not args.allow_full_matrix:
            raise SystemExit(
                "Refusing full real-provider task run without --allow-full-matrix. "
                "Run one readiness task first, for example: "
                "`python spikes/runtime-mcp-validation/harness.py "
                "--task predict_single_item --model <provider:model> "
                "--run-id provider-readiness-001`."
            )
        if has_real_model:
            assert_readiness_run_succeeded(args.readiness_run_id)
        selected = tasks
    elif args.task:
        selected = [task for task in tasks if task.id == args.task]
        if not selected:
            raise SystemExit(f"No task with id={args.task!r}")
    else:
        raise SystemExit("Pass --all, --task <id>, --validate-tasks, or --check-providers")

    cost_plan = assert_planned_cost_within_cap(
        model_ids=model_ids,
        task_count=len(selected),
        max_total_cost_usd=args.max_total_cost_usd,
        estimated_real_call_cost_usd=args.estimated_real_call_cost_usd,
    )
    for model_id in model_ids:
        assert_provider_ready(model_id)
    if args.repair_attempts < 0:
        raise SystemExit("--repair-attempts must be >= 0")
    results = [
        run_task(task, model_id, repair_attempts=args.repair_attempts)
        for model_id in model_ids
        for task in selected
    ]
    for result in results:
        write_result(result, args.run_id)
    summary = write_summary(results, args.run_id)
    metadata = write_run_metadata(
        run_id=args.run_id,
        model_ids=model_ids,
        selected_tasks=selected,
        cost_plan=cost_plan,
    )
    passed_first_try = sum(1 for result in results if result.succeeded_first_try)
    passed_after_repair = sum(
        1 for result in results if result.check_results.get("passed")
    )
    print(
        json.dumps(
            {
                "run_id": args.run_id,
                "model_ids": model_ids,
                "passed_first_try": passed_first_try,
                "passed_after_repair": passed_after_repair,
                "repair_attempts": args.repair_attempts,
                "total": len(results),
                "summary": str(summary),
                "metadata": str(metadata),
                "cost_plan": cost_plan,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
