"""
Comprehensive tests for LangGraphScore output mapping functionality.

This test suite focuses on the critical output mapping logic that was previously 
untested and suspected of having problems. It covers all aspects of value setting,
aliasing, literal handling, and edge cases.

Key areas tested:
- create_value_setter_node function
- generate_output_aliasing_function 
- Literal vs state field handling
- Complex output mapping scenarios
- Edge cases and error conditions
"""

import pytest
from unittest.mock import MagicMock, patch
import sys
import os

# Mock problematic dependencies upfront
class MockModule:
    def __getattr__(self, name):
        return MockModule()
    def __call__(self, *args, **kwargs):
        return MockModule()

sys.modules['mlflow'] = MockModule()
sys.modules['pandas'] = MockModule()
sys.modules['graphviz'] = MockModule()

class TestValueSetterNode:
    """Test the core create_value_setter_node functionality"""
    
    def test_basic_state_field_mapping(self):
        """Test basic mapping from state fields to output aliases"""
        try:
            from plexus.scores.LangGraphScore import LangGraphScore
        except ImportError:
            pytest.skip("LangGraphScore dependencies not available")
            
        output_mapping = {
            "value": "classification",
            "explanation": "reasoning"
        }
        
        value_setter = LangGraphScore.create_value_setter_node(output_mapping)
        
        # Create mock state with the source fields
        class MockState:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)
                    
            def model_dump(self):
                return {k: v for k, v in self.__dict__.items()}
        
        state = MockState(
            classification="Yes", 
            reasoning="Strong evidence found",
            other_field="preserved"
        )
        
        result = value_setter(state)
        
        # Verify mapping worked correctly
        assert result.value == "Yes"
        assert result.explanation == "Strong evidence found"
        assert result.other_field == "preserved"
        assert result.classification == "Yes"  # Original field preserved
        assert result.reasoning == "Strong evidence found"  # Original field preserved

    def test_literal_value_handling(self):
        """Test handling of literal values when state fields don't exist"""
        try:
            from plexus.scores.LangGraphScore import LangGraphScore
        except ImportError:
            pytest.skip("LangGraphScore dependencies not available")
            
        output_mapping = {
            "source": "manual_classifier",  # Literal
            "status": "completed",  # Literal
            "value": "classification",  # State field
            "timestamp": "process_time"  # Missing state field - should be literal
        }
        
        value_setter = LangGraphScore.create_value_setter_node(output_mapping)
        
        class MockState:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)
                    
            def model_dump(self):
                return {k: v for k, v in self.__dict__.items()}
        
        state = MockState(classification="Maybe")
        result = value_setter(state)
        
        # Verify literal and state field handling
        assert result.source == "manual_classifier"  # Literal value
        assert result.status == "completed"  # Literal value  
        assert result.value == "Maybe"  # From state field
        assert result.timestamp == "process_time"  # Missing field treated as literal

    def test_complex_output_mapping_scenarios(self):
        """Test complex scenarios with mixed data types and edge cases"""
        try:
            from plexus.scores.LangGraphScore import LangGraphScore
        except ImportError:
            pytest.skip("LangGraphScore dependencies not available")
            
        output_mapping = {
            "final_classification": "classification",
            "confidence_score": "confidence",
            "explanation_text": "explanation", 
            "source_system": "LangGraphScore",  # Literal
            "processing_stage": "final",  # Literal
            "empty_field": "missing_field",  # Will be literal
            "none_field": "null_field"  # State field that's None
        }
        
        value_setter = LangGraphScore.create_value_setter_node(output_mapping)
        
        class MockState:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)
                    
            def model_dump(self):
                return {k: v for k, v in self.__dict__.items()}
        
        state = MockState(
            classification="Probably Yes",
            confidence=0.85,
            explanation="Based on multiple indicators", 
            null_field=None,  # Test None handling
            preserved_data="should remain"
        )
        
        result = value_setter(state)
        
        # Verify complex mapping
        assert result.final_classification == "Probably Yes"
        assert result.confidence_score == 0.85
        assert result.explanation_text == "Based on multiple indicators"
        assert result.source_system == "LangGraphScore"  # Literal
        assert result.processing_stage == "final"  # Literal
        assert result.empty_field == "missing_field"  # Missing -> literal
        assert result.none_field is None  # None preserved
        assert result.preserved_data == "should remain"

    def test_edge_cases_and_error_conditions(self):
        """Test edge cases that might cause problems"""
        try:
            from plexus.scores.LangGraphScore import LangGraphScore
        except ImportError:
            pytest.skip("LangGraphScore dependencies not available")
            
        # Test with empty mapping
        empty_mapper = LangGraphScore.create_value_setter_node({})
        
        class MockState:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)
                    
            def model_dump(self):
                return {k: v for k, v in self.__dict__.items()}
        
        state = MockState(test_field="test_value")
        result = empty_mapper(state)
        assert result.test_field == "test_value"  # No changes
        
        # Test with complex field names and special characters
        complex_mapping = {
            "field_with_underscore": "source_field",
            "field-with-dash": "target-field",  # Literal (no such field)
            "fieldWithCamelCase": "camelCaseSource"
        }
        
        complex_mapper = LangGraphScore.create_value_setter_node(complex_mapping)
        state = MockState(source_field="underscore_value", camelCaseSource="camelValue")
        result = complex_mapper(state)
        
        assert result.field_with_underscore == "underscore_value"
        assert hasattr(result, "field-with-dash")  # Should be set as literal
        assert result.fieldWithCamelCase == "camelValue"

    def test_value_setter_state_object_creation(self):
        """Test that value setter properly creates new state objects"""
        try:
            from plexus.scores.LangGraphScore import LangGraphScore
        except ImportError:
            pytest.skip("LangGraphScore dependencies not available")
            
        output_mapping = {"result": "classification", "source": "test"}
        value_setter = LangGraphScore.create_value_setter_node(output_mapping)
        
        class MockState:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)
                    
            def model_dump(self):
                return {k: v for k, v in self.__dict__.items()}
        
        original_state = MockState(classification="Test")
        result_state = value_setter(original_state)
        
        # Verify new state object was created
        assert result_state is not original_state
        assert isinstance(result_state, MockState)
        assert result_state.result == "Test"
        assert result_state.source == "test"


