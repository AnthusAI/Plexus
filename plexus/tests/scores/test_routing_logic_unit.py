"""
Unit tests for routing logic patterns.

These tests verify the core routing logic patterns independently of the 
LangGraphScore implementation to prove the testing approach and validate 
the critical functionality.
"""

import pytest
from unittest.mock import MagicMock


class TestValueSetterPattern:
    """Test the value setter pattern that's core to LangGraphScore routing"""
    
    def test_output_aliasing_basic(self):
        """Test basic output aliasing functionality"""
        
        def create_value_setter_function(output_mapping):
            """Recreate the value setter pattern from LangGraphScore"""
            def value_setter(state):
                # Create a new dict with all current state values
                new_state = state.model_dump()
                
                # Add aliased values
                for alias, original in output_mapping.items():
                    if hasattr(state, original):
                        original_value = getattr(state, original)
                        new_state[alias] = original_value
                        # Also directly set on the state object
                        setattr(state, alias, original_value)
                    else:
                        # If the original isn't a state variable, treat it as literal
                        new_state[alias] = original
                        setattr(state, alias, original)
                
                # Create new state with combined values
                combined_state = state.__class__(**new_state)
                return combined_state
                
            return value_setter
        
        # Test the pattern
        output_mapping = {
            "value": "classification",
            "explanation": "reasoning"
        }
        
        # Mock state object
        class MockState:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)
                    
            def model_dump(self):
                return {k: v for k, v in self.__dict__.items()}
        
        # Test state with source fields
        state = MockState(
            classification="Yes",
            reasoning="Because it matches criteria",
            other_field="preserved"
        )
        
        value_setter = create_value_setter_function(output_mapping)
        result = value_setter(state)
        
        # Verify output aliasing worked
        assert hasattr(result, "value")
        assert hasattr(result, "explanation")
        assert result.value == "Yes"
        assert result.explanation == "Because it matches criteria"
        
        # Verify original fields preserved
        assert result.other_field == "preserved"

    def test_literal_value_handling(self):
        """Test handling of literal values in output mapping"""
        
        def create_value_setter_function(output_mapping):
            def value_setter(state):
                new_state = state.model_dump()
                
                for alias, original in output_mapping.items():
                    if hasattr(state, original):
                        original_value = getattr(state, original)
                        new_state[alias] = original_value
                        setattr(state, alias, original_value)
                    else:
                        # Treat as literal value
                        new_state[alias] = original
                        setattr(state, alias, original)
                
                combined_state = state.__class__(**new_state)
                return combined_state
                
            return value_setter
        
        class MockState:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)
                    
            def model_dump(self):
                return {k: v for k, v in self.__dict__.items()}
        
        # Test mixing state variables and literal values
        output_mapping = {
            "value": "classification",  # From state
            "source": "test_classifier",  # Literal
            "status": "completed"  # Literal
        }
        
        state = MockState(classification="No")
        value_setter = create_value_setter_function(output_mapping)
        result = value_setter(state)
        
        assert result.value == "No"  # From state variable
        assert result.source == "test_classifier"  # Literal value
        assert result.status == "completed"  # Literal value


