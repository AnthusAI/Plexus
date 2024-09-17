import unittest
import numpy as np
from unittest import TestCase, mock
from unittest.mock import patch
from plexus.nlp.cluster.TopicModelClusterer import TopicModelClusterer

class TestTopicModelClusterer(unittest.TestCase):
    def setUp(self):
        self.explanations = [
            "The AI assessed the buyer's income as sufficient, but the human evaluator found discrepancies in the reported figures.",
            "While the AI determined the credit score met the threshold, the human evaluator interpreted the score differently based on recent credit history."
        ]
        self.clusterer = TopicModelClusterer(self.explanations)

    def test_preprocess_documents(self):
        processed = self.clusterer._preprocess_documents(self.explanations)
        self.assertIsInstance(processed, list)
        self.assertEqual(len(processed), 2)
        self.assertTrue(all(isinstance(doc, list) for doc in processed))

    def test_create_dictionary(self):
        dictionary = self.clusterer._create_dictionary()
        self.assertIsNotNone(dictionary)
        self.assertTrue(len(dictionary) > 0)

    def test_create_corpus(self):
        corpus = self.clusterer._create_corpus()
        self.assertIsInstance(corpus, list)
        self.assertEqual(len(corpus), 2)

    @patch('plexus.nlp.cluster.TopicModelClusterer.LdaMulticore')
    @patch('plexus.nlp.cluster.TopicModelClusterer.CoherenceModel')
    def test_determine_optimal_topics(self, mock_coherence_model, mock_lda):
        # Configure the mock LdaMulticore instance
        mock_lda_instance = mock_lda.return_value
        mock_lda_instance.get_topics.return_value = np.array([
            [0.1, 0.2, 0.3, 0.4],
            [0.2, 0.3, 0.4, 0.1]
        ])
        mock_lda_instance.show_topics.return_value = [
            (0, [('word1', 0.1), ('word2', 0.2), ('word3', 0.3), ('word4', 0.4)]),
            (1, [('word2', 0.2), ('word3', 0.3), ('word4', 0.4), ('word1', 0.1)])
        ]

        # Configure the mock CoherenceModel instance
        mock_coherence_instance = mock_coherence_model.return_value
        mock_coherence_instance.get_coherence.return_value = 0.5

        # Execute the method under test
        coherence_values = self.clusterer.determine_optimal_topics(limit=10, start=2, step=2)

        # Assertions
        self.assertIsNotNone(coherence_values)
        self.assertGreater(len(coherence_values), 0)
        self.assertEqual(len(coherence_values), 4)  # (10-2)/2 = 4 iterations

        # Check if LdaMulticore and CoherenceModel were called
        mock_lda.assert_called()
        mock_coherence_model.assert_called()

        # Verify that get_topics was called
        self.assertEqual(mock_lda_instance.get_topics.call_count, 4)  # Called once for each iteration

        # Verify that show_topics was not called (we're not using it in this implementation)
        mock_lda_instance.show_topics.assert_not_called()

    def test_analyze_topic_distributions_without_model(self):
        with self.assertRaises(ValueError):
            self.clusterer.analyze_topic_distributions()

    def test_get_lda_topics_without_analysis(self):
        with self.assertRaises(ValueError):
            self.clusterer.get_lda_topics()

    @patch('plexus.nlp.cluster.TopicModelClusterer.openai')
    def test_generate_llm_explanations_without_prominent_topics(self, mock_openai):
        with self.assertRaises(ValueError):
            self.clusterer.generate_llm_explanations()

    @patch('plexus.nlp.cluster.TopicModelClusterer.openai')
    def test_generate_summary_without_topics(self, mock_openai):
        with self.assertRaises(ValueError):
            self.clusterer.generate_summary()

if __name__ == '__main__':
    unittest.main()