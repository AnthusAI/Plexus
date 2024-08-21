from datasets import load_dataset
from pydantic import Field
from .DataCache import DataCache
from plexus.CustomLogging import logging
import pandas as pd

class HuggingFaceDataCache(DataCache):
    """
    A class to load and cache datasets from Hugging Face.
    """

    class Parameters(DataCache.Parameters):
        name: str  # The name of the Hugging Face dataset to load

    def __init__(self, **parameters):
        super().__init__(**parameters)
        logging.info(f"------------------------------------------------")
        logging.info(f"Initialized HuggingFaceDataCache for dataset: {self.parameters.name}")

    def load_dataframe(self, *args, **kwargs):
        # Load the dataset using the Hugging Face datasets library
        dataset = load_dataset(self.parameters.name, **kwargs)

        # Assuming the dataset has a 'train' split, convert it to a pandas DataFrame
        df = dataset['train'].to_pandas()
        return df

    def verify_dataset(self, df: pd.DataFrame):
        """
        Perform basic verification checks on the loaded DataFrame and return results
        in a more readable format and a dictionary for testing.
        """
        # Check shape
        dataset_shape = f"Dataset shape: {df.shape[0]} rows, {df.shape[1]} columns"

        # Check for missing values
        missing_values = df.isnull().sum()
        missing_values_info = "Missing values in each column:\n"
        for column, missing_count in missing_values.items():
            missing_values_info += f" - {column}: {missing_count} missing values\n"

        # Check column data types
        data_types = df.dtypes
        data_types_info = "Data types of columns:\n"
        for column, dtype in data_types.items():
            data_types_info += f" - {column}: {dtype}\n"

        # Display column names
        column_names_info = f"Column names: {', '.join(list(df.columns))}"

        # Combine all the information into a formatted string
        verification_report = f"{dataset_shape}\n{missing_values_info}{data_types_info}{column_names_info}"

        # Log the report
        logging.info(verification_report)

        # Return both the formatted string and a dictionary for testing
        verification_data = {
            "shape": df.shape,
            "missing_values": missing_values,
            "data_types": data_types,
            "column_names": list(df.columns)
        }

        return verification_report, verification_data

    def analyze_dataset(self, df: pd.DataFrame):
        """
        Display basic analysis of the loaded DataFrame.
        """
        # Show the first few rows of the dataframe
        logging.info(f"First few rows:\n{df.head()}")

        # Show basic statistics
        logging.info(f"Summary statistics:\n{df.describe(include='all')}")

        # Show value counts for categorical columns
        for column in df.select_dtypes(include=['object', 'category']).columns:
            logging.info(f"Value counts for column '{column}':\n{df[column].value_counts()}")

        return {
            "head": df.head(),
            "summary_statistics": df.describe(include='all'),
            "value_counts": {col: df[col].value_counts() for col in df.select_dtypes(include=['object', 'category']).columns}
        }
