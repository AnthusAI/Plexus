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


def __getattr__(name: str):
    module_name = _CLASS_MODULES.get(name)
    if not module_name:
        raise AttributeError(f"module 'plexus.scores' has no attribute {name!r}")

    module = import_module(module_name)
    value = getattr(module, name)
    globals()[name] = value
    return value


__all__ = ["Score", *_CLASS_MODULES.keys()]
