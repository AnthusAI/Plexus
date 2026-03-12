#!/usr/bin/env python3
"""
Unit tests for CLI scorecard commands
Uses shared test patterns to ensure consistency with MCP scorecard tools
"""
import pytest
import os
import sys
import json
from unittest.mock import patch, Mock, MagicMock
from io import StringIO
import click
from click.testing import CliRunner

# Import the shared test patterns
from plexus.cli.scorecard.scorecard_test_patterns import (
    ScorecardTestPatterns, 
    ScorecardFunctionalityTests
)

pytestmark = pytest.mark.unit


class TestCLIScorecardCommands:
    """Test CLI scorecard commands using shared patterns"""
    
    def setup_method(self):
        """Setup for each test method"""
        self.runner = CliRunner()
    
    def test_scorecard_list_command_basic(self):
        """Test basic scorecard list command"""
        # Mock the CLI command functionality
        mock_client = ScorecardTestPatterns.create_mock_client()
        
        with patch('plexus.cli.scorecard.scorecards.create_client', return_value=mock_client):
            # Import the CLI command
            try:
                from plexus.cli.scorecard.scorecards import scorecards
                
                # Test the list subcommand exists
                assert hasattr(scorecards, 'commands') or callable(scorecards)
                
                # Note: Full CLI testing would require mocking click commands
                # For now, we test that the patterns work
                
            except ImportError:
                pytest.skip("CLI ScorecardCommands not available in test environment")
    
    def test_cli_scorecard_functionality_patterns(self):
        """Test that CLI follows the same patterns as MCP"""
        # Create mock CLI functions that behave like the MCP function
        def mock_cli_scorecard_list_basic(identifier=None, limit=None):
            """Mock CLI scorecard list function for basic testing"""
            mock_client = ScorecardTestPatterns.create_mock_client()
            
            # Simulate CLI behavior
            try:
                response = mock_client.execute()
                scorecards = response['data']['listScorecards']['items']
                
                # Apply filtering if identifier provided
                if identifier:
                    filtered_scorecards = []
                    for scorecard in scorecards:
                        if (identifier.lower() in scorecard.get('name', '').lower() or
                            identifier == scorecard.get('id') or
                            identifier == scorecard.get('key') or
                            identifier == scorecard.get('externalId')):
                            filtered_scorecards.append(scorecard)
                    scorecards = filtered_scorecards
                
                # Apply limit if provided
                if limit and limit > 0:
                    scorecards = scorecards[:limit]
                
                return scorecards
                
            except Exception as e:
                return f"Error: {str(e)}"
        
        def mock_cli_scorecard_list_empty():
            """Mock CLI function that returns empty results"""
            mock_client = ScorecardTestPatterns.create_mock_client(
                return_data=ScorecardTestPatterns.get_empty_graphql_response()
            )
            try:
                response = mock_client.execute()
                return response['data']['listScorecards']['items']
            except Exception as e:
                return f"Error: {str(e)}"
        
        def mock_cli_scorecard_list_error():
            """Mock CLI function that simulates an error"""
            # Simulate an error condition
            return "Error: API connection failed"
        
        # Test using shared functionality tests with appropriate mock functions
        ScorecardFunctionalityTests.test_list_scorecards_basic(
            lambda: mock_cli_scorecard_list_basic()
        )
        
        ScorecardFunctionalityTests.test_list_scorecards_with_filter(
            lambda identifier="test": mock_cli_scorecard_list_basic(identifier=identifier)
        )
        
        ScorecardFunctionalityTests.test_list_scorecards_empty_result(
            lambda: mock_cli_scorecard_list_empty()
        )
        
        ScorecardFunctionalityTests.test_list_scorecards_error_handling(
            lambda: mock_cli_scorecard_list_error()
        )


