from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from plexus.cli.shared.shared import get_score_yaml_path


@dataclass(frozen=True)
class LocalRubricMemorySource:
    """A local rubric-memory corpus folder with its score hierarchy scope."""

    root: Path
    scope_level: str


@dataclass(frozen=True)
class LocalRubricMemoryCorpusPaths:
    """Convention-derived local rubric-memory paths for one score."""

    scorecard_root: Path
    scorecard_knowledge_base: Path
    score_knowledge_base: Path

    @property
    def sources(self) -> list[LocalRubricMemorySource]:
        return [
            LocalRubricMemorySource(
                root=self.scorecard_knowledge_base,
                scope_level="scorecard",
            ),
            LocalRubricMemorySource(
                root=self.score_knowledge_base,
                scope_level="score",
            ),
        ]


class LocalRubricMemoryCorpusResolver:
    """Resolve rubric-memory folders using the existing pulled-score convention."""

    def resolve(
        self,
        *,
        scorecard_name: str,
        score_name: str,
    ) -> LocalRubricMemoryCorpusPaths:
        score_yaml_path = get_score_yaml_path(scorecard_name, score_name)
        scorecard_root = score_yaml_path.parent
        return LocalRubricMemoryCorpusPaths(
            scorecard_root=scorecard_root,
            scorecard_knowledge_base=scorecard_root / "scorecard.knowledge-base",
            score_knowledge_base=score_yaml_path.with_suffix(".knowledge-base"),
        )
