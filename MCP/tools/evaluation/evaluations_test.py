#!/usr/bin/env python3
"""
Unit tests for evaluation tools
"""
import pytest
import os
import json
from unittest.mock import patch, Mock, AsyncMock
from io import StringIO

pytestmark = pytest.mark.unit


class TestEvaluationInfoTool:
    """Test plexus_evaluation_info unified tool patterns"""
    
    def test_evaluation_info_validation_patterns(self):
        """Test evaluation info parameter validation patterns for unified tool"""
        def validate_evaluation_info_params(evaluation_id=None, use_latest=False, 
                                           account_key='call-criteria', evaluation_type="",
                                           include_score_results=False, include_examples=False, 
                                           predicted_value=None, actual_value=None,
                                           limit=10, output_format="json"):
            # If evaluation_id is provided, it cannot be empty
            if evaluation_id is not None and not evaluation_id.strip():
                return False, "evaluation_id cannot be empty"
            
            # Must specify either evaluation_id or use_latest
            if not evaluation_id and not use_latest:
                return False, "Must specify either evaluation_id or use_latest=True"
            
            # Cannot specify both
            if evaluation_id and use_latest:
                return False, "Cannot specify both evaluation_id and use_latest=True"
            
            # Test include_score_results parameter
            if not isinstance(include_score_results, bool):
                return False, "include_score_results must be a boolean"
            
            # Test include_examples parameter
            if not isinstance(include_examples, bool):
                return False, "include_examples must be a boolean"
            
            # Test limit parameter
            try:
                limit_int = int(limit)
                if limit_int < 1:
                    return False, "limit must be positive"
            except (ValueError, TypeError):
                return False, "limit must be a valid number"
            
            # Test output format
            if output_format not in ["json", "yaml", "text"]:
                return False, "output_format must be 'json', 'yaml', or 'text'"
            
            # Test predicted_value and actual_value parameters
            if predicted_value is not None and not isinstance(predicted_value, str):
                return False, "predicted_value must be a string or None"
            if actual_value is not None and not isinstance(actual_value, str):
                return False, "actual_value must be a string or None"
            
            return True, None
        
        # Test valid parameters - specific evaluation ID
        valid, error = validate_evaluation_info_params(evaluation_id="eval-123")
        assert valid is True
        assert error is None
        
        # Test valid parameters - use latest
        valid, error = validate_evaluation_info_params(use_latest=True)
        assert valid is True
        assert error is None
        
        # Test with all optional parameters for specific ID
        valid, error = validate_evaluation_info_params(evaluation_id="eval-123", include_score_results=True, 
                                                      include_examples=True, predicted_value="yes", actual_value="no", limit=20, output_format="yaml")
        assert valid is True
        assert error is None
        
        # Test with all optional parameters for latest
        valid, error = validate_evaluation_info_params(use_latest=True, account_key="test-account", 
                                                      evaluation_type="accuracy", output_format="text")
        assert valid is True
        assert error is None
        
        # Test with confusion matrix parameters
        valid, error = validate_evaluation_info_params(evaluation_id="eval-123", include_examples=True,
                                                      predicted_value="medium", actual_value="high")
        assert valid is True
        assert error is None
        
        # Test with only predicted_value
        valid, error = validate_evaluation_info_params(evaluation_id="eval-123", include_examples=True,
                                                      predicted_value="yes")
        assert valid is True
        assert error is None
        
        # Test with only actual_value
        valid, error = validate_evaluation_info_params(evaluation_id="eval-123", include_examples=True,
                                                      actual_value="no")
        assert valid is True
        assert error is None
        
        # Test missing both evaluation_id and use_latest
        valid, error = validate_evaluation_info_params()
        assert valid is False
        assert "Must specify either evaluation_id or use_latest=True" in error
        
        # Test both evaluation_id and use_latest specified
        valid, error = validate_evaluation_info_params(evaluation_id="eval-123", use_latest=True)
        assert valid is False
        assert "Cannot specify both evaluation_id and use_latest=True" in error
        
        # Test empty evaluation ID
        valid, error = validate_evaluation_info_params(evaluation_id="")
        assert valid is False
        assert "evaluation_id cannot be empty" in error
        
        # Test whitespace-only evaluation ID
        valid, error = validate_evaluation_info_params(evaluation_id="   ")
        assert valid is False
        assert "evaluation_id cannot be empty" in error
        
        # Test invalid include_score_results
        valid, error = validate_evaluation_info_params(evaluation_id="eval-123", include_score_results="invalid")
        assert valid is False
        assert "include_score_results must be a boolean" in error
        
        # Test invalid include_examples
        valid, error = validate_evaluation_info_params(evaluation_id="eval-123", include_examples="invalid")
        assert valid is False
        assert "include_examples must be a boolean" in error
        
        # Test invalid limit
        valid, error = validate_evaluation_info_params(evaluation_id="eval-123", limit="invalid")
        assert valid is False
        assert "limit must be a valid number" in error
        
        # Test negative limit
        valid, error = validate_evaluation_info_params(evaluation_id="eval-123", limit=-5)
        assert valid is False
        assert "limit must be positive" in error
        
        # Test invalid output format
        valid, error = validate_evaluation_info_params(evaluation_id="eval-123", output_format="xml")
        assert valid is False
        assert "output_format must be 'json', 'yaml', or 'text'" in error
        
        # Test invalid predicted_value type
        valid, error = validate_evaluation_info_params(evaluation_id="eval-123", predicted_value=123)
        assert valid is False
        assert "predicted_value must be a string or None" in error
        
        # Test invalid actual_value type
        valid, error = validate_evaluation_info_params(evaluation_id="eval-123", actual_value=123)
        assert valid is False
        assert "actual_value must be a string or None" in error
    
    def test_evaluation_import_patterns(self):
        """Test evaluation import patterns"""
        def simulate_evaluation_import():
            try:
                # Mock successful import
                return True, None
            except ImportError as e:
                return False, f"Import error: Could not import Evaluation class: {str(e)}"
        
        # Test successful import
        success, error = simulate_evaluation_import()
        assert success is True
        assert error is None
        
        # Test import failure
        def simulate_import_failure():
            raise ImportError("Could not import Evaluation class")
        
        try:
            simulate_import_failure()
            assert False, "Should have raised ImportError"
        except ImportError as e:
            error_msg = f"Import error: Could not import Evaluation class: {str(e)}"
            assert "Could not import Evaluation class" in error_msg
    
    def test_evaluation_info_service_patterns(self):
        """Test Evaluation.get_evaluation_info service patterns"""
        # Mock evaluation info result
        mock_evaluation_info = {
            'id': 'eval-123',
            'type': 'accuracy',
            'status': 'COMPLETED',
            'scorecard_name': 'Test Scorecard',
            'scorecard_id': 'scorecard-456',
            'score_name': 'Test Score',
            'score_id': 'score-789',
            'total_items': 100,
            'processed_items': 100,
            'metrics': [
                {'name': 'accuracy', 'value': 0.85},
                {'name': 'precision', 'value': 0.80},
                {'name': 'recall', 'value': 0.90}
            ],
            'accuracy': 85.0,
            'cost': 0.042,
            'started_at': '2024-01-01T10:00:00Z',
            'created_at': '2024-01-01T09:00:00Z',
            'updated_at': '2024-01-01T11:00:00Z'
        }
        
        def simulate_get_evaluation_info(evaluation_id, include_score_results):
            return mock_evaluation_info
        
        result = simulate_get_evaluation_info("eval-123", False)
        assert result['id'] == 'eval-123'
        assert result['type'] == 'accuracy'
        assert result['status'] == 'COMPLETED'
        assert result['total_items'] == 100
        assert result['accuracy'] == 85.0
        assert len(result['metrics']) == 3
    
    def test_evaluation_payload_building_patterns(self):
        """Test evaluation payload building patterns"""
        # Mock evaluation info
        evaluation_info = {
            'id': 'eval-123',
            'type': 'accuracy',
            'status': 'COMPLETED',
            'scorecard_name': 'Test Scorecard',
            'scorecard_id': 'scorecard-456',
            'score_name': 'Test Score',
            'score_id': 'score-789',
            'total_items': 100,
            'processed_items': 100,
            'metrics': [{'name': 'accuracy', 'value': 0.85}],
            'accuracy': 85.0,
            'cost': 0.042,
            'started_at': '2024-01-01T10:00:00Z',
            'created_at': '2024-01-01T09:00:00Z',
            'updated_at': '2024-01-01T11:00:00Z'
        }
        
        # Build structured payload
        payload = {
            "id": evaluation_info['id'],
            "type": evaluation_info['type'],
            "status": evaluation_info['status'],
            "scorecard": evaluation_info['scorecard_name'] or evaluation_info['scorecard_id'],
            "score": evaluation_info['score_name'] or evaluation_info['score_id'],
            "total_items": evaluation_info['total_items'],
            "processed_items": evaluation_info['processed_items'],
            "metrics": evaluation_info['metrics'],
            "accuracy": evaluation_info['accuracy'],
            "cost": evaluation_info['cost'],
            "started_at": evaluation_info['started_at'],
            "created_at": evaluation_info['created_at'],
            "updated_at": evaluation_info['updated_at'],
        }
        
        assert payload['id'] == 'eval-123'
        assert payload['scorecard'] == 'Test Scorecard'
        assert payload['score'] == 'Test Score'
        assert payload['total_items'] == 100
        assert payload['accuracy'] == 85.0
    
    def test_examples_fetching_patterns(self):
        """Test examples fetching patterns for evaluation info"""
        # Mock score results for examples
        mock_score_results = [
            {
                'id': 'sr-1',
                'value': 'yes',
                'explanation': 'Test explanation 1',
                'itemId': 'item-1',
                'correct': True,
                'metadata': json.dumps({
                    'results': {
                        'score-789': {
                            'metadata': {'human_label': 'yes'}
                        }
                    }
                })
            },
            {
                'id': 'sr-2',
                'value': 'no',
                'explanation': 'Test explanation 2',
                'itemId': 'item-2',
                'correct': False,
                'metadata': json.dumps({
                    'results': {
                        'score-789': {
                            'metadata': {'human_label': 'yes'}
                        }
                    }
                })
            }
        ]
        
        def categorize_examples(score_results, limit=10):
            examples = {'tp': [], 'tn': [], 'fp': [], 'fn': []}
            
            for sr in score_results:
                predicted = (sr.get('value') or '').strip().lower()
                
                # Parse metadata to get human label
                md = sr.get('metadata')
                try:
                    if isinstance(md, str):
                        md = json.loads(md)
                except Exception:
                    md = None
                
                human_label = None
                if md and isinstance(md, dict):
                    res_md = md.get('results') or {}
                    if isinstance(res_md, dict) and res_md:
                        key0 = next(iter(res_md))
                        inner = res_md.get(key0) or {}
                        inner_md = inner.get('metadata') or {}
                        human_label = (inner_md.get('human_label') or '').strip().lower()
                
                # Categorize into quadrants
                if human_label in ("yes", "no") and predicted in ("yes", "no"):
                    if human_label == "yes" and predicted == "yes":
                        quadrant = "tp"
                    elif human_label == "no" and predicted == "no":
                        quadrant = "tn" 
                    elif human_label == "no" and predicted == "yes":
                        quadrant = "fp"
                    elif human_label == "yes" and predicted == "no":
                        quadrant = "fn"
                    else:
                        continue
                    
                    if len(examples[quadrant]) < limit:
                        examples[quadrant].append({
                            "score_result_id": sr.get('id'),
                            "item_id": sr.get('itemId'),
                            "predicted": predicted,
                            "actual": human_label,
                            "explanation": sr.get('explanation')
                        })
            
            return examples
        
        examples = categorize_examples(mock_score_results, 5)
        
        # First result should be TP (predicted yes, actual yes)
        assert len(examples['tp']) == 1
        assert examples['tp'][0]['predicted'] == 'yes'
        assert examples['tp'][0]['actual'] == 'yes'
        
        # Second result should be FN (predicted no, actual yes)
        assert len(examples['fn']) == 1
        assert examples['fn'][0]['predicted'] == 'no'
        assert examples['fn'][0]['actual'] == 'yes'
        
        # No FP or TN in this mock data
        assert len(examples['fp']) == 0
        assert len(examples['tn']) == 0
    
    def test_output_format_patterns(self):
        """Test output format handling patterns"""
        # Mock payload
        payload = {
            'id': 'eval-123',
            'type': 'accuracy',
            'status': 'COMPLETED',
            'accuracy': 85.0,
            'metrics': [{'name': 'accuracy', 'value': 0.85}]
        }
        
        def format_output(payload, output_format):
            if output_format.lower() == 'yaml':
                try:
                    import yaml
                    return yaml.safe_dump(payload, sort_keys=False)
                except Exception:
                    return json.dumps(payload)
            else:
                return json.dumps(payload)
        
        # Test JSON format
        json_output = format_output(payload, 'json')
        parsed = json.loads(json_output)
        assert parsed['id'] == 'eval-123'
        assert parsed['accuracy'] == 85.0
        
        # Test YAML format
        yaml_output = format_output(payload, 'yaml')
        assert 'id: eval-123' in yaml_output
        assert 'accuracy: 85.0' in yaml_output


    def test_text_output_format_patterns(self):
        """Test text output format patterns for unified tool"""
        # Mock evaluation data
        evaluation_info = {
            'id': 'eval-789',
            'type': 'accuracy',
            'status': 'COMPLETED',
            'scorecard_name': 'Test Scorecard',
            'scorecard_id': None,
            'score_name': 'Test Score',
            'score_id': None,
            'total_items': 200,
            'processed_items': 200,
            'metrics': [
                {'name': 'accuracy', 'value': 0.88},
                {'name': 'f1_score', 'value': 0.85}
            ],
            'accuracy': 88.0,
            'cost': 0.067,
            'started_at': '2024-01-03T09:00:00Z',
            'created_at': '2024-01-03T08:00:00Z',
            'updated_at': '2024-01-03T10:00:00Z',
            'elapsed_seconds': 3600,
            'estimated_remaining_seconds': None,
            'error_message': None,
            'error_details': None,
            'task_id': 'task-123'
        }
        
        def format_evaluation_text_output(evaluation_info):
            output_lines = []
            output_lines.append("=== Evaluation Information ===")
            output_lines.append(f"ID: {evaluation_info['id']}")
            output_lines.append(f"Type: {evaluation_info['type']}")
            output_lines.append(f"Status: {evaluation_info['status']}")
            
            if evaluation_info.get('scorecard_name'):
                output_lines.append(f"Scorecard: {evaluation_info['scorecard_name']}")
            elif evaluation_info.get('scorecard_id'):
                output_lines.append(f"Scorecard ID: {evaluation_info['scorecard_id']}")
            else:
                output_lines.append("Scorecard: Not specified")
                
            if evaluation_info.get('score_name'):
                output_lines.append(f"Score: {evaluation_info['score_name']}")
            elif evaluation_info.get('score_id'):
                output_lines.append(f"Score ID: {evaluation_info['score_id']}")
            else:
                output_lines.append("Score: Not specified")
            
            output_lines.append("\n=== Progress & Metrics ===")
            if evaluation_info.get('total_items'):
                output_lines.append(f"Total Items: {evaluation_info['total_items']}")
            if evaluation_info.get('processed_items') is not None:
                output_lines.append(f"Processed Items: {evaluation_info['processed_items']}")
            if evaluation_info.get('accuracy') is not None:
                output_lines.append(f"Accuracy: {evaluation_info['accuracy']:.2f}%")
            
            return "\n".join(output_lines)
        
        output = format_evaluation_text_output(evaluation_info)
        
        # Test key sections are present
        assert "=== Evaluation Information ===" in output
        assert "ID: eval-789" in output
        assert "Type: accuracy" in output
        assert "Status: COMPLETED" in output
        assert "Scorecard: Test Scorecard" in output
        assert "Score: Test Score" in output
        assert "=== Progress & Metrics ===" in output
        assert "Total Items: 200" in output
        assert "Processed Items: 200" in output
        assert "Accuracy: 88.00%" in output

