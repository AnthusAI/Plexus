import pandas as pd
from plexus.processors.DataframeProcessor import DatasetProcessor
from plexus.CustomLogging import logging, console


class MergeColumnsDatasetFilter(DatasetProcessor):

    def __init__(self, **parameters):
        super().__init__(**parameters)
        self.columns_to_merge = parameters.get('columns_to_merge')
        self.new_column_name = parameters.get('new_column_name')

    def process(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        matched_rows = {}
        
        for column_name, column_info in self.columns_to_merge.items():
            labels = column_info['labels']
            new_label = column_info['new_label']
            
            matched_rows[column_name] = dataframe[dataframe[column_name].isin(labels)].index
            
            logging.info(f"Matched rows for column '{column_name}': {len(matched_rows[column_name])}")
        
        unique_rows = set()
        for column_name, rows in matched_rows.items():
            unique_rows ^= set(rows)
        
        logging.info(f"Total unique rows: {len(unique_rows)}")
        
        result_dataframe = dataframe.loc[list(unique_rows)].copy()
        result_dataframe[self.new_column_name] = ''
        
        for column_name, column_info in self.columns_to_merge.items():
            new_label = column_info['new_label']
            
            matched_indices = result_dataframe.index.intersection(matched_rows[column_name])
            result_dataframe.loc[matched_indices, self.new_column_name] = new_label
            
            logging.info(f"Assigned label '{new_label}' to {len(matched_indices)} rows for column '{column_name}'")
        
        return result_dataframe
