import pandas as pd
from pydantic import Field
from plexus.CustomLogging import logging
from .DataCache import DataCache


class TestDataCache(DataCache):
    """
    A simple test data cache that generates sample data for testing purposes.
    """
    
    class Parameters(DataCache.Parameters):
        num_rows: int = Field(default=100, description="Number of rows to generate")
        columns: list = Field(default=["text", "label"], description="Column names")
        
    def __init__(self, **parameters):
        super().__init__(**parameters)
        logging.info(f"Initializing TestDataCache with {self.parameters.num_rows} rows")
        
    def load_dataframe(self, data=None, fresh=False):
        """
        Generate a test dataframe with sample data.
        
        Returns
        -------
        pd.DataFrame
            A test dataframe with sample text and labels
        """
        logging.info(f"Generating test dataframe with {self.parameters.num_rows} rows")
        
        # Generate sample data
        sample_texts = [
            "This is a positive review of the product",
            "I didn't like this service at all",
            "The quality was excellent and delivery was fast",
            "Poor customer service experience",
            "Highly recommend this to everyone",
            "Waste of money, very disappointed",
            "Great value for the price",
            "Not worth buying, low quality"
        ] * (self.parameters.num_rows // 8 + 1)
        
        sample_labels = ["positive", "negative", "positive", "negative"] * (self.parameters.num_rows // 4 + 1)
        
        data = {
            "text": sample_texts[:self.parameters.num_rows],
            "label": sample_labels[:self.parameters.num_rows],
            "id": range(1, self.parameters.num_rows + 1)
        }
        
        df = pd.DataFrame(data)
        logging.info(f"Generated test dataframe: {df.shape[0]} rows, {df.shape[1]} columns")
        
        return df