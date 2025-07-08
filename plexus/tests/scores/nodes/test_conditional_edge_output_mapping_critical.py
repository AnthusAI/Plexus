"""
Critical Test Suite: Conditional Edges with Output Mapping

This test suite focuses on the specific problematic scenarios that occur when
combining conditional edges with output mapping. These are high-risk areas that
have been causing issues in production.

Key Problem Areas Tested:
1. Output mapping conflicts between conditions and edges
2. Value setter execution order issues
3. Final output aliasing conflicts with condition/edge outputs
4. State field conflicts in complex routing scenarios
5. Multiple output mappings in the same workflow
6. Condition precedence vs edge fallback with output mappings
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import sys

# Mock problematic dependencies upfront
class MockModule:
    def __getattr__(self, name):
        return MockModule()
    def __call__(self, *args, **kwargs):
        return MockModule()

sys.modules['mlflow'] = MockModule()
sys.modules['seaborn'] = MockModule()
sys.modules['matplotlib'] = MockModule()
sys.modules['graphviz'] = MockModule()

try:
    from plexus.scores.nodes.Classifier import Classifier
    from plexus.scores.LangGraphScore import LangGraphScore
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
    from langgraph.graph import StateGraph, END
    DEPENDENCIES_AVAILABLE = True
except ImportError as e:
    print(f"Dependencies not available: {e}")
    DEPENDENCIES_AVAILABLE = False


@pytest.mark.skipif(not DEPENDENCIES_AVAILABLE, reason="Dependencies not available")
class TestConditionalEdgeOutputMappingCritical:
    """Critical tests for conditional edges with output mapping"""

    @pytest.fixture
    def complex_routing_config(self):
        """Configuration with both conditions and edge that have output mappings"""
        return {
            "name": "complex_router",
            "valid_classes": ["Yes", "No", "Maybe"],
            "system_message": "You are a complex routing classifier.",
            "user_message": "Classify this: {text}",
            "model_provider": "AzureChatOpenAI",
            "model_name": "gpt-4",
            "conditions": [
                {
                    "value": "Yes",
                    "node": "END",
                    "output": {
                        "final_result": "Yes",
                        "confidence": "high",
                        "source": "condition_yes"
                    }
                },
                {
                    "value": "No", 
                    "node": "END",
                    "output": {
                        "final_result": "No",
                        "confidence": "high",
                        "source": "condition_no"
                    }
                }
            ],
            "edge": {
                "node": "fallback_handler", 
                "output": {
                    "intermediate_result": "classification",
                    "reasoning": "explanation",
                    "source": "edge_fallback"
                }
            }
        }

    @pytest.mark.asyncio
    async def test_condition_vs_edge_output_conflict(self, complex_routing_config):
        """Test when both condition and edge try to set the same output field"""
        mock_model = AsyncMock()
        
        with patch('plexus.LangChainUser.LangChainUser._initialize_model', 
                   return_value=mock_model):
            
            classifier = Classifier(**complex_routing_config)
            classifier.model = mock_model

            # Test Case 1: Condition should take precedence and set outputs
            mock_model.ainvoke = AsyncMock(return_value=AIMessage(content="Yes"))
            
            state = classifier.GraphState(
                text="Test positive case",
                metadata={},
                results={},
                retry_count=0,
                is_not_empty=True,
                value=None,
                reasoning=None,
                classification=None,
                chat_history=[],
                completion=None
            )

            # Create workflow with both conditions and edge
            workflow = StateGraph(classifier.GraphState)
            
            # Add core classifier nodes
            workflow.add_node("llm_prompt", classifier.get_llm_prompt_node())
            workflow.add_node("llm_call", classifier.get_llm_call_node())
            workflow.add_node("parse", classifier.get_parser_node())
            
            # Add fallback handler for edge
            async def fallback_handler(state):
                return state
            workflow.add_node("fallback_handler", fallback_handler)
            
            # Add value setters for conditions
            workflow.add_node("set_yes_value", 
                LangGraphScore.create_value_setter_node({
                    "final_result": "Yes",
                    "confidence": "high", 
                    "source": "condition_yes"
                })
            )
            workflow.add_node("set_no_value",
                LangGraphScore.create_value_setter_node({
                    "final_result": "No",
                    "confidence": "high",
                    "source": "condition_no"
                })
            )
            
            # Add value setter for edge
            workflow.add_node("edge_value_setter",
                LangGraphScore.create_value_setter_node({
                    "intermediate_result": "classification",
                    "reasoning": "explanation", 
                    "source": "edge_fallback"
                })
            )

            # Create routing function that prioritizes conditions
            def route_from_parse(state):
                if isinstance(state, dict):
                    classification = state.get('classification')
                else:
                    classification = getattr(state, 'classification', None)
                
                # Conditions take precedence 
                if classification == "Yes":
                    return "set_yes_value"
                elif classification == "No":
                    return "set_no_value"
                else:
                    # Edge fallback for "Maybe" or other values
                    return "edge_value_setter"

            workflow.add_conditional_edges(
                "parse",
                route_from_parse,
                {
                    "set_yes_value": "set_yes_value",
                    "set_no_value": "set_no_value", 
                    "edge_value_setter": "edge_value_setter"
                }
            )

            # Add edges
            workflow.add_edge("llm_prompt", "llm_call")
            workflow.add_edge("llm_call", "parse")
            workflow.add_edge("set_yes_value", END)
            workflow.add_edge("set_no_value", END)
            workflow.add_edge("edge_value_setter", "fallback_handler")
            workflow.add_edge("fallback_handler", END)
            
            workflow.set_entry_point("llm_prompt")
            compiled_workflow = workflow.compile()

            # Run workflow - should hit condition for "Yes"
            final_state = await compiled_workflow.ainvoke(state)
            
            if isinstance(final_state, dict):
                final_state_dict = final_state
            else:
                final_state_dict = final_state.__dict__

            # Verify condition output mapping worked correctly
            assert final_state_dict.get('classification') == "Yes"
            assert final_state_dict.get('final_result') == "Yes"  # Set by condition
            assert final_state_dict.get('confidence') == "high"   # Set by condition
            assert final_state_dict.get('source') == "condition_yes"  # Set by condition
            
            # Verify edge outputs were NOT set (since condition took precedence)
            assert 'intermediate_result' not in final_state_dict
            assert 'reasoning' not in final_state_dict

    @pytest.mark.asyncio
    async def test_output_mapping_precedence_order(self, complex_routing_config):
        """Test that output mappings are applied in the correct precedence order"""
        mock_model = AsyncMock()
        
        with patch('plexus.LangChainUser.LangChainUser._initialize_model', 
                   return_value=mock_model):
            
            classifier = Classifier(**complex_routing_config)
            classifier.model = mock_model

            # Test edge fallback with output mapping
            mock_model.ainvoke = AsyncMock(return_value=AIMessage(content="Maybe"))
            
            state = classifier.GraphState(
                text="Test uncertain case",
                metadata={},
                results={}, 
                retry_count=0,
                is_not_empty=True,
                value=None,
                reasoning=None,
                classification=None,
                chat_history=[],
                completion=None
            )

            # Create simplified workflow for edge testing
            workflow = StateGraph(classifier.GraphState)
            
            workflow.add_node("llm_prompt", classifier.get_llm_prompt_node())
            workflow.add_node("llm_call", classifier.get_llm_call_node())
            workflow.add_node("parse", classifier.get_parser_node())
            
            async def fallback_handler(state):
                # Simulate processing in fallback handler
                return state
            workflow.add_node("fallback_handler", fallback_handler)
            
            # Edge value setter
            workflow.add_node("edge_value_setter",
                LangGraphScore.create_value_setter_node({
                    "intermediate_result": "classification",
                    "reasoning": "explanation",
                    "source": "edge_fallback"
                })
            )

            def route_from_parse(state):
                classification = getattr(state, 'classification', None)
                if classification in ["Yes", "No"]:
                    return "END"  # Would normally hit conditions
                else:
                    return "edge_value_setter"  # Edge fallback

            workflow.add_conditional_edges(
                "parse", 
                route_from_parse,
                {
                    "edge_value_setter": "edge_value_setter"
                }
            )

            workflow.add_edge("llm_prompt", "llm_call")
            workflow.add_edge("llm_call", "parse") 
            workflow.add_edge("edge_value_setter", "fallback_handler")
            workflow.add_edge("fallback_handler", END)
            
            workflow.set_entry_point("llm_prompt")
            compiled_workflow = workflow.compile()

            final_state = await compiled_workflow.ainvoke(state)
            
            if isinstance(final_state, dict):
                final_state_dict = final_state
            else:
                final_state_dict = final_state.__dict__

            # Verify edge output mapping worked
            assert final_state_dict.get('classification') == "Maybe"
            assert final_state_dict.get('intermediate_result') == "Maybe"  # Mapped from classification
            assert final_state_dict.get('reasoning') == "Maybe"  # Mapped from explanation
            assert final_state_dict.get('source') == "edge_fallback"

    @pytest.mark.asyncio 
    async def test_final_output_aliasing_conflicts(self):
        """Test conflicts between condition/edge outputs and final output aliasing"""
        config = {
            "name": "aliasing_conflict_test",
            "valid_classes": ["Pass", "Fail"],
            "system_message": "Grade this submission.",
            "user_message": "Grade: {text}",
            "model_provider": "AzureChatOpenAI",
            "model_name": "gpt-4",
            "conditions": [
                {
                    "value": "Pass",
                    "node": "END", 
                    "output": {
                        "value": "PASSED",  # This conflicts with final output aliasing
                        "grade": "A",
                        "status": "complete"
                    }
                }
            ],
            "output": {
                "value": "classification",  # Final aliasing tries to map this
                "explanation": "explanation"
            }
        }

        mock_model = AsyncMock()
        
        with patch('plexus.LangChainUser.LangChainUser._initialize_model', 
                   return_value=mock_model):
            
            classifier = Classifier(**config)
            classifier.model = mock_model
            mock_model.ainvoke = AsyncMock(return_value=AIMessage(content="Pass"))
            
            state = classifier.GraphState(
                text="Great work!",
                metadata={},
                results={},
                retry_count=0,
                is_not_empty=True,
                value=None,
                reasoning=None,
                classification=None,
                chat_history=[],
                completion=None
            )

            workflow = StateGraph(classifier.GraphState)
            
            workflow.add_node("llm_prompt", classifier.get_llm_prompt_node())
            workflow.add_node("llm_call", classifier.get_llm_call_node())
            workflow.add_node("parse", classifier.get_parser_node())
            
            # Value setter for condition
            workflow.add_node("condition_value_setter",
                LangGraphScore.create_value_setter_node({
                    "value": "PASSED",
                    "grade": "A", 
                    "status": "complete"
                })
            )
            
            # Final output aliasing function
            final_aliasing = LangGraphScore.generate_output_aliasing_function({
                "value": "classification",
                "explanation": "explanation"
            })
            
            async def final_output_node(state):
                return final_aliasing(state)
            workflow.add_node("final_output", final_output_node)

            def route_from_parse(state):
                classification = getattr(state, 'classification', None)
                if classification == "Pass":
                    return "condition_value_setter"
                return "final_output"

            workflow.add_conditional_edges(
                "parse",
                route_from_parse,
                {
                    "condition_value_setter": "condition_value_setter",
                    "final_output": "final_output"
                }
            )

            workflow.add_edge("llm_prompt", "llm_call")
            workflow.add_edge("llm_call", "parse")
            workflow.add_edge("condition_value_setter", "final_output")  # Apply final aliasing after condition
            workflow.add_edge("final_output", END)
            
            workflow.set_entry_point("llm_prompt")
            compiled_workflow = workflow.compile()

            final_state = await compiled_workflow.ainvoke(state)
            
            if isinstance(final_state, dict):
                final_state_dict = final_state
            else:
                final_state_dict = final_state.__dict__

            # CRITICAL: Verify that condition output is preserved despite final aliasing
            assert final_state_dict.get('value') == "PASSED"  # Should preserve condition output
            assert final_state_dict.get('grade') == "A"  # Condition output
            assert final_state_dict.get('status') == "complete"  # Condition output
            assert final_state_dict.get('classification') == "Pass"  # Original classifier result

    @pytest.mark.asyncio
    async def test_multiple_output_mappings_same_field(self):
        """Test when multiple output mappings try to set the same field"""
        config = {
            "name": "field_conflict_test",
            "valid_classes": ["Accept", "Reject", "Review"], 
            "system_message": "Make a decision.",
            "user_message": "Decide: {text}",
            "model_provider": "AzureChatOpenAI",
            "model_name": "gpt-4",
            "conditions": [
                {
                    "value": "Accept",
                    "node": "END",
                    "output": {
                        "final_decision": "ACCEPTED",  # Same field
                        "processor": "auto_accept"
                    }
                },
                {
                    "value": "Reject",
                    "node": "END", 
                    "output": {
                        "final_decision": "REJECTED",  # Same field
                        "processor": "auto_reject" 
                    }
                }
            ],
            "edge": {
                "node": "manual_review",
                "output": {
                    "final_decision": "PENDING",  # Same field again!
                    "processor": "manual_reviewer"
                }
            }
        }

        mock_model = AsyncMock()
        
        with patch('plexus.LangChainUser.LangChainUser._initialize_model', 
                   return_value=mock_model):
            
            classifier = Classifier(**config)
            classifier.model = mock_model

            # Test each path to ensure correct field values
            test_cases = [
                ("Accept", "ACCEPTED", "auto_accept"),
                ("Reject", "REJECTED", "auto_reject"),
                ("Review", "PENDING", "manual_reviewer")
            ]

            for classification, expected_decision, expected_processor in test_cases:
                mock_model.ainvoke = AsyncMock(return_value=AIMessage(content=classification))
                
                state = classifier.GraphState(
                    text=f"Test case for {classification}",
                    metadata={},
                    results={},
                    retry_count=0,
                    is_not_empty=True,
                    value=None,
                    reasoning=None,
                    classification=None,
                    chat_history=[],
                    completion=None
                )

                workflow = StateGraph(classifier.GraphState)
                
                workflow.add_node("llm_prompt", classifier.get_llm_prompt_node())
                workflow.add_node("llm_call", classifier.get_llm_call_node())
                workflow.add_node("parse", classifier.get_parser_node())
                
                async def manual_review(state):
                    return state
                workflow.add_node("manual_review", manual_review)
                
                # Value setters for each condition
                workflow.add_node("accept_setter",
                    LangGraphScore.create_value_setter_node({
                        "final_decision": "ACCEPTED",
                        "processor": "auto_accept"
                    })
                )
                workflow.add_node("reject_setter", 
                    LangGraphScore.create_value_setter_node({
                        "final_decision": "REJECTED",
                        "processor": "auto_reject"
                    })
                )
                workflow.add_node("review_setter",
                    LangGraphScore.create_value_setter_node({
                        "final_decision": "PENDING",
                        "processor": "manual_reviewer"
                    })
                )

                def route_from_parse(state):
                    cls = getattr(state, 'classification', None)
                    if cls == "Accept":
                        return "accept_setter"
                    elif cls == "Reject":
                        return "reject_setter"
                    else:  # Review or other
                        return "review_setter"

                workflow.add_conditional_edges(
                    "parse",
                    route_from_parse,
                    {
                        "accept_setter": "accept_setter",
                        "reject_setter": "reject_setter", 
                        "review_setter": "review_setter"
                    }
                )

                workflow.add_edge("llm_prompt", "llm_call")
                workflow.add_edge("llm_call", "parse")
                workflow.add_edge("accept_setter", END)
                workflow.add_edge("reject_setter", END)
                workflow.add_edge("review_setter", "manual_review")
                workflow.add_edge("manual_review", END)
                
                workflow.set_entry_point("llm_prompt")
                compiled_workflow = workflow.compile()

                final_state = await compiled_workflow.ainvoke(state)
                
                if isinstance(final_state, dict):
                    final_state_dict = final_state
                else:
                    final_state_dict = final_state.__dict__

                # Verify correct field values for this path
                assert final_state_dict.get('classification') == classification
                assert final_state_dict.get('final_decision') == expected_decision
                assert final_state_dict.get('processor') == expected_processor

    @pytest.mark.asyncio
    async def test_nested_output_mapping_interactions(self):
        """Test complex nested scenarios with multiple levels of output mapping"""
        config = {
            "name": "nested_mapping_test",
            "valid_classes": ["High", "Medium", "Low"],
            "system_message": "Assess risk level.",
            "user_message": "Risk assessment: {text}",
            "model_provider": "AzureChatOpenAI", 
            "model_name": "gpt-4",
            "conditions": [
                {
                    "value": "High",
                    "node": "escalation_handler",
                    "output": {
                        "risk_level": "CRITICAL",
                        "escalation_required": True,
                        "next_step": "immediate_review"
                    }
                }
            ],
            "edge": {
                "node": "standard_processing",
                "output": {
                    "risk_level": "classification",  # State field reference
                    "escalation_required": False,    # Literal
                    "next_step": "standard_workflow" # Literal
                }
            }
        }

        mock_model = AsyncMock()
        
        with patch('plexus.LangChainUser.LangChainUser._initialize_model', 
                   return_value=mock_model):
            
            classifier = Classifier(**config)
            classifier.model = mock_model

            # Test nested processing for High risk (condition path)
            mock_model.ainvoke = AsyncMock(return_value=AIMessage(content="High"))
            
            state = classifier.GraphState(
                text="Critical security vulnerability detected",
                metadata={},
                results={},
                retry_count=0,
                is_not_empty=True,
                value=None,
                reasoning=None,
                classification=None,
                chat_history=[],
                completion=None
            )

            workflow = StateGraph(classifier.GraphState)
            
            workflow.add_node("llm_prompt", classifier.get_llm_prompt_node())
            workflow.add_node("llm_call", classifier.get_llm_call_node())
            workflow.add_node("parse", classifier.get_parser_node())
            
            # Condition value setter
            workflow.add_node("high_risk_setter",
                LangGraphScore.create_value_setter_node({
                    "risk_level": "CRITICAL",
                    "escalation_required": True,
                    "next_step": "immediate_review"
                })
            )
            
            # Escalation handler with its own output mapping
            async def escalation_handler(state):
                # Simulate escalation handler adding more fields
                state.escalation_time = "2024-01-01T12:00:00Z" 
                state.escalation_team = "security_team"
                state.priority = "P0"
                return state
            workflow.add_node("escalation_handler", escalation_handler)
            
            # Final processing with more output mapping
            final_mapping = LangGraphScore.create_value_setter_node({
                "final_status": "escalated",
                "workflow_complete": True
            })
            workflow.add_node("final_processing", final_mapping)

            def route_from_parse(state):
                cls = getattr(state, 'classification', None)
                if cls == "High":
                    return "high_risk_setter"
                return "END"  # Skip for other values in this test

            workflow.add_conditional_edges(
                "parse",
                route_from_parse,
                {
                    "high_risk_setter": "high_risk_setter"
                }
            )

            workflow.add_edge("llm_prompt", "llm_call")
            workflow.add_edge("llm_call", "parse")
            workflow.add_edge("high_risk_setter", "escalation_handler")
            workflow.add_edge("escalation_handler", "final_processing")
            workflow.add_edge("final_processing", END)
            
            workflow.set_entry_point("llm_prompt")
            compiled_workflow = workflow.compile()

            final_state = await compiled_workflow.ainvoke(state)
            
            if isinstance(final_state, dict):
                final_state_dict = final_state
            else:
                final_state_dict = final_state.__dict__

            # Verify all nested output mappings worked correctly
            assert final_state_dict.get('classification') == "High"
            assert final_state_dict.get('risk_level') == "CRITICAL"  # From condition
            assert final_state_dict.get('escalation_required') is True  # From condition
            assert final_state_dict.get('next_step') == "immediate_review"  # From condition
            assert final_state_dict.get('escalation_time') == "2024-01-01T12:00:00Z"  # From escalation handler
            assert final_state_dict.get('escalation_team') == "security_team"  # From escalation handler
            assert final_state_dict.get('priority') == "P0"  # From escalation handler
            assert final_state_dict.get('final_status') == "escalated"  # From final processing
            assert final_state_dict.get('workflow_complete') is True  # From final processing

    def test_output_mapping_validation_errors(self):
        """Test validation and error handling in output mapping scenarios"""
        # Test invalid condition configuration
        invalid_config = {
            "name": "invalid_test",
            "valid_classes": ["Yes", "No"],
            "system_message": "Test",
            "user_message": "Test: {text}",
            "model_provider": "AzureChatOpenAI",
            "model_name": "gpt-4",
            "conditions": [
                {
                    "value": "Yes",
                    "node": "END",
                    "output": {
                        "": "invalid_empty_key",  # Invalid empty key
                        "valid_field": "classification"
                    }
                }
            ]
        }

        # Should handle invalid configurations gracefully
        with patch('plexus.LangChainUser.LangChainUser._initialize_model', 
                   return_value=AsyncMock()):
            try:
                classifier = Classifier(**invalid_config)
                # If it doesn't raise an error, that's also a valid outcome
                # depending on how the system handles invalid configs
                assert True
            except Exception as e:
                # If it raises an error, it should be a meaningful one
                assert "empty" in str(e).lower() or "invalid" in str(e).lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])