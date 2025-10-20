#!/usr/bin/env python3
"""
Focused tests for Evaluation.py prediction processing and metrics computation.

Tests the most critical business logic:
- Metrics calculation accuracy
- Label standardization 
- Confusion matrix building
- Distribution calculations
- Edge cases and error handling
"""

import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
from datetime import datetime

from plexus.Evaluation import Evaluation, AccuracyEvaluation
from plexus.scores.Score import Score
from plexus.Scorecard import Scorecard


class MockScorecard:
    """Mock scorecard for testing"""
    def __init__(self, name="test_scorecard"):
        self.name = name
        self.properties = {'scores': []}
    
    def score_names(self):
        return ["test_score"]
    
    def get_accumulated_costs(self):
        return {"total_cost": 10.0}


def create_mock_score_result(predicted_value, actual_label, correct=None, score_name="test_score"):
    """Create a mock Score.Result for testing"""
    if correct is None:
        # Standardize labels for comparison like the real code does
        pred_clean = str(predicted_value).lower().strip()
        actual_clean = str(actual_label).lower().strip()
        pred_clean = 'na' if pred_clean in ['', 'nan', 'n/a', 'none', 'null'] else pred_clean
        actual_clean = 'na' if actual_clean in ['', 'nan', 'n/a', 'none', 'null'] else actual_clean
        correct = pred_clean == actual_clean
    
    # Create proper Score.Parameters instance
    parameters = Score.Parameters(
        name=score_name,
        scorecard_name="test_scorecard"
    )
    
    result = Score.Result(
        parameters=parameters,
        value=predicted_value,
        explanation=f"Explanation for {predicted_value}",
        metadata={
            'human_label': actual_label,
            'correct': correct,
            'explanation': f"Explanation for {predicted_value}"
        }
    )
    return result


def create_mock_evaluation_results(prediction_pairs, score_name="test_score"):
    """Create mock evaluation results from (predicted, actual) pairs"""
    results = []
    for i, (predicted, actual) in enumerate(prediction_pairs):
        if predicted == "ERROR":
            # Create error result
            parameters = Score.Parameters(
                name=score_name,
                scorecard_name="test_scorecard"
            )
            score_result = Score.Result(
                parameters=parameters,
                value="ERROR",
                error="Test error",
                metadata={}
            )
        else:
            score_result = create_mock_score_result(predicted, actual, score_name=score_name)
        
        result = {
            'form_id': f'form_{i}',
            'results': {
                score_name: score_result
            }
        }
        results.append(result)
    
    return results


@pytest.fixture
def mock_evaluation():
    """Create a mock evaluation instance"""
    with patch('plexus.Evaluation.PlexusDashboardClient') as mock_client:
        # Mock the dashboard client to return None to avoid initialization
        mock_client.for_account.return_value = None
        
        evaluation = Evaluation(
            scorecard_name="test_scorecard",
            scorecard=MockScorecard(),
            labeled_samples_filename="test.csv",
            account_key="test-account"
        )
        evaluation.subset_of_score_names = ["test_score"]
        evaluation.dashboard_client = None  # Ensure it's None to avoid issues
        return evaluation


