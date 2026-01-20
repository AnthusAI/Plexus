from abc import ABC, abstractmethod
import pandas as pd

class Processor(ABC):
    """
    Base class for processors that transform Score.Input → Score.Input.

    These processors work on individual items (per-item processing),
    ensuring the same transformation in production and development.

    Use this for per-item text transformations that should work identically
    in production (single item) and development (datasets).

    Examples: FilterCustomerOnlyProcessor, RemoveSpeakerIdentifiersTranscriptFilter, etc.
    """

    def __init__(self, **parameters):
        """
        Initialize the processor with configuration parameters.

        Args:
            **parameters: Processor-specific configuration parameters
        """
        self.parameters = parameters
        self.before_summary = None
        self.after_summary = None

    @abstractmethod
    def process(self, score_input: 'Score.Input') -> 'Score.Input':
        """
        Transform a Score.Input.

        Args:
            score_input: Input to transform (contains text, metadata, results)

        Returns:
            Transformed Score.Input with modified text/metadata
        """
        pass

    def display_summary(self):
        """Display before/after summary (for debugging/logging)."""
        if self.before_summary or self.after_summary:
            from plexus.CustomLogging import console
            console.rule(f"[bold]{self.__class__.__name__}[/bold]")
            if self.before_summary:
                console.print("Before:", self.before_summary)
            if self.after_summary:
                console.print("After:", self.after_summary)


class DatasetProcessor(ABC):
    """
    Base class for dataset-level processors that operate on DataFrames.

    These processors are used during evaluation/training to filter, transform,
    or balance datasets. They operate on entire DataFrames, not individual items.

    Examples: ByColumnValueDatasetFilter, DownsampleClassDatasetFilter, etc.

    Note: Dataset processors are NOT used in production - they're dev/eval only.
    They belong in the 'data:' section of YAML configs, not the 'item:' section.
    """

    def __init__(self, **parameters):
        self.parameters = parameters
        self.before_summary = None
        self.after_summary = None

    @abstractmethod
    def process(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        """
        Transform a DataFrame (dataset-level operation).

        Args:
            dataframe: Input DataFrame

        Returns:
            Transformed DataFrame
        """
        pass

    def display_summary(self):
        """Display before/after summary (for debugging/logging)."""
        if self.before_summary or self.after_summary:
            from plexus.CustomLogging import console
            console.rule(f"[bold]{self.__class__.__name__}[/bold]")
            if self.before_summary:
                console.print("Before:", self.before_summary)
            if self.after_summary:
                console.print("After:", self.after_summary)


# Backwards compatibility alias (DEPRECATED - use Processor or DatasetProcessor)
DataframeProcessor = Processor
