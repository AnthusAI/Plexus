from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


DEMO_PREFIX = "k8s-demo"
HUGGING_FACE_DATASET = "PolyAI/banking77"
HUGGING_FACE_REVISION = "90d4e2ee5521c04fc1488f065b8b083658768c57"
SOURCE_REVISION = "9d081458ff52e53cf7e848f414e6e9344e4e6696"
SOURCE_SHA256 = "b06e26ac675513959a63135f11b94ea7786ed02da65db93a5650d8838cbc664b"
SOURCE_URL = (
    "https://raw.githubusercontent.com/PolyAI-LDN/task-specific-datasets/"
    f"{SOURCE_REVISION}/banking_data/train.csv"
)

POSITIVE_LABEL = "declined_cash_withdrawal"
NEGATIVE_LABELS = ("cash_withdrawal_charge", "cash_withdrawal_not_recognised")
REQUIRED_LABEL_COUNTS = {
    POSITIVE_LABEL: 100,
    NEGATIVE_LABELS[0]: 50,
    NEGATIVE_LABELS[1]: 50,
}
PHASES = (
    "infrastructure",
    "seed",
    "prediction",
    "evaluation",
    "reporting",
    "optimization",
    "recovery",
)
RUN_ID_PATTERN = re.compile(r"^\d{8}T\d{6}Z-[a-z0-9]{4,12}$")


@dataclass(frozen=True)
class BenchmarkRow:
    row_index: int
    source_label: str
    expected: str
    text: str = field(repr=False)

    @property
    def resource_key(self) -> str:
        return f"{self.source_label}:{self.row_index}"


@dataclass(frozen=True)
class BenchmarkSplit:
    feedback: tuple[BenchmarkRow, ...]
    regression: tuple[BenchmarkRow, ...]

    @property
    def checksum(self) -> str:
        payload = [
            (partition, row.resource_key, row.expected)
            for partition, rows in (("feedback", self.feedback), ("regression", self.regression))
            for row in rows
        ]
        return hashlib.sha256(
            json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        ).hexdigest()


@dataclass(frozen=True)
class AcceptanceMetrics:
    baseline_accuracy: float
    baseline_feedback_ac1: float
    baseline_regression_ac1: float
    candidate_feedback_ac1: float
    candidate_regression_ac1: float
    final_feedback_ac1: float | None
    evaluation_items: int
    regression_items: int
    execution_errors: int
    candidate_promoted: bool
    candidates_safely_rejected: bool = False


@dataclass(frozen=True)
class AcceptanceOutcome:
    passed: bool
    assertions: tuple[dict[str, Any], ...]


