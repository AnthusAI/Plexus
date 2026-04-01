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
        self.log_messages = []
        try:
            return await self._run()
        except Exception as exc:
            import traceback
            self._log(f"ERROR: {exc}", level="ERROR")
            self._log(traceback.format_exc())
            error_data = {"error": str(exc), "topics": []}
            return error_data, "\n".join(self.log_messages)

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
            }, "\n".join(self.log_messages)

        # --- Per-item LLM contradiction analysis ---
        self._log(f"Running contradiction analysis (max_concurrent={max_concurrent})…")
        contradictions = await self._analyze_items(valid_items, guidelines, max_concurrent)
        self._log(f"Contradictions found: {len(contradictions)} / {len(valid_items)}")

        # --- Topic clustering ---
        topics: List[Dict[str, Any]] = []
        if contradictions:
            self._log(f"Clustering {len(contradictions)} contradictions into up to {num_topics} topics…")
            topics = await self._cluster_topics(contradictions, num_topics)
            self._log(f"Produced {len(topics)} topic clusters.")

        output = {
            "score_name": score_obj.name,
            "total_items_analyzed": len(valid_items),
            "contradictions_found": len(contradictions),
            "topics": topics,
        }
        return output, "\n".join(self.log_messages)

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

    async def _analyze_items(
        self,
        items: List[Any],
        guidelines: Optional[str],
        max_concurrent: int,
    ) -> List[Dict[str, Any]]:
        """Return a list of contradiction dicts for items that contradict guidelines."""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def analyze_one(item) -> Optional[Dict[str, Any]]:
            async with semaphore:
                return await asyncio.to_thread(
                    self._check_contradiction, item, guidelines
                )

        results = await asyncio.gather(*[analyze_one(it) for it in items])
        return [r for r in results if r is not None]

    def _check_contradiction(self, item: Any, guidelines: Optional[str]) -> Optional[Dict[str, Any]]:
        """
        Call Bedrock Haiku to decide whether this feedback item contradicts
        the score guidelines.  Returns a contradiction dict or None.
        """
        try:
            import boto3

            initial = getattr(item, "initialAnswerValue", "") or ""
            final = getattr(item, "finalAnswerValue", "") or ""
            edit_comment = getattr(item, "editCommentValue", "") or ""

            # Skip items where nothing actually changed or comment is missing
            if initial == final and not edit_comment:
                return None

            guideline_section = ""
            if guidelines:
                # Truncate to keep prompt manageable
                guideline_section = f"\n\nScore Guidelines:\n{guidelines[:3000]}"

            prompt = (
                f"A quality reviewer corrected a score prediction. "
                f"The score changed from '{initial}' to '{final}'. "
                f"Reviewer comment: \"{edit_comment}\""
                f"{guideline_section}\n\n"
                "Does this reviewer correction appear to CONTRADICT or be INCONSISTENT with the guidelines above? "
                "Reply with a JSON object with three keys:\n"
                "  \"contradicts\": true or false\n"
                "  \"reason\": one sentence explaining why it contradicts, or \"Consistent\" if it does not\n"
                "  \"guideline_quote\": the exact short phrase or sentence from the guidelines that the reviewer correction contradicts (empty string if not contradicting)\n"
                "Reply ONLY with valid JSON, no other text."
            )

            bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 200,
                "messages": [{"role": "user", "content": prompt}],
            })
            response = bedrock.invoke_model(
                modelId="anthropic.claude-3-haiku-20240307-v1:0",
                body=body,
                contentType="application/json",
                accept="application/json",
            )
            raw = json.loads(response["body"].read())
            text = raw["content"][0]["text"].strip()

            # Strip markdown code fences if present
            if "```" in text:
                import re as _re
                m = _re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
                if m:
                    text = m.group(1).strip()

            # Extract JSON object even if surrounded by prose
            import re as _re
            obj_m = _re.search(r"\{[\s\S]*\}", text)
            if obj_m:
                text = obj_m.group(0)

            parsed = json.loads(text)
            if not parsed.get("contradicts"):
                return None

            edited_at = getattr(item, "editedAt", None)
            if hasattr(edited_at, "isoformat"):
                edited_at = edited_at.isoformat()

            return {
                "feedback_item_id": item.id,
                "item_id": getattr(item, "itemId", None),
                "initial_value": initial,
                "final_value": final,
                "edit_comment": edit_comment,
                "editor_name": getattr(item, "editorName", None),
                "edited_at": edited_at,
                "reason": parsed.get("reason", ""),
                "guideline_quote": parsed.get("guideline_quote", ""),
                "is_invalid": getattr(item, "isInvalid", False) or False,
            }
        except Exception as exc:
            logger.debug(f"Contradiction check failed for item {getattr(item, 'id', '?')}: {exc}")
            return None

    # --------------------------------------------------------------------------
    # Topic clustering
    # --------------------------------------------------------------------------

    async def _cluster_topics(
        self, contradictions: List[Dict[str, Any]], num_topics: int
    ) -> List[Dict[str, Any]]:
        """
        Group contradictions into semantic topic clusters using a single LLM call.

        Each contradiction's 'reason' string is sent to the LLM with instructions
        to assign a short topic label.  Results are grouped and sorted by count.
        """
        # Build a numbered list of reason strings
        reasons_text = "\n".join(
            f"{i + 1}. {c['reason']}" for i, c in enumerate(contradictions)
        )

        prompt = (
            f"Below are {len(contradictions)} short descriptions of reviewer corrections that contradict score guidelines.\n\n"
            f"{reasons_text}\n\n"
            f"Group these into at most {num_topics} semantic topic clusters. "
            "For each item number assign a short topic label (3-6 words). "
            "Reply ONLY with a JSON object mapping item number (as a string) to topic label. "
            "Example: {{\"1\": \"Copay guarantee language\", \"2\": \"Copay guarantee language\", \"3\": \"Qualifying insurance not mentioned\"}}"
        )

        try:
            topic_map = await asyncio.to_thread(self._call_bedrock_for_topics, prompt)
        except Exception as exc:
            self._log(f"Topic clustering LLM call failed: {exc}", level="WARNING")
            # Fall back: each contradiction is its own topic
            topic_map = {str(i + 1): "Unclustered" for i in range(len(contradictions))}

        # Group contradictions by label
        label_to_items: Dict[str, List[Dict[str, Any]]] = {}
        for i, contradiction in enumerate(contradictions):
            label = topic_map.get(str(i + 1), "Other")
            label_to_items.setdefault(label, []).append(contradiction)

        # Build sorted topic list (most common first), keep up to 3 exemplars per topic
        topics = []
        for label, items in sorted(label_to_items.items(), key=lambda kv: -len(kv[1])):
            topics.append({
                "label": label,
                "count": len(items),
                "exemplars": items[:3],
            })

        return topics

    def _call_bedrock_for_topics(self, prompt: str) -> Dict[str, str]:
        """Synchronous Bedrock call for topic labeling — runs in a thread."""
        import boto3
        import re
        bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 2048,
            "messages": [{"role": "user", "content": prompt}],
        })
        response = bedrock.invoke_model(
            modelId="anthropic.claude-3-haiku-20240307-v1:0",
            body=body,
            contentType="application/json",
            accept="application/json",
        )
        raw = json.loads(response["body"].read())
        text = raw["content"][0]["text"].strip()

        # Strip markdown fences
        if "```" in text:
            # Extract content between first ``` pair
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
