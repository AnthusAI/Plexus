"""
Backward compatibility module for ExperimentTemplate model.
This module provides imports for the renamed ProcedureTemplate model to maintain compatibility.
"""

# Import the new model with the old name for backward compatibility
from .procedure_template import ProcedureTemplate as ExperimentTemplate

# Re-export for backward compatibility
__all__ = ['ExperimentTemplate']