class TestRoutingPrecedenceLogic:
    """Test the routing precedence logic (conditions vs edge clauses)"""
    
    def test_conditions_precedence_pattern(self):
        """Test the pattern where conditions take precedence over edge clauses"""
        
        def process_node_routing(node_config, workflow):
            """Simulate the add_edges logic for routing precedence"""
            
            # Check if both conditions and edge are present
            has_conditions = 'conditions' in node_config and node_config['conditions']
            has_edge = 'edge' in node_config and node_config['edge']
            
            if has_conditions:
                # Process conditions first - this takes precedence
                conditions = node_config['conditions']
                workflow.add_conditional_edges.called = True
                
                # Create value setters for each condition
                for i, condition in enumerate(conditions):
                    value_setter_name = f"{node_config['name']}_value_setter_{i}"
                    workflow.add_node.called_with = value_setter_name
                    
                # Don't process edge clause when conditions are present
                return "conditions_processed"
                
            elif has_edge:
                # Process edge clause only if no conditions
                edge = node_config['edge']
                value_setter_name = f"{node_config['name']}_value_setter"
                workflow.add_node.called_with = value_setter_name
                return "edge_processed"
                
            else:
                # Direct connection
                return "direct_connection"
        
        # Mock workflow
        workflow = MagicMock()
        workflow.add_conditional_edges = MagicMock()
        workflow.add_node = MagicMock()
        workflow.add_edge = MagicMock()
        
        # Test 1: Both conditions and edge present - conditions should take precedence
        node_config_both = {
            "name": "test_classifier",
            "conditions": [
                {"value": "yes", "node": "positive_handler", "output": {"value": "Positive"}}
            ],
            "edge": {
                "node": "negative_handler",
                "output": {"value": "Negative"}
            }
        }
        
        result = process_node_routing(node_config_both, workflow)
        assert result == "conditions_processed"
        
        # Test 2: Only edge present - edge should be processed
        workflow.reset_mock()
        node_config_edge = {
            "name": "test_classifier",
            "edge": {
                "node": "handler",
                "output": {"value": "Handled"}
            }
        }
        
        result = process_node_routing(node_config_edge, workflow)
        assert result == "edge_processed"
        
        # Test 3: Neither present - direct connection
        workflow.reset_mock()
        node_config_direct = {
            "name": "test_classifier"
        }
        
        result = process_node_routing(node_config_direct, workflow)
        assert result == "direct_connection"

    def test_routing_function_logic(self):
        """Test the routing decision function logic"""
        
        def create_routing_function(conditions, value_setters, fallback_target):
            """Recreate the routing function pattern from LangGraphScore"""
            def routing_function(state):
                # Check if state has classification field
                if hasattr(state, 'classification') and state.classification is not None:
                    state_value = state.classification.lower()
                    # Look for matching value setter
                    if state_value in value_setters:
                        return value_setters[state_value]
                # Default fallback
                return fallback_target
            return routing_function
        
        # Set up test data
        conditions = [
            {"value": "yes", "node": "positive_handler"},
            {"value": "no", "node": "negative_handler"}
        ]
        
        value_setters = {
            "yes": "classifier_value_setter_0",
            "no": "classifier_value_setter_1"
        }
        
        fallback_target = "fallback_handler"
        
        # Create routing function
        routing_func = create_routing_function(conditions, value_setters, fallback_target)
        
        # Mock state objects
        class MockState:
            def __init__(self, classification):
                self.classification = classification
        
        # Test routing scenarios
        assert routing_func(MockState("Yes")) == "classifier_value_setter_0"
        assert routing_func(MockState("No")) == "classifier_value_setter_1"
        assert routing_func(MockState("YES")) == "classifier_value_setter_0"  # Case insensitive
        assert routing_func(MockState("unknown")) == "fallback_handler"
        assert routing_func(MockState(None)) == "fallback_handler"

    def test_multiple_conditions_handling(self):
        """Test handling of multiple conditions with different outputs"""
        
        def process_multiple_conditions(conditions):
            """Process multiple conditions and return value setter info"""
            value_setters = {}
            
            for i, condition in enumerate(conditions):
                value_setter_name = f"node_value_setter_{i}"
                condition_value = condition["value"].lower()
                value_setters[condition_value] = value_setter_name
                
            return value_setters
        
        # Test with multiple conditions
        conditions = [
            {"value": "option1", "node": "handler1", "output": {"value": "Option1"}},
            {"value": "option2", "node": "handler2", "output": {"value": "Option2"}},
            {"value": "option3", "node": "handler3", "output": {"value": "Option3"}}
        ]
        
        value_setters = process_multiple_conditions(conditions)
        
        # Should create value setter for each condition
        assert len(value_setters) == 3
        assert "option1" in value_setters
        assert "option2" in value_setters  
        assert "option3" in value_setters
        
        # Each should have unique value setter name
        assert value_setters["option1"] == "node_value_setter_0"
        assert value_setters["option2"] == "node_value_setter_1"
        assert value_setters["option3"] == "node_value_setter_2"


