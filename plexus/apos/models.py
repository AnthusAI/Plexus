"""
Base models for the Automated Prompt Optimization System.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Any
from enum import Enum, auto


class OptimizationStatus(Enum):
    """Status of the optimization process."""
    NOT_STARTED = auto()
    IN_PROGRESS = auto()
    COMPLETED = auto()
    FAILED = auto()
    STOPPED = auto()


@dataclass
class PromptChange:
    """Represents a change made to a prompt during optimization."""
    component: str
    old_text: str
    new_text: str
    rationale: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MismatchAnalysis:
    """Analysis of a single mismatch between model output and ground truth."""
    transcript_id: str
    question_name: str
    ground_truth: str
    model_answer: str
    transcript_text: str
    analysis: str
    error_category: Optional[str] = None
    root_cause: Optional[str] = None
    suggested_improvements: List[str] = field(default_factory=list)
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IterationResult:
    """Results and analysis from a single optimization iteration."""
    iteration: int
    accuracy: float
    mismatches: List[MismatchAnalysis]
    prompt_changes: List[PromptChange]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metrics: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_improvement(self, previous: Optional['IterationResult']) -> float:
        """Calculate improvement from previous iteration."""
        if not previous:
            return 0.0
        return self.accuracy - previous.accuracy


@dataclass
class OptimizationState:
    """Tracks the overall state and progress of the optimization process."""
    scorecard_name: str
    score_name: str
    target_accuracy: float
    max_iterations: int
    current_iteration: int = 0
    best_accuracy: float = 0.0
    current_accuracy: float = 0.0
    start_time: datetime = field(default_factory=datetime.utcnow)
    status: OptimizationStatus = OptimizationStatus.NOT_STARTED
    history: List[IterationResult] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

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


@dataclass
class Mismatch:
    """Represents a single mismatch between expected and actual results."""
    transcript_id: str
    ground_truth: str
    model_answer: str
    analysis: str
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PatternInfo:
    """Information about an identified error pattern."""
    category: str
    frequency: int
    affected_questions: List[str]
    example_mismatches: List[Mismatch]
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Recommendation:
    """A recommendation for improving a prompt based on pattern analysis."""
    description: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SynthesisResult:
    """Result of pattern synthesis process."""
    patterns: List[PatternInfo]
    recommendations: List[Recommendation]
    metrics: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvaluationResult:
    """Result of an evaluation run."""
    accuracy: float
    mismatches: List[Mismatch]
    prompt_changes: List[PromptChange] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict) 