class TestMetricsCalculation:
    """Test core metrics calculation logic"""
    
    def test_perfect_binary_classification(self, mock_evaluation):
        """Test perfect binary classification metrics"""
        results = create_mock_evaluation_results([
            ('yes', 'yes'), ('no', 'no'), ('yes', 'yes'), ('no', 'no')
        ])
        
        metrics = mock_evaluation.calculate_metrics(results)
        
        assert metrics['accuracy'] == 1.0
        assert metrics['precision'] == 1.0
        assert metrics['alignment'] == 1.0
        assert metrics['recall'] == 1.0
    
    def test_imperfect_binary_classification(self, mock_evaluation):
        """Test binary classification with some errors"""
        results = create_mock_evaluation_results([
            ('yes', 'yes'),  # TP
            ('no', 'no'),    # TN  
            ('yes', 'no'),   # FP
            ('no', 'yes')    # FN
        ])
        
        metrics = mock_evaluation.calculate_metrics(results)
        
        # TP=1, TN=1, FP=1, FN=1
        # Accuracy = (TP+TN)/(TP+TN+FP+FN) = 2/4 = 0.5
        # Precision = TP/(TP+FP) = 1/2 = 0.5
        # Alignment = Gwet's AC1 coefficient
        # Recall = TP/(TP+FN) = 1/2 = 0.5  
        assert metrics['accuracy'] == 0.5
        assert metrics['precision'] == 0.5
        assert metrics['alignment'] >= 0  # AC1 can be negative, but gets mapped to 0
        assert metrics['recall'] == 0.5
    
    def test_all_positive_predictions(self, mock_evaluation):
        """Test edge case where all predictions are positive"""
        results = create_mock_evaluation_results([
            ('yes', 'yes'), ('yes', 'no'), ('yes', 'yes'), ('yes', 'no')
        ])
        
        metrics = mock_evaluation.calculate_metrics(results)
        
        # TP=2, TN=0, FP=2, FN=0
        # Precision = TP/(TP+FP) = 2/4 = 0.5
        # Recall = TP/(TP+FN) = 2/2 = 1.0
        assert metrics['accuracy'] == 0.5
        assert metrics['precision'] == 0.5
        assert metrics['recall'] == 1.0
    
    def test_empty_results(self, mock_evaluation):
        """Test handling of empty results"""
        metrics = mock_evaluation.calculate_metrics([])
        
        assert metrics['accuracy'] == 0
        assert metrics['precision'] == 0
        assert metrics['alignment'] == 0
        assert metrics['recall'] == 0
        assert 'confusionMatrix' in metrics  # Should have default matrix
        assert len(metrics['predictedClassDistribution']) == 1
        assert len(metrics['datasetClassDistribution']) == 1


class TestLabelStandardization:
    """Test label standardization and comparison logic"""
    
    def test_case_insensitive_matching(self, mock_evaluation):
        """Test that label matching is case insensitive"""
        results = create_mock_evaluation_results([
            ('Yes', 'yes'), ('NO', 'no'), ('Yes', 'YES'), ('No', 'NO')
        ])
        
        metrics = mock_evaluation.calculate_metrics(results)
        assert metrics['accuracy'] == 1.0
    
    def test_whitespace_handling(self, mock_evaluation):
        """Test whitespace is handled in label comparison"""
        results = create_mock_evaluation_results([
            (' yes ', 'yes'), ('no ', ' no'), ('  yes', 'yes  ')
        ])
        
        metrics = mock_evaluation.calculate_metrics(results)
        assert metrics['accuracy'] == 1.0
    
    def test_null_value_standardization(self, mock_evaluation):
        """Test various null representations are standardized to 'na'"""
        results = create_mock_evaluation_results([
            ('', 'na'),         # Empty string to na
            ('nan', 'na'),      # nan to na
            ('n/a', 'na'),      # n/a to na  
            ('none', 'na'),     # none to na
            ('null', 'na'),     # null to na
            ('N/A', 'na'),      # Case insensitive N/A
        ])
        
        metrics = mock_evaluation.calculate_metrics(results)
        assert metrics['accuracy'] == 1.0
    
    def test_mixed_null_representations(self, mock_evaluation):
        """Test mixed null representations in actual vs predicted"""
        results = create_mock_evaluation_results([
            ('', ''),           # Both empty
            ('nan', 'n/a'),     # Different null representations should match
            ('none', 'null'),   # Different null representations should match
            ('N/A', 'na'),      # Case differences in nulls
        ])
        
        metrics = mock_evaluation.calculate_metrics(results)
        assert metrics['accuracy'] == 1.0


