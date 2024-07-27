import pandas as pd
import contractions
from plexus.processors.DataframeProcessor import DataframeProcessor

class ExpandContractionsProcessor(DataframeProcessor):

    def __init__(self, **parameters):
        super().__init__(**parameters)

    def process(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        random_row_index = dataframe.sample(n=1).index[0]
        original_transcript = dataframe.at[random_row_index, 'text']
        truncated_original_transcript = (original_transcript[:512] + '...') if len(original_transcript) > 512 else original_transcript

        dataframe['text'] = dataframe['text'].apply(
            lambda transcript: contractions.fix(transcript)
        )

        modified_transcript = dataframe.at[random_row_index, 'text']
        truncated_modified_transcript = (modified_transcript[:512] + '...') if len(modified_transcript) > 512 else modified_transcript

        self.before_summary = truncated_original_transcript
        self.after_summary = truncated_modified_transcript

        self.display_summary()
        return dataframe