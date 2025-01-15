import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from plexus.scores.nodes.Classifier import Classifier
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

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
async def test_classifier_detects_turnip_present(turnip_classifier_config):
    mock_model = AsyncMock()
    mock_response = AIMessage(content="yes")
    mock_model.ainvoke = AsyncMock(return_value=mock_response)
    
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', 
               return_value=mock_model):
        classifier = Classifier(**turnip_classifier_config)
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
            completion=None
        )
        
        llm_prompt_node = classifier.get_llm_prompt_node()
        llm_call_node = classifier.get_llm_call_node()
        parse_node = classifier.get_parser_node()
        
        # Run prompt node
        state_after_prompt = await llm_prompt_node(state)
        # Run LLM call node
        state_after_llm = await llm_call_node(state_after_prompt)
        # Run parser node
        final_state = await parse_node(state_after_llm)
        
        assert final_state.classification == "yes"

@pytest.mark.asyncio
async def test_classifier_detects_turnip_absent(turnip_classifier_config):
    mock_model = AsyncMock()
    mock_response = AIMessage(content="no")
    mock_model.ainvoke = AsyncMock(return_value=mock_response)
    
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', 
               return_value=mock_model):
        classifier = Classifier(**turnip_classifier_config)
        classifier.model = mock_model
        
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
        
        llm_prompt_node = classifier.get_llm_prompt_node()
        llm_call_node = classifier.get_llm_call_node()
        parse_node = classifier.get_parser_node()
        
        # Run prompt node
        state_after_prompt = await llm_prompt_node(state)
        # Run LLM call node
        state_after_llm = await llm_call_node(state_after_prompt)
        # Run parser node
        final_state = await parse_node(state_after_llm)
        
        assert final_state.classification == "no"

@pytest.mark.asyncio
async def test_classifier_succeeds_after_retry(turnip_classifier_config):
    mock_model = AsyncMock()
    responses = [
        AIMessage(content="Well, let me analyze this carefully..."),
        AIMessage(content="yes")
    ]
    mock_model.ainvoke = AsyncMock(side_effect=responses)
    
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', 
               return_value=mock_model):
        classifier = Classifier(**turnip_classifier_config)
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
            completion=None
        )
        
        llm_prompt_node = classifier.get_llm_prompt_node()
        llm_call_node = classifier.get_llm_call_node()
        parse_node = classifier.get_parser_node()
        retry_node = classifier.get_retry_node()
        
        # First attempt
        state_after_prompt = await llm_prompt_node(state)
        state_after_llm = await llm_call_node(state_after_prompt)
        state_after_parse = await parse_node(state_after_llm)
        
        # Should need retry
        assert state_after_parse.classification is None
        
        # Retry attempt - clear completion to force new LLM call
        state_after_retry = await retry_node(state_after_parse)
        
        # Verify retry message was added to chat history
        assert len(state_after_retry.chat_history) > 0
        messages = state_after_retry.chat_history
        
        # Verify original completion is in chat history
        assert any(
            msg['type'] == 'ai' and 
            msg['content'] == "Well, let me analyze this carefully..."
            for msg in messages
        )
        
        # Verify retry message is in chat history
        retry_message = messages[-1]
        assert retry_message['type'] == 'human'
        assert "You responded with an invalid classification" in retry_message['content']
        assert "Please classify as one of: 'yes', 'no'" in retry_message['content']
        
        state_after_retry = classifier.GraphState(
            **{k: v for k, v in state_after_retry.model_dump().items() if k != 'completion'},
            completion=None
        )
        state_after_prompt2 = await llm_prompt_node(state_after_retry)
        
        # Verify both the original completion and retry message are included in messages sent to LLM
        assert len(state_after_prompt2.messages) > 0
        assert any(
            msg['type'] == 'ai' and 
            msg['content'] == "Well, let me analyze this carefully..."
            for msg in state_after_prompt2.messages
        )
        assert any(
            msg['type'] == 'human' and
            "You responded with an invalid classification" in msg['content']
            for msg in state_after_prompt2.messages
        )
        
        state_after_llm2 = await llm_call_node(state_after_prompt2)
        final_state = await parse_node(state_after_llm2)
        
        assert final_state.classification == "yes"
        assert final_state.retry_count == 1
        
        # Verify the LLM was called with the complete message history
        all_llm_calls = mock_model.ainvoke.call_args_list
        assert len(all_llm_calls) == 2  # First attempt and retry
        retry_call_messages = all_llm_calls[1][0][0]  # Second call's messages
        
        # Find system message (should be first)
        assert isinstance(retry_call_messages[0], SystemMessage)
        assert "You are a classifier that detects if the word 'turnip' appears in text" in retry_call_messages[0].content
        
        # Find user message (should be second)
        assert isinstance(retry_call_messages[1], HumanMessage)
        assert "Does this text contain the word 'turnip'" in retry_call_messages[1].content
        
        # Find original completion
        assert any(
            isinstance(msg, AIMessage) and 
            msg.content == "Well, let me analyze this carefully..."
            for msg in retry_call_messages
        )
        
        # Find retry message (should be last)
        assert isinstance(retry_call_messages[-1], HumanMessage)
        assert "You responded with an invalid classification" in retry_call_messages[-1].content

