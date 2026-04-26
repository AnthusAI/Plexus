"""Shared guideline-vetting voting engine for feedback contradiction/alignment analysis."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from plexus.rubric_memory import validate_rubric_memory_citations

logger = logging.getLogger(__name__)


def _build_prior_votes_context(votes: List[tuple]) -> str:
    """Format prior vote results into a context block for tiebreaker prompts."""
    lines = ["--- Prior Vote Results ---"]
    for i, (model, result) in enumerate(votes, 1):
        if result is None:
            lines.append(f"Vote {i} ({model}): FAILED - no response")
            continue
        verdict = "YES - contradiction/policy gap" if result["contradicts"] else "NO - not a contradiction"
        lines.append(f"Vote {i} ({model}): {verdict}")
        if result.get("reason"):
            lines.append(f"  Reason: {result['reason']}")
        if result.get("category"):
            lines.append(f"  Category: {result['category']}")
        if result.get("guideline_quote"):
            lines.append(f"  Guideline quote: {result['guideline_quote']}")
    lines.append("---")
    lines.append("Please weigh the above prior vote results in your assessment.")
    return "\n".join(lines)


class GuidelineVettingService:
    """Reusable per-item voting service used by contradiction and aligned report modes."""

    def __init__(
        self,
        invoke_bedrock: Optional[Callable[[str, bool], Dict[str, Any]]] = None,
        invoke_openai: Optional[Callable[[str, str], Dict[str, Any]]] = None,
    ):
        self._invoke_bedrock_fn = invoke_bedrock or self._invoke_bedrock
        self._invoke_openai_fn = invoke_openai or self._invoke_openai

    def _build_prompt(
        self,
        item: Any,
        guidelines: Optional[str],
        score_explanation: str,
        rubric_memory_context: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Build classifier prompt for a feedback item; return None when item should be skipped."""
        initial = getattr(item, "initialAnswerValue", "") or ""
        final = getattr(item, "finalAnswerValue", "") or ""
        edit_comment = getattr(item, "editCommentValue", "") or ""

        if initial == final and not edit_comment:
            return None

        situation_lines = [
            "A phone call was evaluated by an AI scoring system.",
            f"- AI score result: '{initial}'",
        ]
        if score_explanation:
            situation_lines.append(f"- AI reasoning: {score_explanation}")
        if initial != final:
            situation_lines.append(f"- A human reviewer then changed the score to '{final}'.")
        else:
            situation_lines.append(f"- A human reviewer left the score as '{final}' but added a comment.")
        situation_lines.append(f"- Reviewer's comment: \"{edit_comment}\"")

        situation = "\n".join(situation_lines)
        guideline_section = f"\nScore Guidelines:\n{guidelines[:3000]}\n" if guidelines else ""
        rubric_memory_section = ""
        if rubric_memory_context and rubric_memory_context.get("markdown_context"):
            rubric_memory_section = (
                "\nRubric Memory Citation Context:\n"
                f"{rubric_memory_context['markdown_context'][:6000]}\n"
            )

        return (
            f"{situation}\n"
            f"{guideline_section}\n"
            f"{rubric_memory_section}\n"
            "Based on the above, evaluate whether this feedback item falls into EITHER of "
            "these two categories:\n\n"
            "  A) CONTRADICTION: The reviewer's correction is INCONSISTENT with what the "
            "guidelines say. For example, the guidelines prohibit something but the reviewer "
            "approved it, or the guidelines permit something but the reviewer flagged it.\n\n"
            "  B) POLICY GAP: The reviewer's comment describes agent behavior that the "
            "guidelines do NOT address at all - neither permitting nor prohibiting it. This "
            "means the guidelines may need to be updated to cover this behavior.\n\n"
            "Mark `contradicts` as true for EITHER category A or B.\n\n"
            "Reply ONLY with a JSON object with five keys:\n"
            '  "contradicts": true or false\n'
            '  "category": "contradiction" or "policy_gap" (or null if contradicts is false)\n'
            '  "reason": one sentence focused on the POLICY issue - for contradictions, '
            "name the specific guideline policy that is violated and what the agent did that "
            "violates it; for policy gaps, name the agent behavior that the guidelines should "
            "address but currently do not. Do NOT describe what the reviewer did.\n"
            '  "guideline_quote": the exact short phrase from the guidelines being '
            'contradicted (for category A), or "Policy gap: not addressed in guidelines" '
            "(for category B), or empty string if not contradicting\n"
            '  "citation_ids": an array of exact rubric-memory citation IDs used for any policy-memory claim, or []\n'
            "Reply ONLY with valid JSON, no other text."
        )

    def _parse_classifier_response(self, text: str) -> Dict[str, Any]:
        """Extract and parse JSON classifier response."""
        import re as _re

        if "```" in text:
            match = _re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
            if match:
                text = match.group(1).strip()
        obj_match = _re.search(r"\{[\s\S]*\}", text)
        if obj_match:
            text = obj_match.group(0)
        return json.loads(text)

    def _invoke_bedrock(self, prompt: str, use_thinking: bool = False) -> Dict[str, Any]:
        """Single Sonnet classifier call with one parse retry."""
        import boto3

        bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
        body_dict: Dict[str, Any] = {
            "anthropic_version": "bedrock-2023-05-31",
            "messages": [{"role": "user", "content": prompt}],
        }
        if use_thinking:
            body_dict["max_tokens"] = 4000
            body_dict["temperature"] = 1
            body_dict["thinking"] = {"type": "enabled", "budget_tokens": 3000}
        else:
            body_dict["max_tokens"] = 400
            body_dict["temperature"] = 0

        body = json.dumps(body_dict)
        last_error: Optional[Exception] = None
        for _ in range(2):
            response = bedrock.invoke_model(
                modelId="us.anthropic.claude-sonnet-4-6",
                body=body,
                contentType="application/json",
                accept="application/json",
            )
            raw = json.loads(response["body"].read())
            thinking_text = ""
            text = ""
            for block in raw.get("content", []):
                if block.get("type") == "thinking":
                    thinking_text = block.get("thinking", "")
                elif block.get("type") == "text":
                    text = (block.get("text") or "").strip()
            if not text and raw.get("content"):
                text = (raw["content"][0].get("text") or "").strip()
            try:
                parsed = self._parse_classifier_response(text)
                if thinking_text:
                    parsed["_thinking"] = thinking_text
                return parsed
            except json.JSONDecodeError as exc:
                last_error = exc
        if last_error:
            raise last_error
        raise ValueError("Classifier response parsing failed without exception context.")

    def _invoke_openai(self, prompt: str, reasoning_effort: str = "low") -> Dict[str, Any]:
        """GPT-5.4 classifier with corrective retries for strict JSON output."""
        import os
        from dotenv import load_dotenv
        from openai import OpenAI

        load_dotenv(override=False)
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

        input_messages: List[Dict[str, str]] = [{"role": "user", "content": prompt}]
        last_error: Optional[Exception] = None
        reasoning_summary = ""

        for _ in range(4):
            response = client.responses.create(
                model="gpt-5.4",
                reasoning={"effort": reasoning_effort},
                input=input_messages,
                max_output_tokens=4000 if reasoning_effort == "high" else 400,
            )
            text = response.output_text.strip()
            reasoning_summary = ""
            for item in response.output:
                if getattr(item, "type", None) != "reasoning":
                    continue
                for part in getattr(item, "summary", []) or []:
                    if getattr(part, "type", None) == "summary_text":
                        reasoning_summary += getattr(part, "text", "")
            try:
                parsed = self._parse_classifier_response(text)
                if reasoning_summary:
                    parsed["_thinking"] = reasoning_summary
                return parsed
            except json.JSONDecodeError as exc:
                last_error = exc
                input_messages.append({"role": "assistant", "content": text or "(empty response)"})
                input_messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Your response was not valid JSON. Respond ONLY with a valid JSON object "
                            "with exactly these keys: \"contradicts\" (boolean), \"reason\" (string), "
                            "\"category\" (string), \"guideline_quote\" (string), "
                            "\"citation_ids\" (array). "
                            "No prose, no code blocks, no extra text."
                        ),
                    }
                )
        if last_error:
            raise last_error
        raise ValueError("OpenAI classifier did not return JSON and no parse error was captured.")

    def _build_result_item(
        self,
        item: Any,
        best_result: Dict[str, Any],
        votes_meta: List[Dict[str, Any]],
        score_explanation: str,
        confidence: str,
        verdict: str,
        associated_dataset_eligible: bool,
        rubric_memory_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        edited_at = getattr(item, "editedAt", None)
        if hasattr(edited_at, "isoformat"):
            edited_at = edited_at.isoformat()

        nested_item = getattr(item, "item", None)
        item_external_id = getattr(nested_item, "externalId", None) if nested_item else None
        modern_identifiers = getattr(nested_item, "item_identifiers", None) if nested_item else None
        if modern_identifiers:
            item_identifiers = json.dumps(
                [
                    {
                        "name": identifier.get("name", ""),
                        "id": identifier.get("value", ""),
                        "url": identifier.get("url"),
                    }
                    for identifier in sorted(modern_identifiers, key=lambda x: x.get("position") or 0)
                ]
            )
        else:
            item_identifiers = getattr(nested_item, "identifiers", None) if nested_item else None

        category = best_result.get("category", "") or ""
        if verdict == "aligned" and not category:
            category = "aligned"
        citation_validation = validate_rubric_memory_citations(
            best_result.get("citation_ids") or [],
            rubric_memory_context,
            require_citation=bool(rubric_memory_context and rubric_memory_context.get("citation_index")),
        )

        return {
            "feedback_item_id": item.id,
            "item_id": getattr(item, "itemId", None),
            "item_identifiers": item_identifiers,
            "item_external_id": item_external_id,
            "initial_value": getattr(item, "initialAnswerValue", "") or "",
            "final_value": getattr(item, "finalAnswerValue", "") or "",
            "score_result_explanation": score_explanation,
            "edit_comment": getattr(item, "editCommentValue", "") or "",
            "editor_name": getattr(item, "editorName", None),
            "edited_at": edited_at,
            "reason": best_result.get("reason", "") or "",
            "category": category,
            "guideline_quote": best_result.get("guideline_quote", "") or "",
            "is_invalid": getattr(item, "isInvalid", False) or False,
            "confidence": confidence,
            "voting": votes_meta,
            "verdict": verdict,
            "associated_dataset_eligible": associated_dataset_eligible,
            "citation_ids": citation_validation.valid_ids,
            "citation_validation": citation_validation.model_dump(mode="json"),
            "rubric_memory_citation_count": len(
                (rubric_memory_context or {}).get("citation_index") or []
            ),
        }

    async def analyze_items(
        self,
        items: List[Any],
        guidelines: Optional[str],
        max_concurrent: int,
        score_results_by_item: Dict[str, Any],
        rubric_memory_contexts_by_item: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Analyze items via shared voting and return both contradiction and aligned results.

        Each returned item includes per-vote traces, confidence, verdict, and
        strict associated-dataset eligibility (`unanimous non-contradiction` only).
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def analyze_one(item: Any) -> Optional[Dict[str, Any]]:
            async with semaphore:
                item_id = getattr(item, "itemId", None)
                score_result = score_results_by_item.get(item_id) if item_id else None
                score_explanation = (score_result.get("explanation") or "") if score_result else ""
                rubric_memory_context = (
                    (rubric_memory_contexts_by_item or {}).get(item_id)
                    or (rubric_memory_contexts_by_item or {}).get(getattr(item, "id", ""))
                )

                prompt = self._build_prompt(
                    item,
                    guidelines,
                    score_explanation,
                    rubric_memory_context=rubric_memory_context,
                )
                if prompt is None:
                    return None

                round_one_raw = await asyncio.gather(
                    asyncio.to_thread(self._invoke_bedrock_fn, prompt),
                    asyncio.to_thread(self._invoke_openai_fn, prompt),
                    asyncio.to_thread(self._invoke_bedrock_fn, prompt),
                    return_exceptions=True,
                )
                round_one_models = ["sonnet", "gpt", "sonnet"]
                round_one_votes: List[Tuple[str, Optional[Dict[str, Any]]]] = [
                    (model, result if not isinstance(result, Exception) else None)
                    for model, result in zip(round_one_models, round_one_raw)
                ]

                valid_round_one = [(model, result) for model, result in round_one_votes if result is not None]
                if len(valid_round_one) < 2:
                    logger.warning("Too many vote failures for feedback item %s; skipping", getattr(item, "id", "unknown"))
                    return None

                round_one_bools = [result["contradicts"] for _, result in valid_round_one]
                yes_count = sum(round_one_bools)
                no_count = len(round_one_bools) - yes_count
                any_round_one_failed = len(valid_round_one) < len(round_one_votes)
                round_one_unanimous = not any_round_one_failed and (yes_count == len(round_one_bools) or no_count == len(round_one_bools))

                round_two_votes: List[Tuple[str, Optional[Dict[str, Any]]]] = []
                if not round_one_unanimous:
                    round_one_context = _build_prior_votes_context(round_one_votes)

                    prompt_round_two_sonnet = prompt + "\n\n" + round_one_context
                    try:
                        round_two_sonnet = await asyncio.to_thread(self._invoke_bedrock_fn, prompt_round_two_sonnet, True)
                    except Exception:
                        round_two_sonnet = None

                    round_two_context = _build_prior_votes_context(round_one_votes + [("sonnet", round_two_sonnet)])
                    prompt_round_two_gpt = prompt + "\n\n" + round_two_context
                    try:
                        round_two_gpt = await asyncio.to_thread(self._invoke_openai_fn, prompt_round_two_gpt, "high")
                    except Exception:
                        round_two_gpt = None

                    round_two_votes = [("sonnet", round_two_sonnet), ("gpt", round_two_gpt)]
                    valid_round_two = [(model, result) for model, result in round_two_votes if result is not None]
                    round_two_bools = [result["contradicts"] for _, result in valid_round_two]
                    yes_count += sum(round_two_bools)
                    no_count += len(round_two_bools) - sum(round_two_bools)

                all_votes = round_one_votes + round_two_votes
                votes_meta = [
                    {
                        "model": model,
                        "result": result["contradicts"] if result is not None else None,
                        "reason": result.get("reason", "") if result else "",
                        "category": result.get("category", "") if result else "",
                        "guideline_quote": result.get("guideline_quote", "") if result else "",
                        "citation_ids": result.get("citation_ids", []) if result else [],
                        "citation_validation": validate_rubric_memory_citations(
                            result.get("citation_ids", []) if result else [],
                            rubric_memory_context,
                            require_citation=False,
                        ).model_dump(mode="json"),
                        "thinking": result.get("_thinking", "") if result else "",
                    }
                    for model, result in all_votes
                ]

                verdict = "contradiction" if yes_count > no_count else "aligned"
                winning_value = verdict == "contradiction"
                winning_votes = [
                    result
                    for _, result in all_votes
                    if result is not None and bool(result.get("contradicts")) is winning_value
                ]
                if not winning_votes:
                    return None
                best_result = winning_votes[0]

                total_votes = len(votes_meta)
                winning_count = sum(1 for vote in votes_meta if vote["result"] is winning_value)
                confidence_ratio = winning_count / total_votes if total_votes else 0
                if confidence_ratio == 1.0:
                    confidence = "high"
                elif confidence_ratio >= 0.8:
                    confidence = "medium"
                else:
                    confidence = "low"

                associated_dataset_eligible = bool(
                    round_one_unanimous and no_count > 0 and yes_count == 0 and not round_two_votes
                )

                return self._build_result_item(
                    item=item,
                    best_result=best_result,
                    votes_meta=votes_meta,
                    score_explanation=score_explanation,
                    confidence=confidence,
                    verdict=verdict,
                    associated_dataset_eligible=associated_dataset_eligible,
                    rubric_memory_context=rubric_memory_context,
                )

        analyzed = await asyncio.gather(*[analyze_one(item) for item in items])
        return [result for result in analyzed if result is not None]
