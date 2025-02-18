import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from plexus.scores.nodes.Classifier import Classifier
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from plexus.scores.LangGraphScore import BatchProcessingPause, LangGraphScore, END
from langgraph.graph import StateGraph

pytest.asyncio_fixture_scope = "function"
pytest_plugins = ('pytest_asyncio',)

@pytest.fixture(autouse=True)
def disable_batch_mode(monkeypatch):
    monkeypatch.setenv('PLEXUS_ENABLE_BATCH_MODE', 'false')
    monkeypatch.setenv('PLEXUS_ENABLE_LLM_BREAKPOINTS', 'false')

@pytest.fixture
def basic_config():
    return {
        "name": "test_classifier",
        "valid_classes": ["positive", "negative"],
        "system_message": "You are a binary classifier.",
        "user_message": "Classify the following text: {text}",
        "model_provider": "AzureChatOpenAI",
        "model_name": "gpt-40-mini",
        "temperature": 0.0
    }

@pytest.fixture
def turnip_classifier_config():
    return {
        "name": "turnip_detector",
        "valid_classes": ["yes", "no"],
        "system_message": "You are a classifier that detects if the word 'turnip' appears in text.",
        "user_message": "Does this text contain the word 'turnip'? Answer only yes or no: {text}",
        "model_provider": "AzureChatOpenAI",
        "model_name": "gpt-4",
        "temperature": 0.0
    }

@pytest.fixture
def empathy_classifier_config():
    return {
        "name": "empathy_detector",
        "valid_classes": ["Yes", "No", "NA"],
        "system_message": "You are a classifier that detects if empathy was shown.",
        "user_message": "Did the agent show empathy? Answer Yes, No, or NA: {text}",
        "model_provider": "AzureChatOpenAI",
        "model_name": "gpt-4",
        "temperature": 0.0
    }

@pytest.fixture
def call_outcome_classifier_config():
    return {
        "name": "call_outcome",
        "valid_classes": [
            "Successfully Resolved Issue",
            "Escalated to Supervisor",
            "Customer Declined Solution",
            "Follow Up Required",
            "Technical Difficulties"
        ],
        "system_message": "You are a classifier that determines call outcomes.",
        "user_message": "What was the outcome of this call? {text}",
        "model_provider": "AzureChatOpenAI",
        "model_name": "gpt-4",
        "temperature": 0.0
    }