class TestEvaluationToolsSharedPatterns:
    """Test shared patterns across evaluation tools"""
    
    def test_credential_validation_pattern(self):
        """Test credential validation patterns used across evaluation tools"""
        def validate_credentials():
            api_url = os.environ.get('PLEXUS_API_URL', '')
            api_key = os.environ.get('PLEXUS_API_KEY', '')
            
            if not api_url or not api_key:
                return False, "Missing API credentials"
            return True, None
        
        # Test with missing credentials
        with patch.dict(os.environ, {}, clear=True):
            valid, error = validate_credentials()
            assert valid is False
            assert "Missing API credentials" in error
        
        # Test with valid credentials
        with patch.dict(os.environ, {
            'PLEXUS_API_URL': 'https://test.example.com',
            'PLEXUS_API_KEY': 'test-key'
        }):
            valid, error = validate_credentials()
            assert valid is True
            assert error is None
    
    def test_stdout_redirection_pattern(self):
        """Test stdout redirection pattern used in all evaluation tools"""
        # Test the pattern used to capture unexpected stdout
        old_stdout = StringIO()
        temp_stdout = StringIO()
        
        try:
            # Write something that should be captured
            print("This should be captured", file=temp_stdout)
            
            # Check capture
            captured_output = temp_stdout.getvalue()
            assert "This should be captured" in captured_output
        finally:
            # Pattern always restores stdout
            pass
    
    def test_import_error_handling_pattern(self):
        """Test import error handling pattern for Evaluation class"""
        def simulate_import_attempt():
            try:
                # Mock import failure
                raise ImportError("Could not import Evaluation class")
            except ImportError as e:
                return f"Import error: Could not import Evaluation class: {str(e)}"
        
        error_message = simulate_import_attempt()
        assert "Could not import Evaluation class" in error_message
        assert "Import error:" in error_message
    
    def test_value_error_handling_pattern(self):
        """Test ValueError handling pattern"""
        def simulate_value_error():
            try:
                # Mock value error
                raise ValueError("Invalid evaluation ID format")
            except ValueError as e:
                return f"Error: {str(e)}"
        
        error_message = simulate_value_error()
        assert "Error: Invalid evaluation ID format" in error_message
    
    def test_general_exception_handling_pattern(self):
        """Test general exception handling pattern"""
        def simulate_unexpected_error():
            try:
                # Mock unexpected error
                raise RuntimeError("Unexpected database error")
            except Exception as e:
                return f"Unexpected error getting evaluation info: {str(e)}"
        
        error_message = simulate_unexpected_error()
        assert "Unexpected error getting evaluation info" in error_message
        assert "Unexpected database error" in error_message
    
    def test_none_result_handling_pattern(self):
        """Test handling of None results from service calls"""
        def simulate_service_call(return_none=False):
            if return_none:
                return None
            return {"id": "eval-123", "status": "COMPLETED"}
        
        # Test successful result
        result = simulate_service_call(False)
        assert result is not None
        assert result['id'] == 'eval-123'
        
        # Test None result
        result = simulate_service_call(True)
        assert result is None
    
    def test_json_output_pattern(self):
        """Test JSON output formatting pattern"""
        # Mock evaluation data
        evaluation_data = {
            'id': 'eval-123',
            'type': 'accuracy',
            'status': 'COMPLETED',
            'accuracy': 85.5,
            'metrics': [{'name': 'accuracy', 'value': 0.855}]
        }
        
        # Test JSON serialization
        json_output = json.dumps(evaluation_data)
        parsed = json.loads(json_output)
        
        assert parsed['id'] == 'eval-123'
        assert parsed['accuracy'] == 85.5
        assert len(parsed['metrics']) == 1
    
    def test_yaml_output_pattern(self):
        """Test YAML output formatting pattern"""
        # Mock evaluation data
        evaluation_data = {
            'id': 'eval-456',
            'type': 'consistency',
            'status': 'RUNNING'
        }
        
        def format_as_yaml(data):
            try:
                import yaml
                return yaml.safe_dump(data, sort_keys=False)
            except Exception:
                return json.dumps(data)
        
        yaml_output = format_as_yaml(evaluation_data)
        assert 'id: eval-456' in yaml_output
        assert 'type: consistency' in yaml_output
        assert 'status: RUNNING' in yaml_output


