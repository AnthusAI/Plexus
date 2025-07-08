"""
Simple Test: Conditional Edges with Output Mapping Issues

This test demonstrates specific problems that occur when combining conditional 
edges with output mapping. These are real scenarios that have been causing issues.

Focus Areas:
1. Condition vs Edge output conflicts
2. Final output aliasing conflicts
3. Value setter precedence issues
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Optional


@pytest.mark.asyncio
async def test_existing_conditions_with_output_mapping():
    """Test the existing multi-node conditional routing with added output mapping validation"""
    
    # This test uses the pattern from the working test_multi_node_condition_routing
    # but adds validation for output mapping scenarios that cause problems
    
    mock_model = AsyncMock()
    
    # Mock the dependencies we need
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', return_value=mock_model):
        try:
            from plexus.scores.nodes.Classifier import Classifier
            from langgraph.graph import StateGraph, END
            
            config = {
                "name": "test_classifier",
                "valid_classes": ["Yes", "No"],
                "system_message": "You are a helpful assistant.",
                "user_message": "Answer with Yes or No: {{text}}",
                "model_provider": "AzureChatOpenAI",
                "model_name": "gpt-4"
            }
            
            classifier = Classifier(**config)
            classifier.model = mock_model
            
            # Create a workflow that tests both condition and edge output mapping
            workflow = StateGraph(classifier.GraphState)
            
            # Add basic nodes
            workflow.add_node("classifier", classifier.get_llm_call_node())
            workflow.add_node("parse", classifier.get_parser_node())
            
            # Test condition with output mapping
            async def condition_value_setter(state):
                """Simulates condition output mapping"""
                if hasattr(state, 'classification') and state.classification == "Yes":
                    state.final_result = "ACCEPTED"  # Condition sets this
                    state.source = "condition_path"
                    state.confidence = "high"
                return state
            
            # Test edge with output mapping  
            async def edge_value_setter(state):
                """Simulates edge output mapping"""
                if hasattr(state, 'classification') and state.classification == "No":
                    state.final_result = "REJECTED"  # Edge sets this  
                    state.source = "edge_path"
                    state.confidence = "medium"
                return state
            
            # Test final output aliasing
            async def final_aliasing(state):
                """Simulates final output aliasing that might conflict"""
                # This is where conflicts often happen - final aliasing tries to overwrite
                # values that were set by conditions or edges
                if not hasattr(state, 'value') or state.value is None:
                    state.value = getattr(state, 'final_result', 'Unknown')
                if not hasattr(state, 'explanation') or state.explanation is None:  
                    state.explanation = f"Processed via {getattr(state, 'source', 'unknown')}"
                return state
            
            workflow.add_node("condition_setter", condition_value_setter)
            workflow.add_node("edge_setter", edge_value_setter)
            workflow.add_node("final_aliasing", final_aliasing)
            
            # Routing logic that prioritizes conditions over edges
            def route_after_parse(state):
                classification = getattr(state, 'classification', None)
                if classification == "Yes":
                    return "condition_setter"  # Condition takes precedence
                elif classification == "No":
                    return "edge_setter"      # Edge fallback
                else:
                    return "final_aliasing"   # Direct to final
            
            workflow.add_conditional_edges(
                "parse",
                route_after_parse,
                {
                    "condition_setter": "condition_setter",
                    "edge_setter": "edge_setter", 
                    "final_aliasing": "final_aliasing"
                }
            )
            
            workflow.add_edge("classifier", "parse")
            workflow.add_edge("condition_setter", "final_aliasing")
            workflow.add_edge("edge_setter", "final_aliasing") 
            workflow.add_edge("final_aliasing", END)
            
            workflow.set_entry_point("classifier")
            compiled_workflow = workflow.compile()
            
            # Test Case 1: Condition path (Yes)
            mock_model.ainvoke = AsyncMock(side_effect=[
                MagicMock(content="Yes")  # Classifier response
            ])
            
            initial_state = classifier.GraphState(
                text="This looks good",
                metadata={},
                results={},
                retry_count=0,
                value=None,
                classification=None
            )
            
            final_state = await compiled_workflow.ainvoke(initial_state)
            
            # Verify condition output mapping worked and wasn't overwritten
            assert getattr(final_state, 'classification', None) == "Yes"
            assert getattr(final_state, 'final_result', None) == "ACCEPTED"  # Set by condition
            assert getattr(final_state, 'source', None) == "condition_path"  # Set by condition
            assert getattr(final_state, 'confidence', None) == "high"        # Set by condition
            assert getattr(final_state, 'value', None) == "ACCEPTED"         # Preserved by final aliasing
            assert "condition_path" in getattr(final_state, 'explanation', '')  # Uses condition source
            
            # Test Case 2: Edge path (No)
            mock_model.ainvoke = AsyncMock(side_effect=[
                MagicMock(content="No")  # Classifier response
            ])
            
            initial_state = classifier.GraphState(
                text="This is problematic",
                metadata={},
                results={},
                retry_count=0,
                value=None,
                classification=None
            )
            
            final_state = await compiled_workflow.ainvoke(initial_state)
            
            # Verify edge output mapping worked and wasn't overwritten
            assert getattr(final_state, 'classification', None) == "No"
            assert getattr(final_state, 'final_result', None) == "REJECTED"  # Set by edge
            assert getattr(final_state, 'source', None) == "edge_path"      # Set by edge
            assert getattr(final_state, 'confidence', None) == "medium"     # Set by edge
            assert getattr(final_state, 'value', None) == "REJECTED"        # Preserved by final aliasing
            assert "edge_path" in getattr(final_state, 'explanation', '')   # Uses edge source
            
            print("✅ All conditional edge + output mapping tests passed!")
            
        except ImportError as e:
            pytest.skip(f"Dependencies not available: {e}")


def test_output_mapping_precedence_rules():
    """Test the rules for output mapping precedence in complex scenarios"""
    
    # This test validates the expected behavior without requiring full workflow execution
    
    # Scenario 1: Condition output vs Final aliasing conflict
    # Expected: Condition output should be preserved
    condition_output = {"value": "PASSED", "grade": "A"}
    final_aliasing = {"value": "classification"}  # Tries to overwrite value
    
    # Rule: Condition outputs should take precedence over final aliasing
    # Implementation should check if field already has a meaningful value
    
    def simulate_final_aliasing(state, aliasing_config):
        """Simulate how final aliasing should work"""
        for target_field, source_field in aliasing_config.items():
            current_value = getattr(state, target_field, None)
            # Only apply aliasing if field is empty/None (preserve existing values)
            if current_value is None or current_value == "":
                source_value = getattr(state, source_field, None)
                if source_value is not None:
                    setattr(state, target_field, source_value)
        return state
    
    # Create mock state with condition output already set
    class MockState:
        def __init__(self):
            self.value = "PASSED"        # Set by condition
            self.grade = "A"             # Set by condition
            self.classification = "Pass" # Original classifier result
    
    state = MockState()
    state = simulate_final_aliasing(state, final_aliasing)
    
    # Verify condition output was preserved
    assert state.value == "PASSED"  # Should NOT be overwritten by classification
    
    # Scenario 2: Edge output vs Final aliasing
    class MockState2:
        def __init__(self):
            self.intermediate_result = "PENDING"  # Set by edge
            self.reasoning = "Needs review"       # Set by edge  
            self.classification = "Maybe"         # Original classifier result
            self.final_value = None               # Will be set by aliasing
    
    edge_aliasing = {"final_value": "intermediate_result"}
    state2 = MockState2() 
    state2 = simulate_final_aliasing(state2, edge_aliasing)
    
    # Verify edge output mapping worked
    assert state2.final_value == "PENDING"  # Should map from intermediate_result
    assert state2.intermediate_result == "PENDING"  # Original should be preserved
    
    print("✅ Output mapping precedence rules validated!")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])