import importlib
from types import ModuleType

import plexus.scores as score_namespace


def test_resolve_score_class_ignores_same_named_cached_submodule():
    """Feature: lazy score class resolution

    Scenario: Python cached the score submodule on the package
      Given the package attribute is the same-named module
      When the configured score class is resolved
      Then the resolver returns the class exported by that module
    """
    score_module = importlib.import_module("plexus.scores.LangGraphScore")
    assert isinstance(score_namespace.LangGraphScore, ModuleType)

    resolved = score_namespace.resolve_score_class("LangGraphScore")

    assert resolved is score_module.LangGraphScore