@pytest.mark.asyncio
async def test_classifier_routing_missing_condition(turnip_classifier_config):
    """Test that classifier correctly handles when a classification value has no matching condition."""
    mock_model = AsyncMock()
    mock_response = AIMessage(content="yes")
    mock_model.ainvoke = AsyncMock(return_value=mock_response)
    
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', 
               return_value=mock_model):
        # Create a classifier with conditions only for 'no'
        config = turnip_classifier_config.copy()
        config['conditions'] = [
            {
                'value': 'no',
                'node': 'END',
                'output': {'value': 'no_turnip'}
            }
        ]
        
        classifier = Classifier(**config)
        classifier.model = mock_model
        
        state = classifier.GraphState(
            text="I love eating turnip soup.",
            metadata={},
            results={},
            retry_count=0,
            is_not_empty=True,
            value=None,
            reasoning=None,
            classification=None,
            chat_history=[],
            completion=None,
            result=None
        )
        
        # Create workflow
        workflow = StateGraph(classifier.GraphState)
        
        # Add core nodes
        workflow.add_node("llm_prompt", classifier.get_llm_prompt_node())
        workflow.add_node("llm_call", classifier.get_llm_call_node())
        workflow.add_node("parse", classifier.get_parser_node())
        
        # Add a proper next_node that preserves state
        async def next_node(state):
            # If state is a dict, convert it to GraphState while preserving all fields
            if isinstance(state, dict):
                # Create GraphState with all fields from the dict
                return state
            # Return the state as is
            return state
        workflow.add_node("next_node", next_node)
        
        # Add value setter nodes for each condition
        for condition in config['conditions']:
            if 'output' in condition:
                node_name = f"set_{condition['value']}_value"
                print(f"Creating value setter node {node_name} with output {condition['output']}")  # Debug print
                workflow.add_node(node_name, LangGraphScore.create_value_setter_node(condition['output']))
                workflow.add_edge(node_name, END)

        # Create a function that routes based on classification and conditions
        def get_next_node(state):
            # Convert state to dict if it isn't already
            state_dict = state if isinstance(state, dict) else state.__dict__
            classification = state_dict.get('classification')
            print(f"get_next_node called with classification: {classification}")  # Add logging
            if classification is not None:
                # Find matching condition
                for condition in config['conditions']:
                    if condition['value'] == classification and 'output' in condition:
                        node_name = f"set_{condition['value']}_value"
                        print(f"Routing to {node_name}")  # Add logging
                        return node_name
            
            # If no condition matches, continue to next node
            print("Continuing to next node")  # Add logging
            return "next_node"

        # Add conditional edges from parse
        workflow.add_conditional_edges(
            "parse",
            get_next_node,
            {
                "set_no_value": "set_no_value",
                "next_node": "next_node"
            }
        )
        
        # Add regular edges
        workflow.add_edge("llm_prompt", "llm_call")
        workflow.add_edge("llm_call", "parse")
        workflow.add_edge("next_node", END)
        workflow.add_edge("set_no_value", END)  # Make sure this edge exists
        
        # Set entry point
        workflow.set_entry_point("llm_prompt")
        
        # Compile workflow
        workflow = workflow.compile()
        
        # Test with 'yes' - should continue to next node since there's no condition for 'yes'
        final_state = await workflow.ainvoke(state)
        
        final_state_dict = final_state if isinstance(final_state, dict) else final_state.__dict__
        assert final_state_dict.get('classification') == "yes"
        # Should not have 'result' field since no condition matched
        assert 'result' not in final_state_dict
        
        # Test with 'no' - should route to END with output
        mock_model.ainvoke = AsyncMock(return_value=AIMessage(content="no"))
        
        state = classifier.GraphState(
            text="I love eating potato soup.",
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
        
        final_state = await workflow.ainvoke(state)
        
        # Get final state as dict, prioritizing direct dict access to preserve all fields
        if isinstance(final_state, dict):
            final_state_dict = final_state
        elif hasattr(final_state, '__dict__'):
            final_state_dict = final_state.__dict__
        else:
            final_state_dict = final_state.model_dump()
        
        assert final_state_dict.get('classification') == "no"
        assert 'value' in final_state_dict
        assert final_state_dict.get('value') == "no_turnip"

@pytest.mark.asyncio
async def test_classifier_message_handling_between_nodes(turnip_classifier_config):
    mock_model = AsyncMock()
    # First node responses
    first_responses = [
        AIMessage(content="yes")
    ]
    # Second node should get fresh messages, not reuse first node's
    second_responses = [
        AIMessage(content="This is a fresh response")
    ]
    mock_model.ainvoke = AsyncMock(side_effect=first_responses + second_responses)
    
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', 
               return_value=mock_model):
        # Create two classifiers to simulate two nodes
        first_classifier = Classifier(**turnip_classifier_config)
        first_classifier.model = mock_model
        
        second_config = turnip_classifier_config.copy()
        second_config['name'] = 'second_classifier'
        second_config['system_message'] = "You are a different classifier."  # Different message
        second_config['user_message'] = "Classify this: {text}"  # Different message
        second_classifier = Classifier(**second_config)
        second_classifier.model = mock_model
        
        # Initial state
        state = first_classifier.GraphState(
            text="Test message",
            metadata={},
            results={},
            retry_count=0,
            is_not_empty=True,
            value=None,
            reasoning=None,
            classification=None,
            chat_history=[],
            completion=None,
            messages=None  # Explicitly start with no messages
        )
        
        # Run through first classifier's nodes
        first_llm_prompt = first_classifier.get_llm_prompt_node()
        first_llm_call = first_classifier.get_llm_call_node()
        first_parse = first_classifier.get_parser_node()
        
        state = await first_llm_prompt(state)
        state = await first_llm_call(state)
        state = await first_parse(state)
        
        # Store first node's message count for comparison
        first_node_message_count = len(state.messages) if state.messages else 0
        first_messages = state.messages.copy() if state.messages else []
        
        # Now run through second classifier's nodes
        second_llm_prompt = second_classifier.get_llm_prompt_node()
        second_llm_call = second_classifier.get_llm_call_node()
        second_parse = second_classifier.get_parser_node()
        
        state = await second_llm_prompt(state)
        
        # Verify that the second node built its own messages and didn't reuse first node's
        assert len(state.messages) <= first_node_message_count, \
            "Second node should not accumulate messages from first node"
        
        # Verify messages are different from first node
        assert state.messages != first_messages, \
            "Second node should have different messages than first node"
        
        # Complete second node execution
        state = await second_llm_call(state)
        final_state = await second_parse(state)
        
        # Verify the LLM was called with different messages each time
        all_calls = mock_model.ainvoke.call_args_list
        assert len(all_calls) == 2, "Expected exactly two LLM calls"
        
        first_call_messages = all_calls[0][0][0]
        second_call_messages = all_calls[1][0][0]
        assert first_call_messages != second_call_messages, \
            "Each node should use its own distinct messages"

