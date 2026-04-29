from __future__ import annotations

import asyncio
import contextlib
import io
import json
import os
from pathlib import Path

import click
import yaml

from plexus.cli.shared.client_utils import create_client
from plexus.cli.shared.memoized_resolvers import (
    memoized_resolve_score_identifier,
    memoized_resolve_scorecard_identifier,
)
from plexus.cli.shared.shared import sanitize_path_name
from plexus.rubric_memory import (
    LocalRubricMemoryCorpusResolver,
    RUBRIC_MEMORY_BUCKET_ENV_VAR,
    RubricMemoryPreparedCorpusManager,
    RubricMemoryRecentBriefingProvider,
    S3RubricMemoryCorpusResolver,
)


@click.group(name="rubric-memory")
def rubric_memory() -> None:
    """Commands for syncing and preparing rubric memory."""


@rubric_memory.command(name="sync")
@click.option("--scorecard", "scorecard_name", required=True, help="Scorecard name.")
@click.option("--score", "score_name", help="Optional score name.")
def sync(
    *,
    scorecard_name: str,
    score_name: str | None,
) -> None:
    """Upload local .knowledge-base folders to the rubric-memory S3 bucket."""

    bucket_name = _rubric_memory_bucket_name()
    local_roots = _local_sync_roots(
        scorecard_name=scorecard_name,
        score_name=score_name,
    )
    import boto3

    s3_client = boto3.client("s3")
    uploaded = 0
    for root in local_roots:
        for source_file in _source_files(root):
            key = _s3_key_for_local_source(
                scorecard_name=scorecard_name,
                source_file=source_file,
            )
            s3_client.upload_file(str(source_file), bucket_name, key)
            uploaded += 1
    click.echo(f"bucket: {bucket_name}")
    click.echo(f"uploaded_file_count: {uploaded}")
    for root in local_roots:
        click.echo(f"synced_knowledge_base: {root}")


@rubric_memory.command(name="prewarm")
@click.option("--scorecard", "scorecard_name", required=True, help="Scorecard name.")
@click.option("--score", "score_name", required=True, help="Score name.")
@click.option(
    "--retriever-id",
    default="scan",
    show_default=True,
    help="Biblicus retriever id.",
)
@click.option(
    "--force",
    is_flag=True,
    help="Rebuild the prepared corpus even if the fingerprint matches.",
)
def prewarm(
    *,
    scorecard_name: str,
    score_name: str,
    retriever_id: str,
    force: bool,
) -> None:
    """Prepare the canonical S3 rubric-memory corpus for a score."""

    _rubric_memory_bucket_name()
    paths = S3RubricMemoryCorpusResolver().resolve(
        scorecard_name=scorecard_name,
        score_name=score_name,
    )
    prepared = RubricMemoryPreparedCorpusManager().prepare(
        corpus_sources=paths.sources,
        retriever_id=retriever_id,
        force=force,
    )

    click.echo(f"status: {prepared.status}")
    click.echo(f"bucket: {paths.bucket_name}")
    click.echo(f"retriever_id: {prepared.retriever_id}")
    click.echo(f"fingerprint: {prepared.fingerprint}")
    click.echo(f"prepared_corpus_path: {prepared.corpus_root}")
    click.echo(f"manifest_path: {prepared.manifest_path}")
    click.echo(f"source_file_count: {prepared.source_file_count}")
    for source in paths.sources:
        click.echo(
            f"included_knowledge_base[{source.scope_level}]: "
            f"s3://{source.bucket_name}/{source.prefix} "
            f"({len(source.objects)} files)"
        )
    click.echo(
        f"scorecard_knowledge_base: "
        f"s3://{paths.bucket_name}/{paths.scorecard_knowledge_base_prefix}"
    )
    for prefix_knowledge_base in paths.prefix_knowledge_base_prefixes:
        click.echo(
            f"prefix_knowledge_base: s3://{paths.bucket_name}/{prefix_knowledge_base}"
        )
    click.echo(
        f"score_knowledge_base: "
        f"s3://{paths.bucket_name}/{paths.score_knowledge_base_prefix}"
    )