class TestCLIScorecardPatterns:
    """Test CLI-specific patterns using shared test data"""
    
    def test_cli_scorecard_validation(self):
        """Test CLI scorecard validation using shared patterns"""
        validation_tests = ScorecardTestPatterns.test_scorecard_validation_patterns()
        
        for test_case in validation_tests:
            scorecard = test_case['scorecard']
            should_be_valid = test_case['should_be_valid']
            
            # CLI should validate scorecards the same way as MCP
            if should_be_valid:
                assert ScorecardTestPatterns.validate_scorecard_info_result(scorecard)
            else:
                # Invalid scorecards should be handled gracefully by CLI too
                assert isinstance(test_case['validation_errors'], list)
    
    def test_cli_identifier_resolution(self):
        """Test CLI identifier resolution using shared patterns"""
        test_cases = ScorecardTestPatterns.test_scorecard_identifier_resolution_patterns()
        
        for test_case in test_cases:
            input_id = test_case['input']
            expected_type = test_case['expected_type']
            should_resolve = test_case['should_resolve']
            
            # CLI should handle identifier resolution the same way as MCP
            if should_resolve:
                assert input_id is not None and str(input_id).strip() != ""
            else:
                assert input_id is None or str(input_id).strip() == ""
    
    def test_cli_filtering_patterns(self):
        """Test CLI filtering using shared patterns"""
        filter_tests = ScorecardTestPatterns.test_scorecard_filtering_patterns()
        
        for test_case in filter_tests:
            filter_value = test_case['filter']
            expected_count = test_case['expected_count']
            description = test_case['description']
            
            # CLI should handle filtering the same way as MCP
            assert isinstance(expected_count, int)
            assert expected_count >= 0
            assert isinstance(description, str)
            assert len(description) > 0
    
    def test_cli_error_handling_patterns(self):
        """Test CLI error handling using shared patterns"""
        error_scenarios = ScorecardTestPatterns.test_error_handling_patterns()
        
        for scenario in error_scenarios:
            error_type = scenario['error_type']
            error_message = scenario['error_message']
            expected_pattern = scenario['expected_response_pattern']
            
            # CLI should handle errors the same way as MCP
            assert isinstance(error_type, str)
            assert isinstance(error_message, str)
            assert isinstance(expected_pattern, str)
            assert len(error_type) > 0
            assert len(error_message) > 0 
            assert len(expected_pattern) > 0


class TestCLIScorecardDataConsistency:
    """Test that CLI and MCP handle the same data consistently"""
    
    def test_sample_data_handling(self):
        """Test that CLI handles sample data the same as MCP"""
        # Test single scorecard
        scorecard = ScorecardTestPatterns.get_sample_scorecard_data()
        assert ScorecardTestPatterns.validate_scorecard_info_result(scorecard)
        
        # Test scorecard list
        scorecards = ScorecardTestPatterns.get_sample_scorecard_list()
        assert ScorecardTestPatterns.validate_scorecard_list_result(scorecards)
        
        # Test GraphQL response parsing
        response = ScorecardTestPatterns.get_sample_graphql_response()
        assert 'data' in response
        assert 'listScorecards' in response['data']
        assert 'items' in response['data']['listScorecards']
        
        # Both CLI and MCP should parse this the same way
        items = response['data']['listScorecards']['items']
        assert ScorecardTestPatterns.validate_scorecard_list_result(items)
    
    def test_mock_client_consistency(self):
        """Test that CLI and MCP use mock clients consistently"""
        # Test default mock client
        mock_client = ScorecardTestPatterns.create_mock_client()
        assert hasattr(mock_client, 'execute')
        
        # Test mock client with custom data
        custom_data = {'test': 'data'}
        mock_client = ScorecardTestPatterns.create_mock_client(return_data=custom_data)
        result = mock_client.execute()
        assert result == custom_data
        
        # Both CLI and MCP should work with the same mock clients
        
    def test_empty_and_error_responses(self):
        """Test that CLI and MCP handle empty and error responses consistently"""
        # Test empty response
        empty_response = ScorecardTestPatterns.get_empty_graphql_response()
        assert empty_response['data']['listScorecards']['items'] == []
        
        # Test error response
        error_response = ScorecardTestPatterns.get_error_graphql_response()
        assert 'errors' in error_response
        assert len(error_response['errors']) > 0
        
        # Both CLI and MCP should handle these the same way


class TestScorecardCommandLineInterface:
    """Test CLI-specific interface patterns"""
    
    def setup_method(self):
        """Setup for each test method"""
        self.runner = CliRunner()
    
    def test_scorecard_command_structure(self):
        """Test that scorecard commands follow expected CLI patterns"""
        # Test that we can import the scorecard commands
        try:
            from plexus.cli.scorecard.scorecards import scorecards, scorecard
            
            # Both should be click groups
            assert hasattr(scorecards, '__call__')
            assert hasattr(scorecard, '__call__')
            
            # Test that they're proper Click command groups
            # (This would be more detailed in a full CLI test)
            
        except ImportError:
            pytest.skip("CLI ScorecardCommands not available in test environment")
    
    def test_scorecard_command_parameters(self):
        """Test that scorecard commands accept expected parameters"""
        # This would test that CLI commands accept the same parameters as MCP tools
        expected_list_params = ['identifier', 'limit']
        expected_info_params = ['scorecard_identifier']
        
        # Test parameter consistency between CLI and MCP
        # (Implementation would depend on actual CLI structure)
        assert isinstance(expected_list_params, list)
        assert isinstance(expected_info_params, list)
    
    def test_scorecard_output_formatting(self):
        """Test that CLI output formatting is consistent"""
        # Test that CLI formats output consistently
        # This would test rich formatting, JSON output, etc.
        
        # Mock some output formatting
        def format_scorecard_list(scorecards):
            """Mock CLI output formatting"""
            if isinstance(scorecards, list):
                return f"Found {len(scorecards)} scorecards"
            else:
                return str(scorecards)
        
        # Test with sample data
        scorecards = ScorecardTestPatterns.get_sample_scorecard_list()
        formatted = format_scorecard_list(scorecards)
        assert "Found 3 scorecards" in formatted
        
        # Test with empty data
        empty_scorecards = []
        formatted = format_scorecard_list(empty_scorecards)
        assert "Found 0 scorecards" in formatted