class TestOutputAliasingFunction:
    """Test the generate_output_aliasing_function functionality"""
    
    def test_basic_output_aliasing(self):
        """Test basic output aliasing functionality"""
        try:
            from plexus.scores.LangGraphScore import LangGraphScore
        except ImportError:
            pytest.skip("LangGraphScore dependencies not available")
            
        output_mapping = {
            "value": "classification",
            "explanation": "reasoning"
        }
        
        aliasing_func = LangGraphScore.generate_output_aliasing_function(output_mapping)
        
        class MockState:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)
                    
            def model_dump(self):
                return {k: v for k, v in self.__dict__.items()}
        
        state = MockState(
            classification="No",
            reasoning="Insufficient evidence"
        )
        
        result = aliasing_func(state)
        
        assert result.value == "No"
        assert result.explanation == "Insufficient evidence"

    def test_existing_value_preservation(self):
        """Test that existing meaningful values are preserved"""
        try:
            from plexus.scores.LangGraphScore import LangGraphScore
        except ImportError:
            pytest.skip("LangGraphScore dependencies not available")
            
        output_mapping = {
            "value": "classification",
            "explanation": "reasoning"
        }
        
        aliasing_func = LangGraphScore.generate_output_aliasing_function(output_mapping)
        
        class MockState:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)
                    
            def model_dump(self):
                return {k: v for k, v in self.__dict__.items()}
        
        # State where target fields already have values
        state = MockState(
            classification="Maybe",
            reasoning="Unclear signals",
            value="Yes",  # Existing meaningful value
            explanation="Pre-existing explanation"  # Existing meaningful value
        )
        
        result = aliasing_func(state)
        
        # Existing values should be preserved
        assert result.value == "Yes"  # Preserved existing
        assert result.explanation == "Pre-existing explanation"  # Preserved existing

    def test_none_value_default_handling(self):
        """Test handling of None values with proper defaults"""
        try:
            from plexus.scores.LangGraphScore import LangGraphScore
        except ImportError:
            pytest.skip("LangGraphScore dependencies not available")
            
        output_mapping = {
            "value": "classification",
            "explanation": "reasoning",
            "criteria_met": "criteria_status"
        }
        
        aliasing_func = LangGraphScore.generate_output_aliasing_function(output_mapping)
        
        class MockState:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)
                    
            def model_dump(self):
                return {k: v for k, v in self.__dict__.items()}
        
        # State with None values
        state = MockState(
            classification=None,
            reasoning=None, 
            criteria_status=None
        )
        
        result = aliasing_func(state)
        
        # Should get appropriate defaults for None values
        assert result.value == "No"  # Default for value field
        assert result.explanation == ""  # Default for explanation field
        assert result.criteria_met == ""  # Default for other text fields

    def test_literal_value_handling_in_aliasing(self):
        """Test literal value handling in output aliasing"""
        try:
            from plexus.scores.LangGraphScore import LangGraphScore
        except ImportError:
            pytest.skip("LangGraphScore dependencies not available")
            
        output_mapping = {
            "value": "classification",
            "source": "final_classifier",  # Literal
            "version": "2.0"  # Literal
        }
        
        aliasing_func = LangGraphScore.generate_output_aliasing_function(output_mapping)
        
        class MockState:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)
                    
            def model_dump(self):
                return {k: v for k, v in self.__dict__.items()}
        
        state = MockState(classification="Yes")
        result = aliasing_func(state)
        
        assert result.value == "Yes"  # From state
        assert result.source == "final_classifier"  # Literal
        assert result.version == "2.0"  # Literal


