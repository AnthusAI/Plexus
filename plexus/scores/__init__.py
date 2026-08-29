"""
Score class namespace.

Scorecard loading resolves score classes dynamically with
``getattr(plexus.scores, class_name)``. Keep that behavior, but do not import
every score implementation at package import time. Many score types require
optional training, ML, provider, or workflow dependencies that should only load
when that score class is selected.
"""

from importlib import import_module

from plexus.scores.Score import Score


_SCORE_CLASS_MODULES = {
    "AgenticExtractor": "plexus.scores.AgenticExtractor",
    "AgenticValidator": "plexus.scores.AgenticValidator",
    "AWSComprehendEntityExtractor": "plexus.scores.AWSComprehendEntityExtractor",
    "AWSComprehendSentimentScore": "plexus.scores.AWSComprehendSentimentScore",
    "CompositeScore": "plexus.scores.CompositeScore",
    "DeepLearningOneStepSemanticClassifier": (
        "plexus.scores.DeepLearningOneStepSemanticClassifier"
    ),
    "DeepLearningSemanticClassifier": "plexus.scores.DeepLearningSemanticClassifier",
    "DeepLearningSlidingWindowSemanticClassifier": (
        "plexus.scores.DeepLearningSlidingWindowSemanticClassifier"
    ),
    "ExplainableClassifier": "plexus.scores.ExplainableClassifier",
    "FastTextClassifier": "plexus.scores.FastTextClassifier",
    "KeywordClassifier": "plexus.scores.KeywordClassifier",
    "LangGraphScore": "plexus.scores.LangGraphScore",
    "OpenAIEmbeddingsClassifier": "plexus.scores.OpenAIEmbeddingsClassifier",
    "SourceSpanOverlapScore": "plexus.scores.SourceSpanOverlapScore",
    "SubjectIdentityScore": "plexus.scores.SubjectIdentityScore",
    "SubjectSpanOverlapScore": "plexus.scores.SubjectSpanOverlapScore",
    "SVMClassifier": "plexus.scores.SVMClassifier",
    "TactusScore": "plexus.scores.TactusScore",
}

_NODE_CLASS_MODULES = {
    "BeforeAfterSlicer": "plexus.scores.nodes.BeforeAfterSlicer",
    "Classifier": "plexus.scores.nodes.Classifier",
    "ContextExtractor": "plexus.scores.nodes.ContextExtractor",
    "Extractor": "plexus.scores.nodes.Extractor",
    "Generator": "plexus.scores.nodes.Generator",
    "LogicalClassifier": "plexus.scores.nodes.LogicalClassifier",
    "MultiClassClassifier": "plexus.scores.nodes.MultiClassClassifier",
    "NumericClassifier": "plexus.scores.nodes.NumericClassifier",
    "YesOrNoClassifier": "plexus.scores.nodes.YesOrNoClassifier",
}

_CLASS_MODULES = {
    **_SCORE_CLASS_MODULES,
    **_NODE_CLASS_MODULES,
}


def resolve_score_class(name: str):
    """Resolve a configured score class without trusting package attributes.

    Importing ``plexus.scores.<ClassName>`` makes Python cache that submodule on
    this package under ``ClassName``.  Looking up the package attribute after
    that point returns the module instead of invoking ``__getattr__``.  Resolve
    through the explicit module map so registry behavior is import-order safe.
    """
    module_name = _CLASS_MODULES.get(name)
    if not module_name:
        raise AttributeError(f"module 'plexus.scores' has no attribute {name!r}")

    module = import_module(module_name)
    return getattr(module, name)


def __getattr__(name: str):
    value = resolve_score_class(name)
    globals()[name] = value
    return value


__all__ = ["Score", "resolve_score_class", *_CLASS_MODULES.keys()]
