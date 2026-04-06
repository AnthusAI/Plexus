from __future__ import annotations

from typing import Any, Callable, Dict, Optional

import boto3

from plexus.cli.shared.candidate_assessment_bundle import (
    STAGE_DETERMINISTIC,
    STAGE_RANDOM_GATE,
    STAGE_RANDOM_LOOP,
    build_candidate_assessment_attachment_key,
    build_candidate_assessment_attachment_payload,
    build_candidate_assessment_compact_summary,
    create_candidate_assessment_bundle,
)
from plexus.cli.shared.optimization_acceptance_policy import (
    AcceptancePolicyConfig,
    assess_candidate,
)
from plexus.cli.shared.generalization_metrics import compute_generalization_metrics
from plexus.cli.shared.workflow_decision_synthesis import synthesize_workflow_decision

DEFAULT_WORKFLOW_DAYS = 180
DEFAULT_LOOP_SAMPLE_SIZE = 50
DEFAULT_GATE_SAMPLE_SIZE = 200


def upload_task_attachment_json(
    *,
    bucket_name: str,
    key: str,
    payload_json: str,
) -> str:
    """
    Upload JSON payload to task attachments bucket and return uploaded key.
    """
    if not bucket_name:
        raise ValueError("bucket_name is required for task attachment upload.")
    if not key:
        raise ValueError("key is required for task attachment upload.")
    if not payload_json:
        raise ValueError("payload_json is required for task attachment upload.")

    s3_client = boto3.client("s3")
    s3_client.put_object(
        Bucket=bucket_name,
        Key=key,
        Body=payload_json.encode("utf-8"),
        ContentType="application/json",
    )
    return key


def _require_stage_pair(stage_pair: Any, stage_key: str) -> Dict[str, Any]:
    if not isinstance(stage_pair, dict):
        raise ValueError(f"{stage_key} result must be a dictionary.")
    if "baseline" not in stage_pair or "candidate" not in stage_pair:
        raise ValueError(f"{stage_key} result must include 'baseline' and 'candidate'.")
    baseline = stage_pair.get("baseline")
    candidate = stage_pair.get("candidate")
    if not isinstance(baseline, dict) or not isinstance(candidate, dict):
        raise ValueError(f"{stage_key} baseline/candidate must be dictionaries.")
    return {
        "baseline": baseline,
        "candidate": candidate,
    }


