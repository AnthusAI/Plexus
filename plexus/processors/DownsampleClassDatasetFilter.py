import pandas as pd
from plexus.processors.DataframeProcessor import DatasetProcessor

class DownsampleClassDatasetFilter(DatasetProcessor):

    def __init__(self, **parameters):
        super().__init__(**parameters)
        self.filter_type = parameters.get('filter-type')
        self.column_name = parameters.get('column-name')
        self.value =       parameters.get('value')

    def process(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        value_counts = dataframe[self.column_name].value_counts()
        largest_class_size = value_counts[value_counts.index != self.value].max()
        
        # Ensure the target value is included in the value counts
        if self.value not in value_counts:
            value_counts[self.value] = 0
        
        self.before_summary = self.generate_summary(value_counts)

        target_class_size = value_counts.get(self.value, 0)
        
        if target_class_size <= largest_class_size:
            self.after_summary = self.before_summary
            self.display_summary()
            return dataframe
        
        non_target_class_dataframe = dataframe[dataframe[self.column_name] != self.value]
        target_class_dataframe = dataframe[dataframe[self.column_name] == self.value].sample(n=largest_class_size, random_state=1)
        
        downsampled_dataframe = pd.concat([non_target_class_dataframe, target_class_dataframe])
        
        self.after_summary = self.generate_summary(downsampled_dataframe[self.column_name].value_counts())
        
        self.display_summary()
        return downsampled_dataframe

    def generate_summary(self, value_counts):
        from rich.table import Table
        summary_table = Table(title="Class Distribution")
        summary_table.add_column("Class Value", justify="right", style="cyan", no_wrap=True)
        summary_table.add_column("Count", style="magenta")
        
        for class_value, count in value_counts.items():
            summary_table.add_row(str(class_value), str(count))
        
        return summary_table
