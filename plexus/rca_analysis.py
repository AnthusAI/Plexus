#!/usr/bin/env python3
"""
Shared RCA analysis utilities for score result investigation.

Used by both the feedback evaluation RCA pipeline (Evaluation.py)
and the on-demand plexus_score_result_investigate MCP tool.
"""
import json
import logging

logger = logging.getLogger(__name__)


def analyze_score_result(
    transcript: str,
    predicted: str,
    correct: str,
    explanation: str,
    topic_label: str = "Score result investigation",
    score_guidelines: str = "",
    score_yaml_code: str = "",
    feedback_context: str = "",
) -> tuple:
    """
    Run a two-turn Bedrock Haiku conversation to analyze a misclassification.

    Returns (detailed_cause, suggested_fix):
      - detailed_cause: why the AI prediction was wrong (2-4 sentences)
      - suggested_fix: one concrete score code change to prevent this error

    Args:
        transcript: Call transcript text
        predicted: The AI's predicted value
        correct: The correct/human-labeled value
        explanation: The AI's reasoning for its prediction
        topic_label: Topic or cluster context label
        score_guidelines: Score guidelines text (truncated to 2000 chars)
        score_yaml_code: Score YAML configuration (truncated to 4000 chars)
        feedback_context: Additional context about reviewer feedback
    """
    import boto3

    system = (
        "You are an expert quality analyst reviewing AI scoring errors on customer calls."
    )

    turn1_prompt = (
        f"Topic context: {topic_label}\n"
        f"AI predicted: {predicted}\n"
        f"Correct answer: {correct}\n"
        f"AI reasoning: {(explanation or '')[:400]}\n"
    )
    if feedback_context:
        turn1_prompt += f"{feedback_context}\n"
    turn1_prompt += "\n"
    if score_guidelines:
        turn1_prompt += f"Score guidelines:\n{score_guidelines[:2000]}\n\n"
    if score_yaml_code:
        turn1_prompt += f"Score configuration:\n```yaml\n{score_yaml_code[:4000]}\n```\n\n"
    turn1_prompt += (
        f"Call transcript:\n{transcript[:6000]}\n\n"
        "Write a single concise paragraph (2-4 sentences) explaining specifically why "
        "the AI prediction was wrong. Focus on what was said or not said in the "
        "transcript that makes the correct answer clear."
    )

    try:
        client = boto3.client("bedrock-runtime", region_name="us-east-1")

        def _haiku_call(messages: list, max_tokens: int) -> str:
            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "system": system,
                "messages": messages,
            })
            resp = client.invoke_model(
                modelId="anthropic.claude-3-haiku-20240307-v1:0",
                body=body,
                contentType="application/json",
                accept="application/json",
            )
            return json.loads(resp["body"].read())["content"][0]["text"].strip()

        messages = [{"role": "user", "content": turn1_prompt}]
        detailed_cause = _haiku_call(messages, max_tokens=200)

        messages.append({"role": "assistant", "content": detailed_cause})
        messages.append({"role": "user", "content": (
            "Based on this specific error and the score configuration above, "
            "suggest one concrete change to the score code that would prevent "
            "this specific misclassification. Be specific and brief (1-2 sentences)."
        )})
        suggested_fix = _haiku_call(messages, max_tokens=150)

        return detailed_cause, suggested_fix
    except Exception as exc:
        logger.warning("analyze_score_result failed: %s", exc)
        return "", ""


def build_feedback_context(
    feedback_comment: str = "",
    feedback_initial: str = "",
    feedback_final: str = "",
    predicted_value: str = "",
) -> str:
    """
    Build a feedback context string for the analysis prompt that handles
    the confusing case where a reviewer "agreed" with the production result
    but the evaluation produced a different result.

    Returns a string to include in the analysis prompt.
    """
    parts = []
    if feedback_comment:
        parts.append(f"Reviewer comment: {feedback_comment[:300]}")
    if feedback_initial and feedback_initial != feedback_final:
        parts.append(f"Original production value: {feedback_initial}")
        parts.append(f"Reviewer corrected to: {feedback_final}")
    elif feedback_initial and feedback_initial == feedback_final:
        parts.append(
            f"Note: Reviewer AGREED with original production value '{feedback_initial}'. "
            f"The evaluation produced '{predicted_value}' which differs from the agreed-upon "
            f"correct value '{feedback_final}'. The reviewer comment may refer to the original "
            f"production result, not the evaluation result."
        )
    return "\n".join(parts)