@pytest.mark.asyncio
async def test_classifier_maximum_retries(turnip_classifier_config):
    mock_model = AsyncMock()
    responses = [
        AIMessage(content="Let me think about it..."),
        AIMessage(content="I need to analyze this further..."),
        AIMessage(content="Well, considering the text...")
    ]
    mock_model.ainvoke = AsyncMock(side_effect=responses)
    
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', 
               return_value=mock_model):
        classifier = Classifier(**turnip_classifier_config)
        classifier.model = mock_model
        classifier.parameters.maximum_retry_count = 3
        
        initial_state = classifier.GraphState(
            text="I love eating turnip soup.",
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
        
        llm_prompt_node = classifier.get_llm_prompt_node()
        llm_call_node = classifier.get_llm_call_node()
        parse_node = classifier.get_parser_node()
        retry_node = classifier.get_retry_node()
        max_retries_node = classifier.get_max_retries_node()
        
        current_state = initial_state
        for _ in range(3):
            # Clear chat history and completion before each attempt
            current_state = classifier.GraphState(
                **{k: v for k, v in current_state.model_dump().items() 
                   if k not in ['chat_history', 'completion']},
                chat_history=[],
                completion=None
            )
            
            current_state = await llm_prompt_node(current_state)
            current_state = await llm_call_node(current_state)
            current_state = await parse_node(current_state)
            if current_state.classification is None:
                current_state = await retry_node(current_state)
        
        final_state = await max_retries_node(current_state)
        
        assert final_state.classification == "unknown"
        assert final_state.explanation == "Maximum retries reached"
        assert final_state.retry_count == 3
        assert mock_model.ainvoke.call_count == 3

@pytest.mark.asyncio
async def test_classifier_parse_from_end_default(turnip_classifier_config):
    mock_model = AsyncMock()
    mock_response = AIMessage(
        content="Yes I see it here, but no is my final answer"
    )
    mock_model.ainvoke = AsyncMock(return_value=mock_response)
    
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', 
               return_value=mock_model):
        classifier = Classifier(**turnip_classifier_config)
        classifier.model = mock_model

        state = classifier.GraphState(
            text="Does this contain a turnip?",
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

        llm_prompt_node = classifier.get_llm_prompt_node()
        llm_call_node = classifier.get_llm_call_node()
        parse_node = classifier.get_parser_node()

        state_after_prompt = await llm_prompt_node(state)
        state_after_llm = await llm_call_node(state_after_prompt)
        final_state = await parse_node(state_after_llm)

        assert final_state.classification == "no"
        # Ensures that when parse_from_start=False, it picks 'no'

@pytest.mark.asyncio
async def test_classifier_parse_from_start_explicit(turnip_classifier_config):
    mock_model = AsyncMock()
    mock_response = AIMessage(
        content="Yes is my answer, even though you might think no when you first look"
    )
    mock_model.ainvoke = AsyncMock(return_value=mock_response)

    with patch('plexus.LangChainUser.LangChainUser._initialize_model',
               return_value=mock_model):
        # Explicitly set parse_from_start to True
        turnip_classifier_config["parse_from_start"] = True
        classifier = Classifier(**turnip_classifier_config)
        classifier.model = mock_model

        state = classifier.GraphState(
            text="Does this contain a turnip?",
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

        llm_prompt_node = classifier.get_llm_prompt_node()
        llm_call_node = classifier.get_llm_call_node()
        parse_node = classifier.get_parser_node()

        state_after_prompt = await llm_prompt_node(state)
        state_after_llm = await llm_call_node(state_after_prompt)
        final_state = await parse_node(state_after_llm)

        assert final_state.classification == "yes"
        # Ensures that when parse_from_start=True, it picks 'yes'

@pytest.mark.asyncio
async def test_classifier_handles_yes_no_na(empathy_classifier_config):
    mock_model = AsyncMock()
    responses = [
        AIMessage(content="Yes, the agent showed clear empathy"),
        AIMessage(content="No empathy was shown in this interaction"),
        AIMessage(content="This was a routine inquiry, so NA")
    ]
    mock_model.ainvoke = AsyncMock(side_effect=responses)
    
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', 
               return_value=mock_model):
        classifier = Classifier(**empathy_classifier_config)
        classifier.model = mock_model
        
        test_cases = [
            ("Agent: I'm so sorry to hear about your problem.", "Yes"),
            ("Agent: Your account number is 12345.", "No"),
            ("Agent: Let me check the price for you.", "NA")
        ]
        
        for text, expected in test_cases:
            state = classifier.GraphState(
                text=text,
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
            
            # Run through nodes
            state = await classifier.get_llm_prompt_node()(state)
            state = await classifier.get_llm_call_node()(state)
            final_state = await classifier.get_parser_node()(state)
            
            assert final_state.classification == expected

@pytest.mark.asyncio
async def test_classifier_handles_multi_word_classes(call_outcome_classifier_config):
    mock_model = AsyncMock()
    responses = [
        AIMessage(content="The agent Successfully Resolved Issue by fixing the customer's login problem"),
        AIMessage(content="Due to complexity, this was Escalated to Supervisor"),
        AIMessage(content="The call ended with Technical Difficulties when the line dropped"),
        AIMessage(content="Customer Declined Solution offered by the agent"),
        AIMessage(content="Agent scheduled Follow Up Required in two days")
    ]
    mock_model.ainvoke = AsyncMock(side_effect=responses)
    
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', 
               return_value=mock_model):
        classifier = Classifier(**call_outcome_classifier_config)
        classifier.model = mock_model
        
        test_cases = [
            ("Agent fixed the login issue", "Successfully Resolved Issue"),
            ("Had to transfer to tier 2 support", "Escalated to Supervisor"),
            ("Call dropped unexpectedly", "Technical Difficulties"),
            ("Customer said no to the offer", "Customer Declined Solution"),
            ("Will call back next week", "Follow Up Required")
        ]
        
        for text, expected in test_cases:
            state = classifier.GraphState(
                text=text,
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
            
            # Run through nodes
            state = await classifier.get_llm_prompt_node()(state)
            state = await classifier.get_llm_call_node()(state)
            final_state = await classifier.get_parser_node()(state)
            
            assert final_state.classification == expected

@pytest.mark.asyncio
async def test_classifier_handles_multi_word_retry(call_outcome_classifier_config):
    mock_model = AsyncMock()
    responses = [
        AIMessage(content="The call ended without resolution"),  # Invalid response
        AIMessage(content="Technical Difficulties occurred")     # Valid response
    ]
    mock_model.ainvoke = AsyncMock(side_effect=responses)
    
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', 
               return_value=mock_model):
        classifier = Classifier(**call_outcome_classifier_config)
        classifier.model = mock_model
        
        state = classifier.GraphState(
            text="The call dropped mid-conversation",
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
        
        # First attempt - should fail
        state = await classifier.get_llm_prompt_node()(state)
        state = await classifier.get_llm_call_node()(state)
        state = await classifier.get_parser_node()(state)
        assert state.classification is None
        
        # Retry
        state = await classifier.get_retry_node()(state)
        state = classifier.GraphState(
            **{k: v for k, v in state.model_dump().items() if k != 'completion'},
            completion=None
        )
        state = await classifier.get_llm_prompt_node()(state)
        state = await classifier.get_llm_call_node()(state)
        final_state = await classifier.get_parser_node()(state)
        
        assert final_state.classification == "Technical Difficulties"
        assert final_state.retry_count == 1

@pytest.mark.asyncio
async def test_classifier_handles_explanatory_text(empathy_classifier_config):
    mock_model = AsyncMock()
    mock_response = AIMessage(content=(
        "The agent uses empathy statements such as 'Oh, I'm sorry. You're dealing with that.' "
        "and 'Again, I'm so sorry that you're doing dealing with that.' to acknowledge the "
        "caller's issue with the clogged kitchen drain.\n"
        "Therefore, the agent does use an empathy statement to acknowledge the caller's issue.\n"
        "YES"
    ))
    mock_model.ainvoke = AsyncMock(return_value=mock_response)
    
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', 
               return_value=mock_model):
        classifier = Classifier(**empathy_classifier_config)
        classifier.model = mock_model
        
        state = classifier.GraphState(
            text="Agent: Oh, I'm sorry you're dealing with that clogged drain.",
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
        
        # Run through nodes
        state = await classifier.get_llm_prompt_node()(state)
        state = await classifier.get_llm_call_node()(state)
        final_state = await classifier.get_parser_node()(state)
        
        assert final_state.classification == "Yes"

@pytest.mark.asyncio
async def test_classifier_parser_edge_cases():
    """Test various edge cases in the ClassificationOutputParser."""
    parser = Classifier.ClassificationOutputParser(
        valid_classes=["yes", "no", "not now", "SUCCESS", "in_progress"]
    )
    
    # Case sensitivity tests
    assert parser.parse("YES").get("classification") == "yes"
    assert parser.parse("No").get("classification") == "no"
    assert parser.parse("SUCCESS").get("classification") == "SUCCESS"
    
    # Whitespace handling
    assert parser.parse("   yes   ").get("classification") == "yes"
    assert parser.parse("in   progress").get("classification") == "in_progress"
    assert parser.parse("\nyes\n").get("classification") == "yes"
    
    # Special character handling
    assert parser.parse("(yes!)").get("classification") == "yes"
    assert parser.parse("Result: no.").get("classification") == "no"
    assert parser.parse("Status: in_progress...").get("classification") == "in_progress"
    
    # Order-dependent cases with parse_from_start=False (default)
    assert parser.parse("yes, but actually no").get("classification") == "no"
    assert parser.parse("no... not now").get("classification") == "not now"
    assert parser.parse("yes\nmaybe\nno\nyes").get("classification") == "yes"
    
    # Order-dependent cases with parse_from_start=True
    parser_forward = Classifier.ClassificationOutputParser(
        valid_classes=["yes", "no", "not now"],
        parse_from_start=True
    )
    assert parser_forward.parse("yes, but actually no").get("classification") == "yes"
    assert parser_forward.parse("no... not now").get("classification") == "no"
    assert parser_forward.parse("yes\nmaybe\nno\nyes").get("classification") == "yes"
    
    # Overlapping terms tests
    parser_overlapping = Classifier.ClassificationOutputParser(
        valid_classes=["no", "not now", "not available"]
    )
    assert parser_overlapping.parse("The answer is not now").get("classification") == "not now"
    
    # None cases
    assert parser.parse("maybe").get("classification") is None
    assert parser.parse("").get("classification") is None
    assert parser.parse("   ").get("classification") is None

@pytest.mark.asyncio
async def test_classifier_parser_multiline_response():
    """Test parsing of complex multiline responses with reasoning."""
    parser = Classifier.ClassificationOutputParser(
        valid_classes=["yes", "no"],
        parse_from_start=False
    )
    
    complex_response = """
    Let me analyze this carefully:
    1. First point suggests yes
    2. Second point suggests no
    3. Additional evidence points to yes
    
    However, considering all factors:
    no is my final answer.
    """
    
    result = parser.parse(complex_response)
    assert result["classification"] == "no"
    assert result["explanation"] == complex_response.strip()
    
    # Test with parse_from_start=True
    parser_forward = Classifier.ClassificationOutputParser(
        valid_classes=["yes", "no"],
        parse_from_start=True
    )
    result_forward = parser_forward.parse(complex_response)
    assert result_forward["classification"] == "yes"
    assert result_forward["explanation"] == complex_response.strip()

@pytest.mark.asyncio
async def test_classifier_parser_valid_classes_order():
    """Test that the order of valid_classes affects matching priority."""
    # When parsing from end, longer matches should take precedence
    parser = Classifier.ClassificationOutputParser(
        valid_classes=["no", "not now", "not available"],
        parse_from_start=False
    )
    
    text = "The status is not now, but also not available"
    assert parser.parse(text).get("classification") == "not available"
    
    # When parsing from start, first match in valid_classes should win
    parser_forward = Classifier.ClassificationOutputParser(
        valid_classes=["no", "not now", "not available"],
        parse_from_start=True
    )
    assert parser_forward.parse(text).get("classification") == "not now"
    
    # Test with reordered valid_classes
    parser_reordered = Classifier.ClassificationOutputParser(
        valid_classes=["not available", "not now", "no"],
        parse_from_start=True
    )
    assert parser_reordered.parse(text).get("classification") == "not available"

@pytest.mark.asyncio
async def test_classifier_parser_empty_valid_classes():
    """Test that empty valid_classes defaults to ["Yes", "No"]."""
    parser = Classifier.ClassificationOutputParser(valid_classes=[])
    
    # Verify default classes are set
    assert parser.valid_classes == ["Yes", "No"]
    
    # Test parsing with default classes
    assert parser.parse("Yes, that's correct").get("classification") == "Yes"
    assert parser.parse("No, that's not right").get("classification") == "No"
    assert parser.parse("YES definitely").get("classification") == "Yes"
    assert parser.parse("Absolutely NO").get("classification") == "No"
    
    # Test parse_from_start behavior
    parser_forward = Classifier.ClassificationOutputParser(
        valid_classes=[],
        parse_from_start=True
    )
    # Since Yes comes before No in default classes, it should be found first
    assert parser_forward.parse("Yes, but actually no").get("classification") == "Yes"
    assert parser_forward.parse("No, but actually yes").get("classification") == "Yes"
    
    # Test parse from end behavior
    parser_backward = Classifier.ClassificationOutputParser(
        valid_classes=[],
        parse_from_start=False
    )
    assert parser_backward.parse("Yes, but actually no").get("classification") == "No"
    assert parser_backward.parse("No, but actually yes").get("classification") == "Yes"
    
    # Test with complex reasoning
    complex_response = """
    Let me think about this:
    1. Initially it seems like Yes
    2. But on further consideration
    3. Actually No is more accurate
    
    Final answer: No
    """
    assert parser_backward.parse(complex_response).get("classification") == "No"
    assert parser_forward.parse(complex_response).get("classification") == "Yes"

@pytest.mark.asyncio
async def test_classifier_message_sequence_two_retries(turnip_classifier_config):
    mock_model = AsyncMock()
    responses = [
        AIMessage(content="Let me think about it..."),  # First invalid response
        AIMessage(content="I need more time..."),       # Second invalid response
        AIMessage(content="yes")                        # Final valid response
    ]
    mock_model.ainvoke = AsyncMock(side_effect=responses)
    
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', 
               return_value=mock_model):
        classifier = Classifier(**turnip_classifier_config)
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
            completion=None
        )
        
        llm_prompt_node = classifier.get_llm_prompt_node()
        llm_call_node = classifier.get_llm_call_node()
        parse_node = classifier.get_parser_node()
        retry_node = classifier.get_retry_node()
        
        # First attempt
        state = await llm_prompt_node(state)
        state = await llm_call_node(state)
        state = await parse_node(state)
        assert state.classification is None
        
        # First retry
        state = await retry_node(state)
        state = await llm_prompt_node(state)
        state = await llm_call_node(state)
        state = await parse_node(state)
        assert state.classification is None
        
        # Second retry
        state = await retry_node(state)
        state = await llm_prompt_node(state)
        
        # Verify the complete message sequence from the state
        assert len(state.messages) == 6
        
        # Verify message types and content
        assert state.messages[0]['type'] == 'system'
        assert "classifier that detects if the word 'turnip' appears" in state.messages[0]['content']
        
        assert state.messages[1]['type'] == 'human'
        assert "Does this text contain the word 'turnip'" in state.messages[1]['content']
        
        assert state.messages[2]['type'] == 'ai'
        assert "Let me think about it..." == state.messages[2]['content']
        
        assert state.messages[3]['type'] == 'human'
        assert "You responded with an invalid classification" in state.messages[3]['content']
        assert "attempt 1 of" in state.messages[3]['content']
        
        assert state.messages[4]['type'] == 'ai'
        assert "I need more time..." == state.messages[4]['content']
        
        assert state.messages[5]['type'] == 'human'
        assert "You responded with an invalid classification" in state.messages[5]['content']
        assert "attempt 2 of" in state.messages[5]['content']
        
        # Complete the sequence and verify final classification
        state = await llm_call_node(state)
        final_state = await parse_node(state)
        assert final_state.classification == "yes"
        assert final_state.retry_count == 2