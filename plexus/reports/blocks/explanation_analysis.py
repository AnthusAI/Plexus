from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from plexus.dashboard.api.models.score import Score
from plexus.dashboard.api.models.scorecard import Scorecard

from . import feedback_utils
from .feedback_analysis import FeedbackAnalysis
from .reinforcement_helpers import (
    fetch_item_identifiers,
    is_normal_prediction_score_result,
    parse_iso_timestamp,
)

logger = logging.getLogger(__name__)


class ExplanationAnalysis(FeedbackAnalysis):
    """
    Semantic reinforcement-memory analysis over normal production
    ScoreResult explanations.

    This is intentionally a separate report block from FeedbackAnalysis.
    """

    DEFAULT_NAME = "Explanation Analysis"
    DEFAULT_DESCRIPTION = "Semantic reinforcement-memory analysis over ScoreResult explanations"

    async def generate(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        self.log_messages = []
        final_output_data = None

        try:
            self._log("Starting ExplanationAnalysis block generation.")
            self._log(f"Config keys: {list(self.config.keys())}")

            scorecard_param = self.config.get("scorecard")
            if not scorecard_param:
                self._log("ERROR: 'scorecard' missing in block configuration.", level="ERROR")
                raise ValueError("'scorecard' is required in the block configuration.")

            final_output_data = await self._generate_single_scorecard_analysis(scorecard_param)
            return final_output_data, "\n".join(self.log_messages)
        except ValueError as ve:
            self._log(f"Configuration or Value Error: {ve}")
            final_output_data = {"type": "ExplanationAnalysis", "status": "error", "error": str(ve), "scores": []}
            return final_output_data, "\n".join(self.log_messages)
        except Exception as e:
            self._log(f"ERROR during ExplanationAnalysis generation: {str(e)}", level="ERROR")
            import traceback
            self._log(traceback.format_exc(), level="DEBUG")
            final_output_data = {"type": "ExplanationAnalysis", "status": "error", "error": str(e), "scores": []}
            return final_output_data, "\n".join(self.log_messages)

    async def _generate_single_scorecard_analysis(
        self,
        scorecard_param: str,
        skip_indexed_items: bool = False,
    ) -> Dict[str, Any]:
        del skip_indexed_items
        days = int(self.config.get("days", 14))
        start_date_str = self.config.get("start_date")
        end_date_str = self.config.get("end_date")
        score_id_param = (
            self.config.get("score_id")
            or self.config.get("score")
            or self.params.get("score_id")
            or self.params.get("score")
            or self.params.get("param_score_id")
            or self.params.get("param_score")
        )
        if score_id_param is not None:
            raw_score_id = str(score_id_param).strip()
            score_id_param = None if not raw_score_id or raw_score_id.lower() == "none" else raw_score_id

        if start_date_str:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        else:
            start_date = datetime.now() - timedelta(days=days)
        start_date = start_date.replace(tzinfo=timezone.utc)

        if end_date_str:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
        else:
            end_date = datetime.now()
        end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=timezone.utc)

        account_id = self._resolve_account_id()
        if not account_id:
            raise ValueError("account_id required for ScoreResult explanation analysis")

        plexus_scorecard = await self._resolve_scorecard(scorecard_param)
        scores_to_process = await self._resolve_scores_to_process(plexus_scorecard, score_id_param)

        if not scores_to_process:
            return {
                "type": "ExplanationAnalysis",
                "status": "ok",
                "scorecard_id": plexus_scorecard.id,
                "scorecard_name": plexus_scorecard.name,
                "date_range": {"start": start_date.isoformat(), "end": end_date.isoformat()},
                "scores": [],
                "items_processed": 0,
                "summary": "No scores available for explanation analysis.",
            }

        per_score_raw_texts: List[Dict[str, Any]] = []
        total_score_results_retrieved = 0
        total_explanations_retained = 0

        for score_info in scores_to_process:
            self._log(
                f"--- Processing ScoreResult explanations for score '{score_info['plexus_score_name']}' "
                f"(ID: {score_info['plexus_score_id']}, CC ID: {score_info['cc_question_id']}) ---"
            )
            score_results = await feedback_utils.fetch_score_results_for_score(
                self.api_client,
                account_id,
                plexus_scorecard.id,
                score_info["plexus_score_id"],
                start_date,
                end_date,
            )
            total_score_results_retrieved += len(score_results)

            retained_items = []
            for score_result in score_results:
                if not is_normal_prediction_score_result(score_result):
                    continue

                explanation = score_result.get("explanation") or ""
                if not isinstance(explanation, str):
                    continue
                explanation = explanation.strip()
                if not explanation:
                    continue

                retained_items.append(
                    {
                        "doc_id": score_result.get("id") or f"{score_result.get('itemId')}_{score_result.get('scoreId')}",
                        "score_result_id": score_result.get("id"),
                        "score_id": score_info["plexus_score_id"],
                        "score_name": score_info["plexus_score_name"],
                        "item_id": score_result.get("itemId"),
                        "value": score_result.get("value"),
                        "text": explanation,
                        "explanation": explanation,
                        "timestamp": parse_iso_timestamp(score_result.get("updatedAt") or score_result.get("createdAt")) or end_date,
                        "score_result": score_result,
                    }
                )

            total_explanations_retained += len(retained_items)
            self._log(
                f"Retained {len(retained_items)} production ScoreResult explanations for score "
                f"'{score_info['plexus_score_name']}' (fetched {len(score_results)} records)."
            )

            per_score_raw_texts.append(
                {
                    "score_id": score_info["cc_question_id"] or score_info["plexus_score_id"],
                    "score_name": score_info["plexus_score_name"],
                    "items": retained_items,
                }
            )

        analysis_output = await self._run_explanation_analysis(per_score_raw_texts)
        if not analysis_output:
            return {
                "type": "ExplanationAnalysis",
                "status": "ok",
                "scorecard_id": plexus_scorecard.id,
                "scorecard_name": plexus_scorecard.name,
                "date_range": {"start": start_date.isoformat(), "end": end_date.isoformat()},
                "scores": [],
                "items_processed": total_explanations_retained,
                "total_score_results_retrieved": total_score_results_retrieved,
                "total_explanations_retained": total_explanations_retained,
                "summary": "No topics formed from production ScoreResult explanations.",
            }

        scores = analysis_output.get("scores") or []
        total_topics = sum(len(score.get("topics") or []) for score in scores)
        items_processed = sum(int(score.get("items_processed") or 0) for score in scores)
        output_data: Dict[str, Any] = {
            "type": "ExplanationAnalysis",
            "status": "ok",
            "scorecard_id": plexus_scorecard.id,
            "scorecard_name": plexus_scorecard.name,
            "date_range": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "scores": scores,
            "items_processed": items_processed,
            "total_score_results_retrieved": total_score_results_retrieved,
            "total_explanations_retained": total_explanations_retained,
            "summary": (
                f"Processed {items_processed} production ScoreResult explanations across "
                f"{len(scores)} scores and formed {total_topics} topics."
            ),
        }

        if len(scores) == 1:
            output_data["topics"] = scores[0].get("topics") or []
            output_data["cluster_version"] = scores[0].get("cluster_version")

        self._log(output_data["summary"])
        return output_data

    def _resolve_account_id(self) -> Optional[str]:
        account_id = self.params.get("account_id")
        if not account_id and hasattr(self.api_client, "context") and self.api_client.context:
            account_id = getattr(self.api_client.context, "account_id", None)
        return account_id

    async def _resolve_scorecard(self, scorecard_param: str):
        is_uuid = len(str(scorecard_param)) > 20 and "-" in str(scorecard_param)
        if is_uuid:
            plexus_scorecard = await asyncio.to_thread(
                Scorecard.get_by_id,
                id=str(scorecard_param),
                client=self.api_client,
            )
        else:
            plexus_scorecard = await asyncio.to_thread(
                Scorecard.get_by_external_id,
                external_id=str(scorecard_param),
                client=self.api_client,
            )
        if not plexus_scorecard:
            raise ValueError(f"Scorecard not found: {scorecard_param}")
        self._log(f"Found Plexus Scorecard: '{plexus_scorecard.name}' (ID: {plexus_scorecard.id})")
        return plexus_scorecard

    async def _resolve_scores_to_process(self, plexus_scorecard, score_id_param: Optional[str]) -> List[Dict[str, str]]:
        if not score_id_param:
            scores = await feedback_utils.fetch_scores_for_scorecard(self.api_client, plexus_scorecard.id)
            self._log(f"Identified {len(scores)} score(s) for explanation analysis.")
            return scores

        self._log(f"Looking up specific Plexus Score for identifier: {score_id_param}")
        is_uuid_like = (
            len(score_id_param) == 36
            and score_id_param.count("-") == 4
            and all(c in "0123456789abcdefABCDEF-" for c in score_id_param)
        )
        if is_uuid_like:
            plexus_score = await asyncio.to_thread(
                Score.get_by_id,
                id=score_id_param,
                client=self.api_client,
            )
            if plexus_score and plexus_score.scorecard_id != plexus_scorecard.id:
                plexus_score = None
        else:
            plexus_score = await asyncio.to_thread(
                Score.get_by_external_id,
                external_id=str(score_id_param),
                scorecard_id=plexus_scorecard.id,
                client=self.api_client,
            )

        if not plexus_score:
            self._log(f"WARNING: Plexus Score not found for identifier: {score_id_param}.", level="WARNING")
            return []

        return [
            {
                "plexus_score_id": plexus_score.id,
                "plexus_score_name": plexus_score.name,
                "cc_question_id": str(score_id_param),
            }
        ]

    async def _run_explanation_analysis(self, per_score_raw_texts: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        try:
            import numpy as np
            from datetime import timezone as _tz
            from biblicus.analysis.reinforcement_memory import (
                S3EmbeddingCache,
                sentence_transformer_embedder,
            )
            from biblicus.analysis.reinforcement_memory._clusterer import TopicClusterer
            from biblicus.analysis.reinforcement_memory._lifecycle import derive_lifecycle
            from biblicus.analysis.reinforcement_memory._weights import tier_from_weight

            cache_bucket = self.config.get("memory_cache_bucket", "")
            model_id = self.config.get("memory_model_id", "all-MiniLM-L6-v2")
            min_topic_size = self.config.get("memory_min_topic_size", 5)
            use_llm_labels = self.config.get("memory_llm_labels", True)
            use_causal_inference = self.config.get("memory_causal_inference", True)

            cache = S3EmbeddingCache(bucket_name=cache_bucket) if cache_bucket else None
            embed_fn = sentence_transformer_embedder(model_id=model_id, cache=cache)

            now = datetime.now(_tz.utc)
            scores_out = []

            for score_data in per_score_raw_texts:
                items = score_data.get("items") or []
                texts = [item["text"] for item in items]
                topics = []

                if len(texts) >= 2:
                    self._log(
                        f"ExplanationAnalysis: embedding {len(texts)} explanations for score "
                        f"'{score_data['score_name']}'"
                    )
                    embeddings = np.array(await asyncio.to_thread(embed_fn, texts))
                    clusterer = TopicClusterer(min_topic_size=min(min_topic_size, max(2, len(texts) // 3)))
                    topic_ids, cluster_version = clusterer.cluster(embeddings, texts)
                    topic_ids_arr = np.array(topic_ids)

                    for tid in sorted(set(topic_ids_arr.tolist())):
                        if tid == -1:
                            continue
                        member_count = int(np.sum(topic_ids_arr == tid))
                        keywords = clusterer.get_keywords(int(tid), n=8)
                        exemplars_raw = clusterer.get_representative_exemplars(int(tid), n=3)

                        exemplars = []
                        for ex_idx, ex_text in exemplars_raw:
                            item_record = items[ex_idx]
                            item_id = item_record.get("item_id")
                            identifiers = await fetch_item_identifiers(self.api_client, item_id)
                            exemplar: Dict[str, Any] = {
                                "text": ex_text[:300] + "…" if len(ex_text) > 300 else ex_text,
                                "item_id": item_id,
                            }
                            if identifiers:
                                exemplar["identifiers"] = identifiers

                            if use_causal_inference and item_record.get("score_result_id"):
                                causal_ctx = await self._gather_explanation_causal_context(
                                    explanation_text=ex_text,
                                    score_result_id=item_record["score_result_id"],
                                    raw_score_result=item_record.get("score_result") or {},
                                    item_id=item_id,
                                )
                                if causal_ctx:
                                    exemplar["_causal_context"] = causal_ctx

                            exemplars.append(exemplar)

                        member_indices = list(np.where(topic_ids_arr == tid)[0])
                        cluster_timestamps = [
                            items[i]["timestamp"]
                            for i in member_indices
                            if i < len(items) and items[i].get("timestamp") is not None
                        ]
                        days_inactive: Optional[int] = None
                        if cluster_timestamps:
                            most_recent = max(
                                (ts if ts.tzinfo else ts.replace(tzinfo=_tz.utc) for ts in cluster_timestamps)
                            )
                            days_inactive = max(0, (now - most_recent).days)

                        member_ts_iso = [
                            (ts if ts.tzinfo else ts.replace(tzinfo=_tz.utc)).isoformat()
                            for ts in cluster_timestamps
                        ]
                        lifecycle_tier, is_new, is_trending, _ = derive_lifecycle(member_ts_iso, now=now)
                        weight = 0.5
                        tier = tier_from_weight(weight)
                        topic_entry: Dict[str, Any] = {
                            "cluster_id": int(tid),
                            "label": None,
                            "keywords": keywords,
                            "exemplars": exemplars,
                            "member_count": member_count,
                            "memory_weight": weight,
                            "memory_tier": tier,
                            "lifecycle_tier": lifecycle_tier,
                            "is_new": is_new,
                            "is_trending": is_trending,
                            "_llm_input": (keywords, [e["text"] for e in exemplars]) if use_llm_labels and keywords else None,
                        }
                        if days_inactive is not None:
                            topic_entry["days_inactive"] = days_inactive
                        topics.append(topic_entry)
                else:
                    cluster_version = None

                scores_out.append(
                    {
                        "score_id": score_data["score_id"],
                        "score_name": score_data["score_name"],
                        "items_processed": len(texts),
                        "cluster_version": cluster_version,
                        "topics": topics,
                    }
                )

            all_topic_entries = [topic for score in scores_out for topic in score["topics"]]
            llm_tasks = []
            llm_indices = []
            for idx, topic in enumerate(all_topic_entries):
                llm_input = topic.pop("_llm_input", None)
                if llm_input:
                    llm_tasks.append(asyncio.to_thread(self._generate_topic_label_llm, llm_input[0], llm_input[1]))
                    llm_indices.append(idx)
                else:
                    keywords = topic.get("keywords", [])
                    topic["label"] = ", ".join(keywords[:3]) if keywords else f"Topic {topic['cluster_id']}"

            if llm_tasks:
                self._log(f"ExplanationAnalysis: generating {len(llm_tasks)} LLM topic labels in parallel")
                llm_results = await asyncio.gather(*llm_tasks, return_exceptions=True)
                for idx, result in zip(llm_indices, llm_results):
                    topic = all_topic_entries[idx]
                    keywords = topic.get("keywords", [])
                    if isinstance(result, Exception) or not result:
                        topic["label"] = ", ".join(keywords[:3]) if keywords else f"Topic {topic['cluster_id']}"
                    else:
                        topic["label"] = result

            if use_causal_inference:
                causal_tasks = []
                causal_topic_refs = []
                for score in scores_out:
                    for topic in score["topics"]:
                        for exemplar in topic["exemplars"]:
                            ctx = exemplar.pop("_causal_context", None)
                            if ctx:
                                causal_tasks.append(asyncio.to_thread(self._infer_explanation_root_cause_llm, **ctx))
                                causal_topic_refs.append(topic)

                if causal_tasks:
                    self._log(
                        f"ExplanationAnalysis: inferring root causes for {len(causal_tasks)} exemplar(s) in parallel"
                    )
                    causal_results = await asyncio.gather(*causal_tasks, return_exceptions=True)
                    for topic, result in zip(causal_topic_refs, causal_results):
                        if not isinstance(result, Exception) and result:
                            topic.setdefault("_exemplar_causes", []).append(result)

                synthesis_tasks = []
                synthesis_topic_refs = []
                for score in scores_out:
                    for topic in score["topics"]:
                        causes = topic.pop("_exemplar_causes", None)
                        if causes:
                            synthesis_tasks.append(
                                asyncio.to_thread(
                                    self._synthesize_topic_cause_llm,
                                    topic["label"],
                                    topic.get("keywords", []),
                                    causes,
                                )
                            )
                            synthesis_topic_refs.append(topic)

                if synthesis_tasks:
                    self._log(
                        f"ExplanationAnalysis: synthesizing root cause for {len(synthesis_tasks)} topic(s) in parallel"
                    )
                    synthesis_results = await asyncio.gather(*synthesis_tasks, return_exceptions=True)
                    for topic, result in zip(synthesis_topic_refs, synthesis_results):
                        if not isinstance(result, Exception) and result:
                            topic["cause"] = result
                            topic["root_cause"] = result

            self._log(f"ExplanationAnalysis complete: {len(scores_out)} score(s) processed.")
            return {"scores": scores_out}
        except Exception as e:
            self._log(f"ExplanationAnalysis failed (non-fatal): {e}", level="WARNING")
            import traceback
            self._log(traceback.format_exc(), level="DEBUG")
            return None

    async def _gather_explanation_causal_context(
        self,
        explanation_text: str,
        score_result_id: str,
        raw_score_result: Dict[str, Any],
        item_id: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        try:
            ctx: Dict[str, Any] = {
                "explanation_text": explanation_text,
                "score_value": raw_score_result.get("value") or "",
            }

            score_result = await self._fetch_score_result_details(score_result_id)
            if score_result:
                ctx["score_explanation"] = (score_result.get("explanation") or explanation_text)[:1000] or None

                trace = score_result.get("trace")
                if trace:
                    import json as _json
                    try:
                        trace_str = _json.dumps(trace, indent=2) if isinstance(trace, dict) else str(trace)
                        ctx["trace_summary"] = trace_str[:1500]
                    except Exception as exc:
                        logger.warning(
                            "Failed to summarize explanation-analysis trace: %s",
                            exc,
                        )

                attachments = score_result.get("attachments") or []
                for attachment_path in attachments:
                    try:
                        from plexus.utils.score_result_s3_utils import (
                            download_score_result_log_file,
                            download_score_result_trace_file,
                        )
                        if attachment_path.endswith("trace.json") and "trace_summary" not in ctx:
                            content, _ = await asyncio.to_thread(download_score_result_trace_file, attachment_path)
                            import json as _json
                            ctx["trace_summary"] = _json.dumps(content, indent=2)[:1500]
                        elif attachment_path.endswith("log.txt"):
                            content, _ = await asyncio.to_thread(download_score_result_log_file, attachment_path)
                            ctx["log_excerpt"] = content[-1500:] if len(content) > 1500 else content
                    except Exception as exc:
                        logger.warning(
                            "Failed to process explanation-analysis attachment '%s': %s",
                            attachment_path,
                            exc,
                        )

                score_version = score_result.get("scoreVersion") or {}
                if score_version.get("configuration"):
                    ctx["score_config_yaml"] = score_version["configuration"][:2000]
                if score_version.get("guidelines"):
                    ctx["score_guidelines"] = score_version["guidelines"][:1500]
            else:
                ctx["score_explanation"] = explanation_text[:1000]

            if item_id:
                item_text = await self._fetch_item_text(item_id)
                if item_text:
                    ctx["item_text_excerpt"] = item_text[:1000]

            return ctx
        except Exception:
            return None

    async def _fetch_score_result_details(self, score_result_id: str) -> Optional[Dict[str, Any]]:
        try:
            gql = """
            query GetScoreResult($id: ID!) {
                getScoreResult(id: $id) {
                    id
                    value
                    explanation
                    trace
                    attachments
                    scoreVersion {
                        configuration
                        guidelines
                    }
                }
            }
            """
            result = await asyncio.to_thread(self.api_client.execute, gql, {"id": score_result_id})
            return (result or {}).get("getScoreResult")
        except Exception:
            return None

    def _infer_explanation_root_cause_llm(
        self,
        explanation_text: str,
        score_value: str = "",
        score_explanation: Optional[str] = None,
        trace_summary: Optional[str] = None,
        log_excerpt: Optional[str] = None,
        score_config_yaml: Optional[str] = None,
        score_guidelines: Optional[str] = None,
        item_text_excerpt: Optional[str] = None,
    ) -> Optional[str]:
        try:
            import boto3
            import json as _json

            sections = []
            if score_value:
                sections.append(f"Prediction value: {score_value}")
            if score_explanation:
                sections.append(f"Score explanation: {score_explanation}")
            if score_config_yaml:
                sections.append(f"Score configuration (YAML):\n{score_config_yaml}")
            if score_guidelines:
                sections.append(f"Score guidelines:\n{score_guidelines}")
            if item_text_excerpt:
                sections.append(f"Item text (excerpt):\n{item_text_excerpt}")
            if trace_summary:
                sections.append(f"Score trace (excerpt):\n{trace_summary}")
            if log_excerpt:
                sections.append(f"Score log (excerpt):\n{log_excerpt}")

            system_msg = (
                "You identify root causes concisely. Write one short phrase or sentence — "
                "no preamble, no mention of AI/classifiers/misalignment, just the specific reason."
            )
            user_msg = f"Score explanation text: {explanation_text}\n"
            if sections:
                user_msg += "\n" + "\n\n".join(sections) + "\n"
            user_msg += "\nRoot cause (one short phrase):"

            client = boto3.client("bedrock-runtime", region_name="us-east-1")
            body = _json.dumps(
                {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 60,
                    "system": system_msg,
                    "messages": [{"role": "user", "content": user_msg}],
                }
            )
            response = client.invoke_model(
                modelId="anthropic.claude-3-haiku-20240307-v1:0",
                body=body,
                contentType="application/json",
                accept="application/json",
            )
            result = _json.loads(response["body"].read())
            cause = result["content"][0]["text"].strip()
            return cause if cause else None
        except Exception as e:
            self._log(f"ExplanationAnalysis causal inference LLM call failed: {e}", level="WARNING")
            return None
