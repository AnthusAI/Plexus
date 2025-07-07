"""
Tests for plexus.cli.universal_code module

Tests the Universal Code YAML generation functionality for task outputs.
"""

import pytest
import json
import yaml
from datetime import datetime
from unittest.mock import patch

from plexus.cli.universal_code import (
    generate_universal_code_yaml,
    generate_prediction_universal_code,
    generate_evaluation_universal_code,
    detect_task_type_from_command,
    extract_scorecard_from_command,
    extract_score_from_command
)


class TestUniversalCodeGeneration:
    """Test Universal Code YAML generation functionality"""
    
    def test_generate_basic_universal_code_yaml(self):
        """Test basic YAML generation with minimal inputs"""
        command = "plexus predict --scorecard test-scorecard --score test-score"
        output_data = {"result": "success", "value": "positive"}
        task_type = "Prediction"
        
        result = generate_universal_code_yaml(
            command=command,
            output_data=output_data,
            task_type=task_type
        )
        
        # Verify it's valid YAML
        parsed = yaml.safe_load(result)
        
        # Check required structure
        assert "task_info" in parsed
        assert parsed["task_info"]["command"] == command
        assert parsed["task_info"]["type"] == task_type
        assert parsed["task_info"]["format"] == "Universal Code YAML"
        assert "generated_at" in parsed["task_info"]
        
        # Check output data is included
        assert parsed["result"] == "success"
        assert parsed["value"] == "positive"
        
        # Check header comments are present
        assert "# Prediction Task Output" in result
        assert f"# Command: {command}" in result
        assert "# Format: Universal Code YAML" in result
    
    def test_generate_universal_code_with_all_metadata(self):
        """Test YAML generation with all optional metadata"""
        command = "plexus predict --scorecard customer-sentiment --score sentiment-analysis"
        output_data = {"prediction": "positive", "confidence": 0.85}
        
        result = generate_universal_code_yaml(
            command=command,
            output_data=output_data,
            task_type="Prediction",
            task_description="Analyzes customer sentiment from support tickets",
            scorecard_name="customer-sentiment",
            score_name="sentiment-analysis"
        )
        
        parsed = yaml.safe_load(result)
        
        # Check all metadata is included
        assert parsed["task_info"]["description"] == "Analyzes customer sentiment from support tickets"
        assert parsed["task_info"]["scorecard"] == "customer-sentiment"
        assert parsed["task_info"]["score"] == "sentiment-analysis"
        
        # Check header comments include metadata
        assert "# Task Description: Analyzes customer sentiment from support tickets" in result
        assert "# Scorecard: customer-sentiment" in result
        assert "# Score: sentiment-analysis" in result
    
    def test_generate_universal_code_with_json_string_input(self):
        """Test YAML generation when output_data is a JSON string"""
        command = "plexus predict"
        json_output = '{"prediction": "negative", "explanation": "Contains negative sentiment"}'
        
        result = generate_universal_code_yaml(
            command=command,
            output_data=json_output,
            task_type="Prediction"
        )
        
        parsed = yaml.safe_load(result)
        
        # Check JSON was parsed correctly
        assert parsed["prediction"] == "negative"
        assert parsed["explanation"] == "Contains negative sentiment"
    
    def test_generate_universal_code_with_invalid_json_string(self):
        """Test YAML generation when output_data is invalid JSON string"""
        command = "plexus predict"
        invalid_json = "this is not json"
        
        result = generate_universal_code_yaml(
            command=command,
            output_data=invalid_json,
            task_type="Prediction"
        )
        
        parsed = yaml.safe_load(result)
        
        # Check invalid JSON is treated as plain text
        assert parsed["output"] == "this is not json"
    
    def test_generate_universal_code_with_list_data(self):
        """Test YAML generation when output_data is a list"""
        command = "plexus batch-predict"
        list_data = [
            {"item_id": "1", "prediction": "positive"},
            {"item_id": "2", "prediction": "negative"}
        ]
        
        result = generate_universal_code_yaml(
            command=command,
            output_data=list_data,
            task_type="Batch Processing"
        )
        
        parsed = yaml.safe_load(result)
        
        # Check list data is stored under "results"
        assert "results" in parsed
        assert len(parsed["results"]) == 2
        assert parsed["results"][0]["item_id"] == "1"
        assert parsed["results"][1]["prediction"] == "negative"


class TestPredictionUniversalCode:
    """Test prediction-specific Universal Code generation"""
    
    def test_generate_prediction_universal_code_basic(self):
        """Test basic prediction Universal Code generation"""
        command = "plexus predict --scorecard test --score sentiment"
        json_output = '{"prediction": "positive", "confidence": 0.9}'
        
        result = generate_prediction_universal_code(
            command=command,
            json_output=json_output,
            scorecard_name="test",
            score_name="sentiment"
        )
        
        parsed = yaml.safe_load(result)
        
        # Check prediction-specific structure
        assert parsed["task_info"]["type"] == "Prediction"
        assert "Executes a prediction using Plexus scorecards" in parsed["task_info"]["description"]
        assert parsed["prediction"] == "positive"
        assert parsed["confidence"] == 0.9
    
    def test_generate_prediction_universal_code_with_invalid_json(self):
        """Test prediction Universal Code with invalid JSON output"""
        command = "plexus predict"
        invalid_json = "Error: failed to generate prediction"
        
        result = generate_prediction_universal_code(
            command=command,
            json_output=invalid_json
        )
        
        parsed = yaml.safe_load(result)
        
        # Check invalid JSON is handled gracefully
        assert "raw_output" in parsed
        assert parsed["raw_output"] == "Error: failed to generate prediction"