@pytest.mark.asyncio
async def test_multi_node_condition_routing():
    """Test routing between multiple nodes where middle node has conditions."""
    # Mock the LLM responses for each node
    mock_model = AsyncMock()
    mock_responses = [
        # First test case responses
        AIMessage(content="Yes"),  # First node
        AIMessage(content="No"),   # Second node (routes to END)
        
        # Second test case responses
        AIMessage(content="Yes"),  # First node
        AIMessage(content="Yes"),  # Second node (continues to third)
        AIMessage(content="No")    # Third node
    ]
    mock_model.ainvoke = AsyncMock(side_effect=mock_responses)
    
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', 
               return_value=mock_model):
        # Create three classifiers to simulate three nodes
        first_config = {
            "name": "first_node",
            "valid_classes": ["Yes", "No"],
            "system_message": "You are the first classifier.",
            "user_message": "First classification: {text}",
            "model_provider": "AzureChatOpenAI",
            "model_name": "gpt-4"
        }
        
        second_config = {
            "name": "second_node",
            "valid_classes": ["Yes", "No"],
            "system_message": "You are the second classifier.",
            "user_message": "Second classification: {text}",
            "model_provider": "AzureChatOpenAI",
            "model_name": "gpt-4",
            "conditions": [
                {
                    "value": "No",
                    "node": "END",
                    "output": {
                        "value": "No",
                        "explanation": "No turnip was found in the text."
                    }
                }
            ]
        }
        
        third_config = {
            "name": "third_node",
            "valid_classes": ["Yes", "No"],
            "system_message": "You are the third classifier.",
            "user_message": "Third classification: {text}",
            "model_provider": "AzureChatOpenAI",
            "model_name": "gpt-4"
        }
        
        first_classifier = Classifier(**first_config)
        second_classifier = Classifier(**second_config)
        third_classifier = Classifier(**third_config)
        
        # Set up mock model for all classifiers
        first_classifier.model = mock_model
        second_classifier.model = mock_model
        third_classifier.model = mock_model
        
        # Initial state
        initial_state = first_classifier.GraphState(
            text="Test message",
            metadata={},
            results={},
            retry_count=0,
            is_not_empty=True,
            value=None,
            reasoning=None,
            classification=None,
            chat_history=[],
            completion=None,
            messages=None
        )
        
        # Test case 1: Second node returns "No" - should route to END
        # Create workflow
        workflow = StateGraph(first_classifier.GraphState)
        
        # Add nodes for each classifier
        workflow.add_node("first_llm_prompt", first_classifier.get_llm_prompt_node())
        workflow.add_node("first_llm_call", first_classifier.get_llm_call_node())
        workflow.add_node("first_parse", first_classifier.get_parser_node())
        
        workflow.add_node("second_llm_prompt", second_classifier.get_llm_prompt_node())
        workflow.add_node("second_llm_call", second_classifier.get_llm_call_node())
        workflow.add_node("second_parse", second_classifier.get_parser_node())
        
        workflow.add_node("third_llm_prompt", third_classifier.get_llm_prompt_node())
        workflow.add_node("third_llm_call", third_classifier.get_llm_call_node())
        workflow.add_node("third_parse", third_classifier.get_parser_node())
        
        # Add value setter node for the "No" condition
        workflow.add_node("set_no_value", 
            LangGraphScore.create_value_setter_node({
                "value": "No",
                "explanation": "No turnip was found in the text."
            })
        )
        
        # Add edges between nodes
        workflow.add_edge("first_llm_prompt", "first_llm_call")
        workflow.add_edge("first_llm_call", "first_parse")
        workflow.add_edge("first_parse", "second_llm_prompt")
        workflow.add_edge("second_llm_prompt", "second_llm_call")
        workflow.add_edge("second_llm_call", "second_parse")
        
        # Add conditional routing from second parse
        def route_from_second_parse(state):
            if getattr(state, 'classification') == "No":
                return "set_no_value"
            return "third_llm_prompt"
            
        workflow.add_conditional_edges(
            "second_parse",
            route_from_second_parse,
            {
                "set_no_value": "set_no_value",
                "third_llm_prompt": "third_llm_prompt"
            }
        )
        
        # Add remaining edges
        workflow.add_edge("set_no_value", END)
        workflow.add_edge("third_llm_prompt", "third_llm_call")
        workflow.add_edge("third_llm_call", "third_parse")
        workflow.add_edge("third_parse", END)
        
        # Set entry point
        workflow.set_entry_point("first_llm_prompt")
        
        # Compile workflow
        workflow = workflow.compile()
        
        # Run workflow with "No" response
        final_state = await workflow.ainvoke(initial_state)
        
        # Get final state as dict, prioritizing direct dict access to preserve all fields
        if isinstance(final_state, dict):
            final_state_dict = final_state
        elif hasattr(final_state, '__dict__'):
            final_state_dict = final_state.__dict__
        else:
            final_state_dict = final_state.model_dump()
        
        # Verify that workflow ended after second node with correct output
        assert 'value' in final_state_dict
        assert 'explanation' in final_state_dict
        assert final_state_dict['value'] == "No"
        assert final_state_dict['explanation'] == "No turnip was found in the text."
        assert final_state_dict['classification'] == "No"  # From second node
        assert 'third_node_result' not in final_state_dict  # Verify third node wasn't reached
        
        # Reset initial state for second test
        initial_state = first_classifier.GraphState(
            text="Test message",
            metadata={},
            results={},
            retry_count=0,
            is_not_empty=True,
            value=None,
            reasoning=None,
            classification=None,
            chat_history=[],
            completion=None,
            messages=None
        )
        
        # Run workflow again - this time second node returns "Yes"
        final_state = await workflow.ainvoke(initial_state)
        
        # Get final state as dict again
        if isinstance(final_state, dict):
            final_state_dict = final_state
        elif hasattr(final_state, '__dict__'):
            final_state_dict = final_state.__dict__
        else:
            final_state_dict = final_state.model_dump()
        
        # Verify workflow continued to third node
        assert final_state_dict['classification'] == "No"  # From third node
        # Check that the "No" condition output wasn't set
        assert 'value' not in final_state_dict  # Value setter node wasn't triggered
        assert final_state_dict['explanation'] == "No"  # This comes from the parser, not the value setter