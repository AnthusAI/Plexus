from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import PurePosixPath
from typing import Any

from plexus.cli.shared.shared import sanitize_path_name


RUBRIC_MEMORY_BUCKET_ENV_VAR = "AMPLIFY_STORAGE_RUBRICMEMORY_BUCKET_NAME"


@dataclass(frozen=True)
class S3RubricMemoryObject:
    """One raw S3 object in a rubric-memory corpus source."""

    key: str
    size: int
    etag: str
    last_modified: datetime | None


@dataclass(frozen=True)
class S3RubricMemorySource:
    """An S3 rubric-memory prefix with its score hierarchy scope."""

    bucket_name: str
    prefix: str
    scope_level: str
    objects: tuple[S3RubricMemoryObject, ...]


@dataclass(frozen=True)
class S3RubricMemoryCorpusPaths:
    """Convention-derived S3 rubric-memory prefixes for one score."""

    bucket_name: str
    scorecard_prefix: str
    scorecard_knowledge_base_prefix: str
    prefix_knowledge_base_prefixes: list[str]
    score_knowledge_base_prefix: str
    sources: list[S3RubricMemorySource]


class S3RubricMemoryCorpusResolver:
    """Resolve rubric-memory S3 prefixes using the name-based hierarchy."""

    def __init__(
        self,
        *,
        bucket_name: str | None = None,
        s3_client: Any | None = None,
    ):
        self.bucket_name = bucket_name or os.environ.get(RUBRIC_MEMORY_BUCKET_ENV_VAR)
        if not self.bucket_name:
            raise ValueError(
                f"Missing required environment variable: {RUBRIC_MEMORY_BUCKET_ENV_VAR}"
            )
        if s3_client is None:
            import boto3

            s3_client = boto3.client("s3")
        self.s3_client = s3_client

    def resolve(
        self,
        *,
        scorecard_name: str,
        score_name: str,
    ) -> S3RubricMemoryCorpusPaths:
        scorecard_prefix = self._prefix(scorecard_name)
        scorecard_knowledge_base_prefix = (
            f"{scorecard_prefix}scorecard.knowledge-base/"
        )
        score_knowledge_base_prefix = (
            f"{scorecard_prefix}{sanitize_path_name(score_name)}.knowledge-base/"
        )
        prefix_knowledge_base_prefixes = self._matching_prefix_knowledge_bases(
            scorecard_prefix=scorecard_prefix,
            score_name=score_name,
            score_knowledge_base_prefix=score_knowledge_base_prefix,
        )
        sources = [
            self._source_for_prefix(
                prefix=scorecard_knowledge_base_prefix,
                scope_level="scorecard",
                required=True,
            ),
            *[
                self._source_for_prefix(
                    prefix=prefix,
                    scope_level="prefix",
                    required=False,
                )
                for prefix in prefix_knowledge_base_prefixes
            ],
            self._source_for_prefix(
                prefix=score_knowledge_base_prefix,
                scope_level="score",
                required=True,
            ),
        ]
        sources = [source for source in sources if source.objects]
        return S3RubricMemoryCorpusPaths(
            bucket_name=self.bucket_name,
            scorecard_prefix=scorecard_prefix,
            scorecard_knowledge_base_prefix=scorecard_knowledge_base_prefix,
            prefix_knowledge_base_prefixes=prefix_knowledge_base_prefixes,
            score_knowledge_base_prefix=score_knowledge_base_prefix,
            sources=sources,
        )

    def _matching_prefix_knowledge_bases(
        self,
        *,
        scorecard_prefix: str,
        score_name: str,
        score_knowledge_base_prefix: str,
    ) -> list[str]:
        sanitized_score_name = sanitize_path_name(score_name)
        candidates: list[str] = []
        paginator = self.s3_client.get_paginator("list_objects_v2")
        for page in paginator.paginate(
            Bucket=self.bucket_name,
            Prefix=scorecard_prefix,
            Delimiter="/",
        ):
            for common_prefix in page.get("CommonPrefixes", []):
                prefix = str(common_prefix.get("Prefix") or "")
                folder_name = PurePosixPath(prefix.rstrip("/")).name
                if folder_name == "scorecard.knowledge-base":
                    continue
                if prefix == score_knowledge_base_prefix:
                    continue
                if not folder_name.endswith(".knowledge-base"):
                    continue
                stem = folder_name[: -len(".knowledge-base")]
                if self._is_prefix_match(
                    prefix=stem,
                    sanitized_score_name=sanitized_score_name,
                ):
                    candidates.append(prefix)

        return sorted(
            set(candidates),
            key=lambda prefix: (
                -len(PurePosixPath(prefix.rstrip("/")).name),
                prefix,
            ),
        )

    def _source_for_prefix(
        self,
        *,
        prefix: str,
        scope_level: str,
        required: bool,
    ) -> S3RubricMemorySource:
        objects = tuple(self._objects_for_prefix(prefix))
        if required and not objects:
            raise FileNotFoundError(
                "Rubric memory knowledge-base S3 prefix does not exist or has "
                f"no source files: s3://{self.bucket_name}/{prefix}"
            )
        return S3RubricMemorySource(
            bucket_name=self.bucket_name,
            prefix=prefix,
            scope_level=scope_level,
            objects=objects,
        )

    def _objects_for_prefix(self, prefix: str) -> list[S3RubricMemoryObject]:
        objects: list[S3RubricMemoryObject] = []
        paginator = self.s3_client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
            for item in page.get("Contents", []):
                key = str(item.get("Key") or "")
                if not key or key.endswith("/"):
                    continue
                relative_path = PurePosixPath(key[len(prefix) :])
                if self._is_generated_or_derived(relative_path):
                    continue
                objects.append(
                    S3RubricMemoryObject(
                        key=key,
                        size=int(item.get("Size") or 0),
                        etag=str(item.get("ETag") or "").strip('"'),
                        last_modified=item.get("LastModified"),
                    )
                )
        return sorted(objects, key=lambda obj: obj.key)

    def _is_generated_or_derived(self, relative_path: PurePosixPath) -> bool:
        if relative_path.name.endswith(".biblicus.yml"):
            return True
        return any(
            part
            in {
                ".biblicus",
                "analysis",
                "extracted",
                "graph",
                "metadata",
                "retrieval",
            }
            for part in relative_path.parts
        )

    def _prefix(self, scorecard_name: str) -> str:
        cleaned = sanitize_path_name(scorecard_name).strip("/")
        if not cleaned:
            raise ValueError("scorecard_name must not be empty")
        return f"{cleaned}/"

    def _is_prefix_match(self, *, prefix: str, sanitized_score_name: str) -> bool:
        if not prefix or not sanitized_score_name.startswith(prefix):
            return False
        if len(sanitized_score_name) == len(prefix):
            return False
        boundary = sanitized_score_name[len(prefix)]
        return boundary in {" ", "-", "("}