class TestEvaluationUniversalCode:
    """Test evaluation-specific Universal Code generation"""
    
    def test_generate_evaluation_universal_code(self):
        """Test evaluation Universal Code generation"""
        command = "plexus evaluate --scorecard customer-feedback"
        evaluation_data = {
            "accuracy": 0.85,
            "precision": 0.82,
            "recall": 0.78,
            "total_items": 100
        }
        
        result = generate_evaluation_universal_code(
            command=command,
            output_data=evaluation_data,
            scorecard_name="customer-feedback"
        )
        
        parsed = yaml.safe_load(result)
        
        # Check evaluation-specific structure
        assert parsed["task_info"]["type"] == "Evaluation"
        assert "Executes a scorecard evaluation to measure accuracy" in parsed["task_info"]["description"]
        assert parsed["accuracy"] == 0.85
        assert parsed["total_items"] == 100


class TestCommandParsing:
    """Test command parsing utilities"""
    
    def test_detect_task_type_from_command(self):
        """Test task type detection from various commands"""
        test_cases = [
            ("plexus predict --scorecard test", "Prediction"),
            ("plexus batch-predict --input file.csv", "Prediction"),
            ("plexus evaluate --scorecard customer", "Evaluation"),
            ("plexus evaluation-report", "Evaluation"),
            ("plexus analyze-results", "Analysis"),
            ("plexus training-job", "Training"),
            ("plexus batch-process", "Batch Processing"),
            ("plexus unknown-command", "Command Execution")
        ]
        
        for command, expected_type in test_cases:
            result = detect_task_type_from_command(command)
            assert result == expected_type, f"Command '{command}' should detect '{expected_type}', got '{result}'"
    
    def test_extract_scorecard_from_command(self):
        """Test scorecard name extraction from commands"""
        test_cases = [
            ('plexus predict --scorecard "customer-sentiment"', "customer-sentiment"),
            ('plexus predict --scorecard customer-sentiment', "customer-sentiment"),
            ('plexus predict --scorecard-name "test-scorecard"', "test-scorecard"),
            ('plexus predict --scorecard-name test-scorecard', "test-scorecard"),
            ('plexus predict --input file.csv', None),
            ('plexus predict', None)
        ]
        
        for command, expected_scorecard in test_cases:
            result = extract_scorecard_from_command(command)
            assert result == expected_scorecard, f"Command '{command}' should extract '{expected_scorecard}', got '{result}'"
    
    def test_extract_score_from_command(self):
        """Test score name extraction from commands"""
        test_cases = [
            ('plexus predict --score "sentiment-analysis"', "sentiment-analysis"),
            ('plexus predict --score sentiment-analysis', "sentiment-analysis"),
            ('plexus predict --scores "multi-score"', "multi-score"),
            ('plexus predict --scores multi-score', "multi-score"),
            ('plexus predict --scorecard test', None),
            ('plexus predict', None)
        ]
        
        for command, expected_score in test_cases:
            result = extract_score_from_command(command)
            assert result == expected_score, f"Command '{command}' should extract '{expected_score}', got '{result}'"


class TestTimestampGeneration:
    """Test timestamp generation in Universal Code"""
    
    @patch('plexus.cli.universal_code.datetime')
    def test_consistent_timestamp_generation(self, mock_datetime):
        """Test that timestamps are consistent throughout the YAML"""
        # Mock datetime to return a fixed time
        fixed_time = datetime(2024, 1, 15, 12, 30, 45)
        mock_datetime.now.return_value = fixed_time
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
        
        command = "plexus predict"
        output_data = {"result": "test"}
        
        result = generate_universal_code_yaml(
            command=command,
            output_data=output_data,
            task_type="Prediction"
        )
        
        parsed = yaml.safe_load(result)
        
        # Check timestamp format
        assert parsed["task_info"]["generated_at"] == "2024-01-15T12:30:45"
        
        # Check timestamp appears in header comment
        assert "# Generated: 2024-01-15T12:30:45" in result


class TestErrorHandling:
    """Test error handling in Universal Code generation"""
    
    def test_yaml_generation_with_special_characters(self):
        """Test YAML generation with special characters that might break YAML"""
        command = "plexus predict"
        output_data = {
            "text": "This contains: special characters, quotes \"and\" apostrophes'",
            "unicode": "Special chars: éñüñé 🎯 ✅",
            "multiline": "Line 1\nLine 2\nLine 3"
        }
        
        result = generate_universal_code_yaml(
            command=command,
            output_data=output_data,
            task_type="Prediction"
        )
        
        # Should be able to parse the YAML without errors
        parsed = yaml.safe_load(result)
        assert parsed["text"] == "This contains: special characters, quotes \"and\" apostrophes'"
        assert "🎯" in parsed["unicode"]
        assert "Line 1\nLine 2\nLine 3" in parsed["multiline"]
    
    def test_yaml_generation_with_complex_nested_data(self):
        """Test YAML generation with deeply nested data structures"""
        command = "plexus predict"
        output_data = {
            "predictions": [
                {
                    "item_id": "1",
                    "scores": {
                        "sentiment": {"value": "positive", "confidence": 0.9},
                        "toxicity": {"value": "safe", "confidence": 0.95}
                    },
                    "metadata": {
                        "processing_time": 1.23,
                        "model_version": "v2.1"
                    }
                }
            ]
        }
        
        result = generate_universal_code_yaml(
            command=command,
            output_data=output_data,
            task_type="Batch Processing"
        )
        
        # Should handle complex nested structures
        parsed = yaml.safe_load(result)
        assert len(parsed["predictions"]) == 1
        assert parsed["predictions"][0]["scores"]["sentiment"]["value"] == "positive"
        assert parsed["predictions"][0]["metadata"]["processing_time"] == 1.23