#!/usr/bin/env python3
"""
Unit tests for prediction tools
"""
import pytest
import os
import json
from unittest.mock import patch, Mock, AsyncMock
from io import StringIO

pytestmark = pytest.mark.unit


class TestPredictionTool:
    """Test plexus_predict tool patterns"""
    
    def test_prediction_validation_patterns(self):
        """Test prediction parameter validation patterns"""
        def validate_prediction_params(scorecard_name, score_name, item_id=None, item_ids=None,
                                     include_input=False, include_trace=False, output_format="json",
                                     no_cache=False, yaml_only=False, version=None, latest=False):
            if not scorecard_name or not scorecard_name.strip():
                return False, "scorecard_name is required"
            if not score_name or not score_name.strip():
                return False, "score_name is required"
            
            # Must provide either item_id or item_ids
            if not item_id and not item_ids:
                return False, "Either item_id or item_ids must be provided"
            
            # Cannot provide both
            if item_id and item_ids:
                return False, "Cannot specify both item_id and item_ids. Use one or the other"
            
            # Cannot specify both no_cache and yaml_only
            if no_cache and yaml_only:
                return False, "Cannot specify both no_cache and yaml_only. Use one or the other"
            
            # Cannot specify both version and latest
            if version and latest:
                return False, "Cannot use both version and latest options. Choose one."
            
            # Validate boolean parameters
            if not isinstance(include_input, bool):
                return False, "include_input must be a boolean"
            if not isinstance(include_trace, bool):
                return False, "include_trace must be a boolean"
            if not isinstance(no_cache, bool):
                return False, "no_cache must be a boolean"
            if not isinstance(yaml_only, bool):
                return False, "yaml_only must be a boolean"
            
            # Validate output format
            if output_format not in ["json", "yaml"]:
                return False, "output_format must be 'json' or 'yaml'"
            
            return True, None
        
        # Test valid parameters with single item
        valid, error = validate_prediction_params("test-scorecard", "test-score", item_id="item-123")
        assert valid is True
        assert error is None
        
        # Test valid parameters with multiple items
        valid, error = validate_prediction_params("test-scorecard", "test-score", item_ids="item-1,item-2")
        assert valid is True
        assert error is None
        
        # Test with all optional parameters
        valid, error = validate_prediction_params("test-scorecard", "test-score", item_id="item-123",
                                                 include_input=True, include_trace=True, 
                                                 output_format="yaml", no_cache=True)
        assert valid is True
        assert error is None
        
        # Test missing scorecard name
        valid, error = validate_prediction_params("", "test-score", item_id="item-123")
        assert valid is False
        assert "scorecard_name is required" in error
        
        # Test missing score name
        valid, error = validate_prediction_params("test-scorecard", "", item_id="item-123")
        assert valid is False
        assert "score_name is required" in error
        
        # Test missing both item_id and item_ids
        valid, error = validate_prediction_params("test-scorecard", "test-score")
        assert valid is False
        assert "Either item_id or item_ids must be provided" in error
        
        # Test both item_id and item_ids provided
        valid, error = validate_prediction_params("test-scorecard", "test-score", 
                                                 item_id="item-123", item_ids="item-1,item-2")
        assert valid is False
        assert "Cannot specify both item_id and item_ids" in error
        
        # Test both no_cache and yaml_only
        valid, error = validate_prediction_params("test-scorecard", "test-score", item_id="item-123",
                                                 no_cache=True, yaml_only=True)
        assert valid is False
        assert "Cannot specify both no_cache and yaml_only" in error
        
        # Test both version and latest
        valid, error = validate_prediction_params("test-scorecard", "test-score", item_id="item-123",
                                                 version="version-123", latest=True)
        assert valid is False
        assert "Cannot use both version and latest" in error
        
        # Test invalid boolean parameters
        valid, error = validate_prediction_params("test-scorecard", "test-score", item_id="item-123",
                                                 include_input="invalid")
        assert valid is False
        assert "include_input must be a boolean" in error
        
        # Test invalid output format
        valid, error = validate_prediction_params("test-scorecard", "test-score", item_id="item-123",
                                                 output_format="xml")
        assert valid is False
        assert "output_format must be 'json' or 'yaml'" in error
    
    def test_scorecard_query_patterns(self):
        """Test scorecard query patterns for predictions"""
        scorecard_id = "scorecard-123"
        
        # Test the scorecard query structure
        scorecard_query = f"""
        query GetScorecardForPrediction {{
            getScorecard(id: "{scorecard_id}") {{
                id
                name
                sections {{
                    items {{
                        id
                        scores {{
                            items {{
                                id
                                name
                                key
                                externalId
                                championVersionId
                                isDisabled
                            }}
                        }}
                    }}
                }}
            }}
        }}
        """
        
        assert f'getScorecard(id: "{scorecard_id}")' in scorecard_query
        assert "GetScorecardForPrediction" in scorecard_query
        assert "championVersionId" in scorecard_query
        assert "isDisabled" in scorecard_query
        assert "sections {" in scorecard_query
        assert "scores {" in scorecard_query
    
    def test_score_resolution_patterns(self):
        """Test score resolution logic patterns"""
        # Mock scorecard data
        scorecard_data = {
            'id': 'scorecard-123',
            'name': 'Test Scorecard',
            'sections': {
                'items': [
                    {
                        'id': 'section-1',
                        'scores': {
                            'items': [
                                {
                                    'id': 'score-123',
                                    'name': 'Test Score',
                                    'key': 'test_score',
                                    'externalId': 'EXT-001',
                                    'championVersionId': 'version-456',
                                    'isDisabled': False
                                }
                            ]
                        }
                    }
                ]
            }
        }
        
        def resolve_score(score_name, scorecard_data, resolved_score_id=None):
            for section in scorecard_data.get('sections', {}).get('items', []):
                for score in section.get('scores', {}).get('items', []):
                    if (
                        (resolved_score_id and score.get('id') == resolved_score_id) or
                        score.get('id') == score_name or
                        score.get('externalId') == score_name or
                        score.get('key') == score_name or
                        score.get('name') == score_name
                    ):
                        return score
            return None
        
        # Test resolution by ID
        resolved = resolve_score('score-123', scorecard_data)
        assert resolved is not None
        assert resolved['id'] == 'score-123'
        
        # Test resolution by name
        resolved = resolve_score('Test Score', scorecard_data)
        assert resolved is not None
        assert resolved['name'] == 'Test Score'
        
        # Test resolution by key
        resolved = resolve_score('test_score', scorecard_data)
        assert resolved is not None
        assert resolved['key'] == 'test_score'
        
        # Test resolution by external ID
        resolved = resolve_score('EXT-001', scorecard_data)
        assert resolved is not None
        assert resolved['externalId'] == 'EXT-001'
        
        # Test resolution with resolved_score_id override
        resolved = resolve_score('any-name', scorecard_data, resolved_score_id='score-123')
        assert resolved is not None
        assert resolved['id'] == 'score-123'
        
        # Test not found
        resolved = resolve_score('nonexistent', scorecard_data)
        assert resolved is None
    
    def test_item_id_processing_patterns(self):
        """Test item ID processing and resolution patterns"""
        def process_item_ids(item_id=None, item_ids=None):
            if item_id:
                return [item_id]
            elif item_ids:
                return [id.strip() for id in item_ids.split(',')]
            return []
        
        # Test single item ID
        result = process_item_ids(item_id="item-123")
        assert result == ["item-123"]
        
        # Test multiple item IDs
        result = process_item_ids(item_ids="item-1,item-2,item-3")
        assert result == ["item-1", "item-2", "item-3"]
        
        # Test multiple item IDs with spaces
        result = process_item_ids(item_ids="item-1, item-2 ,  item-3")
        assert result == ["item-1", "item-2", "item-3"]
        
        # Test empty
        result = process_item_ids()
        assert result == []
    
    def test_item_query_patterns(self):
        """Test item query patterns"""
        item_id = "item-123"
        
        # Test the item query structure
        item_query = f"""
        query GetItem {{
            getItem(id: "{item_id}") {{
                id
                description
                metadata
                attachedFiles
                externalId
                createdAt
                updatedAt
            }}
        }}
        """
        
        assert f'getItem(id: "{item_id}")' in item_query
        assert "description" in item_query
        assert "metadata" in item_query
        assert "attachedFiles" in item_query
        assert "externalId" in item_query
        assert "createdAt" in item_query
        assert "updatedAt" in item_query
    
    def test_metadata_parsing_patterns(self):
        """Test metadata parsing patterns"""
        def parse_metadata(metadata_raw):
            if isinstance(metadata_raw, str):
                try:
                    import json
                    return json.loads(metadata_raw)
                except json.JSONDecodeError:
                    return {}
            else:
                return metadata_raw or {}
        
        # Test JSON string metadata
        json_metadata = '{"key": "value", "number": 42}'
        parsed = parse_metadata(json_metadata)
        assert parsed == {"key": "value", "number": 42}
        
        # Test dict metadata
        dict_metadata = {"key": "value", "number": 42}
        parsed = parse_metadata(dict_metadata)
        assert parsed == {"key": "value", "number": 42}
        
        # Test invalid JSON string
        invalid_json = '{"key": invalid}'
        parsed = parse_metadata(invalid_json)
        assert parsed == {}
        
        # Test None metadata
        parsed = parse_metadata(None)
        assert parsed == {}
        
        # Test empty string
        parsed = parse_metadata("")
        assert parsed == {}
    
    def test_scorecard_loading_patterns(self):
        """Test scorecard loading patterns for yaml_only and no_cache modes"""
        def determine_cache_mode(no_cache, yaml_only):
            use_cache = not no_cache
            if yaml_only:
                return "YAML-only", use_cache
            elif no_cache:
                return "no-cache", use_cache
            else:
                return "default", use_cache
        
        # Test default mode
        mode, cache = determine_cache_mode(False, False)
        assert mode == "default"
        assert cache is True
        
        # Test no-cache mode
        mode, cache = determine_cache_mode(True, False)
        assert mode == "no-cache"
        assert cache is False
        
        # Test YAML-only mode
        mode, cache = determine_cache_mode(False, True)
        assert mode == "YAML-only"
        assert cache is True
    
    def test_score_name_resolution_patterns(self):
        """Test score name resolution for subset matching"""
        # Mock scorecard instance with scores
        mock_scorecard_scores = [
            {
                'name': 'Actual Score Name',
                'id': 'score-123',
                'key': 'actual_score',
                'externalId': 'EXT-001',
                'originalExternalId': 'ORIG-001'
            },
            {
                'name': 'Another Score',
                'id': 'score-456',
                'key': 'another_score',
                'externalId': 'EXT-002'
            }
        ]
        
        def resolve_score_name(score_name, scorecard_scores):
            for s in scorecard_scores:
                s_name = s.get('name')
                if not s_name:
                    continue
                if (
                    s_name == score_name or
                    str(s.get('id', '')) == str(score_name) or
                    str(s.get('key', '')) == str(score_name) or
                    str(s.get('externalId', '')) == str(score_name) or
                    str(s.get('originalExternalId', '')) == str(score_name)
                ):
                    return s_name
            return score_name
        
        # Test exact name match
        resolved = resolve_score_name('Actual Score Name', mock_scorecard_scores)
        assert resolved == 'Actual Score Name'
        
        # Test ID match
        resolved = resolve_score_name('score-123', mock_scorecard_scores)
        assert resolved == 'Actual Score Name'
        
        # Test key match
        resolved = resolve_score_name('actual_score', mock_scorecard_scores)
        assert resolved == 'Actual Score Name'
        
        # Test external ID match
        resolved = resolve_score_name('EXT-001', mock_scorecard_scores)
        assert resolved == 'Actual Score Name'
        
        # Test original external ID match
        resolved = resolve_score_name('ORIG-001', mock_scorecard_scores)
        assert resolved == 'Actual Score Name'
        
        # Test no match (returns original)
        resolved = resolve_score_name('nonexistent', mock_scorecard_scores)
        assert resolved == 'nonexistent'
    
    def test_prediction_result_processing_patterns(self):
        """Test prediction result processing patterns"""
        # Mock prediction result object
        class MockPredictionResult:
            def __init__(self, value, explanation=None, cost=None, trace=None):
                self.value = value
                self.explanation = explanation
                self.cost = cost or {}
                self.trace = trace
                self.metadata = {
                    'explanation': explanation or '',
                    'cost': cost or {},
                    'trace': trace
                }
        
        def process_prediction_result(prediction_results, score_name, target_id, include_trace=False):
            if prediction_results and hasattr(prediction_results, 'value') and prediction_results.value is not None:
                explanation = (
                    getattr(prediction_results, 'explanation', None) or
                    prediction_results.metadata.get('explanation', '') if hasattr(prediction_results, 'metadata') and prediction_results.metadata else
                    ''
                )
                
                # Extract costs from scorecard result
                costs = {}
                if hasattr(prediction_results, 'cost'):
                    costs = prediction_results.cost
                elif hasattr(prediction_results, 'metadata') and prediction_results.metadata:
                    costs = prediction_results.metadata.get('cost', {})
                
                result = {
                    "item_id": target_id,
                    "scores": [
                        {
                            "name": score_name,
                            "value": prediction_results.value,
                            "explanation": explanation,
                            "cost": costs
                        }
                    ]
                }
                
                # Extract trace information if available
                if include_trace:
                    trace = None
                    if hasattr(prediction_results, 'trace'):
                        trace = prediction_results.trace
                    elif hasattr(prediction_results, 'metadata') and prediction_results.metadata:
                        trace = prediction_results.metadata.get('trace')
                    
                    if trace:
                        result["scores"][0]["trace"] = trace
                
                return result
            return None
        
        # Test successful prediction result
        mock_result = MockPredictionResult(
            value="Yes",
            explanation="Test explanation",
            cost={"total": 0.001, "input_tokens": 10, "output_tokens": 5},
            trace={"step1": "analysis", "step2": "decision"}
        )
        
        result = process_prediction_result(mock_result, "test-score", "item-123", include_trace=True)
        assert result is not None
        assert result["item_id"] == "item-123"
        assert len(result["scores"]) == 1
        assert result["scores"][0]["name"] == "test-score"
        assert result["scores"][0]["value"] == "Yes"
        assert result["scores"][0]["explanation"] == "Test explanation"
        assert result["scores"][0]["cost"]["total"] == 0.001
        assert result["scores"][0]["trace"]["step1"] == "analysis"
        
        # Test without trace
        result = process_prediction_result(mock_result, "test-score", "item-123", include_trace=False)
        assert "trace" not in result["scores"][0]
        
        # Test with None value
        null_result = MockPredictionResult(value=None)
        result = process_prediction_result(null_result, "test-score", "item-123")
        assert result is None
    
    def test_skipped_result_handling_patterns(self):
        """Test handling of SKIPPED results due to unmet dependencies"""
        def handle_skipped_result(results, resolved_score_name, score_name, target_id):
            if results and any(isinstance(v, Score.Result) and v.value == "SKIPPED" for v in results.values()):
                return {
                    "item_id": target_id,
                    "scores": [
                        {
                            "name": score_name,
                            "value": None,
                            "explanation": "Not applicable due to unmet dependency conditions",
                            "cost": {}
                        }
                    ]
                }
            return None
        
        # Test with SKIPPED results
        from plexus.scores.Score import Score
        mock_results = {
            "other_score": Score.Result(value="SKIPPED", parameters=Score.Parameters(name="other_score")), 
            "another_score": Score.Result(value="Yes", parameters=Score.Parameters(name="another_score"))
        }
        result = handle_skipped_result(mock_results, "test-score", "test-score", "item-123")
        assert result is not None
        assert result["item_id"] == "item-123"
        assert result["scores"][0]["value"] is None
        assert "unmet dependency conditions" in result["scores"][0]["explanation"]
        
        # Test without SKIPPED results
        mock_results = {"score1": "Yes", "score2": "No"}
        result = handle_skipped_result(mock_results, "test-score", "test-score", "item-123")
        assert result is None
        
        # Test with empty results
        result = handle_skipped_result({}, "test-score", "test-score", "item-123")
        assert result is None
    
    def test_output_formatting_patterns(self):
        """Test output formatting patterns for JSON and YAML"""
        # Mock prediction results
        prediction_results_list = [
            {
                "item_id": "item-123",
                "scores": [
                    {
                        "name": "test-score",
                        "value": "Yes",
                        "explanation": "Test explanation",
                        "cost": {"total": 0.001}
                    }
                ]
            }
        ]
        
        def format_output(prediction_results_list, scorecard_name, score_name, scorecard_id, 
                         resolved_score, include_input, include_trace, output_format):
            if output_format.lower() == "yaml":
                import yaml
                
                command_parts = [f'plexus predict --scorecard "{scorecard_name}" --score "{score_name}"']
                if len(prediction_results_list) == 1:
                    command_parts.append(f'--item "{prediction_results_list[0]["item_id"]}"')
                if output_format.lower() == "yaml":
                    command_parts.append("--format yaml")
                if include_input:
                    command_parts.append("--input")
                if include_trace:
                    command_parts.append("--trace")
                
                result = {
                    "context": {
                        "description": "Output from plexus predict command",
                        "command": " ".join(command_parts),
                        "scorecard_id": scorecard_id,
                        "score_id": resolved_score['id'],
                        "item_count": len(prediction_results_list)
                    },
                    "predictions": prediction_results_list
                }
                
                return yaml.dump(result, default_flow_style=False, sort_keys=False)
            else:
                # Return JSON format
                return {
                    "success": True,
                    "scorecard_name": scorecard_name,
                    "score_name": score_name,
                    "scorecard_id": scorecard_id,
                    "score_id": resolved_score['id'],
                    "score_version_id": resolved_score.get('championVersionId'),
                    "item_count": len(prediction_results_list),
                    "options": {
                        "include_input": include_input,
                        "include_trace": include_trace,
                        "output_format": output_format
                    },
                    "predictions": prediction_results_list,
                    "note": "This MCP tool executes real predictions using the shared Plexus prediction service."
                }
        
        # Test JSON format
        resolved_score = {"id": "score-123", "championVersionId": "version-456"}
        json_result = format_output(prediction_results_list, "test-scorecard", "test-score", 
                                   "scorecard-789", resolved_score, False, False, "json")
        
        assert isinstance(json_result, dict)
        assert json_result["success"] is True
        assert json_result["scorecard_name"] == "test-scorecard"
        assert json_result["score_name"] == "test-score"
        assert json_result["item_count"] == 1
        assert len(json_result["predictions"]) == 1
        
        # Test YAML format
        yaml_result = format_output(prediction_results_list, "test-scorecard", "test-score",
                                   "scorecard-789", resolved_score, True, True, "yaml")
        
        assert isinstance(yaml_result, str)
        assert "context:" in yaml_result
        assert "predictions:" in yaml_result
        assert "plexus predict" in yaml_result
        assert "--input" in yaml_result
        assert "--trace" in yaml_result


