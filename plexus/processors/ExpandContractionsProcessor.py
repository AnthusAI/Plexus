import contractions
from plexus.processors.DataframeProcessor import Processor

class ExpandContractionsProcessor(Processor):
    """
    Processor that expands contractions in text (e.g., "don't" -> "do not").
    """

    def process(self, score_input: 'Score.Input') -> 'Score.Input':
        """
        Process the Score.Input by expanding contractions.

        Args:
            score_input: Score.Input with text

        Returns:
            Score.Input with contractions expanded
        """
        from plexus.core.ScoreInput import ScoreInput

        # Expand contractions
        expanded_text = contractions.fix(score_input.text)

        # Return new Score.Input with expanded text
        return ScoreInput(
            text=expanded_text,
            metadata=score_input.metadata,
            results=score_input.results
        )
