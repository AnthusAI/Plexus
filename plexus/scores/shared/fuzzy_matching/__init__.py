"""
Shared fuzzy matching core components for Plexus score nodes.

This module provides common data structures and evaluation logic
used by both FuzzyMatchExtractor and FuzzyMatchClassifier nodes.
"""

from .core import FuzzyTarget, FuzzyTargetGroup, FuzzyMatchingEngine

__all__ = ["FuzzyTarget", "FuzzyTargetGroup", "FuzzyMatchingEngine"]