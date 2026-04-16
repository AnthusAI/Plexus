"""
FeedbackContradictions report block.

Analyzes feedback items for a score against published guidelines using a shared
multi-model voting engine. Supports two modes:
- contradictions: focus on contradictions/policy gaps
- aligned: focus on non-contradicting vetted items
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from .base import BaseReportBlock
from . import feedback_utils
from .guideline_vetting import GuidelineVettingService
from plexus.dashboard.api.models.score import Score
from plexus.dashboard.api.models.scorecard import Scorecard

logger = logging.getLogger(__name__)


class FeedbackContradictions(BaseReportBlock):
    """Guideline-vetting report block with contradiction and aligned modes."""

    DEFAULT_NAME = "Feedback Contradictions"
    DEFAULT_DESCRIPTION = "Guideline Contradiction Analysis"

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

    async def _run(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        scorecard_param = self.config.get("scorecard")
        score_param = self.config.get("score") or self.config.get("score_id")
        if not scorecard_param:
            raise ValueError("'scorecard' is required in block configuration.")
        if not score_param:
            raise ValueError("'score' is required in block configuration.")

        mode = str(self.config.get("mode", "contradictions")).strip().lower()
        if mode not in {"contradictions", "aligned"}:
            raise ValueError("'mode' must be either 'contradictions' or 'aligned'.")

        days = int(self.config.get("days", 360))
        start_date_str = self.config.get("start_date")
        end_date_str = self.config.get("end_date")
        max_concurrent = int(self.config.get("max_concurrent", 20))
        max_feedback_items = int(self.config.get("max_feedback_items", 400))
        num_topics = int(self.config.get("num_topics", 8))
        if max_feedback_items < 0:
            raise ValueError("'max_feedback_items' must be >= 0.")

        if start_date_str:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        else:
            start_date = datetime.now(tz=timezone.utc) - timedelta(days=days)

        if end_date_str:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").replace(
                hour=23,
                minute=59,
                second=59,
                microsecond=999999,
                tzinfo=timezone.utc,
            )
        else:
            end_date = datetime.now(tz=timezone.utc).replace(
                hour=23,
                minute=59,
                second=59,
                microsecond=999999,
            )

        self._log(f"Date range: {start_date.date()} to {end_date.date()}")
        self._log(f"Mode: {mode}")

        self._log(f"Resolving scorecard: {scorecard_param}")
        scorecard_obj = await self._resolve_scorecard(str(scorecard_param))
        if not scorecard_obj:
            raise ValueError(f"Scorecard not found: {scorecard_param}")
        self._log(f"Scorecard: '{scorecard_obj.name}' ({scorecard_obj.id})")

        self._log(f"Resolving score: {score_param}")
        score_obj = await self._resolve_score(str(score_param), scorecard_obj.id)
        if not score_obj:
            raise ValueError(f"Score not found: {score_param}")
        self._log(f"Score: '{score_obj.name}' ({score_obj.id})")

        guidelines = await self._fetch_guidelines(score_obj.id)
        if guidelines:
            line_count = guidelines.count("\n") + 1
            self._log(f"Loaded guidelines ({len(guidelines)} chars, {line_count} lines)")
        else:
            self._log(
                "WARNING: No guidelines found for this score - contradiction detection will be limited.",
                level="WARNING",
            )

        account_id = self._get_account_id()
        self._log(f"Fetching feedback items for score {score_obj.id}...")
        all_items = await feedback_utils.fetch_feedback_items_for_score(
            self.api_client,
            account_id,
            scorecard_obj.id,
            score_obj.id,
            start_date,
            end_date,
            max_feedback_items if max_feedback_items > 0 else None,
        )

        # Group all records by itemId first, then apply invalid + deduplication together.
        # If ANY record for an itemId is marked invalid, the whole item is excluded.
        # Among non-invalid records, keep only the most recent per itemId.
        groups: dict[str, list[Any]] = {}
        no_item_id: list[Any] = []
        for item in all_items:
            item_id = getattr(item, "itemId", None)
            if not item_id:
                no_item_id.append(item)
            else:
                groups.setdefault(item_id, []).append(item)

        invalid_count = 0
        duplicate_count = 0
        valid_items = []
        for item_id, group in groups.items():
            if any(getattr(i, "isInvalid", False) for i in group):
                invalid_count += len(group)
                continue
            best = max(group, key=lambda i: getattr(i, "editedAt", None) or "")
            duplicate_count += len(group) - 1
            valid_items.append(best)
        # Items with no itemId: apply only the isInvalid filter, no deduplication possible.
        for item in no_item_id:
            if getattr(item, "isInvalid", False):
                invalid_count += 1
            else:
                valid_items.append(item)

        self._log(
            f"Fetched {len(all_items)} feedback items; {len(valid_items)} eligible "
            f"({invalid_count} excluded as already-invalid, {duplicate_count} duplicate item IDs removed)."
        )
        if max_feedback_items > 0 and len(valid_items) > max_feedback_items:
            valid_items = valid_items[:max_feedback_items]
            self._log(
                f"Capped eligible feedback items to newest {len(valid_items)} via max_feedback_items={max_feedback_items}."
            )

        if not valid_items:
            base_output: Dict[str, Any] = {
                "mode": mode,
                "score_name": score_obj.name,
                "total_items_analyzed": 0,
                "items_vetted": 0,
                "contradictions_found": 0,
                "aligned_found": 0,
                "selected_items_count": 0,
                "topics": [],
            }
            if mode == "aligned":
                base_output.update(
                    {
                        "eligible_associated_feedback_item_ids": [],
                        "eligible_count": 0,
                        "eligibility_rule": "unanimous non-contradiction",
                        "source_report_block_id": self.report_block_id,
                    }
                )
            return base_output, "\n".join(self._orm.log_messages)

        self._log(f"Fetching score results for {len(valid_items)} items...")
        item_ids = [getattr(item, "itemId", None) for item in valid_items]
        item_ids = [item_id for item_id in item_ids if item_id]
        score_results_by_item = await self._fetch_score_results_by_item_ids(item_ids, score_obj.id)
        self._log(
            f"Loaded {len(score_results_by_item)} score results ({len(score_results_by_item)}/{len(item_ids)} items have explanations)."
        )

        self._log(f"Running guideline-vetting analysis (max_concurrent={max_concurrent})...")
        vetting_service = GuidelineVettingService()
        analyzed_items = await vetting_service.analyze_items(
            valid_items,
            guidelines,
            max_concurrent,
            score_results_by_item,
        )

        contradictions = [item for item in analyzed_items if item.get("verdict") == "contradiction"]
        aligned_items = [item for item in analyzed_items if item.get("verdict") == "aligned"]

        all_votes = [vote for item in analyzed_items for vote in (item.get("voting") or [])]
        yes_votes = sum(1 for vote in all_votes if vote.get("result") is True)
        no_votes = sum(1 for vote in all_votes if vote.get("result") is False)
        null_votes = sum(1 for vote in all_votes if vote.get("result") is None)

        self._log(
            f"Vetting complete: {len(analyzed_items)} analyzed, "
            f"{len(contradictions)} contradictions, {len(aligned_items)} aligned "
            f"(votes: {yes_votes} yes / {no_votes} no / {null_votes} failed)"
        )

        selected_items = contradictions if mode == "contradictions" else aligned_items
        topics: List[Dict[str, Any]] = []
        if selected_items:
            self._log(f"Clustering {len(selected_items)} {mode} items into up to {num_topics} topics...")
            topics = await self._cluster_topics(selected_items, num_topics, guidelines, mode=mode)
            self._log(f"Produced {len(topics)} topic clusters.")

        output: Dict[str, Any] = {
            "mode": mode,
            "score_name": score_obj.name,
            "total_items_analyzed": len(valid_items),
            "items_vetted": len(analyzed_items),
            "contradictions_found": len(contradictions),
            "aligned_found": len(aligned_items),
            "selected_items_count": len(selected_items),
            "guidelines": guidelines,
            "topics": topics,
            "block_configuration": {
                "scorecard": scorecard_param,
                "score": score_param,
                "mode": mode,
                "days": days,
                "max_feedback_items": max_feedback_items if max_feedback_items > 0 else None,
                "max_concurrent": max_concurrent,
                "num_topics": num_topics,
            },
        }

        if mode == "aligned":
            eligible_items = [
                {
                    "feedback_item_id": item["feedback_item_id"],
                    "edited_at": item.get("edited_at"),
                    "final_value": item.get("final_value"),
                }
                for item in aligned_items
                if item.get("associated_dataset_eligible") is True and item.get("feedback_item_id")
            ]
            # Deterministic order: newest first by edited_at, tie-break by feedback_item_id.
            eligible_items.sort(key=lambda row: str(row["feedback_item_id"] or ""))
            eligible_items.sort(key=lambda row: str(row.get("edited_at") or ""), reverse=True)
            eligible_ids = [item["feedback_item_id"] for item in eligible_items]
            output.update(
                {
                    "eligible_associated_feedback_item_ids": eligible_ids,
                    "eligible_associated_feedback_items": eligible_items,
                    "eligible_count": len(eligible_ids),
                    "eligibility_rule": "unanimous non-contradiction",
                    "source_report_block_id": self.report_block_id,
                }
            )

        context_header = (
            "# Feedback Guideline-Vetting Report Output\n"
            "#\n"
            "# This report evaluates feedback items against score guidelines using shared\n"
            "# multi-model voting (Sonnet + GPT-5.4 with optional tiebreakers).\n"
            "#\n"
            "# Modes:\n"
            "#   - contradictions: contradictions/policy gaps\n"
            "#   - aligned: non-contradicting vetted items\n"
            "#\n"
            "# Key fields:\n"
            "#   mode, score_name, total_items_analyzed, items_vetted\n"
            "#   contradictions_found, aligned_found, selected_items_count\n"
            "#   topics[*].exemplars[*].voting/confidence/verdict/associated_dataset_eligible\n"
            "#   aligned mode also includes eligible_associated_feedback_item_ids payload\n"
            "\n"
        )
        formatted_output = context_header + json.dumps(output, indent=2, ensure_ascii=False)
        return formatted_output, "\n".join(self._orm.log_messages)

    async def _resolve_scorecard(self, scorecard_param: str) -> Optional[Any]:
        """Resolve a scorecard by ID, key, name, or externalId using existing model methods."""
        is_uuid = len(scorecard_param) > 20 and "-" in scorecard_param
        for lookup in (
            [lambda p: asyncio.to_thread(Scorecard.get_by_id, id=p, client=self.api_client)]
            if is_uuid
            else [
                lambda p: asyncio.to_thread(Scorecard.list_by_key, key=p, client=self.api_client),
                lambda p: asyncio.to_thread(Scorecard.list_by_name, name=p, client=self.api_client),
                lambda p: asyncio.to_thread(Scorecard.list_by_external_id, external_id=p, client=self.api_client),
            ]
        ):
            try:
                result = await lookup(scorecard_param)
                if result:
                    return result
            except Exception as exc:  # lookup method not supported or lookup failed; try next
                logger.debug("Scorecard lookup failed for %r: %s", scorecard_param, exc)
        return None

    async def _resolve_score(self, score_param: str, scorecard_id: str) -> Optional[Any]:
        """Resolve a score by ID, name, key, or externalId using existing model methods."""
        is_uuid_like = (
            len(score_param) == 36
            and score_param.count("-") == 4
            and all(char in "0123456789abcdefABCDEF-" for char in score_param)
        )
        if is_uuid_like:
            try:
                score_obj = await asyncio.to_thread(Score.get_by_id, id=score_param, client=self.api_client)
                scorecard_link = getattr(score_obj, "scorecardId", None) or getattr(score_obj, "scorecard_id", None)
                if score_obj and scorecard_link == scorecard_id:
                    return score_obj
            except Exception as exc:  # ID lookup failed; fall through to name/key lookups
                logger.debug("Score UUID lookup failed for %r: %s", score_param, exc)

        for lookup in [
            lambda p: asyncio.to_thread(Score.get_by_name, name=p, scorecard_id=scorecard_id, client=self.api_client),
            lambda p: asyncio.to_thread(Score.get_by_key, key=p, scorecard_id=scorecard_id, client=self.api_client),
            lambda p: asyncio.to_thread(Score.get_by_external_id, external_id=p, scorecard_id=scorecard_id, client=self.api_client),
        ]:
            try:
                result = await lookup(score_param)
                if result:
                    return result
            except Exception as exc:  # lookup method not supported or lookup failed; try next
                logger.debug("Score lookup failed for %r: %s", score_param, exc)

        return None

    async def _fetch_guidelines(self, score_id: str) -> Optional[str]:
        try:
            score_result = await asyncio.to_thread(
                self.api_client.execute,
                """
                query GetScoreChampion($id: ID!) {
                    getScore(id: $id) {
                        championVersionId
                    }
                }
                """,
                {"id": score_id},
            )
            champion_id = (score_result or {}).get("getScore", {}).get("championVersionId")
            if not champion_id:
                return None

            version_result = await asyncio.to_thread(
                self.api_client.execute,
                """
                query GetScoreVersion($id: ID!) {
                    getScoreVersion(id: $id) {
                        guidelines
                        configuration
                    }
                }
                """,
                {"id": champion_id},
            )
            score_version = (version_result or {}).get("getScoreVersion", {})
            return score_version.get("guidelines") or score_version.get("configuration") or None
        except Exception as exc:
            self._log(f"Could not fetch guidelines: {exc}", level="WARNING")
            return None

    async def _fetch_score_results_by_item_ids(self, item_ids: List[str], score_id: str) -> Dict[str, Any]:
        query = """
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
        semaphore = asyncio.Semaphore(20)

        async def fetch_one(item_id: str):
            async with semaphore:
                try:
                    result = await asyncio.to_thread(
                        self.api_client.execute,
                        query,
                        {"itemId": item_id, "scoreId": score_id},
                    )
                    score_results = (result or {}).get("listScoreResultByItemId", {}).get("items") or []
                    return item_id, score_results[0] if score_results else None
                except Exception as exc:
                    logger.warning("score result fetch failed for item %s: %s", item_id, exc)
                    return item_id, None

        results = await asyncio.gather(*[fetch_one(item_id) for item_id in item_ids])
        return {item_id: score_result for item_id, score_result in results if score_result is not None}

    async def _cluster_topics(
        self,
        items: List[Dict[str, Any]],
        num_topics: int,
        guidelines: Optional[str] = None,
        mode: str = "contradictions",
    ) -> List[Dict[str, Any]]:
        # For large item sets, sample before clustering to avoid LLM producing
        # near-unique labels (which happens when it gets hundreds of items).
        # Sample evenly across the sorted list to maintain temporal diversity.
        MAX_CLUSTERING_SAMPLE = 40
        if len(items) > MAX_CLUSTERING_SAMPLE:
            step = len(items) / MAX_CLUSTERING_SAMPLE
            sample_items = [items[int(i * step)] for i in range(MAX_CLUSTERING_SAMPLE)]
            self._log(f"Sampling {MAX_CLUSTERING_SAMPLE} of {len(items)} items for topic clustering.")
        else:
            sample_items = items

        reasons_text = "\n".join(f"{index + 1}. {item['reason']}" for index, item in enumerate(sample_items))

        if mode == "aligned":
            cluster_prompt = (
                f"Below are {len(sample_items)} descriptions from vetted feedback items that are aligned with the guidelines.\n\n"
                f"{reasons_text}\n\n"
                f"Group these into exactly {num_topics} semantically distinct topic clusters.\n"
                "Every item must get one of the {num_topics} topic labels — do not create more.\n"
                "Use short labels (3-7 words) describing the behavior/policy area being affirmed. "
                "Reply ONLY with JSON mapping item number (string) to topic label. "
                f"The JSON must include exactly {len(sample_items)} keys."
            )
        else:
            cluster_prompt = (
                f"Below are {len(sample_items)} descriptions of individual reviewer corrections.\n\n"
                f"{reasons_text}\n\n"
                f"Group these into exactly {num_topics} semantically distinct topic clusters.\n"
                f"You MUST use exactly {num_topics} distinct labels — no more, no fewer.\n"
                "Aggressively merge items that describe the same or closely related policy concern. "
                "Assign each item a short topic label (3-7 words) naming the policy concern. "
                "Reply ONLY with JSON mapping item number (string) to topic label. "
                f"The JSON must include exactly {len(sample_items)} keys."
            )

        try:
            topic_map: Dict[str, str] = await asyncio.to_thread(self._call_bedrock_for_topics, cluster_prompt)
            if isinstance(topic_map, dict) and "assignments" in topic_map:
                topic_map = topic_map["assignments"]
            if not isinstance(topic_map, dict):
                raise ValueError(f"Expected dict from topic clustering LLM, got {type(topic_map).__name__}")
        except Exception as exc:
            self._log(f"Topic clustering LLM call failed: {exc}", level="WARNING")
            topic_map = {str(index + 1): "Unclustered" for index in range(len(sample_items))}

        label_to_items: Dict[str, List[Dict[str, Any]]] = {}
        # Assign sample items using the LLM topic_map
        for index, item in enumerate(sample_items):
            label = topic_map.get(str(index + 1), "Other")
            label_to_items.setdefault(label, []).append(item)

        # For non-sample items, assign to the topic whose label has the most word
        # overlap with the item's reason text. This keeps counts accurate without
        # another LLM call.
        if len(items) > len(sample_items):
            sample_id_set = set(id(item) for item in sample_items)
            known_labels = list(label_to_items.keys())
            label_word_sets = {
                label: set(label.lower().split()) for label in known_labels
            }
            for item in items:
                if id(item) in sample_id_set:
                    continue
                reason_words = set(item.get("reason", "").lower().split())
                best_label = max(
                    known_labels,
                    key=lambda lbl: len(label_word_sets[lbl] & reason_words),
                    default=known_labels[0] if known_labels else "Other",
                )
                label_to_items[best_label].append(item)

        summary_map: Dict[str, str] = {}
        guideline_quote_map: Dict[str, str] = {}
        if guidelines and label_to_items:
            cluster_descriptions = "\n".join(
                f"- {label}: {'; '.join(i['reason'][:120] for i in label_items[:3])}"
                for label, label_items in label_to_items.items()
            )

            if mode == "aligned":
                enrich_prompt = (
                    "Below are topic clusters from aligned feedback items that are consistent with the score guidelines.\n\n"
                    f"Score Guidelines:\n{guidelines[:4000]}\n\n"
                    f"Topic clusters:\n{cluster_descriptions}\n\n"
                    "For each cluster label, provide:\n"
                    "  1. summary: one sentence describing the behavior/policy alignment\n"
                    "  2. guideline_quote: exact short phrase from guidelines supporting that alignment\n"
                    "Reply ONLY with JSON object with keys 'summaries' and 'guideline_quotes'."
                )
            else:
                enrich_prompt = (
                    "Below are topic clusters from a feedback contradictions report. Each cluster "
                    "groups feedback items where reviewer corrections appear to conflict with the "
                    "score guidelines, or where reviewer comments flag agent behaviors not covered "
                    "by the guidelines.\n\n"
                    f"Score Guidelines:\n{guidelines[:4000]}\n\n"
                    f"Topic clusters:\n{cluster_descriptions}\n\n"
                    "For each cluster label, provide:\n"
                    "  1. summary: one sentence describing the policy issue\n"
                    "  2. guideline_quote: exact short phrase contradicted, or policy-gap note\n"
                    "Reply ONLY with JSON object with keys 'summaries' and 'guideline_quotes'."
                )

            try:
                enrich_result = await asyncio.to_thread(self._call_bedrock_for_topics, enrich_prompt)
                if not isinstance(enrich_result, dict):
                    raise ValueError(f"Expected dict from topic enrichment LLM, got {type(enrich_result).__name__}")
                raw_summaries = enrich_result.get("summaries", {})
                raw_quotes = enrich_result.get("guideline_quotes", {})
                if not isinstance(raw_summaries, dict):
                    raise ValueError(f"Expected dict for 'summaries', got {type(raw_summaries).__name__}")
                if not isinstance(raw_quotes, dict):
                    raise ValueError(f"Expected dict for 'guideline_quotes', got {type(raw_quotes).__name__}")
                summary_map = raw_summaries
                guideline_quote_map = raw_quotes
            except Exception as exc:
                self._log(f"Topic enrichment LLM call failed: {exc}", level="WARNING")

        topics: List[Dict[str, Any]] = []
        for label, label_items in sorted(label_to_items.items(), key=lambda pair: -len(pair[1])):
            sorted_items = sorted(label_items, key=lambda item: item.get("edited_at") or "", reverse=True)
            topics.append(
                {
                    "label": label,
                    "summary": summary_map.get(label, ""),
                    "guideline_quote": guideline_quote_map.get(label, ""),
                    "count": len(sorted_items),
                    "exemplars": sorted_items,
                }
            )

        return topics

    def _call_bedrock_for_topics(
        self,
        prompt: str,
        model_id: str = "us.anthropic.claude-sonnet-4-6",
    ) -> Dict[str, Any]:
        import boto3
        import re

        bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
        body = json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4096,
                "temperature": 0,
                "messages": [{"role": "user", "content": prompt}],
            }
        )
        response = bedrock.invoke_model(
            modelId=model_id,
            body=body,
            contentType="application/json",
            accept="application/json",
        )
        raw = json.loads(response["body"].read())
        text = raw["content"][0]["text"].strip()

        if "```" in text:
            match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
            if match:
                text = match.group(1).strip()

        obj_match = re.search(r"\{[\s\S]*\}", text)
        if obj_match:
            text = obj_match.group(0)

        return json.loads(text)

    def _get_account_id(self) -> str:
        account_id = self.params.get("account_id")
        if not account_id and hasattr(self.api_client, "context") and self.api_client.context:
            account_id = self.api_client.context.account_id
        if not account_id:
            raise ValueError("Could not determine account_id.")
        return account_id
