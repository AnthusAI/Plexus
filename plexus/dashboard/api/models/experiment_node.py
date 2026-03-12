"""
Backward compatibility module for ExperimentNode model.
This module provides imports for the renamed GraphNode model to maintain compatibility.
"""

# Import the new model with the old name for backward compatibility
from .graph_node import GraphNode as ExperimentNode

# Re-export for backward compatibility
__all__ = ['ExperimentNode']