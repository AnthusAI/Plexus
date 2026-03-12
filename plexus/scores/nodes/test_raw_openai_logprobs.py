#!/usr/bin/env python3
"""
Direct OpenAI API test with logprobs - no Classifier, just raw LangChain calls
to see if the models are genuinely overconfident or if there's an issue in our setup.
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

import asyncio
import logging
import os
import math

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

async def test_raw_openai_logprobs():
    logger.info("=== Direct OpenAI Logprobs Test ===")

    if not os.getenv('OPENAI_API_KEY'):
        logger.error("OPENAI_API_KEY not available")
        return

    # Create OpenAI model with logprobs - same as Classifier does
    model = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.0
    )

    # Bind logprobs exactly like Classifier does
    model_with_logprobs = model.bind(logprobs=True, top_logprobs=20)

    logger.info(f"Model: {model.model_name}")
    logger.info(f"Temperature: {model.temperature}")
    logger.info(f"Logprobs enabled: True, top_logprobs: 20")

    # Test cases
    test_cases = [
        "I absolutely love this amazing product!",
        "This is terrible and awful!",
        "It's okay, I guess.",
        "Pretty decent but could be better.",
        "I love it and hate it equally.",
        "Maybe good, maybe bad, who knows?",
        "It's fine.",
        "Not sure how I feel about this.",
    ]

    system_msg = SystemMessage(content="You are a sentiment classifier. You must answer only 'yes' or 'no'. Answer 'yes' if the text has positive sentiment, 'no' if it has negative or neutral sentiment.")

    for i, text in enumerate(test_cases):
        logger.info(f"\n{'='*80}")
        logger.info(f"TEST {i+1}: '{text}'")
        logger.info(f"{'='*80}")

        human_msg = HumanMessage(content=f"Is this text positive sentiment? Text: {text}")
        messages = [system_msg, human_msg]

        try:
            # Make the API call
            response = await model_with_logprobs.ainvoke(messages)

            logger.info(f"Response: '{response.content}'")

            # Extract logprobs manually
            if hasattr(response, 'response_metadata') and 'logprobs' in response.response_metadata:
                logprobs = response.response_metadata['logprobs']

                if 'content' in logprobs and len(logprobs['content']) > 0:
                    first_token_data = logprobs['content'][0]
                    actual_token = first_token_data['token']
                    actual_logprob = first_token_data['logprob']
                    actual_prob = math.exp(actual_logprob)

                    logger.info(f"Actual token chosen: '{actual_token}' (logprob: {actual_logprob:.4f}, prob: {actual_prob:.6f})")

                    # Show all alternatives
                    top_logprobs = first_token_data.get('top_logprobs', [])
                    logger.info(f"\nAll {len(top_logprobs)} token alternatives:")

                    yes_variants = []
                    no_variants = []
                    other_tokens = []

                    for j, logprob_entry in enumerate(top_logprobs):
                        token = logprob_entry['token']
                        logprob = logprob_entry['logprob']
                        prob = math.exp(logprob)

                        logger.info(f"  {j+1:2d}. '{token}' -> {prob:.8f} (logprob: {logprob:.4f})")

                        # Categorize tokens
                        token_lower = token.lower().strip()
                        if 'yes' in token_lower or token_lower in ['y']:
                            yes_variants.append((token, prob))
                        elif 'no' in token_lower or token_lower in ['n']:
                            no_variants.append((token, prob))
                        else:
                            other_tokens.append((token, prob))

                    # Analysis
                    yes_total = sum(prob for _, prob in yes_variants)
                    no_total = sum(prob for _, prob in no_variants)
                    other_total = sum(prob for _, prob in other_tokens)
                    total_all = yes_total + no_total + other_total

                    logger.info(f"\n📊 PROBABILITY BREAKDOWN:")
                    logger.info(f"  YES variants:  {yes_total:.8f} ({yes_total/total_all*100:.4f}%)")
                    logger.info(f"  NO variants:   {no_total:.8f} ({no_total/total_all*100:.4f}%)")
                    logger.info(f"  Other tokens:  {other_total:.8f} ({other_total/total_all*100:.4f}%)")
                    logger.info(f"  Total:         {total_all:.8f}")

                    # Calculate what confidence would be using our algorithm
                    if response.content.lower().strip() == 'yes':
                        confidence = yes_total
                        alternative = no_total
                        logger.info(f"\n🎯 CONFIDENCE ANALYSIS (predicted 'yes'):")
                        logger.info(f"  Confidence in 'yes': {confidence:.8f}")
                        logger.info(f"  Alternative 'no':    {alternative:.8f}")
                    elif response.content.lower().strip() == 'no':
                        confidence = no_total
                        alternative = yes_total
                        logger.info(f"\n🎯 CONFIDENCE ANALYSIS (predicted 'no'):")
                        logger.info(f"  Confidence in 'no':  {confidence:.8f}")
                        logger.info(f"  Alternative 'yes':   {alternative:.8f}")

                    if alternative > 0:
                        uncertainty = alternative / (confidence + alternative)
                        logger.info(f"  Uncertainty ratio:   {uncertainty:.8f} ({uncertainty*100:.4f}%)")
                    else:
                        logger.info(f"  Uncertainty ratio:   0.00000000 (0.0000%)")

                else:
                    logger.error("No content in logprobs")
            else:
                logger.error("No logprobs in response")

        except Exception as e:
            logger.error(f"Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_raw_openai_logprobs())