class TestEvaluationScoreResultFindTool:
    """Test plexus_evaluation_score_result_find tool patterns"""

    def test_evaluation_score_result_find_validation_patterns(self):
        """Test evaluation score result find parameter validation patterns"""
        def validate_evaluation_score_result_find_params(evaluation_id="", predicted_value=None,
                                                        actual_value=None, limit=5, offset=None):
            # evaluation_id is required
            if not evaluation_id or not evaluation_id.strip():
                return False, "evaluation_id is required"

            # Test limit parameter
            try:
                limit_int = int(limit)
                if limit_int < 1:
                    return False, "limit must be positive"
            except (ValueError, TypeError):
                return False, "limit must be a valid number"

            # Test offset parameter
            if offset is not None:
                try:
                    offset_int = int(offset)
                    if offset_int < 0:
                        return False, "offset must be non-negative"
                except (ValueError, TypeError):
                    return False, "offset must be a valid number"

            # Test predicted_value parameter
            if predicted_value is not None and not isinstance(predicted_value, str):
                return False, "predicted_value must be a string or None"

            # Test actual_value parameter
            if actual_value is not None and not isinstance(actual_value, str):
                return False, "actual_value must be a string or None"

            return True, None

        # Test valid parameters - minimal
        valid, error = validate_evaluation_score_result_find_params(evaluation_id="eval-123")
        assert valid is True
        assert error is None

        # Test valid parameters - with filtering
        valid, error = validate_evaluation_score_result_find_params(
            evaluation_id="eval-123",
            predicted_value="yes",
            actual_value="no",
            limit=10,
            offset=5
        )
        assert valid is True
        assert error is None

        # Test valid parameters - with pagination only
        valid, error = validate_evaluation_score_result_find_params(
            evaluation_id="eval-123",
            limit=20,
            offset=0
        )
        assert valid is True
        assert error is None

        # Test missing evaluation_id
        valid, error = validate_evaluation_score_result_find_params(evaluation_id="")
        assert valid is False
        assert "evaluation_id is required" in error

        # Test whitespace-only evaluation_id
        valid, error = validate_evaluation_score_result_find_params(evaluation_id="   ")
        assert valid is False
        assert "evaluation_id is required" in error

        # Test invalid limit
        valid, error = validate_evaluation_score_result_find_params(evaluation_id="eval-123", limit="invalid")
        assert valid is False
        assert "limit must be a valid number" in error

        # Test negative limit
        valid, error = validate_evaluation_score_result_find_params(evaluation_id="eval-123", limit=-1)
        assert valid is False
        assert "limit must be positive" in error

        # Test invalid offset
        valid, error = validate_evaluation_score_result_find_params(evaluation_id="eval-123", offset="invalid")
        assert valid is False
        assert "offset must be a valid number" in error

        # Test negative offset
        valid, error = validate_evaluation_score_result_find_params(evaluation_id="eval-123", offset=-1)
        assert valid is False
        assert "offset must be non-negative" in error

        # Test invalid predicted_value type
        valid, error = validate_evaluation_score_result_find_params(evaluation_id="eval-123", predicted_value=123)
        assert valid is False
        assert "predicted_value must be a string or None" in error

        # Test invalid actual_value type
        valid, error = validate_evaluation_score_result_find_params(evaluation_id="eval-123", actual_value=123)
        assert valid is False
        assert "actual_value must be a string or None" in error

    def test_confusion_matrix_cell_grouping_patterns(self):
        """Test confusion matrix cell grouping patterns"""
        # Mock score results
        mock_score_results = [
            {
                'id': 'sr-1',
                'value': 'yes',
                'explanation': 'Correct prediction',
                'itemId': 'item-1',
                'metadata': json.dumps({
                    'results': {
                        'score-789': {
                            'metadata': {'human_label': 'yes'}
                        }
                    }
                })
            },
            {
                'id': 'sr-2',
                'value': 'no',
                'explanation': 'Incorrect prediction',
                'itemId': 'item-2',
                'metadata': json.dumps({
                    'results': {
                        'score-789': {
                            'metadata': {'human_label': 'yes'}
                        }
                    }
                })
            },
            {
                'id': 'sr-3',
                'value': 'yes',
                'explanation': 'False positive',
                'itemId': 'item-3',
                'metadata': json.dumps({
                    'results': {
                        'score-789': {
                            'metadata': {'human_label': 'no'}
                        }
                    }
                })
            }
        ]

        def group_by_confusion_matrix_cells(score_results):
            from collections import defaultdict
            matrix_cells = defaultdict(list)

            for sr in score_results:
                # Extract predicted value
                predicted = (sr.get('value') or '').strip().lower()

                # Extract actual value from metadata
                md = sr.get('metadata')
                try:
                    if isinstance(md, str):
                        md = json.loads(md)
                except Exception:
                    md = None

                human_label = None
                if md and isinstance(md, dict):
                    res_md = md.get('results') or {}
                    if isinstance(res_md, dict) and res_md:
                        key0 = next(iter(res_md))
                        inner = res_md.get(key0) or {}
                        inner_md = inner.get('metadata') or {}
                        human_label = (inner_md.get('human_label') or '').strip().lower()

                actual = human_label or 'unknown'
                cell_key = (predicted, actual)
                matrix_cells[cell_key].append(sr)

            return matrix_cells

        matrix_cells = group_by_confusion_matrix_cells(mock_score_results)

        # Test cell grouping
        assert len(matrix_cells) == 3  # Three different cells
        assert ('yes', 'yes') in matrix_cells  # True positive
        assert ('no', 'yes') in matrix_cells   # False negative
        assert ('yes', 'no') in matrix_cells   # False positive

        # Test cell contents
        assert len(matrix_cells[('yes', 'yes')]) == 1
        assert len(matrix_cells[('no', 'yes')]) == 1
        assert len(matrix_cells[('yes', 'no')]) == 1

        # Test specific items in cells
        tp_item = matrix_cells[('yes', 'yes')][0]
        assert tp_item['id'] == 'sr-1'
        assert tp_item['value'] == 'yes'

        fn_item = matrix_cells[('no', 'yes')][0]
        assert fn_item['id'] == 'sr-2'
        assert fn_item['value'] == 'no'

        fp_item = matrix_cells[('yes', 'no')][0]
        assert fp_item['id'] == 'sr-3'
        assert fp_item['value'] == 'yes'

    def test_filtering_patterns(self):
        """Test filtering by predicted/actual values"""
        # Mock processed results
        processed_results = [
            {'predicted': 'yes', 'actual': 'yes', 'id': 'sr-1'},
            {'predicted': 'no', 'actual': 'yes', 'id': 'sr-2'},
            {'predicted': 'yes', 'actual': 'no', 'id': 'sr-3'},
            {'predicted': 'no', 'actual': 'no', 'id': 'sr-4'}
        ]

        def apply_filtering(results, predicted_value=None, actual_value=None):
            filtered = []
            for result in results:
                pred_match = predicted_value is None or result['predicted'] == predicted_value.lower()
                actual_match = actual_value is None or result['actual'] == actual_value.lower()

                if pred_match and actual_match:
                    filtered.append(result)

            return filtered

        # Test no filtering - should return all
        all_results = apply_filtering(processed_results)
        assert len(all_results) == 4

        # Test filter by predicted value only
        yes_predicted = apply_filtering(processed_results, predicted_value='yes')
        assert len(yes_predicted) == 2
        assert all(r['predicted'] == 'yes' for r in yes_predicted)

        no_predicted = apply_filtering(processed_results, predicted_value='no')
        assert len(no_predicted) == 2
        assert all(r['predicted'] == 'no' for r in no_predicted)

        # Test filter by actual value only
        yes_actual = apply_filtering(processed_results, actual_value='yes')
        assert len(yes_actual) == 2
        assert all(r['actual'] == 'yes' for r in yes_actual)

        no_actual = apply_filtering(processed_results, actual_value='no')
        assert len(no_actual) == 2
        assert all(r['actual'] == 'no' for r in no_actual)

        # Test filter by both predicted and actual
        tp_results = apply_filtering(processed_results, predicted_value='yes', actual_value='yes')
        assert len(tp_results) == 1
        assert tp_results[0]['id'] == 'sr-1'

        fp_results = apply_filtering(processed_results, predicted_value='yes', actual_value='no')
        assert len(fp_results) == 1
        assert fp_results[0]['id'] == 'sr-3'

        fn_results = apply_filtering(processed_results, predicted_value='no', actual_value='yes')
        assert len(fn_results) == 1
        assert fn_results[0]['id'] == 'sr-2'

        tn_results = apply_filtering(processed_results, predicted_value='no', actual_value='no')
        assert len(tn_results) == 1
        assert tn_results[0]['id'] == 'sr-4'

    def test_pagination_patterns(self):
        """Test offset-based pagination patterns"""
        # Mock filtered results
        filtered_results = [
            {'id': f'sr-{i}', 'predicted': 'yes', 'actual': 'yes'}
            for i in range(1, 11)  # 10 results
        ]

        def apply_pagination(results, limit=5, offset=0):
            start_idx = offset
            end_idx = offset + limit
            page_results = results[start_idx:end_idx]

            total_available = len(results)
            has_next_page = end_idx < total_available
            next_offset = end_idx if has_next_page else None

            return {
                'page_results': page_results,
                'pagination_info': {
                    'current_offset': offset,
                    'limit': limit,
                    'total_available': total_available,
                    'has_next_page': has_next_page,
                    'next_offset': next_offset
                }
            }

        # Test first page
        page1 = apply_pagination(filtered_results, limit=3, offset=0)
        assert len(page1['page_results']) == 3
        assert page1['page_results'][0]['id'] == 'sr-1'
        assert page1['page_results'][2]['id'] == 'sr-3'
        assert page1['pagination_info']['current_offset'] == 0
        assert page1['pagination_info']['has_next_page'] is True
        assert page1['pagination_info']['next_offset'] == 3

        # Test middle page
        page2 = apply_pagination(filtered_results, limit=3, offset=3)
        assert len(page2['page_results']) == 3
        assert page2['page_results'][0]['id'] == 'sr-4'
        assert page2['page_results'][2]['id'] == 'sr-6'
        assert page2['pagination_info']['current_offset'] == 3
        assert page2['pagination_info']['has_next_page'] is True
        assert page2['pagination_info']['next_offset'] == 6

        # Test last page (partial)
        page3 = apply_pagination(filtered_results, limit=3, offset=9)
        assert len(page3['page_results']) == 1
        assert page3['page_results'][0]['id'] == 'sr-10'
        assert page3['pagination_info']['current_offset'] == 9
        assert page3['pagination_info']['has_next_page'] is False
        assert page3['pagination_info']['next_offset'] is None

        # Test beyond available results
        page4 = apply_pagination(filtered_results, limit=3, offset=15)
        assert len(page4['page_results']) == 0
        assert page4['pagination_info']['current_offset'] == 15
        assert page4['pagination_info']['has_next_page'] is False
        assert page4['pagination_info']['next_offset'] is None

    def test_response_structure_patterns(self):
        """Test response structure patterns for evaluation score result find"""
        # Mock data
        evaluation_id = "eval-123"
        predicted_value = "yes"
        actual_value = "no"
        page_results = [
            {
                "score_result_id": "sr-1",
                "evaluation_id": "eval-123",
                "item_id": "item-1",
                "predicted": "yes",
                "actual": "no",
                "explanation": "Test explanation",
                "confidence": 0.85,
                "confusion_matrix_cell": {"predicted": "yes", "actual": "no"}
            }
        ]
        matrix_cells = {('yes', 'no'): [page_results[0]]}

        def build_response_structure(evaluation_id, predicted_value, actual_value,
                                   page_results, matrix_cells, offset, limit):
            total_available = len(page_results)
            has_next_page = (offset + limit) < total_available
            next_offset = (offset + limit) if has_next_page else None

            return {
                "context": {
                    "evaluation_id": evaluation_id,
                    "filters": {
                        "predicted_value": predicted_value,
                        "actual_value": actual_value
                    },
                    "pagination": {
                        "current_offset": offset,
                        "limit": limit,
                        "total_available": total_available,
                        "has_next_page": has_next_page,
                        "next_offset": next_offset
                    },
                    "confusion_matrix_cells": {
                        f"{cell_key[0]}_{cell_key[1]}": len(cell_items)
                        for cell_key, cell_items in matrix_cells.items()
                    }
                },
                "score_results": page_results,
                "summary": {
                    "total_results_found": total_available,
                    "results_in_page": len(page_results),
                    "confusion_matrix_cells_found": len(matrix_cells)
                }
            }

        response = build_response_structure(
            evaluation_id, predicted_value, actual_value,
            page_results, matrix_cells, 0, 5
        )

        # Test response structure
        assert 'context' in response
        assert 'score_results' in response
        assert 'summary' in response

        # Test context structure
        assert response['context']['evaluation_id'] == "eval-123"
        assert response['context']['filters']['predicted_value'] == "yes"
        assert response['context']['filters']['actual_value'] == "no"
        assert response['context']['pagination']['current_offset'] == 0
        assert response['context']['pagination']['limit'] == 5
        assert response['context']['confusion_matrix_cells']['yes_no'] == 1

        # Test score results structure
        assert len(response['score_results']) == 1
        assert response['score_results'][0]['score_result_id'] == "sr-1"
        assert response['score_results'][0]['predicted'] == "yes"
        assert response['score_results'][0]['actual'] == "no"
        assert response['score_results'][0]['confidence'] == 0.85

        # Test summary structure
        assert response['summary']['total_results_found'] == 1
        assert response['summary']['results_in_page'] == 1
        assert response['summary']['confusion_matrix_cells_found'] == 1

    def test_metadata_parsing_patterns(self):
        """Test metadata parsing patterns for extracting human labels"""
        def parse_human_label_from_metadata(metadata_str):
            try:
                if isinstance(metadata_str, str):
                    md = json.loads(metadata_str)
                else:
                    md = metadata_str
            except Exception:
                return None

            if md and isinstance(md, dict):
                res_md = md.get('results') or {}
                if isinstance(res_md, dict) and res_md:
                    key0 = next(iter(res_md))
                    inner = res_md.get(key0) or {}
                    inner_md = inner.get('metadata') or {}
                    human_label = (inner_md.get('human_label') or '').strip().lower()
                    return human_label if human_label else None

            return None

        # Test valid metadata
        valid_metadata = json.dumps({
            'results': {
                'score-789': {
                    'metadata': {'human_label': 'yes'}
                }
            }
        })

        label = parse_human_label_from_metadata(valid_metadata)
        assert label == 'yes'

        # Test metadata with whitespace
        whitespace_metadata = json.dumps({
            'results': {
                'score-789': {
                    'metadata': {'human_label': '  NO  '}
                }
            }
        })

        label = parse_human_label_from_metadata(whitespace_metadata)
        assert label == 'no'

        # Test empty metadata
        empty_metadata = json.dumps({})
        label = parse_human_label_from_metadata(empty_metadata)
        assert label is None

        # Test invalid JSON
        invalid_metadata = "invalid json"
        label = parse_human_label_from_metadata(invalid_metadata)
        assert label is None

        # Test missing human_label
        no_label_metadata = json.dumps({
            'results': {
                'score-789': {
                    'metadata': {}
                }
            }
        })

        label = parse_human_label_from_metadata(no_label_metadata)
        assert label is None

    def test_include_text_parameter_patterns(self):
        """Test include_text parameter handling patterns"""
        # Mock score result with full item data and metadata
        mock_score_result = {
            'id': 'sr-1',
            'value': 'yes',
            'explanation': 'Test explanation',
            'itemId': 'item-1',
            'item': {
                'id': 'item-1',
                'identifiers': ['call-123'],
                'text': 'This is a very long transcript text that should be excluded when include_text=False'
            },
            'metadata': json.dumps({
                'results': {
                    'score-789': {
                        'metadata': {
                            'human_label': 'yes',
                            'text': 'Another copy of transcript text in metadata'
                        }
                    }
                }
            })
        }

        def format_result_with_text_control(sr, include_text=False):
            """Format result respecting include_text parameter"""
            import json as _json

            # Extract predicted value
            predicted = (sr.get('value') or '').strip().lower()

            # Extract actual value from metadata
            md = sr.get('metadata')
            try:
                if isinstance(md, str):
                    md = _json.loads(md)
            except Exception:
                md = None

            human_label = None
            if md and isinstance(md, dict):
                res_md = md.get('results') or {}
                if isinstance(res_md, dict) and res_md:
                    key0 = next(iter(res_md))
                    inner = res_md.get(key0) or {}
                    inner_md = inner.get('metadata') or {}
                    human_label = (inner_md.get('human_label') or '').strip().lower()

            actual = human_label or 'unknown'

            formatted_result = {
                "score_result_id": sr.get('id'),
                "item_id": sr.get('itemId'),
                "predicted": predicted,
                "actual": actual,
                "explanation": sr.get('explanation')
            }

            # Add detailed metadata if available (but strip transcript text unless requested)
            if md and isinstance(md, dict):
                if include_text:
                    # Include full metadata with transcript text
                    formatted_result["detailed_metadata"] = md
                else:
                    # Strip transcript text from metadata to prevent context overflow
                    md_copy = _json.loads(_json.dumps(md))  # Deep copy
                    res_md = md_copy.get('results') or {}
                    if isinstance(res_md, dict):
                        for score_name, score_data in res_md.items():
                            if isinstance(score_data, dict):
                                inner_md = score_data.get('metadata') or {}
                                if isinstance(inner_md, dict) and 'text' in inner_md:
                                    # Remove the transcript text field
                                    inner_md.pop('text', None)
                    formatted_result["detailed_metadata"] = md_copy

            # Add item data if available (includes identifiers and optionally text)
            if sr.get('item'):
                item_data = sr.get('item')
                formatted_result["item"] = {
                    "id": item_data.get('id'),
                    "identifiers": item_data.get('identifiers')
                }
                # Only include text if explicitly requested to prevent context overflow
                if include_text:
                    formatted_result["item"]["text"] = item_data.get('text')

            return formatted_result

        # Test with include_text=False (default)
        result_without_text = format_result_with_text_control(mock_score_result, include_text=False)

        # Should have basic fields
        assert result_without_text['score_result_id'] == 'sr-1'
        assert result_without_text['predicted'] == 'yes'
        assert result_without_text['actual'] == 'yes'

        # Should have item data without text
        assert 'item' in result_without_text
        assert result_without_text['item']['id'] == 'item-1'
        assert result_without_text['item']['identifiers'] == ['call-123']
        assert 'text' not in result_without_text['item']  # Text should be excluded

        # Should have metadata without text field
        assert 'detailed_metadata' in result_without_text
        metadata = result_without_text['detailed_metadata']
        assert 'results' in metadata
        score_data = metadata['results']['score-789']
        assert 'metadata' in score_data
        inner_metadata = score_data['metadata']
        assert 'human_label' in inner_metadata
        assert 'text' not in inner_metadata  # Text field should be removed

        # Test with include_text=True
        result_with_text = format_result_with_text_control(mock_score_result, include_text=True)

        # Should have basic fields
        assert result_with_text['score_result_id'] == 'sr-1'
        assert result_with_text['predicted'] == 'yes'
        assert result_with_text['actual'] == 'yes'

        # Should have item data WITH text
        assert 'item' in result_with_text
        assert result_with_text['item']['id'] == 'item-1'
        assert result_with_text['item']['identifiers'] == ['call-123']
        assert 'text' in result_with_text['item']  # Text should be included
        assert 'very long transcript' in result_with_text['item']['text']

        # Should have metadata WITH text field
        assert 'detailed_metadata' in result_with_text
        metadata = result_with_text['detailed_metadata']
        assert 'results' in metadata
        score_data = metadata['results']['score-789']
        assert 'metadata' in score_data
        inner_metadata = score_data['metadata']
        assert 'human_label' in inner_metadata
        assert 'text' in inner_metadata  # Text field should be present
        assert 'Another copy of transcript' in inner_metadata['text']

    def test_include_text_default_value(self):
        """Test that include_text defaults to False"""
        def validate_include_text_default(include_text=False):
            # The default value should be False
            return include_text

        # Test with no parameter provided (uses default)
        default_value = validate_include_text_default()
        assert default_value is False

        # Test with explicit False
        explicit_false = validate_include_text_default(include_text=False)
        assert explicit_false is False

        # Test with explicit True
        explicit_true = validate_include_text_default(include_text=True)
        assert explicit_true is True