"""
The `plexus` module is an orchestration system for AI/ML classification at scale. It provides a way to configure classifiers, manage hyperparameters for training, handle training and evaluation, and deploy models to production. It supports running sequences of LLM API requests, machine-learning models for inference, and numerical or heuristic methods for scoring.
"""

import warnings
warnings.filterwarnings(
    "ignore",
    message="Field \"model_.*\" .* has conflict with protected namespace \"model_\".*"
)

from .Evaluation import Evaluation
from .PromptTemplateLoader import PromptTemplateLoader
from .Scorecard import Scorecard
from .ScorecardResults import ScorecardResults
from .ScorecardResultsAnalysis import ScorecardResultsAnalysis

from ._version import __version__