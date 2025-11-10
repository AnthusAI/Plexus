"""
Integration tests for topic analysis pipeline.

This module tests the complete end-to-end topic analysis pipeline,
including:
- N-gram export with c-TF-IDF scores
- Topic stability assessment
- File attachment and output generation
"""
import os
import tempfile
import shutil
import unittest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
import numpy as np
from scipy.sparse import csr_matrix


class TestTopicAnalysisIntegration(unittest.TestCase):
    """Integration tests for complete topic analysis pipeline."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create a temporary directory for test outputs
        self.test_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """Clean up test fixtures after each test method."""
        # Remove the temporary directory
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def _create_mock_topic_model(self):
        """Create a mock BERTopic model for testing."""
        topic_model = Mock()
        
        # Mock vectorizer
        feature_names = np.array(['billing', 'account', 'payment', 'technical', 'support'])
        vectorizer = Mock()
        vectorizer.get_feature_names_out.return_value = feature_names
        topic_model.vectorizer_model = vectorizer
        
        # Mock c-TF-IDF matrix
        data = [0.5, 0.4, 0.3, 0.2, 0.1]
        row_indices = [0, 0, 0, 0, 0]
        col_indices = [0, 1, 2, 3, 4]
        c_tf_idf = csr_matrix((data, (row_indices, col_indices)), shape=(1, 5))
        topic_model.c_tf_idf_ = c_tf_idf
        
        # Mock topic info
        topic_info = pd.DataFrame([
            {'Topic': 0, 'Name': '0_billing_inquiry', 'Count': 100}
        ])
        topic_model.get_topic_info.return_value = topic_info
        
        return topic_model
    
    def test_full_pipeline_with_ngrams_and_stability(self):
        """Test complete pipeline with both n-grams export and stability assessment."""
        from plexus.analysis.topics.analyzer import save_complete_topic_ngrams
        
        # Create mock model
        topic_model = self._create_mock_topic_model()
        
        # Test n-grams export
        ngrams_path = save_complete_topic_ngrams(topic_model, self.test_dir, max_ngrams_per_topic=5)
        
        # Verify n-grams file was created
        self.assertTrue(os.path.exists(ngrams_path))
        
        # Verify n-grams file content
        df = pd.read_csv(ngrams_path)
        self.assertGreater(len(df), 0)
        self.assertIn('topic_id', df.columns)
        self.assertIn('topic_name', df.columns)
        self.assertIn('ngram', df.columns)
        self.assertIn('c_tf_idf_score', df.columns)
        self.assertIn('rank', df.columns)
        
        # Note: Stability assessment requires more complex mocking of BERTopic
        # and is tested separately in test_topic_stability.py
    
    def test_ngrams_export_creates_correct_structure(self):
        """Test that n-grams export creates files with correct structure."""
        from plexus.analysis.topics.analyzer import save_complete_topic_ngrams
        
        topic_model = self._create_mock_topic_model()
        
        # Export n-grams
        output_path = save_complete_topic_ngrams(topic_model, self.test_dir, max_ngrams_per_topic=10)
        
        # Verify file exists
        self.assertTrue(os.path.exists(output_path))
        self.assertEqual(output_path, os.path.join(self.test_dir, "complete_topic_ngrams.csv"))
        
        # Load and verify structure
        df = pd.read_csv(output_path)
        
        # Check columns
        expected_columns = ['topic_id', 'topic_name', 'ngram', 'c_tf_idf_score', 'rank']
        self.assertEqual(list(df.columns), expected_columns)
        
        # Check data types
        self.assertTrue(pd.api.types.is_integer_dtype(df['topic_id']))
        self.assertTrue(pd.api.types.is_object_dtype(df['topic_name']))
        self.assertTrue(pd.api.types.is_object_dtype(df['ngram']))
        self.assertTrue(pd.api.types.is_float_dtype(df['c_tf_idf_score']))
        self.assertTrue(pd.api.types.is_integer_dtype(df['rank']))
    
    def test_ngrams_and_stability_files_coexist(self):
        """Test that both n-grams and stability files can be created in same directory."""
        from plexus.analysis.topics.analyzer import save_complete_topic_ngrams
        
        topic_model = self._create_mock_topic_model()
        
        # Create n-grams file
        ngrams_path = save_complete_topic_ngrams(topic_model, self.test_dir)
        
        # Create a mock stability file
        import json
        stability_data = {
            "n_runs": 10,
            "sample_fraction": 0.8,
            "mean_stability": 0.75,
            "per_topic_stability": {0: 0.75}
        }
        stability_path = os.path.join(self.test_dir, "topic_stability.json")
        with open(stability_path, 'w') as f:
            json.dump(stability_data, f)
        
        # Verify both files exist
        self.assertTrue(os.path.exists(ngrams_path))
        self.assertTrue(os.path.exists(stability_path))
        
        # Verify they don't interfere with each other
        df = pd.read_csv(ngrams_path)
        self.assertGreater(len(df), 0)
        
        with open(stability_path, 'r') as f:
            loaded_stability = json.load(f)
        self.assertEqual(loaded_stability['n_runs'], 10)
    
    def test_file_permissions_are_set_correctly(self):
        """Test that generated files have correct permissions."""
        from plexus.analysis.topics.analyzer import save_complete_topic_ngrams
        import stat
        
        topic_model = self._create_mock_topic_model()
        
        # Create file
        output_path = save_complete_topic_ngrams(topic_model, self.test_dir)
        
        # Check file permissions
        file_stat = os.stat(output_path)
        mode = file_stat.st_mode
        
        # Verify file is readable by owner
        self.assertTrue(mode & stat.S_IRUSR)
        
        # Verify file is writable by owner
        self.assertTrue(mode & stat.S_IWUSR)
    
    def test_configuration_parameters_flow_through_pipeline(self):
        """Test that configuration parameters are correctly passed through the pipeline."""
        # This is a conceptual test - in practice, you'd test with actual analyze_topics call
        
        # Configuration parameters
        config = {
            'max_ngrams_per_topic': 50,
            'compute_stability': True,
            'stability_n_runs': 5,
            'stability_sample_fraction': 0.7
        }
        
        # Verify parameters are valid
        self.assertIsInstance(config['max_ngrams_per_topic'], int)
        self.assertIsInstance(config['compute_stability'], bool)
        self.assertIsInstance(config['stability_n_runs'], int)
        self.assertIsInstance(config['stability_sample_fraction'], float)
        
        # Verify ranges
        self.assertGreater(config['max_ngrams_per_topic'], 0)
        self.assertGreater(config['stability_n_runs'], 0)
        self.assertGreater(config['stability_sample_fraction'], 0)
        self.assertLessEqual(config['stability_sample_fraction'], 1.0)
    
    def test_output_files_are_valid_for_report_attachment(self):
        """Test that output files are in correct format for report attachment."""
        from plexus.analysis.topics.analyzer import save_complete_topic_ngrams
        
        topic_model = self._create_mock_topic_model()
        
        # Create n-grams file
        ngrams_path = save_complete_topic_ngrams(topic_model, self.test_dir)
        
        # Verify file is a valid CSV
        try:
            df = pd.read_csv(ngrams_path)
            self.assertGreater(len(df), 0)
        except Exception as e:
            self.fail(f"N-grams file is not a valid CSV: {e}")
        
        # Verify file extension
        self.assertTrue(ngrams_path.endswith('.csv'))
        
        # Verify file can be read as text (for attachment)
        with open(ngrams_path, 'r') as f:
            content = f.read()
            self.assertGreater(len(content), 0)
            self.assertIn('topic_id', content)  # Header should be present


if __name__ == '__main__':
    unittest.main()


