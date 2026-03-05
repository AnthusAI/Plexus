"""
VectorTopicMemory ReportBlock — full orchestration.

Rebuilds topic memory by re-indexing datasets into S3 Vectors.
Uses S3 embedding cache, global clustering, and memory weights.

Supports two data sources:
- Feedback items: scorecard + days (same as FeedbackAnalysis) — uses transcript text from Items
- ScoreResults: scorecard + days with content_source=score_result_no_explanation —
  uses ScoreResult.explanation where value='No' from normal production predictions
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
    datasets into an AWS S3 Vectors index.

    Config:
        scorecard (str): Scorecard identifier. When provided with days, uses feedback items (same as FeedbackAnalysis).
        days (int): Number of days of feedback to include. Used with scorecard.
        data: { source?: str, dataset?: str, content_column?: str, fresh?: bool, content_source?: str }
          content_source:
            - edit_comment (default): FeedbackItem.editCommentValue for mismatches
            - transcript: Item transcript text linked from feedback items
            - score_result_no_explanation: ScoreResult.explanation for normal production predictions with value='No'
        s3_vectors: { bucket_name: str, index_name: str, index_arn?: str, region?: str }
        embedding: { model_id?: str, preprocessing_version?: str }
        clustering: { min_topic_size?: int }
        mode: "full" | "incremental"  # incremental = KNN assign only, no re-cluster
    """

    DEFAULT_NAME = "Vector Topic Memory"
    DEFAULT_DESCRIPTION = "Persistent vector-based topic memory from S3 Vectors index"
    SHORT_TERM_DAYS = 14
    MEDIUM_TERM_DAYS = 30

    def _resolve_s3_vectors_config(self) -> Dict[str, Optional[str]]:
        """
        Resolve S3 Vectors configuration with safe defaults for prototype stacks.

        Resolution order:
        1) explicit block config (s3_vectors.*)
        2) environment variables
        3) prototype naming convention using ENVIRONMENT (default: development)
        """
        vectors_config = self.config.get("s3_vectors", {})
        environment_name = os.environ.get("ENVIRONMENT", "development")

        default_bucket = f"plexus-vectors-{environment_name}"
        default_index = f"topic-memory-idx-{environment_name}"

        explicit_bucket = vectors_config.get("bucket_name") or os.environ.get("S3_VECTOR_BUCKET_NAME")
        explicit_index = vectors_config.get("index_name") or os.environ.get("S3_VECTOR_INDEX_NAME")
        vector_index_arn = vectors_config.get("index_arn") or os.environ.get("S3_VECTOR_INDEX_ARN")
        region = vectors_config.get("region") or os.environ.get("AWS_REGION", "us-west-2")

        vector_bucket = explicit_bucket or default_bucket
        vector_index = explicit_index or default_index

        if not explicit_bucket or not explicit_index:
            self._log(
                f"Using S3 Vectors defaults for missing settings: "
                f"bucket={vector_bucket}, index={vector_index}, environment={environment_name}"
            )

        return {
            "bucket_name": vector_bucket,
            "index_name": vector_index,
            "index_arn": vector_index_arn,
            "region": region,
        }

    async def generate(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Orchestrates: resolve dataset -> embed -> index -> cluster -> memory weights.
        """
        output_data: Dict[str, Any] = {
            "type": "VectorTopicMemory",
            "status": "ok",
            "cluster_version": None,
            "topics": [],
            "scores": [],
            "summary": "",
            "items_processed": 0,
            "cache_hit_rate": None,
            "index_name": None,
            "indexed_doc_ids": [],
        }

        try:
            # 1. Config validation
            data_config = self.config.get("data", {})
            vectors_config = self._resolve_s3_vectors_config()
            vector_bucket = vectors_config.get("bucket_name")
            vector_index = vectors_config.get("index_name")
            vector_index_arn = vectors_config.get("index_arn")
            region = vectors_config.get("region")

            if not vector_bucket or not vector_index:
                self._log("S3 Vectors bucket/index not configured. Skipping full pipeline.")
                output_data["status"] = "shell"
                output_data["message"] = "S3 Vectors not configured — set s3_vectors.bucket_name and s3_vectors.index_name."
                return output_data, self._get_log_string()

            # 2. Resolve datasets
            scorecard_param = self.config.get("scorecard")
            days_param = self.config.get("days", 14)
            source = data_config.get("source")
            dataset = data_config.get("dataset")

            datasets = []

            if scorecard_param:
                datasets = await self._resolve_feedback_datasets(scorecard_param, days_param)
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
                    return output_data, self._get_log_string()

                if metadata and metadata.get("id"):
                    self.set_resolved_dataset_id(metadata["id"])

                content_col = data_config.get("content_column", "text")
                df = pd.read_parquet(file_path)
                if content_col not in df.columns:
                    content_col = df.columns[0]
                texts = df[content_col].fillna("").astype(str).tolist()
                doc_ids = [str(i) for i in range(len(texts))]
                timestamps = [datetime.now(timezone.utc)] * len(texts)
                self._log(f"Loaded {len(texts)} documents from dataset.")
                datasets.append({
                    "score_id": "dataset",
                    "score_name": "Dataset",
                    "texts": texts,
                    "doc_ids": doc_ids,
                    "timestamps": timestamps
                })
            else:
                self._log("No data config: provide scorecard+days (feedback) or data.source/dataset.", level="ERROR")
                output_data["status"] = "error"
                output_data["summary"] = "Missing data config: scorecard+days or data.source/dataset."
                return output_data, self._get_log_string()

            total_texts = sum(len(ds["texts"]) for ds in datasets)
            if total_texts == 0:
                output_data["status"] = "ok"
                output_data["summary"] = "No documents to process."
                output_data["items_processed"] = 0
                return output_data, self._get_log_string()

            # 3. Embed all texts at once for efficiency
            all_texts = []
            for ds in datasets:
                all_texts.extend(ds["texts"])
            
            from plexus.analysis.embedding_cache import EmbeddingCache, EmbeddingService
            model_id = self.config.get("embedding", {}).get("model_id", "all-MiniLM-L6-v2")
            version = self.config.get("embedding", {}).get("preprocessing_version", "1")
            cache = EmbeddingCache()
            svc = EmbeddingService(cache=cache, model_id=model_id, preprocessing_version=version)
            embeddings = svc.batch_embed(all_texts, model_id=model_id, preprocessing_version=version)
            output_data["items_processed"] = len(embeddings)

            # 4. S3 Vectors index
            from plexus.analysis.s3vectors_client import TopicMemoryVectorStore

            idx_client = TopicMemoryVectorStore(
                bucket_name=vector_bucket,
                index_name=vector_index,
                index_arn=vector_index_arn,
                region=region,
            )
            if not idx_client.health_check():
                self._log("S3 Vectors health check failed.", level="WARNING")
                output_data["status"] = "partial"
                output_data["summary"] = "S3 Vectors unavailable — embeddings computed but not indexed."
                return output_data, self._get_log_string()

            import numpy as np

            # Distribute embeddings back to datasets and build index documents
            documents = []
            current_idx = 0
            for ds in datasets:
                ds_len = len(ds["texts"])
                ds["embeddings"] = embeddings[current_idx:current_idx + ds_len]
                
                for i in range(ds_len):
                    documents.append({
                        "doc_id": ds["doc_ids"][i],
                        "text": ds["texts"][i],
                        "embedding": np.array(ds["embeddings"][i]) if hasattr(ds["embeddings"][i], "tolist") else ds["embeddings"][i],
                        "metadata": {"score_id": ds["score_id"]},
                        "cluster_id": "",
                        "cluster_version": "",
                        "record_type": "item",
                    })
                current_idx += ds_len
                
            build_result = idx_client.build_index(documents)
            index_name = build_result.get("new_index_name")
            output_data["index_name"] = index_name
            output_data["indexed_doc_ids"] = [d["doc_id"] for d in documents]
            self._log(f"Indexed {build_result['success_count']} documents.")

            # 5-8. Cluster per score
            from plexus.analysis.topic_clusterer import TopicClusterer
            from plexus.analysis.memory_weights import tier_from_weight

            clustering_config = self.config.get("clustering", {})
            min_topic_size = clustering_config.get("min_topic_size", 10)
            min_samples = clustering_config.get("min_samples")
            cluster_selection_method = clustering_config.get("cluster_selection_method", "leaf")
            cluster_selection_epsilon = clustering_config.get("cluster_selection_epsilon", 0.5)
            
            label_config = self.config.get("label", {})
            use_llm_labels = label_config.get("use_llm", True)
            api_key_env = label_config.get("api_key_env_var", "OPENAI_API_KEY")
            model_name = label_config.get("model", "gpt-4o-mini")
            openai_key = os.environ.get(api_key_env) if use_llm_labels else None

            # Reference date for calculating decay (usually today)
            end_date = datetime.now(timezone.utc)

            for ds in datasets:
                if len(ds["texts"]) == 0:
                    self._log(f"No items to cluster for score {ds['score_name']}.")
                    continue
                
                self._log(f"Clustering {len(ds['texts'])} items for score {ds['score_name']}...")
                clusterer = TopicClusterer(min_topic_size=min_topic_size)
                emb_array = np.array(ds["embeddings"], dtype=np.float32)
                topics, cluster_version = clusterer.cluster(
                    emb_array,
                    ds["texts"],
                    min_topic_size=min_topic_size,
                    min_samples=min_samples,
                    cluster_selection_method=cluster_selection_method,
                    cluster_selection_epsilon=cluster_selection_epsilon,
                )
                
                records = clusterer.get_cluster_records()
                for r in records:
                    r["metadata"] = {"score_id": ds["score_id"]}
                idx_client.persist_clusters(records, index_name=index_name)

                # Compute weights based on calendar days
                centroids = clusterer.cluster_centroids()
                boundaries = clusterer.cluster_boundaries()
                topics_arr = np.array(topics)
                
                ds_topics = []
                updated_clusters = []
                
                for tid in centroids:
                    member_indices = np.where(topics_arr == tid)[0]
                    member_count = len(member_indices)
                    cluster_timestamps = [ds["timestamps"][i] for i in member_indices if ds["timestamps"][i]]
                    
                    if cluster_timestamps:
                        most_recent = max(cluster_timestamps)
                        if most_recent.tzinfo is None:
                            most_recent = most_recent.replace(tzinfo=timezone.utc)
                        days_inactive = max(0, (end_date - most_recent).days)
                    else:
                        days_inactive = 0

                    lifecycle = self._derive_lifecycle_flags(
                        cluster_timestamps=cluster_timestamps,
                        end_date=end_date,
                        short_term_days=self.SHORT_TERM_DAYS,
                        medium_term_days=self.MEDIUM_TERM_DAYS,
                    )
                        
                    # Simulated history for full rebuild:
                    # If active within last 14 days -> hot (0.8)
                    # If active within last 30 days -> warm (0.5)
                    # If inactive > 30 days -> decay based on days
                    if days_inactive <= 14:
                        weight = 0.8
                    elif days_inactive <= 30:
                        weight = 0.5
                    else:
                        weight = max(0.0, 0.5 - (days_inactive - 30) * 0.01)
                        
                    tier = tier_from_weight(weight)
                    
                    exemplars = clusterer._get_representative_docs(tid, n=5)
                    keywords = clusterer.get_keywords(tid, n=8)
                    exemplars_truncated = [(ex[:300] + "…" if len(ex) > 300 else ex) for ex in exemplars]

                    label = f"Topic {tid}"
                    if use_llm_labels and openai_key and (keywords or exemplars):
                        try:
                            label = self._generate_topic_label(
                                keywords=keywords, exemplars=exemplars[:3],
                                model_name=model_name, api_key=openai_key
                            )
                        except Exception as e:
                            self._log(f"LLM label failed for topic {tid}: {e}", level="WARNING")

                    ds_topics.append({
                        "cluster_id": tid,
                        "label": label,
                        "keywords": keywords,
                        "exemplars": exemplars_truncated,
                        "memory_weight": weight,
                        "memory_tier": tier,
                        "p95_distance": boundaries.get(tid, 0.0),
                        "member_count": member_count,
                        "days_inactive": days_inactive,
                        "has_short_term_memory": lifecycle["has_short_term_memory"],
                        "has_medium_term_memory": lifecycle["has_medium_term_memory"],
                        "has_long_term_memory": lifecycle["has_long_term_memory"],
                        "is_new": lifecycle["is_new"],
                        "is_trending": lifecycle["is_trending"],
                        "lifecycle_tier": lifecycle["lifecycle_tier"],
                    })
                    
                    # Store updated weight back to S3 Vectors
                    updated_clusters.append({
                        "cluster_id": str(tid),
                        "memory_weight": weight,
                        "memory_tier": tier,
                        "metadata": {"score_id": ds["score_id"]}
                    })

                if updated_clusters:
                    idx_client.bulk_update_cluster_weights(updated_clusters, index_name=index_name)

                # Add this score's topics to the output
                output_data["scores"].append({
                    "score_id": ds["score_id"],
                    "score_name": ds["score_name"],
                    "items_processed": len(ds["texts"]),
                    "topics": ds_topics,
                    "cluster_version": cluster_version
                })

            total_clusters = sum(len(s["topics"]) for s in output_data["scores"])
            
            # For backwards compatibility, hoist topics if there's only one score
            if len(output_data["scores"]) == 1:
                output_data["topics"] = output_data["scores"][0]["topics"]
                output_data["cluster_version"] = output_data["scores"][0]["cluster_version"]
                
            output_data["summary"] = f"Processed {total_texts} items across {len(output_data['scores'])} scores, {total_clusters} clusters total."
                
            self._log(output_data["summary"])

        except Exception as e:
            self._log(f"Error: {e}", level="ERROR")
            import traceback
            self._log(traceback.format_exc(), level="DEBUG")
            output_data["status"] = "error"
            output_data["summary"] = str(e)

        return output_data, self._get_log_string()

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
            ("user", f"Topic from reviewer edit comments (what reviewers said when correcting scores). Keywords: {keywords_str}\n\nRepresentative excerpts:\n{docs_str}\n\nProvide a short descriptive label (2-6 words) for this topic. Return only the label.")
        ])
        llm = ChatOpenAI(model=model_name, temperature=0, api_key=api_key)
        chain = prompt | llm
        result = chain.invoke({})
        label = result.content.strip().strip('"\'')
        return label[:80] if label else "Unnamed topic"

    @staticmethod
    def _parse_iso_timestamp(value: Any) -> Optional[datetime]:
        """Parse ISO timestamps consistently and return UTC-aware datetime."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                return None
        return None

    @staticmethod
    def _derive_lifecycle_flags(
        cluster_timestamps: List[datetime],
        end_date: datetime,
        short_term_days: int = SHORT_TERM_DAYS,
        medium_term_days: int = MEDIUM_TERM_DAYS,
    ) -> Dict[str, Any]:
        """
        Derive lifecycle windows from member timestamps.

        Definitions:
        - new = short && !medium && !long
        - trending = (short || medium) && !long
        """
        has_short = False
        has_medium = False
        has_long = False

        for ts in cluster_timestamps:
            ts_aware = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
            age_days = max(0, (end_date - ts_aware).days)
            if age_days <= short_term_days:
                has_short = True
            elif age_days <= medium_term_days:
                has_medium = True
            else:
                has_long = True

        is_new = has_short and (not has_medium) and (not has_long)
        is_trending = (has_short or has_medium) and (not has_long)

        if is_new:
            lifecycle_tier = "new"
        elif is_trending:
            lifecycle_tier = "trending"
        else:
            lifecycle_tier = "established"

        return {
            "has_short_term_memory": has_short,
            "has_medium_term_memory": has_medium,
            "has_long_term_memory": has_long,
            "is_new": is_new,
            "is_trending": is_trending,
            "lifecycle_tier": lifecycle_tier,
        }

    @staticmethod
    def _is_normal_prediction_score_result(score_result: Dict[str, Any]) -> bool:
        """
        Normal production ScoreResult heuristic:
        - prediction type
        - completed status
        - success code 200
        - not linked to an evaluation
        """
        if score_result.get("evaluationId"):
            return False
        score_type = str(score_result.get("type") or "prediction").strip().lower()
        if score_type != "prediction":
            return False
        status = str(score_result.get("status") or "COMPLETED").strip().upper()
        if status != "COMPLETED":
            return False
        code = str(score_result.get("code") or "200").strip()
        return code == "200"

    async def _resolve_feedback_datasets(
        self, scorecard_param: str, days: int
    ) -> List[Dict[str, Any]]:
        """
        Resolve dataset from feedback items for the scorecard and date range.
        Organizes the results per score.
        Returns list of dicts: {"score_id": str, "score_name": str, "texts": [], "doc_ids": [], "timestamps": []}
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
            return []

        datasets = []
        
        for score_info in scores_to_process:
            texts = []
            doc_ids = []
            timestamps = []
            
            items = await feedback_utils.fetch_feedback_items_for_score(
                self.api_client,
                account_id,
                plexus_scorecard.id,
                score_info["plexus_score_id"],
                start_date,
                end_date,
            )
            
            if content_source == "edit_comment":
                for fi in items:
                    # Skip items where the original answer was correct (no mismatch)
                    if fi.initialAnswerValue == fi.finalAnswerValue:
                        continue

                    comment = (fi.editCommentValue or "").strip()
                    if comment:
                        texts.append(comment)
                        doc_ids.append(fi.id or f"{fi.itemId}_{fi.scoreId}")
                        # Parse timestamp
                        ts = self._parse_iso_timestamp(fi.updatedAt or fi.createdAt)
                        timestamps.append(ts or end_date)
            elif content_source == "transcript":
                # content_source == "transcript": use Item transcript text
                seen_item_ids: set = set()
                item_ids_to_fetch: List[str] = []
                item_timestamps = {}
                
                for fi in items:
                    if fi.itemId and fi.itemId not in seen_item_ids:
                        seen_item_ids.add(fi.itemId)
                        item_ids_to_fetch.append(fi.itemId)
                        ts = self._parse_iso_timestamp(fi.updatedAt or fi.createdAt)
                        item_timestamps[fi.itemId] = ts or end_date

                for item_id in item_ids_to_fetch:
                    item = await asyncio.to_thread(Item.get_by_id, item_id, self.api_client)
                    if item and (item.text or "").strip():
                        texts.append((item.text or "").strip())
                        doc_ids.append(item_id)
                        timestamps.append(item_timestamps[item_id])
            elif content_source == "score_result_no_explanation":
                score_results = await feedback_utils.fetch_score_results_for_score(
                    self.api_client,
                    account_id,
                    plexus_scorecard.id,
                    score_info["plexus_score_id"],
                    start_date,
                    end_date,
                )
                retained = 0
                for sr in score_results:
                    if not self._is_normal_prediction_score_result(sr):
                        continue
                    value = str(sr.get("value") or "").strip().lower()
                    if value != "no":
                        continue
                    explanation = (sr.get("explanation") or "").strip()
                    if not explanation:
                        continue

                    texts.append(explanation)
                    doc_ids.append(sr.get("id") or f"{sr.get('itemId')}_{sr.get('scoreId')}")
                    ts = self._parse_iso_timestamp(sr.get("updatedAt") or sr.get("createdAt"))
                    timestamps.append(ts or end_date)
                    retained += 1
                self._log(
                    f"ScoreResult source retained {retained} items for score {score_info['plexus_score_name']} "
                    f"(fetched {len(score_results)} records)."
                )
            else:
                self._log(
                    f"Unsupported content_source '{content_source}'. Supported: edit_comment, transcript, score_result_no_explanation.",
                    level="ERROR",
                )
                continue

            if texts:
                datasets.append({
                    "score_id": score_info["cc_question_id"] or score_info["plexus_score_id"],
                    "score_name": score_info["plexus_score_name"],
                    "texts": texts,
                    "doc_ids": doc_ids,
                    "timestamps": timestamps
                })
                self._log(f"Resolved {len(texts)} items for score {score_info['plexus_score_name']}.")

        return datasets
