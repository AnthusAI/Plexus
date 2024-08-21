import unittest
from unittest.mock import patch, MagicMock
from plexus.data.HuggingFaceDataCache import HuggingFaceDataCache
import pandas as pd
from datasets import DatasetDict

class TestHuggingFaceDataCache(unittest.TestCase):

    @patch('plexus.data.HuggingFaceDataCache.load_dataset')
    def test_load_dataframe(self, mock_load_dataset):
        # Mock the dataset and its 'train' split
        mock_dataset = MagicMock(spec=DatasetDict)
        mock_dataset['train'].to_pandas.return_value = pd.DataFrame({
            'text': ['This is a test', 'Another test'],
            'label': [0, 1]
        })

        mock_load_dataset.return_value = mock_dataset

        # Create an instance of HuggingFaceDataCache with the dataset name
        cache = HuggingFaceDataCache(name='test/good')

        # Load the dataframe
        df = cache.load_dataframe()

        # Assertions
        self.assertIsInstance(df, pd.DataFrame)
        self.assertIn('text', df.columns)
        self.assertIn('label', df.columns)
        self.assertEqual(len(df), 2)

        # Verify the dataset
        print("Verification Results:")
        verification_report, verification_data = cache.verify_dataset(df)
        print(verification_report)

        # Analyze the dataset
        print("Analysis Results:")
        cache.analyze_dataset(df)

    @patch('plexus.data.HuggingFaceDataCache.load_dataset')
    def test_dataset_with_missing_data(self, mock_load_dataset):
        # Mock the dataset with missing values in the 'label' column
        mock_dataset = MagicMock(spec=DatasetDict)
        mock_dataset['train'].to_pandas.return_value = pd.DataFrame({
            'text': ['This is a test', 'Another test', None],  # Missing value in 'text'
            'label': [0, None, 1]  # Missing value in 'label'
        })

        mock_load_dataset.return_value = mock_dataset

        # Create an instance of HuggingFaceDataCache with the dataset name
        cache = HuggingFaceDataCache(name='test/bad')

        # Load the dataframe using the mocked dataset with missing data
        df = cache.load_dataframe()

        # Verify the dataset (should detect missing data)
        verification_report, verification_data = cache.verify_dataset(df)
        print("Verification Results (Missing Data):")
        print(verification_report)

        # Assertions to ensure the missing data is detected correctly
        self.assertEqual(verification_data['missing_values']['text'], 1)
        self.assertEqual(verification_data['missing_values']['label'], 1)

    # def test_load_real_dataset(self):
    #     # Use a real dataset name from Hugging Face
    #     cache = HuggingFaceDataCache(name='fancyzhx/ag_news')

    #     # Load the dataframe with real data
    #     df = cache.load_dataframe()

    #     # Verify the dataset
    #     verification_report, verification_data = cache.verify_dataset(df)
    #     print("Verification Results:")
    #     print(verification_report)

    #     # Analyze the dataset
    #     analysis_results = cache.analyze_dataset(df)
    #     print("Analysis Results:")
    #     print(analysis_results)

    #     # Assertions to ensure basic correctness
    #     self.assertIsInstance(df, pd.DataFrame)
    #     self.assertIn('text', df.columns)
    #     self.assertIn('label', df.columns)
    #     self.assertGreater(len(df), 0)  # Ensure there are rows in the dataset


if __name__ == '__main__':
    unittest.main()
