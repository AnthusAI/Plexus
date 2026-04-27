from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from plexus.cli.shared.shared import get_score_yaml_path, sanitize_path_name


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
    prefix_knowledge_bases: list[Path]
    score_knowledge_base: Path

    @property
    def sources(self) -> list[LocalRubricMemorySource]:
        sources = [
            LocalRubricMemorySource(
                root=self.scorecard_knowledge_base,
                scope_level="scorecard",
            ),
            *[
                LocalRubricMemorySource(root=prefix_root, scope_level="prefix")
                for prefix_root in self.prefix_knowledge_bases
            ],
        ]
        if self.score_knowledge_base.exists() or not self.prefix_knowledge_bases:
            sources.append(
                LocalRubricMemorySource(
                    root=self.score_knowledge_base,
                    scope_level="score",
                )
            )
        return sources


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
            prefix_knowledge_bases=self._matching_prefix_knowledge_bases(
                scorecard_root=scorecard_root,
                score_name=score_name,
                score_knowledge_base=score_yaml_path.with_suffix(".knowledge-base"),
            ),
            score_knowledge_base=score_yaml_path.with_suffix(".knowledge-base"),
        )

    def _matching_prefix_knowledge_bases(
        self,
        *,
        scorecard_root: Path,
        score_name: str,
        score_knowledge_base: Path,
    ) -> list[Path]:
        if not scorecard_root.exists():
            return []

        sanitized_score_name = sanitize_path_name(score_name)
        candidates: list[Path] = []
        for knowledge_base in scorecard_root.glob("*.knowledge-base"):
            if not knowledge_base.is_dir():
                continue
            if knowledge_base.name == "scorecard.knowledge-base":
                continue
            if knowledge_base == score_knowledge_base:
                continue
            if self._is_prefix_match(
                prefix=knowledge_base.stem,
                sanitized_score_name=sanitized_score_name,
            ):
                candidates.append(knowledge_base)

        return sorted(candidates, key=lambda path: (-len(path.stem), path.name))

    def _is_prefix_match(self, *, prefix: str, sanitized_score_name: str) -> bool:
        if not prefix or not sanitized_score_name.startswith(prefix):
            return False
        if len(sanitized_score_name) == len(prefix):
            return False
        boundary = sanitized_score_name[len(prefix)]
        return boundary in {" ", "-", "("}