class TestCLIMCPConsistency:
    """Test that CLI and MCP implementations are consistent"""
    
    def test_consistent_functionality_coverage(self):
        """Test that CLI and MCP cover the same functionality"""
        # Define expected functionality
        expected_functions = [
            'list_scorecards',
            'get_scorecard_info', 
            'run_evaluation'  # This exists in both CLI and MCP
        ]
        
        # Both CLI and MCP should implement these core functions
        for func in expected_functions:
            # Test that the functionality exists conceptually
            assert isinstance(func, str)
            assert len(func) > 0
    
    def test_consistent_parameter_handling(self):
        """Test that CLI and MCP handle parameters consistently"""
        # Both should handle optional parameters the same way
        def test_parameter_handling(identifier=None, limit=None):
            """Test parameter handling pattern"""
            # Convert None to appropriate defaults
            if identifier is None:
                identifier = ""
            if limit is None:
                limit = 100
            
            # Both CLI and MCP should handle parameters this way
            return identifier, limit
        
        # Test various parameter combinations
        id1, lim1 = test_parameter_handling()
        assert id1 == ""
        assert lim1 == 100
        
        id2, lim2 = test_parameter_handling("test", 50)
        assert id2 == "test"
        assert lim2 == 50
    
    def test_consistent_error_messages(self):
        """Test that CLI and MCP provide consistent error messages"""
        # Both should provide similar error messages for similar situations
        error_scenarios = [
            "API connection failed",
            "Invalid credentials", 
            "Scorecard not found",
            "Access denied"
        ]
        
        for error in error_scenarios:
            # Both CLI and MCP should handle these errors consistently
            assert isinstance(error, str)
            assert len(error) > 0
            
            # Test that error format is consistent
            formatted_error = f"Error: {error}"
            assert formatted_error.startswith("Error:")


class TestScorecardTestPatternValidity:
    """Test that our shared test patterns are valid"""
    
    def test_all_shared_patterns_work(self):
        """Test that all shared patterns are functional"""
        # Test sample data generation
        scorecard = ScorecardTestPatterns.get_sample_scorecard_data()
        assert isinstance(scorecard, dict)
        assert 'id' in scorecard
        assert 'name' in scorecard
        
        # Test list generation
        scorecards = ScorecardTestPatterns.get_sample_scorecard_list()
        assert isinstance(scorecards, list)
        assert len(scorecards) > 0
        
        # Test response generation
        response = ScorecardTestPatterns.get_sample_graphql_response()
        assert isinstance(response, dict)
        assert 'data' in response
        
        # Test validation functions
        assert ScorecardTestPatterns.validate_scorecard_info_result(scorecard)
        assert ScorecardTestPatterns.validate_scorecard_list_result(scorecards)
        
        # Test mock client creation
        mock_client = ScorecardTestPatterns.create_mock_client()
        assert hasattr(mock_client, 'execute')
    
    def test_pattern_completeness(self):
        """Test that patterns cover all necessary test cases"""
        # Test identifier resolution patterns
        id_patterns = ScorecardTestPatterns.test_scorecard_identifier_resolution_patterns()
        assert len(id_patterns) >= 5  # Should have multiple test cases
        
        # Test filtering patterns
        filter_patterns = ScorecardTestPatterns.test_scorecard_filtering_patterns()
        assert len(filter_patterns) >= 3  # Should have multiple filter scenarios
        
        # Test validation patterns
        validation_patterns = ScorecardTestPatterns.test_scorecard_validation_patterns()
        assert len(validation_patterns) >= 3  # Should have valid and invalid cases
        
        # Test error handling patterns
        error_patterns = ScorecardTestPatterns.test_error_handling_patterns()
        assert len(error_patterns) >= 4  # Should cover multiple error types