@rubric_memory.command(name="recent")
@click.option("--scorecard", "scorecard_name", required=True, help="Scorecard name.")
@click.option("--score", "score_name", required=True, help="Score name.")
@click.option(
    "--days",
    type=int,
    default=RubricMemoryRecentBriefingProvider.DEFAULT_DAYS,
    show_default=True,
    help="Trailing source-date window.",
)
@click.option("--since", help="Inclusive source date in YYYY-MM-DD.")
@click.option("--query", default="", help="Optional topic query.")
@click.option("--limit", type=int, default=16, show_default=True)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["markdown", "json", "yaml"]),
    default="markdown",
    show_default=True,
)
def recent(
    *,
    scorecard_name: str,
    score_name: str,
    days: int,
    since: str | None,
    query: str,
    limit: int,
    output_format: str,
) -> None:
    """Retrieve recent rubric-memory entries for optimizer preflight review."""

    _rubric_memory_bucket_name()
    client = create_client()
    with contextlib.redirect_stdout(io.StringIO()):
        scorecard_id = memoized_resolve_scorecard_identifier(client, scorecard_name)
        score_id = (
            memoized_resolve_score_identifier(client, scorecard_id, score_name)
            if scorecard_id
            else None
        )
    if not scorecard_id:
        raise click.ClickException(f"Could not resolve scorecard: {scorecard_name}")
    if not score_id:
        raise click.ClickException(
            f"Could not resolve score '{score_name}' in scorecard '{scorecard_name}'"
        )

    context = asyncio.run(
        RubricMemoryRecentBriefingProvider(api_client=client).retrieve_recent(
            scorecard_identifier=scorecard_name,
            score_identifier=score_name,
            score_id=score_id,
            query=query,
            days=days,
            since=since,
            limit=limit,
        )
    )
    payload = {
        "markdown_context": context.markdown_context,
        "citation_index": [
            citation.model_dump(mode="json") for citation in context.citation_index
        ],
        "machine_context": context.machine_context,
        "diagnostics": context.diagnostics,
    }
    if output_format == "json":
        click.echo(json.dumps(payload, indent=2, default=str))
    elif output_format == "yaml":
        click.echo(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True))
    else:
        click.echo(context.markdown_context)


def _rubric_memory_bucket_name() -> str:
    bucket_name = os.environ.get(RUBRIC_MEMORY_BUCKET_ENV_VAR)
    if not bucket_name:
        raise click.ClickException(
            f"Missing required environment variable: {RUBRIC_MEMORY_BUCKET_ENV_VAR}"
        )
    return bucket_name


def _local_scorecard_root(scorecard_name: str) -> Path:
    return Path(os.environ.get("SCORECARD_CACHE_DIR", "scorecards")) / sanitize_path_name(
        scorecard_name
    )


def _local_sync_roots(
    *,
    scorecard_name: str,
    score_name: str | None,
) -> list[Path]:
    scorecard_root = _local_scorecard_root(scorecard_name)
    if not scorecard_root.is_dir():
        raise click.ClickException(
            f"Local scorecard folder does not exist: {scorecard_root}"
        )
    if score_name:
        paths = LocalRubricMemoryCorpusResolver().resolve(
            scorecard_name=scorecard_name,
            score_name=score_name,
        )
        roots = [
            paths.scorecard_knowledge_base,
            *paths.prefix_knowledge_bases,
            paths.score_knowledge_base,
        ]
    else:
        roots = sorted(
            path
            for path in scorecard_root.glob("*.knowledge-base")
            if path.is_dir()
        )
    if not roots:
        raise click.ClickException(
            f"No local .knowledge-base folders found under {scorecard_root}"
        )
    missing = [root for root in roots if not root.is_dir()]
    if missing:
        raise click.ClickException(
            "Missing local .knowledge-base folders: "
            + ", ".join(str(root) for root in missing)
        )
    return roots


def _source_files(root: Path) -> list[Path]:
    ignored_dirs = {
        ".biblicus",
        "analysis",
        "extracted",
        "graph",
        "metadata",
        "retrieval",
    }
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.name.endswith(".biblicus.yml"):
            continue
        if any(part in ignored_dirs for part in path.relative_to(root).parts):
            continue
        files.append(path)
    return files


def _s3_key_for_local_source(
    *,
    scorecard_name: str,
    source_file: Path,
) -> str:
    scorecard_root = _local_scorecard_root(scorecard_name)
    relative_path = source_file.relative_to(scorecard_root).as_posix()
    return f"{sanitize_path_name(scorecard_name)}/{relative_path}"
