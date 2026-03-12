"""
Tests for topic n-gram export functionality.

This module tests the functionality for exporting complete n-gram lists
with c-TF-IDF scores from BERTopic models, including:
- CSV file creation with correct structure
- Fine-tuned topic names inclusion
- N-grams sorted by c-TF-IDF score
- Max n-grams limit enforcement
"""
import os
import tempfile
import shutil
import unittest
from unittest.mock import Mock, MagicMock
import pandas as pd
import numpy as np
from scipy.sparse import csr_matrix

from plexus.analysis.topics.analyzer import save_complete_topic_ngrams


class TestNgramExport(unittest.TestCase):
    """Tests for n-gram export functionality."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create a temporary directory for test outputs
        self.test_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """Clean up test fixtures after each test method."""
        # Remove the temporary directory
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def _create_mock_topic_model(self, num_topics=3, num_features=10):
        """
        Create a mock BERTopic model with c-TF-IDF matrix and topic info.
        
        Args:
            num_topics: Number of topics (including -1 outlier topic)
            num_features: Number of features (n-grams) in vocabulary
        
        Returns:
            Mock BERTopic model
        """
        # Create mock topic model
        topic_model = Mock()
        
        # Create mock vectorizer with feature names
        feature_names = np.array([f"ngram_{i}" for i in range(num_features)])
        vectorizer = Mock()
        vectorizer.get_feature_names_out.return_value = feature_names
        topic_model.vectorizer_model = vectorizer
        
        # Create mock c-TF-IDF matrix (sparse matrix)
        # Shape: (num_topics, num_features)
        # Each row represents a topic, each column a feature
        # Values are c-TF-IDF scores
        data = []
        row_indices = []
        col_indices = []
        
        for topic_idx in range(num_topics):
            # Generate decreasing scores for each topic
            for feature_idx in range(num_features):
                score = (num_features - feature_idx) / num_features * (topic_idx + 1)
                data.append(score)
                row_indices.append(topic_idx)
                col_indices.append(feature_idx)
        
        c_tf_idf = csr_matrix((data, (row_indices, col_indices)), 
                              shape=(num_topics, num_features))
        topic_model.c_tf_idf_ = c_tf_idf
        
        # Create mock topic info DataFrame
        topic_info_data = []
        for i in range(num_topics):
            topic_id = i - 1  # First topic is -1 (outlier)
            topic_info_data.append({
                'Topic': topic_id,
                'Name': f'Topic {topic_id}' if topic_id == -1 else f'{topic_id}_topic_name_{topic_id}',
                'Count': 100 - i * 10
            })
        
        topic_info = pd.DataFrame(topic_info_data)
        topic_model.get_topic_info.return_value = topic_info
        
        return topic_model
    
    def test_save_complete_topic_ngrams_creates_csv(self):
        """Test that save_complete_topic_ngrams creates a CSV file with correct structure."""
        # Create mock model
        topic_model = self._create_mock_topic_model(num_topics=3, num_features=10)
        
        # Call the function
        output_path = save_complete_topic_ngrams(topic_model, self.test_dir, max_ngrams_per_topic=5)
        
        # Assert CSV file was created
        self.assertTrue(os.path.exists(output_path))
        self.assertEqual(output_path, os.path.join(self.test_dir, "complete_topic_ngrams.csv"))
        
        # Load and verify CSV structure
        df = pd.read_csv(output_path)
        
        # Check columns
        expected_columns = ['topic_id', 'topic_name', 'ngram', 'c_tf_idf_score', 'rank']
        self.assertEqual(list(df.columns), expected_columns)
        
        # Check that we have data (excluding outlier topic -1)
        self.assertGreater(len(df), 0)
        
        # Verify no outlier topic (-1) in results
        self.assertNotIn(-1, df['topic_id'].values)
    
    def test_ngrams_include_topic_names(self):
        """Test that n-grams include fine-tuned topic names."""
        # Create mock model with specific topic names
        topic_model = self._create_mock_topic_model(num_topics=3, num_features=10)
        
        # Override topic info with fine-tuned names
        topic_info = pd.DataFrame([
            {'Topic': -1, 'Name': '-1_outlier', 'Count': 50},
            {'Topic': 0, 'Name': '0_billing_inquiry', 'Count': 100},
            {'Topic': 1, 'Name': '1_technical_support', 'Count': 80}
        ])
        topic_model.get_topic_info.return_value = topic_info
        
        # Call the function
        output_path = save_complete_topic_ngrams(topic_model, self.test_dir, max_ngrams_per_topic=5)
        
        # Load CSV
        df = pd.read_csv(output_path)
        
        # Verify topic names are cleaned (ID prefix removed)
        topic_names = df['topic_name'].unique()
        self.assertIn('billing_inquiry', topic_names)
        self.assertIn('technical_support', topic_names)
        
        # Verify outlier topic not included
        self.assertNotIn('outlier', topic_names)
    
    def test_ngrams_sorted_by_score(self):
        """Test that n-grams are sorted by c-TF-IDF score in descending order."""
        # Create mock model
        topic_model = self._create_mock_topic_model(num_topics=2, num_features=10)
        
        # Call the function
        output_path = save_complete_topic_ngrams(topic_model, self.test_dir, max_ngrams_per_topic=10)
        
        # Load CSV
        df = pd.read_csv(output_path)
        
        # Check sorting within each topic
        for topic_id in df['topic_id'].unique():
            topic_df = df[df['topic_id'] == topic_id]
            scores = topic_df['c_tf_idf_score'].values
            
            # Verify scores are in descending order
            self.assertTrue(all(scores[i] >= scores[i+1] for i in range(len(scores)-1)),
                          f"Scores not sorted for topic {topic_id}: {scores}")
            
            # Verify ranks are sequential
            ranks = topic_df['rank'].values
            expected_ranks = list(range(1, len(ranks) + 1))
            self.assertEqual(list(ranks), expected_ranks)
    
    def test_max_ngrams_limit_respected(self):
        """Test that max_ngrams_per_topic parameter limits the number of n-grams."""
        # Create mock model with many features
        topic_model = self._create_mock_topic_model(num_topics=3, num_features=50)
        
        max_ngrams = 10
        
        # Call the function
        output_path = save_complete_topic_ngrams(topic_model, self.test_dir, 
                                                max_ngrams_per_topic=max_ngrams)
        
        # Load CSV
        df = pd.read_csv(output_path)
        
        # Check that each topic has at most max_ngrams entries
        for topic_id in df['topic_id'].unique():
            topic_df = df[df['topic_id'] == topic_id]
            self.assertLessEqual(len(topic_df), max_ngrams,
                               f"Topic {topic_id} has {len(topic_df)} n-grams, expected max {max_ngrams}")
    
    def test_handles_quoted_topic_names(self):
        """Test that quoted topic names are cleaned properly."""
        # Create mock model
        topic_model = self._create_mock_topic_model(num_topics=2, num_features=10)
        
        # Override topic info with quoted names
        topic_info = pd.DataFrame([
            {'Topic': -1, 'Name': '-1_outlier', 'Count': 50},
            {'Topic': 0, 'Name': '"billing_inquiry"', 'Count': 100}
        ])
        topic_model.get_topic_info.return_value = topic_info
        
        # Call the function
        output_path = save_complete_topic_ngrams(topic_model, self.test_dir, max_ngrams_per_topic=5)
        
        # Load CSV
        df = pd.read_csv(output_path)
        
        # Verify quotes are removed
        topic_names = df['topic_name'].unique()
        self.assertIn('billing_inquiry', topic_names)
        self.assertNotIn('"billing_inquiry"', topic_names)
    
    def test_only_positive_scores_included(self):
        """Test that only n-grams with positive c-TF-IDF scores are included."""
        # Create mock model with some zero/negative scores
        topic_model = Mock()
        
        # Create feature names
        feature_names = np.array(['ngram_0', 'ngram_1', 'ngram_2'])
        vectorizer = Mock()
        vectorizer.get_feature_names_out.return_value = feature_names
        topic_model.vectorizer_model = vectorizer
        
        # Create c-TF-IDF matrix with mixed scores
        data = [0.5, 0.0, -0.1]  # positive, zero, negative
        row_indices = [0, 0, 0]
        col_indices = [0, 1, 2]
        c_tf_idf = csr_matrix((data, (row_indices, col_indices)), shape=(1, 3))
        topic_model.c_tf_idf_ = c_tf_idf
        
        # Create topic info
        topic_info = pd.DataFrame([
            {'Topic': 0, 'Name': '0_test_topic', 'Count': 100}
        ])
        topic_model.get_topic_info.return_value = topic_info
        
        # Call the function
        output_path = save_complete_topic_ngrams(topic_model, self.test_dir, max_ngrams_per_topic=10)
        
        # Load CSV
        df = pd.read_csv(output_path)
        
        # Verify only positive scores are included
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]['ngram'], 'ngram_0')
        self.assertGreater(df.iloc[0]['c_tf_idf_score'], 0)


if __name__ == '__main__':
    unittest.main()