class TestCombinedGraphStateCreation:
    """Test combined GraphState creation with output mappings"""
    
    def test_output_mapping_fields_added_to_graphstate(self):
        """Test that output mapping fields are added to combined GraphState"""
        try:
            from plexus.scores.LangGraphScore import LangGraphScore
            from pydantic import BaseModel
            from typing import Optional
        except ImportError:
            pytest.skip("Dependencies not available")
            
        # Create test nodes with output mappings
        class TestNode1:
            class GraphState(BaseModel):
                classification: Optional[str] = None
                reasoning: Optional[str] = None

            parameters = MagicMock()
            parameters.output = {"final_result": "classification", "final_explanation": "reasoning"}

        class TestNode2:
            class GraphState(BaseModel):
                confidence: Optional[float] = None

            parameters = MagicMock()
            parameters.output = {"confidence_score": "confidence"}

        instance = LangGraphScore(model_provider="AzureChatOpenAI", model_name="gpt-4")
        node_instances = [TestNode1(), TestNode2()]
        
        combined_state_class = instance.create_combined_graphstate_class(node_instances)
        
        # Verify output mapping fields were added
        annotations = combined_state_class.__annotations__
        assert "final_result" in annotations
        assert "final_explanation" in annotations
        assert "confidence_score" in annotations
        
        # Verify original fields still present
        assert "classification" in annotations
        assert "reasoning" in annotations
        assert "confidence" in annotations

    def test_edge_output_mappings_in_graphstate(self):
        """Test that edge output mappings are included in GraphState"""
        try:
            from plexus.scores.LangGraphScore import LangGraphScore
            from pydantic import BaseModel
            from typing import Optional
        except ImportError:
            pytest.skip("Dependencies not available")
            
        class TestNode:
            class GraphState(BaseModel):
                classification: Optional[str] = None

            parameters = MagicMock()
            parameters.output = None
            parameters.edge = {"node": "END", "output": {"final_value": "classification", "source": "edge_node"}}

        instance = LangGraphScore(model_provider="AzureChatOpenAI", model_name="gpt-4")
        node_instances = [TestNode()]
        
        combined_state_class = instance.create_combined_graphstate_class(node_instances)
        
        annotations = combined_state_class.__annotations__
        assert "final_value" in annotations
        assert "source" in annotations

    def test_conditions_output_mappings_in_graphstate(self):
        """Test that conditions output mappings are included in GraphState"""
        try:
            from plexus.scores.LangGraphScore import LangGraphScore
            from pydantic import BaseModel
            from typing import Optional
        except ImportError:
            pytest.skip("Dependencies not available")
            
        class TestNode:
            class GraphState(BaseModel):
                classification: Optional[str] = None

            parameters = MagicMock()
            parameters.output = None
            parameters.conditions = [
                {"value": "yes", "node": "handler", "output": {"result": "classification", "confidence": "high"}},
                {"value": "no", "node": "END", "output": {"result": "classification", "confidence": "low"}}
            ]

        instance = LangGraphScore(model_provider="AzureChatOpenAI", model_name="gpt-4")
        node_instances = [TestNode()]
        
        combined_state_class = instance.create_combined_graphstate_class(node_instances)
        
        annotations = combined_state_class.__annotations__
        assert "result" in annotations
        assert "confidence" in annotations

    def test_graph_config_output_mappings_in_graphstate(self):
        """Test that graph config output mappings are included in GraphState"""
        try:
            from plexus.scores.LangGraphScore import LangGraphScore
            from pydantic import BaseModel
            from typing import Optional
        except ImportError:
            pytest.skip("Dependencies not available")
            
        graph_config = [
            {
                "name": "classifier",
                "edge": {"node": "END", "output": {"final_classification": "classification"}},
                "conditions": [{"value": "yes", "node": "handler", "output": {"yes_result": "classification"}}]
            }
        ]
        
        instance = LangGraphScore(
            model_provider="AzureChatOpenAI", 
            model_name="gpt-4",
            graph=graph_config
        )
        
        combined_state_class = instance.create_combined_graphstate_class([])
        
        annotations = combined_state_class.__annotations__
        assert "final_classification" in annotations
        assert "yes_result" in annotations


