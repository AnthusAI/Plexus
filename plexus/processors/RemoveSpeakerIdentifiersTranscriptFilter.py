import re
import pandas as pd
from plexus.processors.DataframeProcessor import DataframeProcessor

class RemoveSpeakerIdentifiersTranscriptFilter(DataframeProcessor):

    def process(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        dataframe["Transcription"] = dataframe["Transcription"].apply(
            lambda transcript: re.sub(r'^\w+:\s*', '', transcript, flags=re.MULTILINE)
        )
        return dataframe