#!/usr/bin/env python3
"""
Re-export of plexus.rca_analysis for backwards compatibility.
The canonical implementation lives in plexus/rca_analysis.py.
"""
from plexus.rca_analysis import analyze_score_result, build_feedback_context

__all__ = ["analyze_score_result", "build_feedback_context"]