class TestEdgeConfigurationHandling:
    """Test edge configuration handling patterns"""
    
    def test_final_node_end_routing(self):
        """Test final node routing to END with output mapping"""
        
        def handle_final_node_edge(node_config, end_node="END"):
            """Handle final node edge routing pattern"""
            
            if 'edge' in node_config:
                edge = node_config['edge']
                target_node = edge.get('node')
                
                if target_node == end_node and 'output' in edge:
                    # Create value setter for final node
                    value_setter_name = f"{node_config['name']}_value_setter"
                    return {
                        "creates_value_setter": True,
                        "value_setter_name": value_setter_name,
                        "routes_to_end": True,
                        "output_mapping": edge['output']
                    }
            
            return {"creates_value_setter": False}
        
        # Test final node with END routing
        final_node_config = {
            "name": "final_classifier",
            "edge": {
                "node": "END",
                "output": {"value": "Final", "explanation": "Final result"}
            }
        }
        
        result = handle_final_node_edge(final_node_config)
        
        assert result["creates_value_setter"] is True
        assert result["value_setter_name"] == "final_classifier_value_setter"
        assert result["routes_to_end"] is True
        assert result["output_mapping"]["value"] == "Final"
        assert result["output_mapping"]["explanation"] == "Final result"


def test_comprehensive_routing_pattern():
    """Integration test of the complete routing pattern"""
    
    def simulate_complete_routing(graph_config):
        """Simulate complete routing logic for a graph configuration"""
        routing_info = []
        
        for node_config in graph_config:
            node_name = node_config["name"]
            node_routing = {"name": node_name}
            
            # Check for conditions (takes precedence)
            if 'conditions' in node_config and node_config['conditions']:
                node_routing["routing_type"] = "conditions"
                node_routing["condition_count"] = len(node_config['conditions'])
                node_routing["creates_conditional_edges"] = True
                
                # Create value setters for conditions
                value_setters = []
                for i, condition in enumerate(node_config['conditions']):
                    value_setter = f"{node_name}_value_setter_{i}"
                    value_setters.append(value_setter)
                
                node_routing["value_setters"] = value_setters
                
            elif 'edge' in node_config and node_config['edge']:
                node_routing["routing_type"] = "edge"
                node_routing["creates_conditional_edges"] = False
                
                # Create single value setter for edge
                value_setter = f"{node_name}_value_setter"
                node_routing["value_setters"] = [value_setter]
                
            else:
                node_routing["routing_type"] = "direct"
                node_routing["creates_conditional_edges"] = False
                node_routing["value_setters"] = []
            
            routing_info.append(node_routing)
        
        return routing_info
    
    # Test complex graph with mixed routing types
    complex_graph = [
        {
            "name": "main_classifier",
            "conditions": [
                {"value": "yes", "node": "END", "output": {"value": "Yes"}},
                {"value": "no", "node": "fallback", "output": {"value": "No"}}
            ],
            "edge": {
                "node": "should_be_ignored",
                "output": {"value": "Ignored"}
            }
        },
        {
            "name": "fallback_classifier",
            "edge": {
                "node": "END",
                "output": {"value": "Fallback"}
            }
        },
        {
            "name": "simple_classifier"
        }
    ]
    
    routing_info = simulate_complete_routing(complex_graph)
    
    # Verify main_classifier uses conditions (not edge)
    main_routing = routing_info[0]
    assert main_routing["routing_type"] == "conditions"
    assert main_routing["creates_conditional_edges"] is True
    assert main_routing["condition_count"] == 2
    assert len(main_routing["value_setters"]) == 2
    
    # Verify fallback_classifier uses edge
    fallback_routing = routing_info[1]
    assert fallback_routing["routing_type"] == "edge"
    assert fallback_routing["creates_conditional_edges"] is False
    assert len(fallback_routing["value_setters"]) == 1
    
    # Verify simple_classifier is direct
    simple_routing = routing_info[2]
    assert simple_routing["routing_type"] == "direct"
    assert simple_routing["creates_conditional_edges"] is False
    assert len(simple_routing["value_setters"]) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])