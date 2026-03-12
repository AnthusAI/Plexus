import pandas as pd
from plexus.processors.DataframeProcessor import DatasetProcessor


class ByColumnValueDatasetFilter(DatasetProcessor):

    def __init__(self, **parameters):
        super().__init__(**parameters)
        self.filter_type = parameters.get('filter-type')
        self.column_name = parameters.get('column-name')
        self.value =       parameters.get('value')

    def process(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        self.before_summary = f"Number of rows: {len(dataframe)}"
        if self.filter_type == 'include':
            dataframe = dataframe[dataframe[self.column_name] == self.value]
        elif self.filter_type == 'exclude':
            dataframe = dataframe[dataframe[self.column_name] != self.value]
        self.after_summary = f"Number of rows: {len(dataframe)}"
        self.display_summary()
        return dataframe
