#!/usr/bin/env python3
"""
Simple confidence test to debug the prompt formatting and confidence calculation.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Load Plexus configuration to get API keys
from plexus.config.loader import load_config
load_config()

import asyncio
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from plexus.scores.nodes.Classifier import Classifier

async def test_simple_confidence():
    logger.info("=== Simple Confidence Test ===")

    if not os.getenv('OPENAI_API_KEY'):
        logger.error("OPENAI_API_KEY not available")
        return

    # Create a simple binary classifier config - let's try a different approach
    config = {
        "name": "simple_confidence_test",
        "valid_classes": ["yes", "no"],
        "system_message": "You are a sentiment classifier. You must answer only 'yes' or 'no'. Answer 'yes' if the text has positive sentiment, 'no' if it has negative or neutral sentiment.",
        "user_message": "Is this text positive sentiment? Text: {text}",
        "model_provider": "ChatOpenAI",
        "model_name": "gpt-4.1-mini",
        "temperature": 0.7,
        "enable_confidence": True
    }

    classifier = Classifier(**config)

    # Override the model configuration to get MORE token alternatives
    if classifier._is_openai_model():
        logger.info("Overriding model to get maximum token alternatives (20)")
        classifier.model = classifier.model.bind(logprobs=True, top_logprobs=20)

    # Test with truly ambiguous mixed sentiment
    test_text = "It's pretty good in some ways but disappointing in others."

    logger.info(f"Testing with text: '{test_text}'")

    # Create initial state
    state = classifier.GraphState(
        text=test_text,
        metadata={},
        results={},
        retry_count=0,
        is_not_empty=True,
        value=None,
        reasoning=None,
        classification=None,
        chat_history=[],
        completion=None,
        confidence=None,
        raw_logprobs=None
    )

    try:
        # Step 1: Prepare prompt (manually since template substitution isn't working)
        logger.info("Step 1: Preparing LLM prompt manually")

        # Create the messages manually with proper text substitution
        manual_messages = [
            {
                'type': 'system',
                'content': 'You are a sentiment classifier. You must answer only \'yes\' or \'no\'. Answer \'yes\' if the text has positive sentiment, \'no\' if it has negative or neutral sentiment.',
                '_type': 'SystemMessage'
            },
            {
                'type': 'human',
                'content': f'Is this text positive sentiment? Text: {test_text}',
                '_type': 'HumanMessage'
            }
        ]

        state.messages = manual_messages

        # Debug: Check what's in the state
        logger.info(f"State content:")
        logger.info(f"  text: '{state.text}'")
        logger.info(f"  All state fields: {list(state.model_dump().keys())}")

        # Check if the prompt was formatted correctly
        if state.messages:
            logger.info("Messages prepared:")
            for i, msg in enumerate(state.messages):
                if isinstance(msg, dict):
                    logger.info(f"  Message {i}: {msg['type']} - '{msg['content']}'")
                else:
                    logger.info(f"  Message {i}: {type(msg).__name__} - '{msg.content}'")
        else:
            logger.error("No messages were prepared!")

        # Step 2: Make LLM call
        logger.info("Step 2: Making LLM call")

        # LOG THE EXACT MESSAGES BEING SENT TO OPENAI
        logger.info(f"\n🔍 EXACT MESSAGES SENT TO OPENAI:")
        if state.messages:
            for i, msg in enumerate(state.messages):
                if isinstance(msg, dict):
                    logger.info(f"   Message {i}: {msg['type']}")
                    logger.info(f"     Content: '{msg['content']}'")
                    logger.info(f"     Type field: '{msg.get('_type', 'N/A')}'")
                else:
                    logger.info(f"   Message {i}: {type(msg).__name__}")
                    logger.info(f"     Content: '{msg.content}'")

        llm_call_node = classifier.get_llm_call_node()
        state = await llm_call_node(state)

        logger.info(f"LLM response: '{state.completion}'")
        logger.info(f"Raw logprobs available: {state.raw_logprobs is not None}")

        if state.raw_logprobs:
            # DETAILED RAW LOGPROBS INSPECTION
            logger.info(f"\n🔍 RAW LOGPROBS STRUCTURE INSPECTION:")
            logger.info(f"   Raw logprobs type: {type(state.raw_logprobs)}")
            logger.info(f"   Raw logprobs keys: {list(state.raw_logprobs.keys()) if isinstance(state.raw_logprobs, dict) else 'Not a dict'}")

            if isinstance(state.raw_logprobs, dict) and 'content' in state.raw_logprobs:
                content = state.raw_logprobs['content']
                logger.info(f"   Content type: {type(content)}")
                logger.info(f"   Content length: {len(content) if content else 0}")

                if content and len(content) > 0:
                    logger.info(f"   First token data:")
                    first_token = content[0]
                    logger.info(f"     Keys: {list(first_token.keys()) if isinstance(first_token, dict) else 'Not a dict'}")
                    logger.info(f"     Token: {first_token.get('token', 'N/A')}")
                    logger.info(f"     Logprob: {first_token.get('logprob', 'N/A')}")
                    logger.info(f"     Bytes: {first_token.get('bytes', 'N/A')}")

                    top_logprobs = first_token.get('top_logprobs', [])
                    logger.info(f"     top_logprobs type: {type(top_logprobs)}")
                    logger.info(f"     top_logprobs length: {len(top_logprobs) if top_logprobs else 0}")

                    if top_logprobs:
                        logger.info(f"     First alternative:")
                        first_alt = top_logprobs[0]
                        logger.info(f"       Keys: {list(first_alt.keys()) if isinstance(first_alt, dict) else 'Not a dict'}")
                        logger.info(f"       Token: {first_alt.get('token', 'N/A')}")
                        logger.info(f"       Logprob: {first_alt.get('logprob', 'N/A')}")
            else:
                logger.error("   ❌ No 'content' key in raw_logprobs or content is None")
                logger.info(f"   Full raw_logprobs: {state.raw_logprobs}")

        if state.raw_logprobs:
            # Show detailed logprobs analysis
            content = state.raw_logprobs.get('content', [])
            if content and len(content) > 0:
                first_token = content[0]
                top_logprobs = first_token.get('top_logprobs', [])
                logger.info(f"\n🔍 COMPLETE TOKEN ANALYSIS ({len(top_logprobs)} alternatives):")

                # Group tokens by classification match
                yes_variants = []
                no_variants = []
                other_tokens = []
                total_prob_check = 0.0

                for i, logprob_entry in enumerate(top_logprobs):
                    token = logprob_entry.get('token', '')
                    logprob = logprob_entry.get('logprob', 0)
                    prob = round(2.71828 ** logprob, 6)  # More precision
                    total_prob_check += prob

                    logger.info(f"  {i+1:2d}. '{token}' -> probability: {prob:.6f} (logprob: {logprob:.4f})")

                    # Check which category this token belongs to
                    normalized_token = token.lower().strip()
                    if 'yes' in normalized_token or normalized_token in ['y', 'yeah', 'yep', 'yup']:
                        yes_variants.append((token, prob))
                    elif 'no' in normalized_token or normalized_token in ['n', 'nope', 'nah']:
                        no_variants.append((token, prob))
                    else:
                        other_tokens.append((token, prob))

                logger.info(f"\n📊 PROBABILITY DISTRIBUTION ANALYSIS:")
                logger.info(f"   Total probability mass: {total_prob_check:.6f}")

                if yes_variants:
                    yes_total = sum(prob for _, prob in yes_variants)
                    logger.info(f"\n   ✅ 'YES' VARIANTS ({len(yes_variants)} tokens, {yes_total:.6f} total probability):")
                    for token, prob in yes_variants:
                        pct = (prob/yes_total*100) if yes_total > 0 else 0
                        logger.info(f"      '{token}': {prob:.6f} ({pct:.2f}% of yes votes)")

                if no_variants:
                    no_total = sum(prob for _, prob in no_variants)
                    logger.info(f"\n   ❌ 'NO' VARIANTS ({len(no_variants)} tokens, {no_total:.6f} total probability):")
                    for token, prob in no_variants:
                        pct = (prob/no_total*100) if no_total > 0 else 0
                        logger.info(f"      '{token}': {prob:.6f} ({pct:.2f}% of no votes)")
                else:
                    logger.info(f"\n   ❌ 'NO' VARIANTS: None found! (0.000000 total probability)")

                if other_tokens:
                    other_total = sum(prob for _, prob in other_tokens)
                    logger.info(f"\n   🤔 OTHER TOKENS ({len(other_tokens)} tokens, {other_total:.6f} total probability):")
                    for token, prob in other_tokens[:10]:  # Show top 10 other tokens
                        logger.info(f"      '{token}': {prob:.6f}")
                    if len(other_tokens) > 10:
                        logger.info(f"      ... and {len(other_tokens) - 10} more other tokens")

                # Summary percentages
                yes_pct = (sum(prob for _, prob in yes_variants) / total_prob_check * 100) if total_prob_check > 0 else 0
                no_pct = (sum(prob for _, prob in no_variants) / total_prob_check * 100) if total_prob_check > 0 else 0
                other_pct = (sum(prob for _, prob in other_tokens) / total_prob_check * 100) if total_prob_check > 0 else 0

                logger.info(f"\n🎯 CLASSIFICATION BREAKDOWN:")
                logger.info(f"   YES variants: {yes_pct:.2f}% of probability mass")
                logger.info(f"   NO variants:  {no_pct:.2f}% of probability mass")
                logger.info(f"   Other tokens: {other_pct:.2f}% of probability mass")

        # Step 3: Parse response
        logger.info("Step 3: Parsing response")
        parse_node = classifier.get_parser_node()
        state = await parse_node(state)

        logger.info(f"Parsed classification: '{state.classification}'")
        logger.info(f"Parsed explanation: '{state.explanation}'")

        # Step 4: Calculate confidence (if classification is valid)
        if state.classification and state.classification in classifier.parameters.valid_classes:
            logger.info("Step 4: Calculating confidence")
            confidence_node = classifier.get_confidence_node()
            state = await confidence_node(state)

            if isinstance(state, dict):
                confidence = state.get('confidence')
            else:
                confidence = state.confidence
            logger.info(f"Final confidence: {confidence}")

            # Manual confidence calculation for verification
            raw_logprobs = state.get('raw_logprobs') if isinstance(state, dict) else state.raw_logprobs
            if raw_logprobs:
                logger.info("\n🧮 MANUAL CONFIDENCE CALCULATION:")
                content = raw_logprobs.get('content', [])
                if content and len(content) > 0:
                    first_token = content[0]
                    top_logprobs = first_token.get('top_logprobs', [])

                    parser = classifier.ClassificationOutputParser(
                        valid_classes=classifier.parameters.valid_classes,
                        parse_from_start=False
                    )

                    total_prob = 0.0
                    matches = []

                    for logprob_entry in top_logprobs:
                        token = logprob_entry.get('token', '')
                        logprob = logprob_entry.get('logprob', float('-inf'))
                        probability = 2.71828 ** logprob if logprob != float('-inf') else 0.0

                        normalized_token = parser.normalize_text(token)

                        for valid_class in classifier.parameters.valid_classes:
                            normalized_class = parser.normalize_text(valid_class)

                            if normalized_token == normalized_class:
                                total_prob += probability
                                matches.append((token, valid_class, probability))
                                logger.info(f"  ✓ '{token}' matches '{valid_class}' -> +{probability:.4f}")
                                break

                    logger.info(f"  Total probability: {total_prob:.4f}")
                    logger.info(f"  Clamped confidence: {min(1.0, max(0.0, total_prob)):.4f}")

                    if not matches:
                        logger.info("  ❌ No token matches found - confidence would be None")
        else:
            logger.info("Step 4: Skipped - invalid classification")

        logger.info("\n✅ Test completed successfully!")

        if isinstance(state, dict):
            return {
                'completion': state.get('completion'),
                'classification': state.get('classification'),
                'confidence': state.get('confidence'),
                'raw_logprobs': state.get('raw_logprobs')
            }
        else:
            return {
                'completion': state.completion,
                'classification': state.classification,
                'confidence': state.confidence,
                'raw_logprobs': state.raw_logprobs
            }

    except Exception as e:
        logger.error(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    result = asyncio.run(test_simple_confidence())
    if result:
        print(f"\n🎉 Final Result:")
        print(f"  Classification: {result['classification']}")
        print(f"  Confidence: {result['confidence']}")
        print(f"  Response: '{result['completion']}'")