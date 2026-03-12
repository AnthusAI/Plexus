#!/usr/bin/env python3
"""
Unit tests for LangGraph edge configuration handling.

This test specifically captures the bug scenario where final nodes with edge
configurations that route to END were not having their output mappings processed.
"""

import unittest
from unittest.mock import Mock, patch
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from plexus.scores.LangGraphScore import LangGraphScore
from langgraph.graph import StateGraph, END


class TestLangGraphEdgeConfiguration(unittest.TestCase):
    """Test edge configuration handling in LangGraph workflows."""

    def test_final_node_edge_configuration_to_end(self):
        """
        Test that final nodes with edge configurations routing to END
        have their output mappings properly processed.
        
        This test captures the bug scenario from CS3ServicesV2 where:
        - non_qualifying_reason_classifier_revonly was the final node
        - It had an edge configuration with output mapping
        - The output mapping was being ignored, causing inconsistent results
        """
        
        # Mock graph configuration that simulates the problematic scenario
        graph_config = [
            {
                'name': 'customer_type_classifier',
                'class': 'LogicalClassifier',
                'conditions': [
                    {
                        'value': 'Yes',
                        'node': 'revenue_only_classifier',
                        'output': {
                            'value': 'classification',
                            'explanation': 'explanation'
                        }
                    }
                ]
            },
            {
                'name': 'revenue_only_classifier', 
                'class': 'Classifier',
                'edge': {
                    'node': 'non_qualifying_reason_classifier_revonly',
                    'output': {
                        'good_call': 'classification',
                        'good_call_explanation': 'explanation'
                    }
                }
            },
            {
                'name': 'non_qualifying_reason_classifier_revonly',
                'class': 'Classifier',
                'edge': {
                    'node': 'END',
                    'output': {
                        'non_qualifying_reason': 'classification',
                        'non_qualifying_explanation': 'explanation'
                    }
                }
            }
        ]
        
        # Create a mock workflow
        workflow = StateGraph(LangGraphScore.GraphState)
        
        # Add mock nodes
        def mock_node(state):
            return state
            
        workflow.add_node('customer_type_classifier', mock_node)
        workflow.add_node('revenue_only_classifier', mock_node)
        workflow.add_node('non_qualifying_reason_classifier_revonly', mock_node)
        
        # Create mock node instances
        node_instances = [
            ('customer_type_classifier', Mock()),
            ('revenue_only_classifier', Mock()),
            ('non_qualifying_reason_classifier_revonly', Mock())
        ]
        
        # Test the add_edges method
        final_node_handled = LangGraphScore.add_edges(
            workflow, 
            node_instances, 
            None, 
            graph_config, 
            end_node='output_aliasing'
        )
        
        # Verify that the final node's edge configuration was handled
        self.assertTrue(
            final_node_handled, 
            "Final node with edge configuration to END should be handled"
        )
        
        # Check that the workflow has the expected value setter node
        workflow_nodes = list(workflow.nodes.keys())
        expected_value_setter = 'non_qualifying_reason_classifier_revonly_value_setter'
        
        self.assertIn(
            expected_value_setter, 
            workflow_nodes,
            f"Expected value setter node {expected_value_setter} should be created for final node edge configuration"
        )
        
        # Verify that other expected nodes are present
        self.assertIn('customer_type_classifier', workflow_nodes)
        self.assertIn('revenue_only_classifier', workflow_nodes) 
        self.assertIn('non_qualifying_reason_classifier_revonly', workflow_nodes)

    def test_final_node_without_edge_configuration(self):
        """
        Test that final nodes without edge configurations are handled normally
        (fallback edge should be created).
        """
        
        graph_config = [
            {
                'name': 'simple_classifier',
                'class': 'Classifier'
                # No edge configuration
            }
        ]
        
        workflow = StateGraph(LangGraphScore.GraphState)
        
        def mock_node(state):
            return state
            
        workflow.add_node('simple_classifier', mock_node)
        
        node_instances = [('simple_classifier', Mock())]
        
        # Test the add_edges method
        final_node_handled = LangGraphScore.add_edges(
            workflow, 
            node_instances, 
            None, 
            graph_config, 
            end_node='output_aliasing'
        )
        
        # Verify that the final node was NOT handled (should use fallback)
        self.assertFalse(
            final_node_handled, 
            "Final node without edge configuration should not be handled by add_edges"
        )

    def test_final_node_edge_configuration_not_to_end(self):
        """
        Test that final nodes with edge configurations that don't route to END
        are not handled by the special final node logic.
        """
        
        graph_config = [
            {
                'name': 'classifier_a',
                'class': 'Classifier'
            },
            {
                'name': 'classifier_b',
                'class': 'Classifier',
                'edge': {
                    'node': 'classifier_a',  # Routes to another node, not END
                    'output': {
                        'some_field': 'classification'
                    }
                }
            }
        ]
        
        workflow = StateGraph(LangGraphScore.GraphState)
        
        def mock_node(state):
            return state
            
        workflow.add_node('classifier_a', mock_node)
        workflow.add_node('classifier_b', mock_node)
        
        node_instances = [
            ('classifier_a', Mock()),
            ('classifier_b', Mock())
        ]
        
        # Test the add_edges method
        final_node_handled = LangGraphScore.add_edges(
            workflow, 
            node_instances, 
            None, 
            graph_config, 
            end_node='output_aliasing'
        )
        
        # Verify that the final node was NOT handled by special logic
        self.assertFalse(
            final_node_handled, 
            "Final node with edge configuration not routing to END should not be handled by special final node logic"
        )

    def test_edge_output_mapping_creation(self):
        """
        Test that the value setter node is created with the correct output mapping.
        """
        
        graph_config = [
            {
                'name': 'final_node',
                'class': 'Classifier',
                'edge': {
                    'node': 'END',
                    'output': {
                        'result_field': 'classification',
                        'explanation_field': 'explanation'
                    }
                }
            }
        ]
        
        workflow = StateGraph(LangGraphScore.GraphState)
        
        def mock_node(state):
            return state
            
        workflow.add_node('final_node', mock_node)
        
        node_instances = [('final_node', Mock())]
        
        # Test the add_edges method
        final_node_handled = LangGraphScore.add_edges(
            workflow, 
            node_instances, 
            None, 
            graph_config, 
            end_node='output_aliasing'
        )
        
        # Verify the value setter was created
        self.assertTrue(final_node_handled)
        
        workflow_nodes = list(workflow.nodes.keys())
        expected_value_setter = 'final_node_value_setter'
        
        self.assertIn(
            expected_value_setter, 
            workflow_nodes,
            "Value setter node should be created with correct name"
        )

    @patch('plexus.scores.LangGraphScore.logging')
    def test_logging_output(self, mock_logging):
        """
        Test that appropriate log messages are generated when handling final node edges.
        """
        
        graph_config = [
            {
                'name': 'test_final_node',
                'class': 'Classifier',
                'edge': {
                    'node': 'END',
                    'output': {
                        'test_field': 'classification'
                    }
                }
            }
        ]
        
        workflow = StateGraph(LangGraphScore.GraphState)
        workflow.add_node('test_final_node', lambda state: state)
        
        node_instances = [('test_final_node', Mock())]
        
        # Test the add_edges method
        LangGraphScore.add_edges(
            workflow, 
            node_instances, 
            None, 
            graph_config, 
            end_node='output_aliasing'
        )
        
        # Verify that the expected log message was called
        expected_log_call = unittest.mock.call(
            "Added final node edge routing: test_final_node -> test_final_node_value_setter -> output_aliasing"
        )
        
        mock_logging.info.assert_any_call(expected_log_call.args[0])


if __name__ == '__main__':
    unittest.main() 