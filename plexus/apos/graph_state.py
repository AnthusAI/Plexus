"""
State management for APOS LangGraph implementation.
"""
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum, auto

from langchain_core.pydantic_v1 import BaseModel, Field

from plexus.apos.models import (
    OptimizationStatus,
    PromptChange,
    MismatchAnalysis,
    SynthesisResult,
    IterationResult
)


class APOSState(BaseModel):
    """
    Central state management for APOS LangGraph workflow.
    Combines all state needed for optimization process.
    """
    # Core prompt components
    system_message: str = Field(description="Current system message for the prompt")
    user_message: str = Field(description="Current user message template for the prompt")
    
    # Optimization state
    scorecard_name: str = Field(description="Name of the scorecard being optimized")
    score_name: str = Field(description="Name of the score being optimized")
    target_accuracy: float = Field(description="Target accuracy to achieve")
    max_iterations: int = Field(description="Maximum number of iterations to run")
    current_iteration: int = Field(default=0, description="Current iteration number")
    best_accuracy: float = Field(default=0.0, description="Best accuracy achieved so far")
    current_accuracy: float = Field(default=0.0, description="Current iteration accuracy")
    
    # Analysis components
    mismatches: List[MismatchAnalysis] = Field(
        default_factory=list,
        description="Current mismatches being analyzed"
    )
    analyzed_mismatches: List[MismatchAnalysis] = Field(
        default_factory=list,
        description="Mismatches that have been analyzed"
    )
    pattern_analysis: Optional[SynthesisResult] = Field(
        default=None,
        description="Results of pattern analysis across mismatches"
    )
    optimization_result: Optional[PromptChange] = Field(
        default=None,
        description="Latest optimization changes to prompts"
    )
    
    # History and tracking
    history: List[IterationResult] = Field(
        default_factory=list,
        description="History of all iteration results"
    )
    start_time: datetime = Field(
        default_factory=datetime.utcnow,
        description="Start time of optimization"
    )
    status: OptimizationStatus = Field(
        default=OptimizationStatus.NOT_STARTED,
        description="Current status of optimization"
    )
    
    # Control flow
    retry_count: int = Field(
        default=0,
        description="Number of retries in current operation"
    )
    max_retries: int = Field(
        default=3,
        description="Maximum number of retries allowed"
    )
    
    # Configuration and metadata
    config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Configuration parameters"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )

    def should_continue(self) -> bool:
        """Determine if optimization should continue based on current state."""
        if self.status != OptimizationStatus.IN_PROGRESS:
            return False
        
        if self.current_iteration >= self.max_iterations:
            return False
            
        if self.current_accuracy >= self.target_accuracy:
            return False
            
        return True

    def add_iteration_result(self, result: IterationResult) -> None:
        """Add a new iteration result and update state."""
        self.history.append(result)
        self.current_iteration = result.iteration
        self.current_accuracy = result.accuracy
        
        if result.accuracy > self.best_accuracy:
            self.best_accuracy = result.accuracy

    @property
    def is_complete(self) -> bool:
        """Check if optimization is complete."""
        return (
            self.status == OptimizationStatus.COMPLETED or
            self.status == OptimizationStatus.FAILED or
            self.current_iteration >= self.max_iterations
        )

    class Config:
        """Pydantic config."""
        arbitrary_types_allowed = True 