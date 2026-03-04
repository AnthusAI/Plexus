"""
VectorTopicMemory ReportBlock — full orchestration.

Rebuilds topic memory by re-indexing datasets into OpenSearch.
Uses S3 embedding cache, global clustering, and memory weights.

Supports two data sources:
- Feedback items: scorecard + days (same as FeedbackAnalysis) — uses transcript text from Items
- DataSource/DataSet: data.source or data.dataset — uses Parquet from DatasetResolver
"""

import asyncio
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from .base import BaseReportBlock
from .data_utils import DatasetResolver
from . import feedback_utils


class VectorTopicMemory(BaseReportBlock):
    """
    ReportBlock that rebuilds a full topic memory view by re-indexing
    datasets into an AWS OpenSearch vector index.

    Config:
        scorecard (str): Scorecard identifier. When provided with days, uses feedback items (same as FeedbackAnalysis).
        days (int): Number of days of feedback to include. Used with scorecard.
        data: { source?: str, dataset?: str, content_column?: str, fresh?: bool }  # Alternative to scorecard+days
        opensearch: { endpoint: str, region: str }
        embedding: { model_id?: str, preprocessing_version?: str }
        clustering: { min_topic_size?: int }
        mode: "full" | "incremental"  # incremental = KNN assign only, no re-cluster
    """

    DEFAULT_NAME = "Vector Topic Memory"
    DEFAULT_DESCRIPTION = "Persistent vector-based topic memory from OpenSearch index"

    async def generate(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Orchestrates: resolve dataset -> embed -> index -> cluster -> memory weights.
        """
        output_data: Dict[str, Any] = {
            "type": "VectorTopicMemory",
            "status": "ok",
            "cluster_version": None,
            "topics": [],
            "summary": "",
            "items_processed": 0,
            "cache_hit_rate": None,
            "index_name": None,
            "indexed_doc_ids": [],  # Item IDs indexed (useful when 0 clusters)
        }

        try:
            # 1. Config validation
            data_config = self.config.get("data", {})
            opensearch_config = self.config.get("opensearch", {})
            endpoint = opensearch_config.get("endpoint") or os.environ.get("OPENSEARCH_ENDPOINT")
            region = opensearch_config.get("region") or os.environ.get("AWS_REGION", "us-west-2")

            if not endpoint:
                self._log("OpenSearch endpoint not configured. Skipping full pipeline.")
                output_data["status"] = "shell"
                output_data["message"] = "OpenSearch not configured — run with opensearch.endpoint."
                log_string = self._get_log_string()
                return output_data, log_string

            # 2. Resolve dataset — feedback items (scorecard+days) or DataSource/DataSet
            scorecard_param = self.config.get("scorecard")
            days_param = self.config.get("days", 14)
            source = data_config.get("source")
            dataset = data_config.get("dataset")

            if scorecard_param:
                # Use feedback items (same as FeedbackAnalysis)
                texts, doc_ids = await self._resolve_feedback_dataset(scorecard_param, days_param)
                self._log(f"Loaded {len(texts)} documents from feedback items.")
            elif source or dataset:
                # Use DataSource/DataSet
                resolver = DatasetResolver(self.api_client)
                file_path, metadata = await resolver.resolve_and_cache_dataset(
                    source=source, dataset=dataset, fresh=data_config.get("fresh", False)
                )
                if not file_path:
                    self._log("Failed to resolve dataset.", level="ERROR")
                    output_data["status"] = "error"
                    output_data["summary"] = "Dataset resolution failed."
                    log_string = self._get_log_string()
                    return output_data, log_string

                if metadata and metadata.get("id"):
                    self.set_resolved_dataset_id(metadata["id"])

                content_col = data_config.get("content_column", "text")
                df = pd.read_parquet(file_path)
                if content_col not in df.columns:
                    content_col = df.columns[0]
                texts = df[content_col].fillna("").astype(str).tolist()
                doc_ids = [str(i) for i in range(len(texts))]
                self._log(f"Loaded {len(texts)} documents from dataset.")
            else:
                self._log("No data config: provide scorecard+days (feedback) or data.source/dataset.", level="ERROR")
                output_data["status"] = "error"
                output_data["summary"] = "Missing data config: scorecard+days or data.source/dataset."
                log_string = self._get_log_string()
                return output_data, log_string

            if len(texts) == 0:
                output_data["status"] = "ok"
                output_data["summary"] = "No documents to process."
                output_data["items_processed"] = 0
                log_string = self._get_log_string()
                return output_data, log_string

            # 3. Embed
            from plexus.analysis.embedding_cache import EmbeddingCache, EmbeddingService

            model_id = self.config.get("embedding", {}).get("model_id", "all-MiniLM-L6-v2")
            version = self.config.get("embedding", {}).get("preprocessing_version", "1")
            cache = EmbeddingCache()
            svc = EmbeddingService(cache=cache, model_id=model_id, preprocessing_version=version)
            embeddings = svc.batch_embed(texts, model_id=model_id, preprocessing_version=version)
            output_data["items_processed"] = len(embeddings)

            # 4. OpenSearch index
            from plexus.analysis.opensearch_client import TopicMemoryIndex

            idx_client = TopicMemoryIndex(endpoint=endpoint, region=region)
            if not idx_client.health_check():
                self._log("OpenSearch health check failed.", level="WARNING")
                output_data["status"] = "partial"
                output_data["summary"] = "OpenSearch unavailable — embeddings computed but not indexed."
                log_string = self._get_log_string()
                return output_data, log_string

            import numpy as np

            documents = [
                {
                    "doc_id": doc_ids[i],
                    "text": texts[i],
                    "embedding": np.array(embeddings[i]) if hasattr(embeddings[i], "tolist") else embeddings[i],
                    "metadata": {},
                    "cluster_id": "",
                    "cluster_version": "",
                    "record_type": "item",
                }
                for i in range(len(embeddings))
            ]
            build_result = idx_client.build_index(documents)
            output_data["index_name"] = build_result.get("new_index_name")
            output_data["indexed_doc_ids"] = doc_ids
            self._log(f"Indexed {build_result['success_count']} documents.")

            # 5. Cluster
            from plexus.analysis.topic_clusterer import TopicClusterer

            clustering_config = self.config.get("clustering", {})
            min_topic_size = clustering_config.get("min_topic_size", 10)
            min_samples = clustering_config.get("min_samples")
            cluster_selection_method = clustering_config.get(
                "cluster_selection_method", "leaf"
            )
            cluster_selection_epsilon = clustering_config.get(
                "cluster_selection_epsilon", 0.5
            )
            clusterer = TopicClusterer(min_topic_size=min_topic_size)
            import numpy as np

            emb_array = np.array(embeddings, dtype=np.float32)
            topics, cluster_version = clusterer.cluster(
                emb_array,
                texts,
                min_topic_size=min_topic_size,
                min_samples=min_samples,
                cluster_selection_method=cluster_selection_method,
                cluster_selection_epsilon=cluster_selection_epsilon,
            )
            output_data["cluster_version"] = cluster_version

            # 6. Cluster records for OpenSearch
            records = clusterer.get_cluster_records()
            idx_client.persist_clusters(records, index_name=build_result.get("new_index_name"))

            # 7. Memory weights (simplified: treat all as active for first run)
            from plexus.analysis.memory_weights import initial_weight, tier_from_weight, update_memory_weights

            existing = [
                {"cluster_id": r["cluster_id"], "memory_weight": initial_weight(), "new_docs_this_run": 10}
                for r in records
            ]
            active_ids = [
                int(r["cluster_id"])
                for r in records
                if str(r["cluster_id"]).lstrip("-").isdigit()
            ]
            updated, _pruned = update_memory_weights(existing, active_ids, prune=False)
            if updated:
                for u in updated:
                    u["metadata"] = u.get("metadata", {})
                idx_client.bulk_update_cluster_weights(
                    updated, index_name=build_result.get("new_index_name")
                )

            # 8. Build topics output with exemplars, keywords, and LLM labels
            centroids = clusterer.cluster_centroids()
            boundaries = clusterer.cluster_boundaries()
            topics_arr = np.array(topics)

            label_config = self.config.get("label", {})
            use_llm_labels = label_config.get("use_llm", True)
            api_key_env = label_config.get("api_key_env_var", "OPENAI_API_KEY")
            model_name = label_config.get("model", "gpt-4o-mini")
            openai_key = os.environ.get(api_key_env) if use_llm_labels else None

            for tid in centroids:
                member_count = int(np.sum(topics_arr == tid))
                weight = 0.5
                tier = tier_from_weight(weight)
                exemplars = clusterer._get_representative_docs(tid, n=5)
                keywords = clusterer.get_keywords(tid, n=8)
                exemplars_truncated = [
                    (ex[:300] + "…" if len(ex) > 300 else ex) for ex in exemplars
                ]

                label = f"Topic {tid}"
                if use_llm_labels and openai_key and (keywords or exemplars):
                    try:
                        label = self._generate_topic_label(
                            keywords=keywords,
                            exemplars=exemplars[:3],
                            model_name=model_name,
                            api_key=openai_key,
                        )
                    except Exception as e:
                        self._log(f"LLM label failed for topic {tid}: {e}", level="WARNING")

                output_data["topics"].append({
                    "cluster_id": tid,
                    "label": label,
                    "keywords": keywords,
                    "exemplars": exemplars_truncated,
                    "memory_weight": weight,
                    "memory_tier": tier,
                    "p95_distance": boundaries.get(tid, 0.0),
                    "member_count": member_count,
                })

            output_data["summary"] = f"Processed {len(texts)} items, {len(output_data['topics'])} clusters."
            self._log(output_data["summary"])

        except Exception as e:
            self._log(f"Error: {e}", level="ERROR")
            import traceback

            self._log(traceback.format_exc(), level="DEBUG")
            output_data["status"] = "error"
            output_data["summary"] = str(e)

        log_string = self._get_log_string()
        return output_data, log_string

    def _generate_topic_label(
        self,
        keywords: List[str],
        exemplars: List[str],
        model_name: str,
        api_key: str,
    ) -> str:
        """Generate a short topic label via LLM from keywords and exemplars."""
        from langchain_openai import ChatOpenAI
        from langchain_core.prompts import ChatPromptTemplate

        keywords_str = ", ".join(keywords[:8]) if keywords else "(none)"
        docs_str = "\n\n".join(
            f"---\n{(ex[:500] + '…' if len(ex) > 500 else ex)}"
            for ex in exemplars[:3]
        ) if exemplars else "(none)"

        prompt = ChatPromptTemplate.from_messages([
            ("system", "You generate short, descriptive topic labels for reviewer feedback/edit comments. Return only the label, no quotes or extra text."),
            ("user", """Topic from reviewer edit comments (what reviewers said when correcting scores). Keywords: {keywords}

Representative excerpts:
{docs}

Provide a short descriptive label (2-6 words) for this topic. Return only the label.""")
        ])
        llm = ChatOpenAI(model=model_name, temperature=0, api_key=api_key)
        chain = prompt | llm
        result = chain.invoke({"keywords": keywords_str, "docs": docs_str})
        label = result.content.strip().strip('"\'')
        return label[:80] if label else "Unnamed topic"

    async def _resolve_feedback_dataset(
        self, scorecard_param: str, days: int
    ) -> Tuple[List[str], List[str]]:
        """
        Resolve dataset from feedback items for the scorecard and date range.
        Uses editCommentValue (reviewer comments) by default — what reviewers said
        when they edited/corrected scores. Set data.content_source: "transcript"
        to use Item transcript text instead.
        Returns (texts, doc_ids).
        """
        from plexus.dashboard.api.models.scorecard import Scorecard
        from plexus.dashboard.api.models.score import Score
        from plexus.dashboard.api.models.item import Item

        content_source = self.config.get("data", {}).get("content_source", "edit_comment")
        score_id_param = self.config.get("score_id")

        # Parse date range
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        end_date = datetime.now(timezone.utc)
        end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)

        self._log(f"Resolving scorecard: {scorecard_param}, days: {days}")
        if score_id_param:
            self._log(f"Targeting specific score: {score_id_param}")
        self._log(f"Date range: {start_date.date()} to {end_date.date()}")
        self._log(f"Content source: {content_source}")

        # Resolve scorecard
        is_uuid = len(str(scorecard_param)) > 20 and "-" in str(scorecard_param)
        if is_uuid:
            plexus_scorecard = await asyncio.to_thread(
                Scorecard.get_by_id, id=str(scorecard_param), client=self.api_client
            )
        else:
            plexus_scorecard = await asyncio.to_thread(
                Scorecard.get_by_external_id,
                external_id=str(scorecard_param),
                client=self.api_client,
            )

        if not plexus_scorecard:
            raise ValueError(f"Scorecard not found: {scorecard_param}")

        self._log(f"Found scorecard: {plexus_scorecard.name}")

        # Get account_id
        account_id = self.params.get("account_id")
        if not account_id and hasattr(self.api_client, "context") and self.api_client.context:
            account_id = self.api_client.context.account_id
        if not account_id:
            raise ValueError("account_id required for feedback resolution")

        # Resolve scores to process
        scores_to_process = []
        if score_id_param:
            self._log(f"Looking up specific Plexus Score: {score_id_param} on Scorecard: {plexus_scorecard.id}")
            try:
                is_score_uuid = len(str(score_id_param)) > 20 and "-" in str(score_id_param)
                if is_score_uuid:
                    plexus_score_obj = await asyncio.to_thread(
                        Score.get_by_id, id=str(score_id_param), client=self.api_client
                    )
                else:
                    plexus_score_obj = await asyncio.to_thread(
                        Score.get_by_external_id,
                        external_id=str(score_id_param),
                        scorecard_id=plexus_scorecard.id,
                        client=self.api_client
                    )

                if plexus_score_obj:
                    scores_to_process.append({
                        'plexus_score_id': plexus_score_obj.id,
                        'plexus_score_name': plexus_score_obj.name,
                        'cc_question_id': str(score_id_param)
                    })
                    self._log(f"Found specific Plexus Score: '{plexus_score_obj.name}'")
                else:
                    self._log(f"Plexus Score not found for: {score_id_param}. Will skip.", level="WARNING")
            except Exception as e:
                self._log(f"ERROR looking up specific Plexus Score ({score_id_param}): {e}", level="ERROR")
        else:
            # Fetch all scores for scorecard
            scores_to_process = await feedback_utils.fetch_scores_for_scorecard(
                self.api_client, plexus_scorecard.id
            )

        if not scores_to_process:
            self._log("No scores to process.", level="WARNING")
            return [], []

        if content_source == "edit_comment":
            # Use edit comments from feedback items — what reviewers said when correcting
            # Only include mismatches (where initial answer != final answer)
            texts = []
            doc_ids = []
            for score_info in scores_to_process:
                items = await feedback_utils.fetch_feedback_items_for_score(
                    self.api_client,
                    account_id,
                    plexus_scorecard.id,
                    score_info["plexus_score_id"],
                    start_date,
                    end_date,
                )
                for fi in items:
                    # Skip items where the original answer was correct (no mismatch)
                    if fi.initialAnswerValue == fi.finalAnswerValue:
                        continue

                    comment = (fi.editCommentValue or "").strip()
                    if comment:
                        texts.append(comment)
                        doc_ids.append(fi.id or f"{fi.itemId}_{fi.scoreId}")

            self._log(f"Resolved {len(texts)} feedback items with edit comments (mismatches only).")
            return texts, doc_ids

        # content_source == "transcript": use Item transcript text (legacy behavior)
        seen_item_ids: set = set()
        item_ids_to_fetch: List[str] = []

        for score_info in scores_to_process:
            items = await feedback_utils.fetch_feedback_items_for_score(
                self.api_client,
                account_id,
                plexus_scorecard.id,
                score_info["plexus_score_id"],
                start_date,
                end_date,
            )
            for fi in items:
                if fi.itemId and fi.itemId not in seen_item_ids:
                    seen_item_ids.add(fi.itemId)
                    item_ids_to_fetch.append(fi.itemId)

        self._log(f"Found {len(item_ids_to_fetch)} unique items from feedback.")

        if not item_ids_to_fetch:
            return [], []

        texts = []
        doc_ids = []
        for item_id in item_ids_to_fetch:
            item = await asyncio.to_thread(Item.get_by_id, item_id, self.api_client)
            if item and (item.text or "").strip():
                texts.append((item.text or "").strip())
                doc_ids.append(item_id)

        self._log(f"Resolved {len(texts)} items with transcript text.")
        return texts, doc_ids
