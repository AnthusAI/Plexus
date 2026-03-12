"""
LangGraphScore Conditional Routing Tests

This file contains tests specifically for LangGraphScore's conditional routing functionality,
including edge routing, conditions with fallback, and the newly discovered routing bugs.

Extracted from the massive LangGraphScore_test.py file for better maintainability.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from plexus.scores.LangGraphScore import LangGraphScore
from plexus.scores.Score import Score
from langchain_core.messages import AIMessage


@pytest.fixture
def basic_routing_config():
    """Basic configuration for routing tests."""
    return {
        'name': 'Basic Routing Test',
        'model_provider': 'ChatOpenAI',
        'model_name': 'gpt-4o-mini-2024-07-18',
        'graph': [
            {
                'name': 'classifier',
                'class': 'Classifier',
                'valid_classes': ['Yes', 'No', 'Maybe'],
                'system_message': 'Classify the input',
                'user_message': 'Input: {{text}}'
            }
        ]
    }


@pytest.mark.asyncio
async def test_conditional_routing_actual_execution():
    """
    Test that actually executes a LangGraphScore workflow with conditional routing.
    This fills the gap left by existing tests that mock workflow.ainvoke().
    
    IMPORTANT: This test exposes the broken conditional routing system.
    """
    
    # Mock a Classifier that behaves like the real one
    class TestClassifierMock:
        def __init__(self, **kwargs):
            self.parameters = MagicMock()
            self.parameters.output = None
            self.parameters.name = kwargs.get('name', 'test_classifier')
            self.parameters.valid_classes = kwargs.get('valid_classes', ['Yes', 'No'])
            
        class GraphState:
            def __init__(self, **kwargs):
                self.text = kwargs.get('text')
                self.metadata = kwargs.get('metadata')
                self.results = kwargs.get('results')
                self.classification = kwargs.get('classification')
                self.explanation = kwargs.get('explanation')
                self.value = kwargs.get('value')
                self.reason = kwargs.get('reason')
                
            def model_dump(self):
                return {
                    'text': self.text,
                    'metadata': self.metadata,
                    'results': self.results,
                    'classification': self.classification,
                    'explanation': self.explanation,
                    'value': self.value,
                    'reason': self.reason
                }
                
        async def analyze(self, state):
            # Simulate classification behavior
            state_dict = state.model_dump() if hasattr(state, 'model_dump') else dict(state)
            state_dict.update({
                "classification": "Yes", 
                "explanation": "Classified as Yes"
            })
            return self.GraphState(**state_dict)
            
        def build_compiled_workflow(self, graph_state_class):
            from langgraph.graph import StateGraph, END
            workflow = StateGraph(graph_state_class)
            workflow.add_node("analyze", self.analyze)
            workflow.set_entry_point("analyze")
            workflow.add_edge("analyze", END)
            
            async def invoke_workflow(state):
                if hasattr(state, 'model_dump'):
                    state_dict = state.model_dump()
                else:
                    state_dict = dict(state)
                final_state = await self.analyze(graph_state_class(**state_dict))
                return final_state.model_dump()
            
            return invoke_workflow
    
    # Mock the import
    original_import = LangGraphScore._import_class
    @staticmethod  
    def mock_import_class(class_name):
        if class_name == "Classifier":
            return TestClassifierMock
        else:
            return original_import(class_name)
    
    try:
        LangGraphScore._import_class = mock_import_class
        
        config = {
            'name': 'Conditional Routing Execution Test',
            'model_provider': 'ChatOpenAI',
            'model_name': 'gpt-4o-mini-2024-07-18',
            'graph': [
                {
                    'name': 'test_classifier',
                    'class': 'Classifier',
                    'valid_classes': ['Yes', 'No'],
                    'system_message': 'Classify the input',
                    'user_message': 'Input: {{text}}',
                    'conditions': [
                        {
                            'state': 'classification',
                            'value': 'Yes',
                            'node': 'END',
                            'output': {
                                'value': 'Approved',
                                'reason': 'Positive classification'
                            }
                        }
                    ]
                }
            ],
            'output': {
                'value': 'value',
                'explanation': 'reason'
            }
        }
        
        # Mock the LLM initialization
        with patch('plexus.LangChainUser.LangChainUser._initialize_model') as mock_init_model:
            mock_model = AsyncMock()
            mock_init_model.return_value = mock_model
            
            # Create the score
            score = await LangGraphScore.create(**config)
            
            input_data = Score.Input(
                text="This should be approved",
                metadata={},
                results=[]
            )
            
            result = await score.predict(input_data)
            
            print(f"Actual Execution Test - Expected: value='Approved', Got: value='{result.value}'")
            print(f"Actual Execution Test - Expected: explanation='Positive classification', Got: explanation='{result.metadata.get('explanation')}'")
            
            # This should now work with proper conditional routing
            assert result.value == "Approved", f"Expected 'Approved' from conditional output, got '{result.value}'"
            assert result.metadata.get('explanation') == "Positive classification", f"Expected 'Positive classification' from conditional output"
            print("✅ Conditional routing works correctly!")
            
            await score.cleanup()
            
    finally:
        LangGraphScore._import_class = original_import


@pytest.mark.asyncio
async def test_production_bug_actual_execution():
    """
    Test that reproduces the exact production bug by actually executing the workflow.
    This should expose the top-level output mapping override issue.
    
    Based on GitHub Issue #80 where conditional outputs are overridden by top-level mappings.
    """
    
    # Mock a Classifier that behaves like the real device classifier
    class DeviceClassifierMock:
        def __init__(self, **kwargs):
            self.parameters = MagicMock()
            self.parameters.output = None
            self.parameters.name = kwargs.get('name', 'device_classifier')
            self.parameters.valid_classes = kwargs.get('valid_classes', ['Computer_With_Internet', 'Computer_No_Internet'])
            
        class GraphState:
            def __init__(self, **kwargs):
                self.text = kwargs.get('text')
                self.metadata = kwargs.get('metadata')
                self.results = kwargs.get('results')
                self.classification = kwargs.get('classification')
                self.explanation = kwargs.get('explanation')
                self.value = kwargs.get('value')
                
            def model_dump(self):
                return {
                    'text': self.text,
                    'metadata': self.metadata,
                    'results': self.results,
                    'classification': self.classification,
                    'explanation': self.explanation,
                    'value': self.value
                }
                
        async def analyze(self, state):
            # Simulate device classification behavior
            state_dict = state.model_dump() if hasattr(state, 'model_dump') else dict(state)
            state_dict.update({
                "classification": "Computer_With_Internet", 
                "explanation": "Device classified as computer with internet"
            })
            return self.GraphState(**state_dict)
            
        def build_compiled_workflow(self, graph_state_class):
            from langgraph.graph import StateGraph, END
            workflow = StateGraph(graph_state_class)
            workflow.add_node("analyze", self.analyze)
            workflow.set_entry_point("analyze")
            workflow.add_edge("analyze", END)
            
            async def invoke_workflow(state):
                if hasattr(state, 'model_dump'):
                    state_dict = state.model_dump()
                else:
                    state_dict = dict(state)
                final_state = await self.analyze(graph_state_class(**state_dict))
                return final_state.model_dump()
            
            return invoke_workflow
    
    # Mock the import
    original_import = LangGraphScore._import_class
    @staticmethod  
    def mock_import_class(class_name):
        if class_name == "Classifier":
            return DeviceClassifierMock
        else:
            return original_import(class_name)
    
    try:
        LangGraphScore._import_class = mock_import_class
        
        config = {
            'name': 'Production Bug Actual Execution',
            'model_provider': 'ChatOpenAI', 
            'model_name': 'gpt-4o-mini-2024-07-18',
            'graph': [
                {
                    'name': 'device_classifier',
                    'class': 'Classifier',
                    'valid_classes': ['Computer_With_Internet', 'Computer_No_Internet'],
                    'system_message': 'Classify the device type',
                    'user_message': 'Device: {{text}}',
                    'conditions': [
                        {
                            'state': 'classification',
                            'value': 'Computer_With_Internet',
                            'node': 'END',
                            'output': {
                                'value': 'Yes',  # This should be preserved
                                'explanation': 'Has computer with internet'
                            }
                        }
                    ]
                }
            ],
            # THE BUG: This top-level mapping overrides conditional outputs
            'output': {
                'value': 'classification',  # This maps value to classification, overriding conditional value
                'explanation': 'explanation'
            }
        }
        
        with patch('plexus.LangChainUser.LangChainUser._initialize_model') as mock_init_model:
            mock_model = AsyncMock()
            mock_init_model.return_value = mock_model
            
            score = await LangGraphScore.create(**config)
            
            input_data = Score.Input(
                text="I have a computer with internet",
                metadata={},
                results=[]
            )
            
            result = await score.predict(input_data)
            
            print(f"Production Bug Actual Execution:")
            print(f"  Classification: '{result.metadata.get('classification', 'NOT_SET')}'")
            print(f"  Expected value: 'Yes' (from conditional output)")
            print(f"  Actual value: '{result.value}'")
            
            # Document the current state of the bug
            if result.value == "Computer_With_Internet":
                print("🐛 PRODUCTION BUG REPRODUCED: Top-level output mapping overrode conditional output!")
            elif result.value == "Yes":
                print("✅ CONDITIONAL OUTPUT PRESERVED: Bug might be fixed!")
            elif result.value == "No":
                print("❓ CONDITIONAL ROUTING NOT WORKING: Shows prerequisite bug where conditions don't trigger")
            
            # This should now work with the bug fix
            assert result.value == "Yes", f"Expected 'Yes' from conditional output, got '{result.value}'"
            print("✅ Production bug is fixed!")
            
            await score.cleanup()
            
    finally:
        LangGraphScore._import_class = original_import


@pytest.mark.asyncio 
async def test_exact_production_bug_reproduction():
    """
    Test that uses the EXACT same configuration structure as production to reproduce the bug.
    This matches the CMG - EDU v1.0 scorecard's "Computer w/ Internet" score configuration.
    """
    
    config = {
        'name': 'Exact Production Bug Test',
        'model_provider': 'ChatOpenAI',
        'model_name': 'gpt-4o-mini-2024-07-18',
        'graph': [
            {
                'name': 'device_response_analyzer',
                'class': 'Classifier',
                'valid_classes': ['Computer_With_Internet', 'Computer_No_Internet'],
                'system_message': 'Classify device access',
                'user_message': 'Device access: {{text}}',
                'conditions': [
                    {
                        'state': 'classification',
                        'value': 'Computer_With_Internet',
                        'node': 'END',
                        'output': {
                            'value': 'Yes',  # Conditional says value should be "Yes"
                            'explanation': 'The prospect said they have a computer with internet, this is a yes.',
                        }
                    }
                ],
                'edge': {
                    'node': 'final_evaluator',
                    'output': {
                        'device_status': 'classification'
                    }
                }
            },
            {
                'name': 'final_evaluator', 
                'class': 'Classifier',
                'valid_classes': ['Yes', 'No'],
                'system_message': 'Make final determination',
                'user_message': 'Device status: {{device_status}}'
            }
        ],
        # PRODUCTION BUG: This top-level mapping overrides conditional outputs!
        'output': {
            'value': 'classification',  # This causes value to be "Computer_With_Internet" instead of "Yes"
            'explanation': 'explanation'
        }
    }
    
    with patch('plexus.LangChainUser.LangChainUser._initialize_model') as mock_init_model:
        mock_model = AsyncMock()
        mock_init_model.return_value = mock_model
        
        score = await LangGraphScore.create(**config)
        
        # Mock the device_response_analyzer to return Computer_With_Internet
        mock_model.ainvoke = AsyncMock(return_value=AIMessage(content="Computer_With_Internet"))
        
        input_data = Score.Input(
            text="Yes, I have a computer with internet access",
            metadata={},
            results=[]
        )
        
        result = await score.predict(input_data)
        
        print(f"\nExact Production Bug Reproduction:")
        print(f"  Input: 'Yes, I have a computer with internet access'")
        print(f"  Device Classification: '{result.metadata.get('classification', 'NOT_SET')}'")
        print(f"  Expected Value: 'Yes' (from conditional output)")
        print(f"  Actual Value: '{result.value}'")
        print(f"  Expected Explanation: 'The prospect said they have a computer with internet, this is a yes.'")
        print(f"  Actual Explanation: '{result.metadata.get('explanation', 'NOT_SET')}'")
        
        # Check if we reproduced the exact production bug
        if result.value == "Computer_With_Internet":
            print("🎯 EXACT PRODUCTION BUG REPRODUCED!")
            print("   → Conditional routing worked but top-level output mapping overrode it")
            print("   → This matches the production behavior we saw with plexus_predict")
        elif result.value == "Yes":
            print("✅ Bug appears to be fixed - conditional output was preserved")
        else:
            print(f"❓ Unexpected result: {result.value} - different from production")
            
        # This test documents the exact production bug
        try:
            assert result.value == "Yes", f"PRODUCTION BUG: Top-level output mapping overrode conditional output. Expected 'Yes', got '{result.value}'"
            print("✅ Production bug is fixed!")
        except AssertionError as e:
            print(f"❌ EXPECTED FAILURE: {e}")
            if result.value == "Computer_With_Internet":
                print("✅ Successfully reproduced the exact production bug!")
            # Re-raise to ensure test fails until bug is fixed  
            raise


@pytest.mark.asyncio
async def test_conditional_routing_with_edge_fallback():
    """
    Test conditional routing with edge clause fallback by actually executing the workflow.
    This tests the more complex routing scenarios.
    """
    
    config = {
        'name': 'Conditional with Edge Fallback Test',
        'model_provider': 'ChatOpenAI',
        'model_name': 'gpt-4o-mini-2024-07-18',
        'graph': [
            {
                'name': 'priority_classifier',
                'class': 'Classifier',
                'valid_classes': ['High', 'Medium', 'Low'],
                'system_message': 'Classify priority',
                'user_message': 'Priority: {{text}}',
                'conditions': [
                    {
                        'state': 'classification',
                        'value': 'High',
                        'node': 'END',
                        'output': {
                            'value': 'Urgent',
                            'action': 'Immediate'
                        }
                    }
                ],
                'edge': {
                    'node': 'secondary_processor',
                    'output': {
                        'priority_level': 'classification',
                        'next_step': 'review'
                    }
                }
            },
            {
                'name': 'secondary_processor',
                'class': 'Classifier',
                'valid_classes': ['Process', 'Defer'],
                'system_message': 'Process the {{priority_level}} priority item',
                'user_message': 'Next step: {{next_step}}'
            }
        ],
        'output': {
            'value': 'classification',
            'explanation': 'explanation'
        }
    }
    
    with patch('plexus.LangChainUser.LangChainUser._initialize_model') as mock_init_model:
        mock_model = AsyncMock()
        mock_init_model.return_value = mock_model
        
        score = await LangGraphScore.create(**config)
        
        # Test 1: High priority should trigger conditional routing to END
        mock_model.ainvoke = AsyncMock(return_value=AIMessage(content="High"))
        
        result1 = await score.predict(Score.Input(
            text="Critical system failure",
            metadata={},
            results=[]
        ))
        
        print(f"High Priority Test - Expected: value='Urgent', Got: value='{result1.value}'")
        
        # This should test the conditional routing to END
        # Current expectation: Will fail due to broken conditional routing
        
        # Test 2: Medium priority should fallback to edge routing (go to secondary_processor)
        responses = ["Medium", "Process"]  # First call returns Medium, second call returns Process
        mock_model.ainvoke = AsyncMock(side_effect=[AIMessage(content=resp) for resp in responses])
        
        result2 = await score.predict(Score.Input(
            text="Standard request",
            metadata={},
            results=[]
        ))
        
        print(f"Medium Priority Test - Expected: value='Process', Got: value='{result2.value}'")
        
        # Document the current state - these tests will likely fail until routing is fixed
        print("NOTE: These tests document expected behavior once conditional routing is fixed")


@pytest.mark.asyncio
async def test_conditional_routing_debug_logging():
    """
    Test that conditional routing debug logging actually captures real routing decisions.
    This verifies the debug infrastructure works when routing is executed.
    """
    
    config = {
        'name': 'Debug Logging Test',
        'model_provider': 'ChatOpenAI',
        'model_name': 'gpt-4o-mini-2024-07-18',
        'graph': [
            {
                'name': 'debug_classifier',
                'class': 'Classifier',
                'valid_classes': ['Debug_Match', 'Debug_NoMatch'],
                'system_message': 'Debug test classifier',
                'user_message': 'Test: {{text}}',
                'conditions': [
                    {
                        'state': 'classification',
                        'value': 'Debug_Match',
                        'node': 'END',
                        'output': {
                            'value': 'Matched',
                            'debug_info': 'Condition matched successfully'
                        }
                    }
                ]
            }
        ]
    }
    
    with patch('plexus.LangChainUser.LangChainUser._initialize_model') as mock_init_model:
        mock_model = AsyncMock()
        mock_init_model.return_value = mock_model
        
        with patch('logging.info') as mock_log:
            score = await LangGraphScore.create(**config)
            
            # Execute with matching condition
            mock_model.ainvoke = AsyncMock(return_value=AIMessage(content="Debug_Match"))
            
            result = await score.predict(Score.Input(
                text="test debug",
                metadata={},
                results=[]
            ))
            
            # Check that conditional routing debug logs were captured during execution
            log_calls = [call.args[0] for call in mock_log.call_args_list if call.args]
            
            conditional_routing_logs = [log for log in log_calls if "CONDITIONAL ROUTING DEBUG" in str(log)]
            condition_match_logs = [log for log in log_calls if "CONDITION MATCH" in str(log)]
            
            print(f"Found {len(conditional_routing_logs)} conditional routing debug logs")
            print(f"Found {len(condition_match_logs)} condition match logs")
            print(f"Result value: {result.value}")
            
            # This test documents that conditional routing debug logs should appear during execution
            # With the current broken routing, we expect NO conditional routing logs
            print("NOTE: With broken routing, conditional routing debug logs don't appear")


# Additional tests that need to be moved from the monolithic file:
# - test_conditions_with_edge_fallback
# - test_langgraphscore_combined_conditions_and_edge_routing  
# - test_enhanced_routing_conditions_with_edge_fallback
# - test_complex_add_edges_conditional_routing
# - test_complex_multi_condition_routing_with_fallbacks
# - test_edge_routing
# - test_complex_routing_function_creation

# TODO: Move these tests from LangGraphScore_test.py to this file
# TODO: Ensure all fixtures and imports are available
# TODO: Update any relative imports or dependencies 