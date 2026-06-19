from __future__ import annotations

import pytest

from plexus.guidelines.validator import validate_guidelines_content

pytestmark = pytest.mark.unit


VALID_BINARY_GUIDELINES = """# Spam Classifier

## Objective

Detect spam messages in customer communications.

## Classes
- Valid labels: [Yes, No]
- Target class: Yes
- Default class: No

## Definition of Yes

Messages that are unsolicited commercial content or malicious.

## Conditions for Yes

- Contains promotional language

## Definition of No

Legitimate customer communications.

## Conditions for No

- Message is service-related
"""


def test_validate_guidelines_content_passes_valid_binary_guidelines() -> None:
    result = validate_guidelines_content(VALID_BINARY_GUIDELINES)

    assert result.is_valid is True
    assert result.classifier_type == "binary"
    assert result.missing_sections == []
    assert "Classes" in result.found_sections


def test_validate_guidelines_content_fails_missing_required_section() -> None:
    content = VALID_BINARY_GUIDELINES.replace(
        "## Conditions for No\n\n- Message is service-related\n",
        "",
    )

    result = validate_guidelines_content(content)

    assert result.is_valid is False
    assert result.missing_sections == ["Conditions for No"]
    assert any("Missing 1 required section" in message for message in result.messages)


def test_validate_guidelines_content_warns_for_unknown_sections_without_failing() -> None:
    result = validate_guidelines_content(
        VALID_BINARY_GUIDELINES + "\n## Nonstandard Notes\n\nOperational notes.\n"
    )

    assert result.is_valid is True
    assert result.unknown_sections == ["Nonstandard Notes"]
    assert any("non-standard section" in message for message in result.messages)


def test_validate_guidelines_content_requires_per_label_sections_for_custom_binary_labels() -> None:
    content = """# Outcome Classifier

## Objective

Classify outcomes.

## Classes
- Valid labels: [Pass, Fail]
- Target class: Pass
- Default class: Fail

## Definition of Pass

Passing outcomes.

## Conditions for Pass

- Meets the criteria.

## Definition of Fail

Failing outcomes.
"""

    result = validate_guidelines_content(content)

    assert result.is_valid is False
    assert result.classifier_type == "binary"
    assert result.missing_sections == ["Conditions for Fail"]
