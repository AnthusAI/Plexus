import json
import os
import subprocess
import threading
from typing import Dict, List, Optional, Set, Tuple

from plexus.CustomLogging import logging
from plexus.scores.Score import Score
from plexus.scores.SourceSpanOverlapScore import _spans_overlap


class SubjectSpanOverlapScore(Score):
    """
    Programmatic detector that scores Items when a finding matches both
    metadata.subjectKey and overlapping source-file spans.
    """

    @classmethod
    async def create(cls, **parameters):
        """Async factory used by Scorecard when loading YAML/API configurations."""
        return cls(**parameters)

    def __init__(
        self,
        scorecard_name=None,
        score_name=None,
        findings: Optional[List[dict]] = None,
        files_scanned: Optional[List[str]] = None,
        findings_command: Optional[str] = None,
        source_root: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(scorecard_name=scorecard_name, score_name=score_name, **kwargs)
        self._injected_findings = findings
        self._injected_files_scanned = files_scanned
        self._findings_command = findings_command or os.environ.get(
            "PLEXUS_SOURCE_FINDINGS_COMMAND"
        )
        self._source_root_param = source_root
        self._cache: Dict[str, Tuple[List[dict], Set[str]]] = {}
        self._lock = threading.Lock()

    def load_context(self, context=None):
        pass

    def predict_validation(self):
        pass

    def register_model(self):
        pass

    def save_model(self):
        pass

    async def predict(self, model_input: Score.Input, **_kwargs) -> Score.Result:
        metadata = model_input.metadata or {}
        subject_key = metadata.get("subjectKey")
        file_path = metadata.get("filePath")
        start_line = metadata.get("startLine")
        end_line = metadata.get("endLine")
        score_name = self.parameters.name or "SubjectSpanOverlapScore"

        if subject_key is None:
            raise Score.SkippedScoreException(
                score_name,
                "Item metadata missing subjectKey",
            )

        if file_path is None or start_line is None or end_line is None:
            raise Score.SkippedScoreException(
                score_name,
                "Item metadata missing filePath, startLine, or endLine",
            )

        source_root = metadata.get("sourceRoot") or self._source_root_param or ""
        findings, inventory = self._get_findings_and_inventory(source_root)

        if file_path not in inventory:
            raise Score.SkippedScoreException(
                score_name,
                f"File '{file_path}' was not in the scanned file inventory",
            )

        expected_labels = metadata.get("expectedLabels")

        for finding in findings:
            if finding.get("subjectKey") != subject_key:
                continue
            if finding.get("filePath") != file_path:
                continue
            finding_start = finding.get("startLine")
            finding_end = finding.get("endLine")
            if finding_start is None or finding_end is None:
                continue
            if not _spans_overlap(
                int(start_line), int(end_line), int(finding_start), int(finding_end)
            ):
                continue
            if expected_labels is not None and not self._labels_match(
                finding.get("labels"), expected_labels
            ):
                continue
            return self._make_result("Yes")

        return self._make_result("No")

    @staticmethod
    def _labels_match(finding_labels, expected_labels) -> bool:
        if not isinstance(expected_labels, (list, tuple, set)):
            return False
        if finding_labels is None:
            return False
        finding_set = set(finding_labels)
        return set(expected_labels).issubset(finding_set)

    def _make_result(self, value: str) -> Score.Result:
        return Score.Result(
            score_name=self.parameters.name,
            parameters=self.parameters,
            value=value,
        )

    def _get_findings_and_inventory(self, source_root: str) -> Tuple[List[dict], Set[str]]:
        with self._lock:
            if source_root in self._cache:
                return self._cache[source_root]

            findings, files_scanned = self._load_findings(source_root)
            inventory = self._build_inventory(findings, files_scanned)
            self._cache[source_root] = (findings, inventory)
            return findings, inventory

    def _load_findings(self, source_root: str) -> Tuple[List[dict], Optional[List[str]]]:
        if self._injected_findings is not None:
            return list(self._injected_findings), self._injected_files_scanned

        if not self._findings_command:
            logging.warning(
                "SubjectSpanOverlapScore has no injected findings and no findings_command"
            )
            return [], self._injected_files_scanned

        command = self._findings_command.format(root=source_root)
        completed = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(completed.stdout)
        findings = payload.get("findings", [])
        files_scanned = payload.get("filesScanned")
        return findings, files_scanned

    @staticmethod
    def _build_inventory(
        findings: List[dict], files_scanned: Optional[List[str]]
    ) -> Set[str]:
        if files_scanned is not None:
            return set(files_scanned)
        return {finding["filePath"] for finding in findings if finding.get("filePath")}
