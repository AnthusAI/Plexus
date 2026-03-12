"""
Base class for all alignment and accuracy metrics in Plexus.

This module provides a standard interface for implementing various evaluation
metrics, ensuring consistent inputs and outputs across different metric types.
"""

from abc import ABC, abstractmethod
from typing import List, Any, Tuple, Optional, Union, Generic, TypeVar
from pydantic import BaseModel, ConfigDict

class Metric(ABC):
    """
    Abstract base class for implementing evaluation metrics in Plexus.

    Metric is the foundation for standardized evaluation metrics. Each implementation
    represents a specific way to measure agreement or performance, such as:
    
    - Agreement coefficients (Gwet's AC1, Cohen's Kappa)
    - Accuracy metrics (raw accuracy, F1 score)
    - Distance metrics (RMSE, MAE)
    
    The Metric class provides:
    - Standard input/output interfaces using Pydantic models
    - Consistent calculation methods
    - Range information for proper visualization
    
    Common usage patterns:
    1. Creating a custom metric:
        class MyMetric(Metric):
            def calculate(self, input_data: Metric.Input) -> Metric.Result:
                # Custom metric calculation logic
                return Metric.Result(
                    name="My Custom Metric",
                    value=calculated_value,
                    range=[0, 1]
                )
    
    2. Using a metric:
        metric = MyMetric()
        result = metric.calculate(Metric.Input(
            reference=["Yes", "No", "Yes"],
            predictions=["Yes", "No", "No"]
        ))
    """
    
    class Input(BaseModel):
        """
        Standard input structure for all metric calculations in Plexus.
        
        The Input class standardizes how data is passed to metric calculations,
        typically consisting of two lists: reference (ground truth) and predictions.
        
        Attributes:
            reference: List of reference/gold standard values
            predictions: List of predicted values to compare against reference
            
        Common usage:
            input_data = Metric.Input(
                reference=["Yes", "No", "Yes", "Yes"],
                predictions=["Yes", "No", "No", "Yes"]
            )
        """
        model_config = ConfigDict(protected_namespaces=())
        reference: List[Any]
        predictions: List[Any]

    class Result(BaseModel):
        """
        Standard output structure for all metric calculations in Plexus.
        
        The Result class provides a consistent way to represent metric outcomes,
        including the metric name, calculated value, and valid range.
        
        Attributes:
            name: The name of the metric (e.g., "Gwet's AC1")
            value: The calculated metric value
            range: Valid range for the metric as [min, max]
            metadata: Optional additional information about the calculation
            
        Common usage:
            result = Metric.Result(
                name="Accuracy",
                value=0.75,
                range=[0, 1],
                metadata={"sample_size": 100}
            )
        """
        model_config = ConfigDict(protected_namespaces=())
        name: str
        value: float
        range: List[float]  # [min, max]
        metadata: dict = {}
    
    @abstractmethod
    def calculate(self, input_data: "Metric.Input") -> "Metric.Result":
        """
        Calculate the metric value based on the provided input data.
        
        This abstract method must be implemented by all concrete metric classes.
        
        Args:
            input_data: Metric.Input object containing reference and prediction data
            
        Returns:
            Metric.Result object with the calculated metric value and metadata
        """
        pass 