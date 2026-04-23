from plexus.cli.shared.optimizer_shadow_invalidation import (
    OPTIMIZER_SHADOW_INVALID_FIELD,
    build_feedback_target_hash,
    extract_shadow_invalid_feedback_item_ids_from_yaml_text,
    normalize_shadow_invalid_feedback_item_ids,
    normalize_shadow_invalid_field_in_yaml_text,
)


def test_normalize_shadow_invalid_feedback_item_ids_trims_dedupes_and_sorts():
    assert normalize_shadow_invalid_feedback_item_ids(
        [" z ", "a", "", None, "a", "b"]
    ) == ["a", "b", "z"]


def test_extract_shadow_invalid_feedback_item_ids_from_yaml_text_reads_top_level_field():
    yaml_text = """
name: Test
valid_classes:
  - Yes
  - No
optimizer_shadow_invalid_feedback_item_ids:
  - fb-2
  - fb-1
"""
    assert extract_shadow_invalid_feedback_item_ids_from_yaml_text(yaml_text) == ["fb-1", "fb-2"]


def test_normalize_shadow_invalid_field_in_yaml_text_rewrites_field_canonically():
    yaml_text = """
name: Test
valid_classes:
  - Yes
  - No
optimizer_shadow_invalid_feedback_item_ids:
  - fb-2
  - " fb-1 "
  - fb-2
"""
    normalized_yaml, normalized_ids = normalize_shadow_invalid_field_in_yaml_text(yaml_text)
    assert normalized_ids == ["fb-1", "fb-2"]
    assert f"{OPTIMIZER_SHADOW_INVALID_FIELD}:" in normalized_yaml
    assert "- fb-1" in normalized_yaml
    assert "- fb-2" in normalized_yaml


def test_build_feedback_target_hash_changes_when_shadow_invalid_ids_change():
    hash_a = build_feedback_target_hash(
        score_version_id="sv-1",
        days=180,
        shadow_invalid_feedback_item_ids=["fb-1"],
    )
    hash_b = build_feedback_target_hash(
        score_version_id="sv-1",
        days=180,
        shadow_invalid_feedback_item_ids=["fb-2"],
    )
    assert hash_a != hash_b
