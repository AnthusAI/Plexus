"""Tests for Tactus template validation rules in procedure service."""

import yaml

from plexus.cli.procedure.service import _validate_yaml_template


def test_validate_tactus_template_accepts_scorecard_create():
    """Known scorecard_create procedure should validate as Tactus."""
    with open("plexus/procedures/scorecard_create.yaml", "r", encoding="utf-8") as f:
        data = yaml.safe_load(f.read())

    assert _validate_yaml_template(data) is True


def test_validate_tactus_template_accepts_score_code_create():
    """Known score_code_create procedure should validate as Tactus."""
    with open("plexus/procedures/score_code_create.yaml", "r", encoding="utf-8") as f:
        data = yaml.safe_load(f.read())

    assert _validate_yaml_template(data) is True


def test_validate_tactus_template_rejects_workflow_field():
    """Tactus definitions should reject legacy workflow field."""
    data = {
        "name": "legacy_like",
        "version": "1.0.0",
        "class": "Tactus",
        "code": "return { success = true }",
        "workflow": "return { success = true }",
    }

    assert _validate_yaml_template(data) is False


def test_validate_tactus_template_rejects_luadsl_class():
    """LuaDSL class should be rejected."""
    data = {
        "name": "legacy",
        "version": "1.0.0",
        "class": "LuaDSL",
        "code": "return { success = true }",
    }

    assert _validate_yaml_template(data) is False
