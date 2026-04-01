"""
FeedbackContradictions report block.

Analyzes feedback items for a score against the score's published guidelines,
using an LLM to flag items where the reviewer's correction appears to contradict
the guidelines.  Contradictions are grouped into semantic topic clusters so
operators can quickly identify patterns and mark specific items as invalid.
"""
from typing import Any, Dict, List, Optional, Tuple
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from .base import BaseReportBlock
from . import feedback_utils
from plexus.dashboard.api.models.score import Score
from plexus.dashboard.api.models.scorecard import Scorecard

logger = logging.getLogger(__name__)



class FeedbackContradictions(BaseReportBlock):
    """
    Identifies feedback items that appear to contradict the score's guidelines.

    For each feedback item in the configured time window the block asks a fast
    LLM (Bedrock Haiku) whether the reviewer's correction is consistent with
    the published guidelines.  Items flagged as contradictions are then
    clustered into semantic topics by a second LLM pass so operators can see
    patterns at a glance.

    Config keys:
        scorecard (str): Scorecard external ID or UUID.  Required.
        score (str): Score name, external ID, or UUID.  Required.
        days (int): Look-back window in days (default: 360).
        start_date (str): ISO date override for window start (YYYY-MM-DD).
        end_date (str): ISO date override for window end (YYYY-MM-DD).
        max_concurrent (int): Parallel LLM calls per batch (default: 20).
        num_topics (int): Target number of topic clusters (default: 8).
    """

    DEFAULT_NAME = "Feedback Contradictions"
    DEFAULT_DESCRIPTION = "Guideline Contradiction Analysis"

    # --------------------------------------------------------------------------
    # Public entry point
    # --------------------------------------------------------------------------

    async def generate(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        self._orm.log_messages.clear()
        try:
            return await self._run()
        except Exception as exc:
            import traceback
            self._log(f"ERROR: {exc}", level="ERROR")
            self._log(traceback.format_exc())
            error_data = {"error": str(exc), "topics": []}
            return error_data, "\n".join(self._orm.log_messages)

    # --------------------------------------------------------------------------
    # Main pipeline
    # --------------------------------------------------------------------------

    async def _run(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        # --- Config ---
        scorecard_param = self.config.get("scorecard")
        score_param = self.config.get("score") or self.config.get("score_id")
        if not scorecard_param:
            raise ValueError("'scorecard' is required in block configuration.")
        if not score_param:
            raise ValueError("'score' is required in block configuration.")

        days = int(self.config.get("days", 360))
        start_date_str = self.config.get("start_date")
        end_date_str = self.config.get("end_date")
        max_concurrent = int(self.config.get("max_concurrent", 20))
        num_topics = int(self.config.get("num_topics", 8))

        # Date range
        if start_date_str:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        else:
            start_date = (datetime.now(tz=timezone.utc) - timedelta(days=days))
        if end_date_str:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, microsecond=999999, tzinfo=timezone.utc
            )
        else:
            end_date = datetime.now(tz=timezone.utc).replace(
                hour=23, minute=59, second=59, microsecond=999999
            )

        self._log(f"Date range: {start_date.date()} to {end_date.date()}")

        # --- Resolve scorecard ---
        self._log(f"Resolving scorecard: {scorecard_param}")
        is_uuid = len(str(scorecard_param)) > 20 and "-" in str(scorecard_param)
        if is_uuid:
            scorecard_obj = await asyncio.to_thread(
                Scorecard.get_by_id, id=str(scorecard_param), client=self.api_client
            )
        else:
            scorecard_obj = await asyncio.to_thread(
                Scorecard.get_by_external_id,
                external_id=str(scorecard_param),
                client=self.api_client,
            )
        if not scorecard_obj:
            raise ValueError(f"Scorecard not found: {scorecard_param}")
        self._log(f"Scorecard: '{scorecard_obj.name}' ({scorecard_obj.id})")

        # --- Resolve score ---
        self._log(f"Resolving score: {score_param}")
        score_obj = await self._resolve_score(str(score_param), scorecard_obj.id)
        if not score_obj:
            raise ValueError(f"Score not found: {score_param}")
        self._log(f"Score: '{score_obj.name}' ({score_obj.id})")

        # --- Fetch champion version guidelines ---
        guidelines = await self._fetch_guidelines(score_obj.id)
        if guidelines:
            self._log(f"Loaded guidelines ({len(guidelines)} chars)")
        else:
            self._log("WARNING: No guidelines found for this score — contradiction detection will be limited.", level="WARNING")

        # --- Fetch feedback items ---
        account_id = self._get_account_id()
        self._log(f"Fetching feedback items for score {score_obj.id}…")
        all_items = await feedback_utils.fetch_feedback_items_for_score(
            self.api_client, account_id, scorecard_obj.id, score_obj.id, start_date, end_date
        )

        # Exclude already-invalid items
        valid_items = [it for it in all_items if not getattr(it, "isInvalid", False)]
        self._log(f"Fetched {len(all_items)} items; {len(valid_items)} eligible after excluding already-invalid.")

        if not valid_items:
            return {
                "score_name": score_obj.name,
                "total_items_analyzed": 0,
                "contradictions_found": 0,
                "topics": [],
            }, "\n".join(self._orm.log_messages)

        # --- Fetch score results for each item in parallel (by itemId + scoreId) ---
        self._log(f"Fetching score results for {len(valid_items)} items…")
        item_ids = [getattr(it, "itemId", None) for it in valid_items]
        item_ids = [iid for iid in item_ids if iid]
        score_results_by_item = await self._fetch_score_results_by_item_ids(
            item_ids, score_obj.id
        )
        self._log(f"Loaded {len(score_results_by_item)} score results.")

        # --- Per-item LLM contradiction analysis ---
        self._log(f"Running contradiction analysis (max_concurrent={max_concurrent})…")
        contradictions = await self._analyze_items(valid_items, guidelines, max_concurrent, score_results_by_item)
        self._log(f"Contradictions found: {len(contradictions)} / {len(valid_items)}")

        # --- Topic clustering ---
        topics: List[Dict[str, Any]] = []
        if contradictions:
            self._log(f"Clustering {len(contradictions)} contradictions into up to {num_topics} topics…")
            topics = await self._cluster_topics(contradictions, num_topics, guidelines)
            self._log(f"Produced {len(topics)} topic clusters.")

        output = {
            "score_name": score_obj.name,
            "total_items_analyzed": len(valid_items),
            "contradictions_found": len(contradictions),
            "topics": topics,
            "block_configuration": {
                "scorecard": scorecard_param,
                "score": score_param,
                "days": days,
                "max_concurrent": max_concurrent,
                "num_topics": num_topics,
            },
        }
        context_header = (
            "# Feedback Contradictions Report Output\n"
            "#\n"
            "# This report analyzes feedback items against score guidelines to identify\n"
            "# contradictions and policy gaps. Items are classified by a multi-model voting\n"
            "# system (Sonnet + GPT-5.4) with optional tiebreaker rounds using extended thinking.\n"
            "#\n"
            "# Structure:\n"
            "#   score_name: The score being analyzed\n"
            "#   total_items_analyzed: Number of feedback items evaluated\n"
            "#   contradictions_found: Number of items flagged as contradictions or policy gaps\n"
            "#   topics: Clustered groups of contradictions with exemplar items\n"
            "#     Each exemplar includes:\n"
            "#       - voting: Per-model votes with reasoning traces\n"
            "#       - confidence: high/medium/low based on vote agreement\n"
            "#       - reason: Synthesized explanation of the policy issue\n"
            "#       - score_result_explanation: Original AI score explanation\n"
            "#       - edit_comment: Human reviewer's correction comment\n"
            "\n"
        )
        formatted_output = context_header + json.dumps(output, indent=2, ensure_ascii=False)
        return formatted_output, "\n".join(self._orm.log_messages)

    # --------------------------------------------------------------------------
    # Score resolution
    # --------------------------------------------------------------------------

    async def _resolve_score(self, score_param: str, scorecard_id: str) -> Optional[Any]:
        """Resolve a score by UUID, name, or external ID within the given scorecard."""
        is_uuid_like = (
            len(score_param) == 36
            and score_param.count("-") == 4
            and all(c in "0123456789abcdefABCDEF-" for c in score_param)
        )
        if is_uuid_like:
            score_obj = await asyncio.to_thread(Score.get_by_id, id=score_param, client=self.api_client)
            if score_obj and score_obj.scorecard_id == scorecard_id:
                return score_obj

        # Try by name on the scorecard
        scores = await feedback_utils.fetch_scores_for_scorecard(self.api_client, scorecard_id)
        for s in scores:
            if (
                s["plexus_score_name"].lower() == score_param.lower()
                or s.get("cc_question_id", "") == score_param
                or s["plexus_score_id"] == score_param
            ):
                return await asyncio.to_thread(
                    Score.get_by_id, id=s["plexus_score_id"], client=self.api_client
                )
        return None

    # --------------------------------------------------------------------------
    # Guidelines fetch
    # --------------------------------------------------------------------------

    async def _fetch_guidelines(self, score_id: str) -> Optional[str]:
        """Return the guidelines text from the champion score version."""
        try:
            gql = """
            query GetScoreChampion($id: ID!) {
                getScore(id: $id) {
                    championVersionId
                }
            }
            """
            result = await asyncio.to_thread(self.api_client.execute, gql, {"id": score_id})
            champion_id = (result or {}).get("getScore", {}).get("championVersionId")
            if not champion_id:
                return None

            version_gql = """
            query GetScoreVersion($id: ID!) {
                getScoreVersion(id: $id) {
                    guidelines
                    configuration
                }
            }
            """
            vresult = await asyncio.to_thread(
                self.api_client.execute, version_gql, {"id": champion_id}
            )
            sv = (vresult or {}).get("getScoreVersion", {})
            return sv.get("guidelines") or sv.get("configuration") or None
        except Exception as exc:
            self._log(f"Could not fetch guidelines: {exc}", level="WARNING")
            return None

    # --------------------------------------------------------------------------
    # Per-item contradiction analysis
    # --------------------------------------------------------------------------

    def _build_contradiction_prompt(
        self, item: Any, guidelines: Optional[str], score_explanation: str
    ) -> Optional[str]:
        """Build the classifier prompt for a feedback item. Returns None if item should be skipped."""
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

        return (
            f"{situation}\n"
            f"{guideline_section}\n"
            "Based on the above, evaluate whether this feedback item falls into EITHER of "
            "these two categories:\n\n"
            "  A) CONTRADICTION: The reviewer's correction is INCONSISTENT with what the "
            "guidelines say. For example, the guidelines prohibit something but the reviewer "
            "approved it, or the guidelines permit something but the reviewer flagged it.\n\n"
            "  B) POLICY GAP: The reviewer's comment describes agent behavior that the "
            "guidelines do NOT address at all — neither permitting nor prohibiting it. This "
            "means the guidelines may need to be updated to cover this behavior.\n\n"
            "Mark `contradicts` as true for EITHER category A or B.\n\n"
            "Reply ONLY with a JSON object with four keys:\n"
            '  "contradicts": true or false\n'
            '  "category": "contradiction" or "policy_gap" (or null if contradicts is false)\n'
            '  "reason": one sentence focused on the POLICY issue — for contradictions, '
            "name the specific guideline policy that is violated and what the agent did that "
            "violates it; for policy gaps, name the agent behavior that the guidelines should "
            "address but currently do not. Do NOT describe what the reviewer did.\n"
            '  "guideline_quote": the exact short phrase from the guidelines being '
            'contradicted (for category A), or "Policy gap: not addressed in guidelines" '
            "(for category B), or empty string if not contradicting\n"
            "Reply ONLY with valid JSON, no other text."
        )

    def _parse_classifier_response(self, text: str) -> Dict:
        """Extract and parse the JSON classifier response. Raises json.JSONDecodeError on failure."""
        import re as _re
        if "```" in text:
            m = _re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
            if m:
                text = m.group(1).strip()
        obj_m = _re.search(r"\{[\s\S]*\}", text)
        if obj_m:
            text = obj_m.group(0)
        return json.loads(text)

    def _invoke_bedrock(self, prompt: str, use_thinking: bool = False) -> Dict:
        """Single Sonnet classifier call with one JSON-parse retry. Returns parsed dict or raises."""
        import boto3
        bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
        body_dict: Dict[str, Any] = {
            "anthropic_version": "bedrock-2023-05-31",
            "messages": [{"role": "user", "content": prompt}],
        }
        if use_thinking:
            body_dict["max_tokens"] = 4000
            body_dict["temperature"] = 1  # required when thinking is enabled
            body_dict["thinking"] = {"type": "enabled", "budget_tokens": 3000}
        else:
            body_dict["max_tokens"] = 400
            body_dict["temperature"] = 0
        body = json.dumps(body_dict)
        last_exc = None
        for _ in range(2):
            response = bedrock.invoke_model(
                modelId="us.anthropic.claude-sonnet-4-6",
                body=body,
                contentType="application/json",
                accept="application/json",
            )
            raw = json.loads(response["body"].read())
            # When thinking is enabled, response has thinking + text blocks
            thinking_text = ""
            text = ""
            for block in raw["content"]:
                if block.get("type") == "thinking":
                    thinking_text = block.get("thinking", "")
                elif block.get("type") == "text":
                    text = block["text"].strip()
            if not text:
                text = raw["content"][0]["text"].strip()
            try:
                parsed = self._parse_classifier_response(text)
                if thinking_text:
                    parsed["_thinking"] = thinking_text
                return parsed
            except json.JSONDecodeError as exc:
                last_exc = exc
        raise last_exc  # type: ignore[misc]

    def _invoke_openai(self, prompt: str, reasoning_effort: str = "low") -> Dict:
        """GPT-5.4 classifier call with multi-turn corrective retry. Returns parsed dict or raises."""
        import os
        from dotenv import load_dotenv
        from openai import OpenAI
        load_dotenv(override=False)  # load .env if OPENAI_API_KEY not already in environment
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        input_messages: List[Dict] = [{"role": "user", "content": prompt}]
        last_exc = None
        reasoning_summary = ""
        for attempt in range(4):  # 4 total: 1 initial + up to 3 corrective retries
            response = client.responses.create(
                model="gpt-5.4",
                reasoning={"effort": reasoning_effort},
                input=input_messages,
                max_output_tokens=400,
            )
            text = response.output_text.strip()
            # Extract reasoning summary if available
            reasoning_summary = ""
            for item in response.output:
                if getattr(item, "type", None) == "reasoning":
                    for part in getattr(item, "summary", []) or []:
                        if getattr(part, "type", None) == "summary_text":
                            reasoning_summary += getattr(part, "text", "")
            try:
                parsed = self._parse_classifier_response(text)
                if reasoning_summary:
                    parsed["_thinking"] = reasoning_summary
                return parsed
            except json.JSONDecodeError as exc:
                last_exc = exc
                # Append corrective turn for next attempt
                input_messages.append({"role": "assistant", "content": text or "(empty response)"})
                input_messages.append({
                    "role": "user",
                    "content": (
                        "Your response was not valid JSON. Respond ONLY with a valid JSON object "
                        "with exactly these keys: \"contradicts\" (boolean), \"reason\" (string), "
                        "\"category\" (string), \"guideline_quote\" (string). "
                        "No prose, no code blocks, no extra text."
                    ),
                })
        raise last_exc  # type: ignore[misc]

    def _build_exemplar(
        self,
        item: Any,
        best_result: Dict,
        votes_meta: List[Dict],
        score_explanation: str,
        confidence: str = "high",
    ) -> Dict:
        """Build the exemplar dict from item metadata and the winning classifier result."""
        edited_at = getattr(item, "editedAt", None)
        if hasattr(edited_at, "isoformat"):
            edited_at = edited_at.isoformat()

        nested_item = getattr(item, "item", None)
        item_external_id = getattr(nested_item, "externalId", None) if nested_item else None

        modern_identifiers = getattr(nested_item, "item_identifiers", None) if nested_item else None
        if modern_identifiers:
            item_identifiers = json.dumps(
                [{"name": i.get("name", ""), "id": i.get("value", ""), "url": i.get("url")}
                 for i in sorted(modern_identifiers, key=lambda x: x.get("position") or 0)]
            )
        else:
            item_identifiers = getattr(nested_item, "identifiers", None) if nested_item else None

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
            "reason": best_result.get("reason", ""),
            "category": best_result.get("category", ""),
            "guideline_quote": best_result.get("guideline_quote", ""),
            "is_invalid": getattr(item, "isInvalid", False) or False,
            "confidence": confidence,
            "voting": votes_meta,
        }

    def _synthesize_explanation(self, prompt: str, votes_meta: List[Dict],
                               use_thinking: bool = False) -> Dict:
        """Synthesize a final explanation from all vote responses using Sonnet."""
        vote_descriptions = []
        for i, v in enumerate(votes_meta, 1):
            if v["result"] is None:
                vote_descriptions.append(f"Vote {i} ({v['model']}): FAILED (no response)")
            else:
                label = "CONTRADICTION" if v["result"] else "NOT A CONTRADICTION"
                desc = (
                    f"Vote {i} ({v['model']}): {label}\n"
                    f"  Reason: {v.get('reason', 'N/A')}\n"
                    f"  Category: {v.get('category', 'N/A')}\n"
                    f"  Guideline quote: {v.get('guideline_quote', 'N/A')}"
                )
                if v.get("thinking"):
                    desc += f"\n  Internal reasoning: {v['thinking'][:500]}"
                vote_descriptions.append(desc)
        votes_text = "\n\n".join(vote_descriptions)
        yes_count = sum(1 for v in votes_meta if v["result"] is True)
        no_count = sum(1 for v in votes_meta if v["result"] is False)
        null_count = sum(1 for v in votes_meta if v["result"] is None)

        if no_count > 0:
            split_instruction = (
                f"\nIMPORTANT — the votes are split. Your 'reason' field MUST explicitly:\n"
                f"1. State what the YES votes identified as the contradiction or policy gap\n"
                f"2. State what the NO votes saw differently — the specific point of disagreement\n"
                f"3. Briefly explain why the majority YES position prevails\n"
                f"This helps reviewers understand the genuine ambiguity.\n"
            )
        else:
            split_instruction = ""

        synthesis_prompt = (
            f"You are reviewing the results of a multi-model voting system that evaluated "
            f"whether a feedback item represents a policy contradiction or gap.\n\n"
            f"ORIGINAL EVALUATION CONTEXT:\n{prompt}\n\n"
            f"VOTE RESULTS ({yes_count} yes / {no_count} no / {null_count} failed):\n\n{votes_text}\n\n"
            f"FINAL VERDICT: This item IS a contradiction/policy gap and is included in this report "
            f"because the majority voted YES ({yes_count} yes vs {no_count} no).\n"
            f"{split_instruction}\n"
            f"Write a SINGLE synthesized explanation from the perspective of the YES (majority) votes. "
            f"Your explanation should describe the policy issue clearly (not what the reviewer did).\n\n"
            f'Reply ONLY with valid JSON: {{"reason": "...", "category": "contradiction" or "policy_gap", '
            f'"guideline_quote": "most relevant guideline phrase or Policy gap: not addressed in guidelines"}}'
        )

        return self._invoke_bedrock(synthesis_prompt, use_thinking=use_thinking)

    async def _fetch_score_results_by_item_ids(
        self, item_ids: List[str], score_id: str
    ) -> Dict[str, Any]:
        """Fetch ScoreResults for a list of item IDs, filtered to a specific score."""
        gql = """
        query GetScoreResultsByItemId($itemId: String!, $scoreId: String!) {
            listScoreResultByItemId(
                itemId: $itemId,
                filter: { scoreId: { eq: $scoreId } }
                limit: 5
            ) {
                items { id value explanation itemId scoreId }
            }
        }
        """
        sem = asyncio.Semaphore(20)

        async def fetch_one(item_id: str):
            async with sem:
                try:
                    result = await asyncio.to_thread(
                        self.api_client.execute, gql,
                        {"itemId": item_id, "scoreId": score_id}
                    )
                    items = (result or {}).get("listScoreResultByItemId", {}).get("items") or []
                    return item_id, items[0] if items else None
                except Exception as exc:
                    logger.warning(f"score result fetch failed for item {item_id}: {exc}")
                    return item_id, None

        results = await asyncio.gather(*[fetch_one(iid) for iid in item_ids])
        return {iid: sr for iid, sr in results if sr is not None}

    async def _analyze_items(
        self,
        items: List[Any],
        guidelines: Optional[str],
        max_concurrent: int,
        score_results_by_item: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Return a list of contradiction dicts for items that contradict guidelines."""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def analyze_one(item) -> Optional[Dict[str, Any]]:
            async with semaphore:
                item_id = getattr(item, "itemId", None)
                sr = score_results_by_item.get(item_id) if item_id else None
                score_explanation = (sr.get("explanation") or "") if sr else ""

                prompt = self._build_contradiction_prompt(item, guidelines, score_explanation)
                if prompt is None:
                    return None

                # --- Round 1: Sonnet + GPT-5.4 + Sonnet (all 3 in parallel) ---
                r1_raw = await asyncio.gather(
                    asyncio.to_thread(self._invoke_bedrock, prompt),
                    asyncio.to_thread(self._invoke_openai, prompt),
                    asyncio.to_thread(self._invoke_bedrock, prompt),
                    return_exceptions=True,
                )
                r1_models = ["sonnet", "gpt", "sonnet"]
                r1 = [
                    (model, r if not isinstance(r, Exception) else None)
                    for model, r in zip(r1_models, r1_raw)
                ]

                valid_r1 = [(m, r) for m, r in r1 if r is not None]
                if len(valid_r1) < 2:
                    logger.warning(f"Too many vote failures for item {item.id}, skipping")
                    return None

                r1_bools = [r["contradicts"] for _, r in valid_r1]
                yes = sum(r1_bools)
                no = len(r1_bools) - yes
                any_r1_failed = len(valid_r1) < len(r1)
                unanimous = not any_r1_failed and ((yes == len(r1_bools)) or (no == len(r1_bools)))

                r2: List[tuple] = []
                if not unanimous:
                    # --- Round 2: Sonnet (thinking) + GPT-5.4 (high reasoning) ---
                    r2_raw = await asyncio.gather(
                        asyncio.to_thread(self._invoke_bedrock, prompt, True),
                        asyncio.to_thread(self._invoke_openai, prompt, "high"),
                        return_exceptions=True,
                    )
                    r2_models = ["sonnet", "gpt"]
                    r2 = [
                        (model, r if not isinstance(r, Exception) else None)
                        for model, r in zip(r2_models, r2_raw)
                    ]
                    valid_r2 = [(m, r) for m, r in r2 if r is not None]
                    r2_bools = [r["contradicts"] for _, r in valid_r2]
                    yes += sum(r2_bools)
                    no += len(r2_bools) - sum(r2_bools)

                if yes <= no:
                    return None

                # Build full vote metadata (with reasons) for synthesis
                all_votes = r1 + r2
                votes_with_reasons = [
                    {
                        "model": m,
                        "result": r["contradicts"] if r is not None else None,
                        "reason": r.get("reason", "") if r else "",
                        "category": r.get("category", "") if r else "",
                        "guideline_quote": r.get("guideline_quote", "") if r else "",
                        "thinking": r.get("_thinking", "") if r else "",
                    }
                    for m, r in all_votes
                ]

                # Compute confidence from all votes (nulls count as non-agreements)
                total_votes = len(votes_with_reasons)
                yes_total = sum(1 for v in votes_with_reasons if v["result"] is True)
                confidence_ratio = yes_total / total_votes if total_votes > 0 else 0
                if confidence_ratio == 1.0:
                    confidence = "high"
                elif confidence_ratio >= 0.8:
                    confidence = "medium"
                else:
                    confidence = "low"

                # Synthesize a unified explanation from all vote responses
                try:
                    best = await asyncio.to_thread(
                        self._synthesize_explanation, prompt, votes_with_reasons,
                        not unanimous,
                    )
                except Exception:
                    # Fall back to first winning-side Sonnet result
                    all_valid = [(m, r) for m, r in all_votes if r is not None and r.get("contradicts")]
                    sonnet_winners = [r for m, r in all_valid if m == "sonnet"]
                    best = sonnet_winners[0] if sonnet_winners else all_valid[0][1]

                return self._build_exemplar(item, best, votes_with_reasons, score_explanation, confidence)

        results = await asyncio.gather(*[analyze_one(it) for it in items])
        return [r for r in results if r is not None]

    # --------------------------------------------------------------------------
    # Topic clustering
    # --------------------------------------------------------------------------

    async def _cluster_topics(
        self, contradictions: List[Dict[str, Any]], num_topics: int,
        guidelines: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Group contradictions into semantic topic clusters using a single LLM call.

        Each contradiction's 'reason' string is sent to the LLM with instructions
        to assign a short topic label, a one-sentence summary, and the specific
        guideline quote that the cluster contradicts.
        Results are grouped and sorted by count.
        """
        # Build a numbered list of reason strings
        reasons_text = "\n".join(
            f"{i + 1}. {c['reason']}" for i, c in enumerate(contradictions)
        )

        # --- Pass 1: cluster by semantic similarity (no guidelines — keeps prompt focused) ---
        cluster_prompt = (
            f"Below are {len(contradictions)} descriptions of individual reviewer corrections.\n\n"
            f"{reasons_text}\n\n"
            f"Group these into at most {num_topics} semantically distinct topic clusters.\n"
            "Merge items that describe the same specific agent behavior into one cluster. "
            "But keep genuinely different behaviors in separate clusters — for example:\n"
            "  - high-pressure enrollment tactics\n"
            "  - copay amount guarantees\n"
            "  - claiming medications are free\n"
            "  - acceptable language incorrectly flagged as a violation\n"
            "  - reviewer score inconsistency\n"
            "  - delivery timeline claims\n"
            "...should each be their OWN cluster, not merged together.\n"
            "Single-item clusters are fine if the behavior is genuinely distinct.\n\n"
            "Assign each item a short topic label (3-7 words) that names the policy concern — either the guideline being contradicted or the unaddressed agent behavior. "
            "Reply ONLY with a JSON object mapping item number (as string) to topic label. "
            f"The JSON must have exactly {len(contradictions)} keys (one per item).\n"
            "Example: {{\"1\": \"Free medication claims\", \"2\": \"Free medication claims\", \"3\": \"High-pressure enrollment tactics\"}}"
        )

        try:
            topic_map: Dict[str, str] = await asyncio.to_thread(self._call_bedrock_for_topics, cluster_prompt, model_id="us.anthropic.claude-sonnet-4-6")
            # Unwrap if LLM returned {assignments: {...}} shape
            if "assignments" in topic_map:
                topic_map = topic_map["assignments"]
        except Exception as exc:
            self._log(f"Topic clustering LLM call failed: {exc}", level="WARNING")
            topic_map = {str(i + 1): "Unclustered" for i in range(len(contradictions))}

        # Group contradictions by label
        label_to_items: Dict[str, List[Dict[str, Any]]] = {}
        for i, contradiction in enumerate(contradictions):
            label = topic_map.get(str(i + 1), "Other")
            label_to_items.setdefault(label, []).append(contradiction)

        # --- Pass 2: generate summary + guideline quote per cluster ---
        summary_map: Dict[str, str] = {}
        guideline_quote_map: Dict[str, str] = {}
        if guidelines and label_to_items:
            cluster_descriptions = "\n".join(
                f"- {label}: {'; '.join(it['reason'][:120] for it in items[:3])}"
                for label, items in label_to_items.items()
            )
            enrich_prompt = (
                "Below are topic clusters from a feedback contradictions report. Each cluster "
                "groups feedback items where reviewer corrections appear to conflict with the "
                "score guidelines, or where reviewer comments flag agent behaviors not covered "
                "by the guidelines.\n\n"
                f"Score Guidelines:\n{guidelines[:4000]}\n\n"
                f"Topic clusters:\n{cluster_descriptions}\n\n"
                "For each cluster label, provide:\n"
                "  1. summary: A one-sentence description of the POLICY issue — what guideline "
                "is being contradicted or what policy gap exists. Focus on the implication for "
                "the guidelines, NOT on what reviewers did.\n"
                "  2. guideline_quote: The exact short phrase from the guidelines that is "
                'contradicted, or "Policy gap: not addressed in guidelines" if the behavior '
                "is absent from the guidelines entirely.\n"
                "Reply ONLY with a JSON object with two keys:\n"
                '  "summaries": object mapping topic label to one-sentence policy-focused summary\n'
                '  "guideline_quotes": object mapping topic label to guideline phrase or policy gap note\n'
            )
            try:
                enrich_result = await asyncio.to_thread(self._call_bedrock_for_topics, enrich_prompt)
                summary_map = enrich_result.get("summaries", {})
                guideline_quote_map = enrich_result.get("guideline_quotes", {})
            except Exception as exc:
                self._log(f"Topic enrichment LLM call failed: {exc}", level="WARNING")

        # Build sorted topic list (most common first); exemplars sorted newest-first
        topics = []
        for label, items in sorted(label_to_items.items(), key=lambda kv: -len(kv[1])):
            sorted_items = sorted(
                items,
                key=lambda x: x.get("edited_at") or "",
                reverse=True,
            )
            topics.append({
                "label": label,
                "summary": summary_map.get(label, ""),
                "guideline_quote": guideline_quote_map.get(label, ""),
                "count": len(sorted_items),
                "exemplars": sorted_items,
            })

        return topics

    def _call_bedrock_for_topics(self, prompt: str, model_id: str = "us.anthropic.claude-sonnet-4-6") -> Dict:
        """Synchronous Bedrock call for topic labeling — runs in a thread."""
        import boto3
        import re
        bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "temperature": 0,
            "messages": [{"role": "user", "content": prompt}],
        })
        response = bedrock.invoke_model(
            modelId=model_id,
            body=body,
            contentType="application/json",
            accept="application/json",
        )
        raw = json.loads(response["body"].read())
        text = raw["content"][0]["text"].strip()

        # Strip markdown fences
        if "```" in text:
            match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
            if match:
                text = match.group(1).strip()

        # Extract just the JSON object if there's surrounding prose
        obj_match = re.search(r"\{[\s\S]*\}", text)
        if obj_match:
            text = obj_match.group(0)

        return json.loads(text)

    # --------------------------------------------------------------------------
    # Helpers
    # --------------------------------------------------------------------------

    def _get_account_id(self) -> str:
        account_id = self.params.get("account_id")
        if not account_id and hasattr(self.api_client, "context") and self.api_client.context:
            account_id = self.api_client.context.account_id
        if not account_id:
            raise ValueError("Could not determine account_id.")
        return account_id