def run_candidate_assessment_workflow(
    *,
    identity: Dict[str, Any],
    run_stage_pair: Callable[..., Dict[str, Any]],
    task_id: Optional[str] = None,
    days: int = DEFAULT_WORKFLOW_DAYS,
    loop_sample_size: int = DEFAULT_LOOP_SAMPLE_SIZE,
    gate_sample_size: int = DEFAULT_GATE_SAMPLE_SIZE,
    deterministic_sample_size: Optional[int] = None,
    malfunction_context: Optional[Dict[str, Any]] = None,
    policy_config: AcceptancePolicyConfig = AcceptancePolicyConfig(),
    persist_bundle: bool = False,
    attachment_uploader: Optional[Callable[..., str]] = None,
    attachment_bucket_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Execute staged candidate assessment workflow and emit one canonical bundle.
    """
    if days <= 0:
        raise ValueError("days must be > 0.")
    if loop_sample_size <= 0:
        raise ValueError("loop_sample_size must be > 0.")
    if gate_sample_size < 200:
        raise ValueError("gate_sample_size must be >= 200.")
    if deterministic_sample_size is not None and deterministic_sample_size <= 0:
        raise ValueError("deterministic_sample_size must be > 0 when provided.")

    deterministic_stage = _require_stage_pair(
        run_stage_pair(
            stage_key=STAGE_DETERMINISTIC,
            sample_size=deterministic_sample_size,
            days=days,
        ),
        STAGE_DETERMINISTIC,
    )
    random_loop_stage = _require_stage_pair(
        run_stage_pair(
            stage_key=STAGE_RANDOM_LOOP,
            sample_size=loop_sample_size,
            days=days,
        ),
        STAGE_RANDOM_LOOP,
    )
    random_gate_stage = _require_stage_pair(
        run_stage_pair(
            stage_key=STAGE_RANDOM_GATE,
            sample_size=gate_sample_size,
            days=days,
        ),
        STAGE_RANDOM_GATE,
    )

    policy_decision = assess_candidate(
        baseline_reference_eval=deterministic_stage["baseline"],
        candidate_reference_eval=deterministic_stage["candidate"],
        baseline_random_eval=random_gate_stage["baseline"],
        candidate_random_eval=random_gate_stage["candidate"],
        config=policy_config,
    )
    workflow_decision = synthesize_workflow_decision(
        policy_decision=policy_decision,
        malfunction_context=malfunction_context or {},
    )
    generalization_metrics = compute_generalization_metrics({
        STAGE_DETERMINISTIC: {
            "baseline": deterministic_stage["baseline"],
            "candidate": deterministic_stage["candidate"],
        },
        STAGE_RANDOM_LOOP: {
            "baseline": random_loop_stage["baseline"],
            "candidate": random_loop_stage["candidate"],
        },
        STAGE_RANDOM_GATE: {
            "baseline": random_gate_stage["baseline"],
            "candidate": random_gate_stage["candidate"],
        },
    })

    bundle = create_candidate_assessment_bundle(
        identity=identity,
        stage_runs={
            STAGE_DETERMINISTIC: {
                "baseline": deterministic_stage["baseline"],
                "candidate": deterministic_stage["candidate"],
                "protocol": {
                    "sample_size": deterministic_sample_size,
                    "days": days,
                },
            },
            STAGE_RANDOM_LOOP: {
                "baseline": random_loop_stage["baseline"],
                "candidate": random_loop_stage["candidate"],
                "protocol": {
                    "sample_size": loop_sample_size,
                    "days": days,
                },
            },
            STAGE_RANDOM_GATE: {
                "baseline": random_gate_stage["baseline"],
                "candidate": random_gate_stage["candidate"],
                "protocol": {
                    "sample_size": gate_sample_size,
                    "days": days,
                },
            },
        },
        decision={
            "decision": policy_decision.get("decision"),
            "reason": policy_decision.get("reason"),
            "confidence": "high" if policy_decision.get("decision") != "inconclusive" else "medium",
        },
        malfunction_context=malfunction_context or {},
        generalization_metrics=generalization_metrics,
        protocol_defaults={
            "days": days,
            "loop_sample_size": loop_sample_size,
            "gate_sample_size": gate_sample_size,
            "deterministic_sample_size": deterministic_sample_size,
        },
    )

    attachment_key = None
    if persist_bundle:
        if not task_id:
            raise ValueError("task_id is required when persist_bundle=True.")
        resolved_uploader = attachment_uploader or upload_task_attachment_json
        if resolved_uploader is upload_task_attachment_json and not attachment_bucket_name:
            raise ValueError(
                "attachment_bucket_name is required when using default upload_task_attachment_json."
            )

        attachment_key = build_candidate_assessment_attachment_key(
            task_id=task_id,
            baseline_score_version_id=bundle["identity"]["baseline_score_version_id"],
            candidate_score_version_id=bundle["identity"]["candidate_score_version_id"],
        )
        payload_json = build_candidate_assessment_attachment_payload(bundle)
        if resolved_uploader is upload_task_attachment_json:
            attachment_key = resolved_uploader(
                bucket_name=attachment_bucket_name,
                key=attachment_key,
                payload_json=payload_json,
            )
        else:
            attachment_key = resolved_uploader(
                key=attachment_key,
                payload_json=payload_json,
            )
        if not attachment_key:
            raise RuntimeError("Attachment uploader returned an empty key.")

    compact_summary = build_candidate_assessment_compact_summary(
        bundle=bundle,
        attachment_key=attachment_key or "pending://not-persisted",
    )

    return {
        "bundle": bundle,
        "compact_summary": compact_summary,
        "policy_decision": policy_decision,
        "workflow_decision": workflow_decision,
        "generalization_metrics": generalization_metrics,
        "attachment_key": attachment_key,
    }
