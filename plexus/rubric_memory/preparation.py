from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from pathlib import Path
from pathlib import PurePosixPath
import re
from typing import Any, Sequence

from .local_corpus import LocalRubricMemorySource
from .s3_corpus import S3RubricMemorySource

RubricMemoryCorpusSource = LocalRubricMemorySource | S3RubricMemorySource


@dataclass(frozen=True)
class PreparedRubricMemoryCorpus:
    """A prepared Biblicus corpus built from rubric-memory sources."""

    corpus_root: Path
    prepared_root: Path
    manifest_path: Path
    fingerprint: str
    retriever_id: str
    status: str
    source_file_count: int
    sources: list[dict[str, Any]]


class RubricMemoryPreparedCorpusManager:
    """Prepare rubric-memory sources into a reusable Biblicus corpus."""

    SIDECAR_SCHEMA_VERSION = "rubric-memory-sidecar-v1"
    _SIDECAR_SUFFIX = ".biblicus.yml"
    _DATE_FOLDER_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    _BIBLICUS_DERIVED_DIRS = {
        ".biblicus",
        "analysis",
        "extracted",
        "graph",
        "metadata",
        "retrieval",
    }

    def __init__(self, cache_root: str | Path | None = None):
        self.cache_root = Path(
            cache_root or Path("tmp") / "rubric-memory" / "prepared"
        ).resolve()

    def prepare(
        self,
        *,
        corpus_sources: Sequence[RubricMemoryCorpusSource],
        retriever_id: str = "scan",
        force: bool = False,
    ) -> PreparedRubricMemoryCorpus:
        sources = [self._normalize_source(source) for source in corpus_sources]
        for source in sources:
            self._validate_source(source)

        fingerprint_payload = self._fingerprint_payload(
            sources=sources,
            retriever_id=retriever_id,
        )
        fingerprint = self._fingerprint(fingerprint_payload)
        prepared_root = self.cache_root / fingerprint[:16]
        corpus_root = prepared_root / "corpus"
        manifest_path = prepared_root / "manifest.json"
        existing_manifest = self._read_manifest(manifest_path)

        if (
            not force
            and existing_manifest is not None
            and existing_manifest.get("fingerprint") == fingerprint
            and corpus_root.exists()
        ):
            return self._prepared_result(
                corpus_root=corpus_root,
                prepared_root=prepared_root,
                manifest_path=manifest_path,
                fingerprint=fingerprint,
                retriever_id=retriever_id,
                status="reused",
                fingerprint_payload=fingerprint_payload,
            )

        if prepared_root.exists():
            shutil.rmtree(prepared_root)
        corpus_root.mkdir(parents=True, exist_ok=True)
        (corpus_root / ".biblicusignore").write_text(
            "*.biblicus.yml\n**/*.biblicus.yml\n",
            encoding="utf-8",
        )
        for index, source in enumerate(sources):
            destination = corpus_root / f"{index:02d}-{source.scope_level}"
            if isinstance(source, LocalRubricMemorySource):
                shutil.copytree(source.root, destination, ignore=self._ignore_generated)
                self._write_local_metadata_sidecars(source, destination)
            else:
                destination.mkdir(parents=True, exist_ok=True)
                self._download_s3_source(source, destination)

        self._build_biblicus_snapshot(
            corpus_root=corpus_root,
            retriever_id=retriever_id,
        )

        manifest = {
            "fingerprint": fingerprint,
            "retriever_id": retriever_id,
            "sidecar_schema_version": self.SIDECAR_SCHEMA_VERSION,
            "prepared_at": datetime.now(timezone.utc).isoformat(),
            "source_file_count": len(fingerprint_payload["files"]),
            "sources": fingerprint_payload["sources"],
            "corpus_root": str(corpus_root),
        }
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        return self._prepared_result(
            corpus_root=corpus_root,
            prepared_root=prepared_root,
            manifest_path=manifest_path,
            fingerprint=fingerprint,
            retriever_id=retriever_id,
            status="rebuilt",
            fingerprint_payload=fingerprint_payload,
        )

    def _build_biblicus_snapshot(self, *, corpus_root: Path, retriever_id: str) -> None:
        from biblicus.knowledge_base import KnowledgeBase

        KnowledgeBase.from_folder(
            corpus_root,
            retriever_id=retriever_id,
        )

    def _prepared_result(
        self,
        *,
        corpus_root: Path,
        prepared_root: Path,
        manifest_path: Path,
        fingerprint: str,
        retriever_id: str,
        status: str,
        fingerprint_payload: dict[str, Any],
    ) -> PreparedRubricMemoryCorpus:
        return PreparedRubricMemoryCorpus(
            corpus_root=corpus_root,
            prepared_root=prepared_root,
            manifest_path=manifest_path,
            fingerprint=fingerprint,
            retriever_id=retriever_id,
            status=status,
            source_file_count=len(fingerprint_payload["files"]),
            sources=fingerprint_payload["sources"],
        )

    def _fingerprint_payload(
        self,
        *,
        sources: Sequence[RubricMemoryCorpusSource],
        retriever_id: str,
    ) -> dict[str, Any]:
        source_payloads = []
        file_payloads = []
        for source in sources:
            if isinstance(source, LocalRubricMemorySource):
                source_payloads.append(
                    {
                        "source_type": "local",
                        "root": str(source.root),
                        "scope_level": source.scope_level,
                    }
                )
                for file_path in self._source_files(source.root):
                    relative_path = file_path.relative_to(source.root)
                    stat = file_path.stat()
                    timestamp = self.infer_source_timestamp(relative_path)
                    file_payloads.append(
                        {
                            "source_type": "local",
                            "source_root": str(source.root),
                            "scope_level": source.scope_level,
                            "relative_path": relative_path.as_posix(),
                            "size": stat.st_size,
                            "mtime_ns": stat.st_mtime_ns,
                            "source_timestamp": (
                                timestamp.isoformat() if timestamp is not None else None
                            ),
                        }
                    )
            else:
                source_payloads.append(
                    {
                        "source_type": "s3",
                        "bucket_name": source.bucket_name,
                        "prefix": source.prefix,
                        "scope_level": source.scope_level,
                    }
                )
                for obj in source.objects:
                    relative_path = self._s3_relative_path(source, obj.key)
                    timestamp = self.infer_source_timestamp(relative_path)
                    file_payloads.append(
                        {
                            "source_type": "s3",
                            "bucket_name": source.bucket_name,
                            "source_prefix": source.prefix,
                            "scope_level": source.scope_level,
                            "key": obj.key,
                            "relative_path": relative_path.as_posix(),
                            "size": obj.size,
                            "etag": obj.etag,
                            "last_modified": (
                                obj.last_modified.isoformat()
                                if obj.last_modified is not None
                                else None
                            ),
                            "source_timestamp": (
                                timestamp.isoformat() if timestamp is not None else None
                            ),
                        }
                    )
        return {
            "retriever_id": retriever_id,
            "sidecar_schema_version": self.SIDECAR_SCHEMA_VERSION,
            "sources": source_payloads,
            "files": sorted(
                file_payloads,
                key=lambda item: (
                    item.get("source_root") or item.get("source_prefix"),
                    item["scope_level"],
                    item["relative_path"],
                ),
            ),
        }

    def _fingerprint(self, payload: dict[str, Any]) -> str:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        return hashlib.sha256(encoded).hexdigest()

    def _source_files(self, root: Path) -> list[Path]:
        files: list[Path] = []
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if self._is_generated_or_derived(path, root):
                continue
            files.append(path)
        return files

    def _is_generated_or_derived(self, path: Path, root: Path) -> bool:
        if path.name.endswith(self._SIDECAR_SUFFIX):
            return True
        relative_parts = path.relative_to(root).parts
        return any(part in self._BIBLICUS_DERIVED_DIRS for part in relative_parts)

    def _ignore_generated(self, directory: str, names: list[str]) -> list[str]:
        ignored = []
        for name in names:
            if name in self._BIBLICUS_DERIVED_DIRS:
                ignored.append(name)
            elif name.endswith(self._SIDECAR_SUFFIX):
                ignored.append(name)
        return ignored

    def _write_local_metadata_sidecars(
        self,
        source: LocalRubricMemorySource,
        destination_root: Path,
    ) -> None:
        for copied_path in sorted(destination_root.rglob("*")):
            if not copied_path.is_file():
                continue
            if self._is_generated_or_derived(copied_path, destination_root):
                continue
            relative_path = copied_path.relative_to(destination_root)
            original_path = source.root / relative_path
            metadata: dict[str, Any] = {
                "scope_level": source.scope_level,
                "source_uri": original_path.resolve().as_uri(),
            }
            source_timestamp = self.infer_source_timestamp(relative_path)
            if source_timestamp is not None:
                metadata["source_timestamp"] = source_timestamp.isoformat()
            copied_path.with_name(
                copied_path.name + self._SIDECAR_SUFFIX
            ).write_text(
                json.dumps(metadata, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

    def _download_s3_source(
        self,
        source: S3RubricMemorySource,
        destination_root: Path,
    ) -> None:
        import boto3

        s3_client = boto3.client("s3")
        for obj in source.objects:
            relative_path = self._s3_relative_path(source, obj.key)
            destination_path = destination_root / Path(*relative_path.parts)
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            s3_client.download_file(source.bucket_name, obj.key, str(destination_path))
            metadata: dict[str, Any] = {
                "scope_level": source.scope_level,
                "source_uri": f"s3://{source.bucket_name}/{obj.key}",
                "bucket_name": source.bucket_name,
                "source_key": obj.key,
            }
            source_timestamp = self.infer_source_timestamp(relative_path)
            if source_timestamp is not None:
                metadata["source_timestamp"] = source_timestamp.isoformat()
            destination_path.with_name(
                destination_path.name + self._SIDECAR_SUFFIX
            ).write_text(
                json.dumps(metadata, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

    def infer_source_timestamp(
        self,
        relative_path: Path | PurePosixPath,
    ) -> datetime | None:
        for part in reversed(relative_path.parts[:-1]):
            if not self._DATE_FOLDER_PATTERN.match(part):
                continue
            try:
                return datetime.combine(date.fromisoformat(part), time.min)
            except ValueError:
                return None
        return None

    def _validate_source(self, source: RubricMemoryCorpusSource) -> None:
        if isinstance(source, S3RubricMemorySource):
            if not source.objects:
                raise FileNotFoundError(
                    "Rubric memory knowledge-base S3 prefix does not exist or has "
                    f"no source files: s3://{source.bucket_name}/{source.prefix}"
                )
            return
        if not source.root.exists():
            raise FileNotFoundError(
                f"Rubric memory knowledge-base folder does not exist: {source.root}"
            )
        if not source.root.is_dir():
            raise NotADirectoryError(
                f"Rubric memory knowledge-base path is not a directory: {source.root}"
            )

    def _normalize_source(
        self,
        source: RubricMemoryCorpusSource,
    ) -> RubricMemoryCorpusSource:
        if isinstance(source, LocalRubricMemorySource):
            return LocalRubricMemorySource(
                root=source.root.resolve(),
                scope_level=source.scope_level,
            )
        return source

    def _s3_relative_path(
        self,
        source: S3RubricMemorySource,
        key: str,
    ) -> PurePosixPath:
        if not key.startswith(source.prefix):
            raise ValueError(
                f"S3 object key is outside rubric-memory source prefix: {key}"
            )
        return PurePosixPath(key[len(source.prefix) :])

    def _read_manifest(self, manifest_path: Path) -> dict[str, Any] | None:
        if not manifest_path.exists():
            return None
        try:
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