class TestConfusionMatrixBuilding:
    """Test confusion matrix construction logic"""
    
    def test_binary_confusion_matrix_structure(self, mock_evaluation):
        """Test binary confusion matrix has correct structure"""
        results = create_mock_evaluation_results([
            ('yes', 'yes'), ('no', 'no'), ('yes', 'no'), ('no', 'yes')
        ])
        
        metrics = mock_evaluation.calculate_metrics(results)
        confusion_matrix = metrics['confusionMatrix']
        
        assert set(confusion_matrix['labels']) == {'yes', 'no'}
        assert len(confusion_matrix['matrix']) == 2
        assert len(confusion_matrix['matrix'][0]) == 2
        
        # Check matrix values - should be [[1, 1], [1, 1]] (TP, FN, FP, TN)
        labels = confusion_matrix['labels']
        matrix = confusion_matrix['matrix']
        
        if labels[0] == 'no':  # Labels are sorted
            # Matrix[actual][predicted]: no->no=1, no->yes=1, yes->no=1, yes->yes=1
            assert matrix[0][0] == 1  # no predicted as no
            assert matrix[0][1] == 1  # no predicted as yes
            assert matrix[1][0] == 1  # yes predicted as no  
            assert matrix[1][1] == 1  # yes predicted as yes
        else:
            # If yes comes first in sorted order
            assert matrix[0][0] == 1  # yes predicted as yes
            assert matrix[0][1] == 1  # yes predicted as no
            assert matrix[1][0] == 1  # no predicted as yes
            assert matrix[1][1] == 1  # no predicted as no
    
    def test_single_class_confusion_matrix(self, mock_evaluation):
        """Test confusion matrix when only one class is present"""
        results = create_mock_evaluation_results([
            ('yes', 'yes'), ('yes', 'yes'), ('yes', 'yes')
        ])
        
        metrics = mock_evaluation.calculate_metrics(results)
        confusion_matrix = metrics['confusionMatrix']
        
        # Should still create a matrix structure, but might be 1x1 or padded
        assert len(confusion_matrix['labels']) >= 1
        assert 'yes' in confusion_matrix['labels']
    
    def test_multiclass_confusion_matrix(self, mock_evaluation):
        """Test confusion matrix for multiclass classification"""
        results = create_mock_evaluation_results([
            ('class_a', 'class_a'), ('class_b', 'class_a'), 
            ('class_c', 'class_c'), ('class_a', 'class_b'),
            ('class_b', 'class_b'), ('class_c', 'class_a')
        ])
        
        metrics = mock_evaluation.calculate_metrics(results)
        confusion_matrix = metrics['confusionMatrix']
        
        assert len(confusion_matrix['labels']) == 3
        assert set(confusion_matrix['labels']) == {'class_a', 'class_b', 'class_c'}
        assert len(confusion_matrix['matrix']) == 3
        assert all(len(row) == 3 for row in confusion_matrix['matrix'])


class TestDistributionCalculations:
    """Test predicted and actual label distribution calculations"""
    
    def test_predicted_distribution_accuracy(self, mock_evaluation):
        """Test predicted label distribution is calculated correctly"""
        results = create_mock_evaluation_results([
            ('yes', 'no'), ('yes', 'yes'), ('no', 'no'), ('no', 'yes')
        ])
        
        metrics = mock_evaluation.calculate_metrics(results)
        pred_dist = {item['label']: item for item in metrics['predictedClassDistribution']}
        
        assert pred_dist['yes']['count'] == 2
        assert pred_dist['no']['count'] == 2
        assert pred_dist['yes']['percentage'] == 50.0
        assert pred_dist['no']['percentage'] == 50.0
        assert pred_dist['yes']['score'] == 'test_score'
    
    def test_actual_distribution_accuracy(self, mock_evaluation):
        """Test actual label distribution is calculated correctly"""
        results = create_mock_evaluation_results([
            ('no', 'yes'), ('yes', 'yes'), ('no', 'no'), ('yes', 'yes')
        ])
        
        metrics = mock_evaluation.calculate_metrics(results)
        actual_dist = {item['label']: item for item in metrics['datasetClassDistribution']}
        
        assert actual_dist['yes']['count'] == 3
        assert actual_dist['no']['count'] == 1
        assert actual_dist['yes']['percentage'] == 75.0
        assert actual_dist['no']['percentage'] == 25.0
        assert actual_dist['yes']['score'] == 'test_score'
    
    def test_distribution_with_standardized_labels(self, mock_evaluation):
        """Test distribution calculation with label standardization"""
        results = create_mock_evaluation_results([
            ('Yes', 'yes'), ('NO', 'n/a'), ('', 'na'), ('null', 'NA')
        ])
        
        metrics = mock_evaluation.calculate_metrics(results)
        pred_dist = {item['label']: item['count'] for item in metrics['predictedClassDistribution']}
        actual_dist = {item['label']: item['count'] for item in metrics['datasetClassDistribution']}
        
        # Check standardization: only specific null values become 'na'
        assert pred_dist.get('yes', 0) == 1    # 'Yes' -> 'yes'
        assert pred_dist.get('no', 0) == 1     # 'NO' -> 'no' (not standardized to na)
        assert pred_dist.get('na', 0) == 2     # '', 'null' -> 'na'
        assert actual_dist.get('yes', 0) == 1  # 'yes' -> 'yes'
        assert actual_dist.get('na', 0) == 3   # 'n/a', 'na', 'NA' all become 'na'


