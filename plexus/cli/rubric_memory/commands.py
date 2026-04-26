from __future__ import annotations

import click

from plexus.rubric_memory import (
    LocalRubricMemoryCorpusResolver,
    RubricMemoryPreparedCorpusManager,
)


@click.group(name="rubric-memory")
def rubric_memory() -> None:
    """Commands for preparing and inspecting local rubric memory."""


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
    """Prepare the canonical local rubric-memory corpus for a score."""

    paths = LocalRubricMemoryCorpusResolver().resolve(
        scorecard_name=scorecard_name,
        score_name=score_name,
    )
    prepared = RubricMemoryPreparedCorpusManager().prepare(
        corpus_sources=paths.sources,
        retriever_id=retriever_id,
        force=force,
    )

    click.echo(f"status: {prepared.status}")
    click.echo(f"retriever_id: {prepared.retriever_id}")
    click.echo(f"fingerprint: {prepared.fingerprint}")
    click.echo(f"prepared_corpus_path: {prepared.corpus_root}")
    click.echo(f"manifest_path: {prepared.manifest_path}")
    click.echo(f"source_file_count: {prepared.source_file_count}")
    click.echo(f"scorecard_knowledge_base: {paths.scorecard_knowledge_base}")
    click.echo(f"score_knowledge_base: {paths.score_knowledge_base}")
