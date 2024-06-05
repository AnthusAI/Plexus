from abc import ABC, abstractmethod
import pandas as pd

class DataframeProcessor(ABC):

    @abstractmethod
    def process(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        pass