class TestErrorHandling:
    """Test error handling in metrics computation"""
    
    def test_error_results_filtered_out(self, mock_evaluation):
        """Test that ERROR results are filtered out of metrics"""
        results = create_mock_evaluation_results([
            ('yes', 'yes'), ('ERROR', 'yes'), ('no', 'no'), ('ERROR', 'no')
        ])
        
        metrics = mock_evaluation.calculate_metrics(results)
        
        # Only non-ERROR results should be counted
        assert metrics['accuracy'] == 1.0  # 2 correct out of 2 non-error results
        
        # Distributions should only include non-error results
        total_predicted = sum(item['count'] for item in metrics['predictedClassDistribution'])
        total_actual = sum(item['count'] for item in metrics['datasetClassDistribution'])
        assert total_predicted == 2
        assert total_actual == 2
    
    def test_all_error_results(self, mock_evaluation):
        """Test handling when all results are errors"""
        results = create_mock_evaluation_results([
            ('ERROR', 'yes'), ('ERROR', 'no'), ('ERROR', 'yes')
        ])
        
        metrics = mock_evaluation.calculate_metrics(results)
        
        # Should handle gracefully with default values
        assert metrics['accuracy'] == 0
        # Should still have default distribution entries
        assert len(metrics['predictedClassDistribution']) == 1
        assert len(metrics['datasetClassDistribution']) == 1
    
    def test_error_as_legitimate_class_label(self, mock_evaluation):
        """Test that 'error' as a class label (without error attribute) is counted in metrics"""
        # Create results where "error" is a legitimate prediction class, not a system error
        results = []
        for i, (predicted, actual) in enumerate([('yes', 'yes'), ('error', 'yes'), ('no', 'no'), ('error', 'error')]):
            # Create normal score result without error attribute
            score_result = create_mock_score_result(predicted, actual, score_name="test_score")
            result = {
                'form_id': f'form_{i}',
                'results': {
                    'test_score': score_result
                }
            }
            results.append(result)
        
        metrics = mock_evaluation.calculate_metrics(results)
        
        # All 4 results should be counted (2 correct: yes->yes, error->error; 2 incorrect: error->yes, no->no incorrect)
        # Wait, let me recalculate: yes==yes (correct), error==yes (incorrect), no==no (correct), error==error (correct)
        # So 3 correct out of 4 = 75%
        assert metrics['accuracy'] == 0.75  # 3 correct out of 4 results
        
        # Distributions should include all 4 results including "error" as a class
        total_predicted = sum(item['count'] for item in metrics['predictedClassDistribution'])
        total_actual = sum(item['count'] for item in metrics['datasetClassDistribution'])
        assert total_predicted == 4
        assert total_actual == 4
        
        # Check that "error" appears in the distributions as a legitimate class
        predicted_labels = {item['label'] for item in metrics['predictedClassDistribution']}
        assert 'error' in predicted_labels
    
    def test_missing_metadata_handling(self, mock_evaluation):
        """Test handling of results with missing metadata"""
        # Create result with minimal metadata
        parameters = Score.Parameters(
            name="test_score",
            scorecard_name="test_scorecard"
        )
        result = {
            'form_id': 'test_form',
            'results': {
                'test_score': Score.Result(
                    parameters=parameters,
                    value="yes",
                    explanation="test",
                    metadata={
                        'human_label': 'yes',
                        'correct': True  # Need this field for metrics calculation
                    }
                )
            }
        }
        
        # Should not crash, should handle missing metadata gracefully
        metrics = mock_evaluation.calculate_metrics([result])
        assert isinstance(metrics, dict)
        assert 'accuracy' in metrics


class TestMultiScoreHandling:
    """Test handling of multiple scores in evaluation"""
    
    def test_primary_score_filtering(self, mock_evaluation):
        """Test that only primary score is used for metrics when specified"""
        # Create results with multiple scores but set primary score
        mock_evaluation.subset_of_score_names = ["primary_score"]
        
        results = []
        for i in range(3):
            result = {
                'form_id': f'form_{i}',
                'results': {
                    'primary_score': create_mock_score_result('yes', 'yes', score_name='primary_score'),
                    'dependency_score': create_mock_score_result('no', 'no', score_name='dependency_score')
                }
            }
            results.append(result)
        
        metrics = mock_evaluation.calculate_metrics(results)
        
        # Should only process primary_score results
        assert metrics['accuracy'] == 1.0
        # All distribution entries should be for primary_score
        assert all(item['score'] == 'primary_score' for item in metrics['predictedClassDistribution'])
        assert all(item['score'] == 'primary_score' for item in metrics['datasetClassDistribution'])


if __name__ == '__main__':
    pytest.main([__file__, '-v'])