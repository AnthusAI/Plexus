from abc import ABC, abstractmethod


class Processor(ABC):
    """
    Base class for processors that transform Score.Input → Score.Input.

    These processors work on individual items (per-item processing),
    ensuring the same transformation in production and development.

    This replaces the old DataframeProcessor - we no longer work on DataFrames.
    Each processor operates on a single Score.Input at a time, allowing the
    exact same pipeline to run in production (1 item) and evaluation (many items).
    """

    def __init__(self, **parameters):
        """
        Initialize the processor with configuration parameters.

        Args:
            **parameters: Processor-specific configuration parameters
        """
        self.parameters = parameters

    @abstractmethod
    def process(self, score_input: 'Score.Input') -> 'Score.Input':
        """
        Transform a Score.Input.

        This is the core method that each processor must implement.
        It takes a Score.Input object and returns a transformed Score.Input object.

        Args:
            score_input: Input to transform (contains text, metadata, results)

        Returns:
            Transformed Score.Input with modified text/metadata

        Example:
            class MyProcessor(Processor):
                def process(self, score_input):
                    # Transform the text
                    transformed_text = self.transform(score_input.text)

                    # Return new Score.Input with transformed text
                    return Score.Input(
                        text=transformed_text,
                        metadata=score_input.metadata,
                        results=score_input.results
                    )
        """
        pass


# Keep DataframeProcessor as an alias for backwards compatibility during transition
# This will be removed in a future version
DataframeProcessor = Processor
