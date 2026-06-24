"""Validation for Plexus classifier guidelines markdown."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class ValidationResult:
    is_valid: bool
    classifier_type: str | None
    missing_sections: list[str]
    found_sections: list[str]
    messages: list[str]
    unknown_sections: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_markdown_sections(content: str) -> dict[str, str]:
    sections = {}
    current_section = None
    current_content = []

    for line in content.split("\n"):
        header_match = re.match(r"^#+\s+(.+)$", line)
        if header_match:
            if current_section:
                sections[current_section] = "\n".join(current_content).strip()
            current_section = header_match.group(1)
            current_content = []
        elif current_section:
            current_content.append(line)

    if current_section:
        sections[current_section] = "\n".join(current_content).strip()

    return sections


def extract_classes_metadata(classes_content: str) -> dict[str, Any]:
    metadata = {}

    valid_labels_match = re.search(r"Valid labels:\s*\[([^\]]+)\]", classes_content)
    if valid_labels_match:
        labels = [label.strip() for label in valid_labels_match.group(1).split(",")]
        metadata["valid_labels"] = labels

    target_match = re.search(r"Target class:\s*(\w+)", classes_content)
    if target_match:
        metadata["target_class"] = target_match.group(1)

    default_match = re.search(r"Default class:\s*(\w+)", classes_content)
    if default_match:
        metadata["default_class"] = default_match.group(1)

    abstain_match = re.search(r"Abstain class:\s*(\w+)", classes_content)
    if abstain_match:
        metadata["abstain_class"] = abstain_match.group(1)

    return metadata


def determine_classifier_type(sections: dict[str, str]) -> tuple[str | None, list[str]]:
    messages = []

    if "Classes" not in sections:
        messages.append("Cannot determine classifier type: 'Classes' section not found")
        return None, messages

    classes_metadata = extract_classes_metadata(sections["Classes"])

    if "valid_labels" not in classes_metadata:
        messages.append("Cannot determine classifier type: Valid labels not found in Classes section")
        return None, messages

    valid_labels = classes_metadata["valid_labels"]
    num_labels = len(valid_labels)
    abstention_labels = {"NA", "N/A", "Unknown", "Unclear", "Abstain", "Inconclusive"}

    if num_labels == 2:
        if "abstain_class" in classes_metadata:
            messages.append("Detected binary classifier with abstentions (2 labels + abstain class)")
            return "binary_with_abstentions", messages
        messages.append("Detected binary classifier")
        return "binary", messages
    if num_labels == 3:
        has_abstention_label = any(label in abstention_labels for label in valid_labels)
        if "abstain_class" in classes_metadata or has_abstention_label:
            messages.append("Detected binary classifier with abstentions (Yes/No/NA pattern)")
            return "binary_with_abstentions", messages
        messages.append("Detected multi-class classifier with 3 classes")
        return "multi_class", messages
    if num_labels > 3:
        messages.append(f"Detected multi-class classifier with {num_labels} classes")
        return "multi_class", messages

    messages.append(f"Invalid classifier: only {num_labels} label(s) found")
    return None, messages


def get_required_sections(classifier_type: str, classes_metadata: dict[str, Any]) -> list[str]:
    if classifier_type == "binary":
        labels = classes_metadata.get("valid_labels", [])
        if labels:
            normalized = [label.strip().lower() for label in labels]
            if set(normalized) != {"yes", "no"}:
                required = ["Objective", "Classes"]
                for label in labels:
                    required.append(f"Definition of {label}")
                    required.append(f"Conditions for {label}")
                return required
        return [
            "Objective",
            "Classes",
            "Definition of Yes",
            "Conditions for Yes",
            "Definition of No",
            "Conditions for No",
        ]

    if classifier_type == "binary_with_abstentions":
        return [
            "Objective",
            "Classes",
            "Definition of No",
            "Conditions for No",
            "Definition of NA",
            "Conditions for NA",
            "Definition of Yes",
        ]

    if classifier_type == "multi_class":
        required = ["Objective", "Classes"]
        if "valid_labels" in classes_metadata:
            for label in classes_metadata["valid_labels"]:
                required.append(f"Definition of {label}")
                required.append(f"Conditions for {label}")
        return required

    return []


def get_optional_sections(classifier_type: str, classes_metadata: dict[str, Any]) -> set[str]:
    optional = {"Examples", "Boundary Cases"}

    if classifier_type == "binary":
        optional.update({"Clear Yes Cases", "Clear No Cases"})

    elif classifier_type == "binary_with_abstentions":
        optional.update({"Clear Yes Cases", "Clear No Cases", "Clear NA Cases"})

    elif classifier_type == "multi_class":
        optional.add("Boundary Conditions")
        if "valid_labels" in classes_metadata:
            labels = classes_metadata["valid_labels"]
            for label in labels:
                optional.add(f"Clear {label} Cases")
            for i, label1 in enumerate(labels):
                for label2 in labels[i + 1 :]:
                    optional.add(f"{label1} vs {label2}")

    return optional


def find_unknown_sections(
    found_sections: list[str],
    required_sections: list[str],
    optional_sections: set[str],
) -> list[str]:
    return [
        section
        for section in found_sections
        if section not in required_sections and section not in optional_sections
    ]


def validate_guidelines_content(content: str) -> ValidationResult:
    messages = []

    title_match = re.match(r"^#\s+(.+)$", content, re.MULTILINE)
    document_title = None
    if not title_match:
        messages.append("Warning: No top-level title (# Classifier Name) found")
    else:
        document_title = title_match.group(1).strip()

    sections = parse_markdown_sections(content)
    found_sections = list(sections.keys())
    sections_for_validation = [
        section for section in found_sections if section != document_title
    ]

    classifier_type, type_messages = determine_classifier_type(sections)
    messages.extend(type_messages)

    if not classifier_type:
        return ValidationResult(
            is_valid=False,
            classifier_type=None,
            missing_sections=[],
            found_sections=found_sections,
            messages=messages,
            unknown_sections=[],
        )

    classes_metadata = extract_classes_metadata(sections.get("Classes", ""))
    required_sections = get_required_sections(classifier_type, classes_metadata)
    optional_sections = get_optional_sections(classifier_type, classes_metadata)

    missing_sections = [
        section for section in required_sections if section not in sections
    ]
    unknown_sections = find_unknown_sections(
        sections_for_validation,
        required_sections,
        optional_sections,
    )

    if classifier_type in {"binary", "binary_with_abstentions"}:
        if "target_class" not in classes_metadata:
            messages.append("Warning: Target class not specified in Classes section")
        if "default_class" not in classes_metadata:
            messages.append("Warning: Default class not specified in Classes section")

    if classifier_type == "binary_with_abstentions" and "abstain_class" not in classes_metadata:
        messages.append("Warning: Abstain class not specified in Classes section")

    for section in unknown_sections:
        messages.append(f"Warning: '{section}' is a non-standard section")

    is_valid = len(missing_sections) == 0
    if is_valid:
        messages.append("✓ All required sections present")
    else:
        messages.append(f"✗ Missing {len(missing_sections)} required section(s)")

    return ValidationResult(
        is_valid=is_valid,
        classifier_type=classifier_type,
        missing_sections=missing_sections,
        found_sections=found_sections,
        messages=messages,
        unknown_sections=unknown_sections,
    )


def validate_guidelines_file(filepath: Path) -> ValidationResult:
    if not filepath.exists():
        return ValidationResult(
            is_valid=False,
            classifier_type=None,
            missing_sections=[],
            found_sections=[],
            messages=[f"File not found: {filepath}"],
            unknown_sections=[],
        )

    return validate_guidelines_content(filepath.read_text(encoding="utf-8"))
