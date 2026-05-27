#!/usr/bin/env python3
"""Read-only scanner for sensitive client references in the Plexus repo."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence


DEFAULT_ALLOWLIST = ("Call Criteria", "Capacity")
DEFAULT_EXCLUDES = ("project/", "skills/client-redaction/")
CLIENT_WORK_CUES = (
    r"\bclient[- ]specific\b",
    r"\bcustomer[- ]specific\b",
    r"\bprospect[- ]specific\b",
    r"\baccount[- ]specific\b",
    r"\bclient work\b",
    r"\bcustomer work\b",
    r"\bclient implementation\b",
    r"\bcustomer implementation\b",
    r"\bclient integration\b",
    r"\bcustomer integration\b",
    r"\bclient deployment\b",
    r"\bcustomer deployment\b",
    r"\bproduction incident\b",
    r"\bsupport case\b",
    r"\bprivate scorecard\b",
    r"\bcustomer scorecard\b",
    r"\bclient scorecard\b",
    r"\btenant[- ]specific\b",
    r"\bpilot customer\b",
)


@dataclass(frozen=True)
class Finding:
    source: str
    kind: str
    pattern: str
    line: int
    text: str


def run_git(args: Sequence[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout


def load_terms(raw_terms: Sequence[str], terms_file: Path | None) -> list[str]:
    terms = [term.strip() for term in raw_terms if term.strip()]
    if terms_file:
        for line in terms_file.read_text(encoding="utf-8").splitlines():
            term = line.strip()
            if term and not term.startswith("#"):
                terms.append(term)
    deduped: list[str] = []
    seen: set[str] = set()
    for term in terms:
        key = term.casefold()
        if key not in seen:
            deduped.append(term)
            seen.add(key)
    return deduped


def tracked_files(include_untracked: bool) -> list[Path]:
    files = [Path(path) for path in run_git(["ls-files", "-z"]).split("\0") if path]
    if include_untracked:
        files.extend(
            Path(path)
            for path in run_git(["ls-files", "-z", "--others", "--exclude-standard"]).split("\0")
            if path
        )
    return files


def read_text(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if b"\0" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def compile_literal_terms(terms: Iterable[str], allowlist: Iterable[str]) -> list[tuple[str, re.Pattern[str]]]:
    allowlisted = {term.casefold() for term in allowlist}
    patterns: list[tuple[str, re.Pattern[str]]] = []
    for term in terms:
        if term.casefold() in allowlisted:
            continue
        escaped = re.escape(term)
        patterns.append((term, re.compile(rf"(?<![\w-]){escaped}(?![\w-])", re.IGNORECASE)))
    return patterns


def scan_text(
    source: str,
    text: str,
    term_patterns: Sequence[tuple[str, re.Pattern[str]]],
    cue_patterns: Sequence[tuple[str, re.Pattern[str]]],
) -> list[Finding]:
    findings: list[Finding] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        for term, pattern in term_patterns:
            if pattern.search(line):
                findings.append(Finding(source, "literal-term", term, line_number, stripped))
        for cue, pattern in cue_patterns:
            if pattern.search(line):
                findings.append(Finding(source, "client-work-cue", cue, line_number, stripped))
    return findings


def git_log_text(rev_range: str | None) -> str:
    args = ["log", "--format=commit %H%nsubject %s%nbody %b%n"]
    if rev_range:
        args.insert(1, rev_range)
    else:
        args.insert(1, "--all")
    return run_git(args)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--term", action="append", default=[], help="Sensitive term to scan for.")
    parser.add_argument("--terms-file", type=Path, help="Newline-delimited sensitive terms file.")
    parser.add_argument(
        "--allow",
        action="append",
        default=list(DEFAULT_ALLOWLIST),
        help="Allowed sponsor/public term. Defaults to Call Criteria and Capacity.",
    )
    parser.add_argument("--include-untracked", action="store_true", help="Scan untracked non-ignored files.")
    parser.add_argument("--include-git-log", action="store_true", help="Scan Git commit subjects and bodies.")
    parser.add_argument("--rev-range", help="Optional Git revision range for --include-git-log.")
    parser.add_argument("--no-cues", action="store_true", help="Only scan supplied literal terms.")
    parser.add_argument(
        "--exclude",
        action="append",
        default=list(DEFAULT_EXCLUDES),
        help="Path prefix to skip. Defaults to the client-redaction skill itself.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    return parser.parse_args(argv)


def is_excluded(path: Path, prefixes: Iterable[str]) -> bool:
    normalized = path.as_posix()
    return any(normalized.startswith(prefix) for prefix in prefixes)


def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)
    terms = load_terms(args.term, args.terms_file)
    term_patterns = compile_literal_terms(terms, args.allow)
    cue_patterns = [] if args.no_cues else [(cue, re.compile(cue, re.IGNORECASE)) for cue in CLIENT_WORK_CUES]

    findings: list[Finding] = []
    for path in tracked_files(args.include_untracked):
        if is_excluded(path, args.exclude):
            continue
        text = read_text(path)
        if text is None:
            continue
        findings.extend(scan_text(str(path), text, term_patterns, cue_patterns))

    if args.include_git_log:
        findings.extend(scan_text("git-log", git_log_text(args.rev_range), term_patterns, cue_patterns))

    if args.json:
        json.dump([asdict(finding) for finding in findings], sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        for finding in findings:
            print(
                f"{finding.source}:{finding.line}: "
                f"{finding.kind} {finding.pattern!r}: {finding.text}"
            )
        print(f"{len(findings)} finding(s)")

    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