class TestOutputMappingEdgeCases:
    """Test edge cases and error conditions in output mapping"""
    
    def test_empty_output_mapping(self):
        """Test handling of empty output mappings"""
        try:
            from plexus.scores.LangGraphScore import LangGraphScore
        except ImportError:
            pytest.skip("LangGraphScore dependencies not available")
            
        # Empty mapping should work without errors
        empty_setter = LangGraphScore.create_value_setter_node({})
        empty_aliasing = LangGraphScore.generate_output_aliasing_function({})
        
        class MockState:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)
                    
            def model_dump(self):
                return {k: v for k, v in self.__dict__.items()}
        
        state = MockState(test="value")
        
        # Should work without modification
        setter_result = empty_setter(state)
        aliasing_result = empty_aliasing(state)
        
        assert setter_result.test == "value"
        assert aliasing_result.test == "value"

    def test_circular_mapping_handling(self):
        """Test handling of potential circular mappings"""
        try:
            from plexus.scores.LangGraphScore import LangGraphScore
        except ImportError:
            pytest.skip("LangGraphScore dependencies not available")
            
        # Potential circular mapping
        circular_mapping = {
            "value": "result",
            "result": "value"  # Circular reference
        }
        
        value_setter = LangGraphScore.create_value_setter_node(circular_mapping)
        
        class MockState:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)
                    
            def model_dump(self):
                return {k: v for k, v in self.__dict__.items()}
        
        state = MockState(result="Final Answer")
        
        # Should handle without infinite loops
        result = value_setter(state)
        assert hasattr(result, "value")
        assert hasattr(result, "result")

    def test_special_characters_in_field_names(self):
        """Test handling of special characters in field names"""
        try:
            from plexus.scores.LangGraphScore import LangGraphScore
        except ImportError:
            pytest.skip("LangGraphScore dependencies not available")
            
        # Field names with special characters
        special_mapping = {
            "field_with_underscores": "source_field", 
            "fieldWithCamelCase": "camelSource",
            "field123": "numeric_source",
            "UPPERCASE_FIELD": "upper_source"
        }
        
        value_setter = LangGraphScore.create_value_setter_node(special_mapping)
        
        class MockState:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)
                    
            def model_dump(self):
                return {k: v for k, v in self.__dict__.items()}
        
        state = MockState(
            source_field="underscore_value",
            camelSource="camel_value", 
            numeric_source="123_value",
            upper_source="UPPER_VALUE"
        )
        
        result = value_setter(state)
        
        assert result.field_with_underscores == "underscore_value"
        assert result.fieldWithCamelCase == "camel_value"
        assert result.field123 == "123_value" 
        assert result.UPPERCASE_FIELD == "UPPER_VALUE"

    def test_large_output_mapping_performance(self):
        """Test performance with large output mappings"""
        try:
            from plexus.scores.LangGraphScore import LangGraphScore
        except ImportError:
            pytest.skip("LangGraphScore dependencies not available")
            
        # Create large mapping
        large_mapping = {}
        for i in range(100):
            large_mapping[f"output_{i}"] = f"source_{i}"
            
        value_setter = LangGraphScore.create_value_setter_node(large_mapping)
        
        class MockState:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)
                    
            def model_dump(self):
                return {k: v for k, v in self.__dict__.items()}
        
        # Create state with some of the source fields
        state_data = {}
        for i in range(0, 100, 2):  # Every other field
            state_data[f"source_{i}"] = f"value_{i}"
            
        state = MockState(**state_data)
        
        # Should handle large mappings efficiently
        result = value_setter(state)
        
        # Verify some of the mappings worked
        assert result.output_0 == "value_0"
        assert result.output_2 == "value_2"
        # Fields without source should be literals
        assert result.output_1 == "source_1"