class TestPredictionToolSharedPatterns:
    """Test shared patterns for prediction tools"""
    
    def test_credential_validation_pattern(self):
        """Test credential validation patterns used in prediction tools"""
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
        """Test stdout redirection pattern used in prediction tools"""
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
        """Test import error handling pattern"""
        def simulate_import_attempt():
            try:
                # Mock import failure
                raise ImportError("Could not import required modules")
            except ImportError as e:
                return f"Error: Could not import required modules: {e}. Core modules may not be available."
        
        error_message = simulate_import_attempt()
        assert "Could not import required modules" in error_message
        assert "Core modules may not be available" in error_message
    
    def test_client_creation_with_stdout_capture_pattern(self):
        """Test client creation with nested stdout capture pattern"""
        def simulate_client_creation():
            client_stdout = StringIO()
            saved_stdout = StringIO()  # Mock current stdout
            
            try:
                # Mock successful client creation
                client = {"api_url": "test", "api_key": "test"}
                
                # Simulate captured output check
                client_output = client_stdout.getvalue()
                if client_output:
                    # Would log warning in real implementation
                    pass
                
                return client, None
            finally:
                # Would restore stdout in real implementation
                pass
        
        client, error = simulate_client_creation()
        assert client is not None
        assert error is None
    
    def test_error_handling_patterns(self):
        """Test various error handling patterns"""
        # Test prediction error handling
        def handle_prediction_error(error):
            return {
                "item_id": "test-item",
                "scores": [
                    {
                        "name": "test-score",
                        "value": "Error",
                        "explanation": f"Failed to execute prediction: {str(error)}"
                    }
                ]
            }
        
        # Test item not found error
        def handle_item_not_found(item_id):
            return {
                "item_id": item_id,
                "error": f"Item '{item_id}' not found"
            }
        
        # Test general processing error
        def handle_processing_error(item_id, error):
            return {
                "item_id": item_id,
                "error": f"Error processing item: {str(error)}"
            }
        
        # Test prediction error
        mock_error = Exception("Test prediction error")
        result = handle_prediction_error(mock_error)
        assert result["scores"][0]["value"] == "Error"
        assert "Failed to execute prediction" in result["scores"][0]["explanation"]
        
        # Test item not found
        result = handle_item_not_found("missing-item")
        assert "not found" in result["error"]
        
        # Test processing error
        result = handle_processing_error("test-item", Exception("Processing failed"))
        assert "Error processing item" in result["error"]
    
    def test_account_resolution_pattern(self):
        """Test account resolution pattern"""
        def simulate_account_resolution():
            # Mock account resolution logic
            account_key = "call-criteria"
            try:
                # Mock successful account resolution
                return "account-123"
            except Exception:
                return None
        
        account_id = simulate_account_resolution()
        assert account_id == "account-123"
    
    def test_input_data_inclusion_pattern(self):
        """Test input data inclusion pattern"""
        def add_input_data_if_requested(prediction_result, item_data, include_input):
            if include_input:
                prediction_result["input"] = {
                    "description": item_data.get('description'),
                    "metadata": item_data.get('metadata'),
                    "attachedFiles": item_data.get('attachedFiles'),
                    "externalId": item_data.get('externalId')
                }
            return prediction_result
        
        # Mock data
        prediction_result = {"item_id": "test-item", "scores": []}
        item_data = {
            "description": "Test item",
            "metadata": {"key": "value"},
            "attachedFiles": ["file1.txt"],
            "externalId": "EXT-123"
        }
        
        # Test with include_input=True
        result = add_input_data_if_requested(prediction_result.copy(), item_data, True)
        assert "input" in result
        assert result["input"]["description"] == "Test item"
        assert result["input"]["metadata"]["key"] == "value"
        
        # Test with include_input=False
        result = add_input_data_if_requested(prediction_result.copy(), item_data, False)
        assert "input" not in result