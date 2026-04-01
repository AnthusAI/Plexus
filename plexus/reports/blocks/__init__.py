from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from .base import BaseReportBlock
from .score_info import ScoreInfo
from .feedback_analysis import FeedbackAnalysis
from .explanation_analysis import ExplanationAnalysis
from .topic_analysis import TopicAnalysis
from .cost_analysis import CostAnalysis
from .vector_topic_memory import VectorTopicMemory
from .action_items_block import ActionItems
from .feedback_contradictions import FeedbackContradictions

__all__ = [
    "BaseReportBlock",
    "ScoreInfo",
    "FeedbackAnalysis",
    "ExplanationAnalysis",
    "TopicAnalysis",
    "CostAnalysis",
    "VectorTopicMemory",
    "ActionItems",
    "FeedbackContradictions",
]
