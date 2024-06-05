import pandas as pd
import nltk
from nltk.corpus import stopwords
from plexus.processors.DataframeProcessor import DataframeProcessor

class RemoveStopWordsTranscriptFilter(DataframeProcessor):

    def __init__(self):
        nltk.download('stopwords')
        self.stop_words = set(stopwords.words('english'))

    def process(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        dataframe["Transcription"] = dataframe["Transcription"].apply(
            lambda transcript: ' '.join(
                [word for word in transcript.split() if word.lower() not in self.stop_words]
            )
        )
        return dataframe