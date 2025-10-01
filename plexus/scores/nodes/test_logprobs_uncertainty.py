#!/usr/bin/env python3
"""
Test multiple cases to see if logprobs EVER show meaningful uncertainty,
or if they always claim 100% confidence.
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from plexus.config.loader import load_config
load_config()

import asyncio
import logging
import os

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

from plexus.scores.nodes.Classifier import Classifier

async def test_multiple_cases_for_uncertainty():
    logger.info("=== Testing Multiple Cases for Uncertainty ===")

    if not os.getenv('OPENAI_API_KEY'):
        logger.error("OPENAI_API_KEY not available")
        return

    config = {
        "name": "uncertainty_test",
        "valid_classes": ["yes", "no"],
        "system_message": "You are a sentiment classifier. You must answer only 'yes' or 'no'. Answer 'yes' if the text has positive sentiment, 'no' if it has negative or neutral sentiment.",
        "user_message": "Is this text positive sentiment? Text: {text}",
        "model_provider": "ChatOpenAI",
        "model_name": "gpt-4.1-mini",
        "temperature": 0.7,
        "enable_confidence": True
    }

    classifier = Classifier(**config)

    # Override to get max alternatives
    if classifier._is_openai_model():
        classifier.model = classifier.model.bind(logprobs=True, top_logprobs=20)

    # Test cases designed to create maximum uncertainty
    test_cases = [
        "I absolutely love this!",  # Clear positive
        "I absolutely hate this!",  # Clear negative
        "It's okay I guess.",       # Neutral
        "It's fine.",               # Neutral
        "Not bad.",                 # Ambiguous
        "Could be worse.",          # Ambiguous
        "It's alright.",            # Neutral
        "Pretty decent.",           # Mildly positive
        "Somewhat disappointing.",  # Mildly negative
        "I have mixed feelings about this.", # Explicitly ambiguous
        "I don't know how I feel.", # Uncertainty
        "Maybe good, maybe bad.",   # Explicitly uncertain
    ]

    results = []

    for i, text in enumerate(test_cases):
        logger.info(f"\n{'='*60}")
        logger.info(f"TEST {i+1}: '{text}'")
        logger.info(f"{'='*60}")

        # Create manual messages
        manual_messages = [
            {
                'type': 'system',
                'content': 'You are a sentiment classifier. You must answer only \'yes\' or \'no\'. Answer \'yes\' if the text has positive sentiment, \'no\' if it has negative or neutral sentiment.',
                '_type': 'SystemMessage'
            },
            {
                'type': 'human',
                'content': f'Is this text positive sentiment? Text: {text}',
                '_type': 'HumanMessage'
            }
        ]

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
            completion=None,
            confidence=None,
            raw_logprobs=None,
            messages=manual_messages
        )

        try:
            # Run through nodes
            llm_call_node = classifier.get_llm_call_node()
            state = await llm_call_node(state)

            parse_node = classifier.get_parser_node()
            state = await parse_node(state)

            # Quick summary
            logger.info(f"Response: '{state.completion}'")
            logger.info(f"Classification: {state.classification}")

            if state.raw_logprobs:
                content = state.raw_logprobs.get('content', [])
                if content and len(content) > 0:
                    first_token = content[0]
                    top_logprobs = first_token.get('top_logprobs', [])

                    # Find yes and no probabilities
                    yes_prob = 0.0
                    no_prob = 0.0

                    for logprob_entry in top_logprobs:
                        token = logprob_entry.get('token', '').lower().strip()
                        prob = 2.71828 ** logprob_entry.get('logprob', float('-inf'))

                        if token == 'yes':
                            yes_prob = prob
                        elif token == 'no':
                            no_prob = prob

                    logger.info(f"YES probability: {yes_prob:.6f}")
                    logger.info(f"NO probability:  {no_prob:.6f}")

                    if yes_prob > 0 and no_prob > 0:
                        ratio = yes_prob / no_prob if no_prob > 0 else float('inf')
                        logger.info(f"YES/NO ratio: {ratio:.6f}")
                    else:
                        logger.info(f"YES/NO ratio: One side has 0 probability")

            # Calculate confidence if valid
            if state.classification and state.classification in classifier.parameters.valid_classes:
                confidence_node = classifier.get_confidence_node()
                state = await confidence_node(state)

                final_confidence = state.get('confidence') if isinstance(state, dict) else state.confidence
                logger.info(f"Final confidence: {final_confidence}")

                results.append({
                    'text': text,
                    'classification': state.get('classification') if isinstance(state, dict) else state.classification,
                    'confidence': final_confidence,
                    'yes_prob': yes_prob,
                    'no_prob': no_prob
                })
            else:
                logger.info("Invalid classification - no confidence calculated")

        except Exception as e:
            logger.error(f"Error: {e}")

    # Analysis
    logger.info(f"\n{'='*80}")
    logger.info("FINAL ANALYSIS - UNCERTAINTY DETECTION")
    logger.info(f"{'='*80}")

    for result in results:
        uncertainty = 1.0 - result['confidence'] if result['confidence'] else 1.0
        logger.info(f"'{result['text'][:30]}...' -> {result['classification']} (confidence: {result['confidence']:.4f}, uncertainty: {uncertainty:.4f})")

    # Check if ANY case showed meaningful uncertainty
    confident_results = [r for r in results if r['confidence'] and r['confidence'] > 0.95]
    uncertain_results = [r for r in results if r['confidence'] and r['confidence'] < 0.95]

    logger.info(f"\n📊 SUMMARY:")
    logger.info(f"Total tests: {len(results)}")
    logger.info(f"High confidence (>95%): {len(confident_results)}")
    logger.info(f"Showing uncertainty (<95%): {len(uncertain_results)}")

    if len(uncertain_results) == 0:
        logger.info("❌ LOGPROBS NEVER SHOW UNCERTAINTY - Feature may not be working properly")
    else:
        logger.info("✅ Found cases with uncertainty - Feature working correctly")

    return results

if __name__ == "__main__":
    asyncio.run(test_multiple_cases_for_uncertainty())