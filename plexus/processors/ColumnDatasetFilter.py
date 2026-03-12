import pandas as pd
from plexus.processors.DataframeProcessor import DatasetProcessor


class ColumnDatasetFilter(DatasetProcessor):

    def __init__(self, **parameters):
        super().__init__(**parameters)
        self.filter_type = parameters.get('filter-type')
        self.columns = parameters.get('columns')

    def process(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        self.before_summary = f"Number of columns: {len(dataframe.columns)}"
        if self.filter_type == 'include':
            columns_to_include = self.columns + ['text']
            dataframe = dataframe[columns_to_include]
        elif self.filter_type == 'exclude':
            dataframe = dataframe.drop(columns=self.columns, errors='ignore')
        self.after_summary = f"Number of columns: {len(dataframe.columns)}"
        self.display_summary()
        return dataframe