@dataclass
class DemoManifest:
    run_id: str
    profile: str
    max_cost_usd: float
    max_iterations: int
    created_at: str
    updated_at: str
    phases: dict[str, dict[str, Any]] = field(default_factory=dict)
    resources: dict[str, list[str]] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def new(
        cls,
        run_id: str,
        profile: str,
        max_cost_usd: float,
        max_iterations: int,
    ) -> "DemoManifest":
        validate_run_id(run_id)
        if profile not in {"strict", "guardrail"}:
            raise ValueError("profile must be strict or guardrail")
        if max_cost_usd <= 0:
            raise ValueError("max_cost_usd must be positive")
        if not 1 <= max_iterations <= 2:
            raise ValueError("max_iterations must be between 1 and 2")
        now = utc_now()
        return cls(
            run_id=run_id,
            profile=profile,
            max_cost_usd=max_cost_usd,
            max_iterations=max_iterations,
            created_at=now,
            updated_at=now,
            metadata={
                "dataset": HUGGING_FACE_DATASET,
                "hugging_face_revision": HUGGING_FACE_REVISION,
                "source_revision": SOURCE_REVISION,
                "source_sha256": SOURCE_SHA256,
            },
        )

    @classmethod
    def load(cls, path: Path) -> "DemoManifest":
        payload = json.loads(path.read_text(encoding="utf-8"))
        manifest = cls(**payload)
        validate_run_id(manifest.run_id)
        return manifest

    def save(self, path: Path) -> None:
        self.updated_at = utc_now()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def record_phase(
        self,
        name: str,
        *,
        passed: bool,
        summary: Mapping[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        if name not in PHASES and name != "verification":
            raise ValueError(f"unknown demo phase: {name}")
        self.phases[name] = {
            "passed": bool(passed),
            "layer": name,
            "completed_at": utc_now(),
            "summary": dict(summary or {}),
            "error": redact_text(error or "") or None,
        }
        self.updated_at = utc_now()

    def add_resource(self, model: str, resource_id: str) -> None:
        assert_cleanup_scope(self.run_id, [resource_id])
        resources = self.resources.setdefault(model, [])
        if resource_id not in resources:
            resources.append(resource_id)

    def completed(self, phase: str) -> bool:
        return bool(self.phases.get(phase, {}).get("passed"))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def generated_run_id(now: datetime | None = None, entropy: str | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    suffix = entropy or hashlib.sha256(str(now.timestamp()).encode()).hexdigest()[:6]
    return validate_run_id(now.strftime("%Y%m%dT%H%M%SZ") + f"-{suffix.lower()}")


def validate_run_id(run_id: str) -> str:
    if not RUN_ID_PATTERN.fullmatch(run_id or ""):
        raise ValueError(
            "run_id must match YYYYMMDDTHHMMSSZ- followed by 4-12 lowercase letters or digits"
        )
    return run_id


def stable_resource_id(run_id: str, kind: str) -> str:
    validate_run_id(run_id)
    normalized = re.sub(r"[^a-z0-9-]+", "-", kind.lower()).strip("-")
    if not normalized:
        raise ValueError("resource kind cannot be empty")
    raw = f"{DEMO_PREFIX}-{run_id.lower()}-{normalized}"
    if len(raw) <= 63:
        return raw
    digest = hashlib.sha256(raw.encode()).hexdigest()[:10]
    return f"{raw[:52].rstrip('-')}-{digest}"


def benchmark_rows(rows: Iterable[Mapping[str, Any]]) -> BenchmarkSplit:
    grouped: dict[str, list[BenchmarkRow]] = {label: [] for label in REQUIRED_LABEL_COUNTS}
    for row in rows:
        label = str(row.get("label") or "")
        if label not in grouped:
            continue
        text = row.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"source row for {label} is missing text")
        try:
            row_index = int(row["row_index"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"source row for {label} is missing row_index") from exc
        grouped[label].append(
            BenchmarkRow(
                row_index=row_index,
                source_label=label,
                expected="Yes" if label == POSITIVE_LABEL else "No",
                text=text,
            )
        )

    selected: dict[str, list[BenchmarkRow]] = {}
    for label, required_count in REQUIRED_LABEL_COUNTS.items():
        candidates = sorted(grouped[label], key=lambda row: (row.row_index, row.text))
        if len(candidates) < required_count:
            raise ValueError(
                f"dataset contains {len(candidates)} {label} rows; {required_count} required"
            )
        selected[label] = candidates[:required_count]

    feedback: list[BenchmarkRow] = []
    regression: list[BenchmarkRow] = []
    for label in (POSITIVE_LABEL, *NEGATIVE_LABELS):
        for index, row in enumerate(selected[label]):
            (feedback if index % 2 == 0 else regression).append(row)

    feedback.sort(key=lambda row: (row.source_label, row.row_index))
    regression.sort(key=lambda row: (row.source_label, row.row_index))
    if len(feedback) != 100 or len(regression) != 100:
        raise AssertionError("benchmark split must be exactly 100 feedback and 100 regression rows")
    return BenchmarkSplit(tuple(feedback), tuple(regression))


def acceptance_outcome(metrics: AcceptanceMetrics, profile: str) -> AcceptanceOutcome:
    if profile not in {"strict", "guardrail"}:
        raise ValueError("profile must be strict or guardrail")
    feedback_delta = metrics.candidate_feedback_ac1 - metrics.baseline_feedback_ac1
    regression_delta = metrics.candidate_regression_ac1 - metrics.baseline_regression_ac1
    assertions = [
        _assertion("feedback_items", metrics.evaluation_items == 100, metrics.evaluation_items, 100),
        _assertion("regression_items", metrics.regression_items == 100, metrics.regression_items, 100),
        _assertion("execution_errors", metrics.execution_errors == 0, metrics.execution_errors, 0),
        _assertion(
            "baseline_accuracy_range",
            0.55 <= metrics.baseline_accuracy <= 0.85,
            metrics.baseline_accuracy,
            "0.55..0.85",
        ),
        _assertion(
            "regression_veto",
            regression_delta >= -0.02
            or (
                profile == "guardrail"
                and metrics.candidates_safely_rejected
                and not metrics.candidate_promoted
            ),
            regression_delta,
            ">=-0.02 for any promoted candidate",
        ),
    ]
    improved = feedback_delta >= 0.05 and regression_delta >= -0.02
    if profile == "strict":
        assertions.extend(
            (
                _assertion("feedback_improvement", feedback_delta >= 0.05, feedback_delta, ">=0.05"),
                _assertion("candidate_promoted", metrics.candidate_promoted, metrics.candidate_promoted, True),
                _assertion(
                    "final_reproduces_improvement",
                    metrics.final_feedback_ac1 is not None
                    and metrics.final_feedback_ac1 - metrics.baseline_feedback_ac1 >= 0.05,
                    metrics.final_feedback_ac1,
                    ">=baseline+0.05",
                ),
            )
        )
    else:
        assertions.append(
            _assertion(
                "improved_or_safely_rejected",
                improved or metrics.candidates_safely_rejected,
                {
                    "feedback_delta": feedback_delta,
                    "regression_delta": regression_delta,
                    "safely_rejected": metrics.candidates_safely_rejected,
                },
                "improvement or safe rejection",
            )
        )
    return AcceptanceOutcome(all(item["passed"] for item in assertions), tuple(assertions))


def _assertion(name: str, passed: bool, actual: Any, expected: Any) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "actual": actual, "expected": expected}


def redact_text(text: str, secrets: Sequence[str] = ()) -> str:
    redacted = str(text or "")
    for secret in sorted((value for value in secrets if value), key=len, reverse=True):
        redacted = redacted.replace(secret, "[REDACTED_SECRET]")
    redacted = re.sub(
        r"(?i)(openai_api_key|api[-_ ]?key|authorization)(\s*[:=]\s*)([^\s,;]+)",
        r"\1\2[REDACTED_SECRET]",
        redacted,
    )
    redacted = re.sub(
        r"(?i)\b(text|transcript|quote|evidence)(\s*[:=]\s*)([^\n]+)",
        r"\1\2[REDACTED_SAMPLE_TEXT]",
        redacted,
    )
    return redacted


def assert_cleanup_scope(run_id: str, resource_ids: Sequence[str]) -> None:
    validate_run_id(run_id)
    prefix = f"{DEMO_PREFIX}-{run_id.lower()}-"
    invalid = [resource_id for resource_id in resource_ids if not resource_id.startswith(prefix)]
    if invalid:
        raise ValueError(f"resource outside run scope: {invalid[0]}")


def render_artifacts(manifest: DemoManifest, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_payload = asdict(manifest)
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    results_payload = {
        "run_id": manifest.run_id,
        "profile": manifest.profile,
        "passed": all(manifest.completed(phase) for phase in PHASES),
        "phases": manifest.phases,
        "metadata": manifest.metadata,
        "updated_at": manifest.updated_at,
    }
    (output_dir / "results.json").write_text(
        json.dumps(results_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    report_lines = [
        f"# Plexus Kubernetes Demo — {manifest.run_id}",
        "",
        f"Profile: `{manifest.profile}`",
        "",
        "| Phase | Result | Summary |",
        "| --- | --- | --- |",
    ]
    for phase in (*PHASES, "verification"):
        result = manifest.phases.get(phase)
        if not result:
            continue
        status = "PASS" if result["passed"] else "FAIL"
        summary = json.dumps(result.get("summary") or {}, sort_keys=True, separators=(",", ":"))
        report_lines.append(f"| {phase} | {status} | `{redact_text(summary)}` |")
    report_lines.extend(
        (
            "",
            "Generated evidence intentionally excludes secrets, transcript text, evidence quotes, and raw rows.",
            "",
        )
    )
    (output_dir / "report.md").write_text("\n".join(report_lines), encoding="utf-8")
    _write_junit(manifest, output_dir / "junit.xml")


def _write_junit(manifest: DemoManifest, path: Path) -> None:
    failures = sum(1 for result in manifest.phases.values() if not result.get("passed"))
    suite = ET.Element(
        "testsuite",
        name="plexus-kubernetes-demo",
        tests=str(len(manifest.phases)),
        failures=str(failures),
        errors="0",
    )
    for phase, result in manifest.phases.items():
        case = ET.SubElement(suite, "testcase", classname="plexus.k8s.demo", name=phase)
        if not result.get("passed"):
            failure = ET.SubElement(case, "failure", message=f"{phase} failed")
            failure.text = redact_text(result.get("error") or json.dumps(result.get("summary") or {}))
    ET.ElementTree(suite).write(path, encoding="unicode", xml_declaration=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n")
