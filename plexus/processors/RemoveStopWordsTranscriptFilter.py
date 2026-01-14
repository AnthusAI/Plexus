import nltk
from nltk.corpus import stopwords
from plexus.processors.DataframeProcessor import Processor


class RemoveStopWordsTranscriptFilter(Processor):
    """
    Processor that removes English stop words from transcript text.
    """

    def __init__(self, **parameters):
        super().__init__(**parameters)
        nltk.download('stopwords', quiet=True)
        self.stop_words = set(stopwords.words('english'))

    def process(self, score_input: 'Score.Input') -> 'Score.Input':
        """
        Process the Score.Input by removing stop words.

        Args:
            score_input: Score.Input with text

        Returns:
            Score.Input with stop words removed
        """
        from plexus.scores.Score import Score

        # Remove stop words
        filtered_text = ' '.join([
            word for word in score_input.text.split()
            if word.lower() not in self.stop_words
        ])

        # Return new Score.Input with filtered text
        return Score.Input(
            text=filtered_text,
            metadata=score_input.metadata,
            results=score_input.results
        )