class TestOutputMappingIntegration:
    """Integration tests combining multiple output mapping features"""
    
    def test_complex_workflow_output_mapping(self):
        """Test complex workflow with multiple output mapping layers"""
        try:
            from plexus.scores.LangGraphScore import LangGraphScore
        except ImportError:
            pytest.skip("LangGraphScore dependencies not available")
            
        # Simulate complex workflow scenario
        # Step 1: Value setter from routing
        routing_mapping = {"intermediate_result": "classification", "stage": "routing"}
        routing_setter = LangGraphScore.create_value_setter_node(routing_mapping)
        
        # Step 2: Final output aliasing
        final_mapping = {"value": "intermediate_result", "explanation": "reasoning"}
        final_aliasing = LangGraphScore.generate_output_aliasing_function(final_mapping)
        
        class MockState:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)
                    
            def model_dump(self):
                return {k: v for k, v in self.__dict__.items()}
        
        # Initial state
        initial_state = MockState(
            classification="Yes",
            reasoning="Strong evidence found"
        )
        
        # Apply routing transformation
        intermediate_state = routing_setter(initial_state)
        
        # Apply final aliasing
        final_state = final_aliasing(intermediate_state)
        
        # Verify the full pipeline worked
        assert final_state.value == "Yes"
        assert final_state.explanation == "Strong evidence found"
        assert final_state.intermediate_result == "Yes"
        assert final_state.stage == "routing"

    def test_mixed_literal_and_state_complex_scenario(self):
        """Test complex scenario mixing literals and state fields"""
        try:
            from plexus.scores.LangGraphScore import LangGraphScore
        except ImportError:
            pytest.skip("LangGraphScore dependencies not available")
            
        complex_mapping = {
            "final_classification": "classification",  # State field
            "confidence_level": "confidence",  # State field  
            "explanation_text": "reasoning",  # State field
            "source_system": "LangGraphScore",  # Literal
            "version": "2.0",  # Literal
            "timestamp": "process_timestamp",  # Missing -> literal
            "status": "completed",  # Literal
            "fallback_reason": "fallback_explanation"  # Missing -> literal
        }
        
        value_setter = LangGraphScore.create_value_setter_node(complex_mapping)
        
        class MockState:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)
                    
            def model_dump(self):
                return {k: v for k, v in self.__dict__.items()}
        
        state = MockState(
            classification="Uncertain",
            confidence=0.6,
            reasoning="Mixed signals detected",
            other_data="preserved"
        )
        
        result = value_setter(state)
        
        # Verify state field mappings
        assert result.final_classification == "Uncertain"
        assert result.confidence_level == 0.6
        assert result.explanation_text == "Mixed signals detected"
        
        # Verify literal mappings
        assert result.source_system == "LangGraphScore"
        assert result.version == "2.0"
        assert result.status == "completed"
        
        # Verify missing fields treated as literals
        assert result.timestamp == "process_timestamp"
        assert result.fallback_reason == "fallback_explanation"
        
        # Verify preservation of other data
        assert result.other_data == "preserved"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])