"""
Utility functions for training operations.

This module contains helper functions for LLM fine-tuning data generation,
including quote verification, completion generation, and path management.
"""

import re
import os
import logging
import textwrap
from typing import Dict, Any, Optional, List
from difflib import SequenceMatcher
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic

logger = logging.getLogger(__name__)


def normalize_name_to_key(name: str) -> str:
    """
    Normalize a display name to a filesystem-safe key.

    Converts name to lowercase and replaces runs of one or more non-word
    characters with hyphens.

    Args:
        name: Display name to normalize (e.g., "A Test Scorecard v 1.0")

    Returns:
        Normalized key (e.g., "a-test-scorecard-v-1-0")

    Examples:
        >>> normalize_name_to_key("A Test Scorecard v 1.0")
        'a-test-scorecard-v-1-0'
        >>> normalize_name_to_key("Randall Reilly v1.0")
        'randall-reilly-v1-0'
        >>> normalize_name_to_key("SelectQuote HCS Medium-Risk")
        'selectquote-hcs-medium-risk'
    """
    # Handle None input
    if name is None:
        return None

    # Lowercase the name
    normalized = name.lower()

    # Replace runs of one or more non-word characters with a single hyphen
    # \W matches any non-word character (not a-z, A-Z, 0-9, or _)
    normalized = re.sub(r'\W+', '-', normalized)

    # Remove leading/trailing hyphens
    normalized = normalized.strip('-')

    return normalized


def get_scorecard_key(scorecard_config: Optional[Dict[str, Any]] = None,
                      scorecard_name: Optional[str] = None) -> str:
    """
    Get the key for a scorecard, preferring explicit 'key' field or normalizing the name.

    Args:
        scorecard_config: Scorecard configuration dict (may contain 'key' field)
        scorecard_name: Scorecard display name (fallback if no config or no key in config)

    Returns:
        Scorecard key suitable for filesystem paths

    Raises:
        ValueError: If neither config nor name provided
    """
    # Try to get key from config first
    if scorecard_config and isinstance(scorecard_config, dict):
        if 'key' in scorecard_config:
            return scorecard_config['key']
        if 'name' in scorecard_config:
            return normalize_name_to_key(scorecard_config['name'])

    # Fallback to provided name
    if scorecard_name:
        return normalize_name_to_key(scorecard_name)

    raise ValueError("Must provide either scorecard_config with name/key or scorecard_name")


def get_score_key(score_config: Dict[str, Any]) -> str:
    """
    Get the key for a score, preferring explicit 'key' field or normalizing the name.

    Args:
        score_config: Score configuration dict (may contain 'key' and 'name' fields)

    Returns:
        Score key suitable for filesystem paths

    Raises:
        ValueError: If score_config doesn't have 'key' or 'name'
    """
    if 'key' in score_config:
        return score_config['key']

    if 'name' in score_config:
        return normalize_name_to_key(score_config['name'])

    raise ValueError("score_config must have either 'key' or 'name' field")


def get_output_dir(scorecard_name: Optional[str] = None,
                   score_name: Optional[str] = None,
                   scorecard_config: Optional[Dict[str, Any]] = None,
                   score_config: Optional[Dict[str, Any]] = None,
                   subsampled: bool = False,
                   max_tokens: Optional[int] = None) -> str:
    """
    Get the output directory path for training files using filesystem-safe keys.

    Prefers using explicit 'key' fields from configs, otherwise normalizes names.
    This ensures paths are filesystem-safe without spaces or special characters.

    Args:
        scorecard_name: DEPRECATED - Use scorecard_config instead
        score_name: DEPRECATED - Use score_config instead
        scorecard_config: Scorecard configuration dict (contains 'key' or 'name')
        score_config: Score configuration dict (contains 'key' or 'name')
        subsampled: Whether this is a subsampled directory
        max_tokens: Maximum tokens (for subsampled directories)

    Returns:
        Directory path string using filesystem-safe keys

    Examples:
        >>> get_output_dir(score_config={'key': 'my-score'}, scorecard_config={'key': 'my-scorecard'})
        'tuning/my-scorecard/my-score'
        >>> get_output_dir(score_config={'name': 'Test Score'}, scorecard_config={'name': 'Test Scorecard'})
        'tuning/test-scorecard/test-score'
    """
    # Get scorecard key (prefer config, fallback to name)
    if scorecard_config:
        scorecard_key = get_scorecard_key(scorecard_config=scorecard_config)
    elif scorecard_name:
        scorecard_key = get_scorecard_key(scorecard_name=scorecard_name)
    else:
        raise ValueError("Must provide either scorecard_config or scorecard_name")

    # Get score key (prefer config, fallback to name)
    if score_config:
        score_key = get_score_key(score_config)
    elif score_name:
        score_key = normalize_name_to_key(score_name)
    else:
        raise ValueError("Must provide either score_config or score_name")

    base_dir = f"tuning/{scorecard_key}/{score_key}"
    if subsampled and max_tokens:
        return f"{base_dir}/{max_tokens}_tokens"
    return base_dir


def get_file_path(output_dir: str, file_type: str) -> str:
    """
    Get the file path for a training/validation JSON-L file.

    Args:
        output_dir: Output directory path
        file_type: Type of file ('training' or 'validation')

    Returns:
        File path string
    """
    return f"{output_dir}/{file_type}.jsonl"


def get_id_file_path(output_dir: str, file_type: str) -> str:
    """
    Get the file path for a training/validation ID tracking file.

    Args:
        output_dir: Output directory path
        file_type: Type of file ('training' or 'validation')

    Returns:
        File path string
    """
    return f"{output_dir}/{file_type}_ids.txt"


def append_feedback_to_conversation(conversation_history: List[Dict[str, str]], feedback_message: str) -> List[Dict[str, str]]:
    """
    Append feedback message to conversation history as a user message.

    Args:
        conversation_history: Existing conversation messages
        feedback_message: Feedback message to append

    Returns:
        Updated conversation history with feedback appended
    """
    if not conversation_history:
        logger.error("Cannot append feedback to empty conversation history")
        return conversation_history

    feedback_user_message = {
        "role": "user",
        "content": f"""FEEDBACK ON YOUR PREVIOUS RESPONSE:

{feedback_message}

Please generate an improved completion that addresses this feedback:"""
    }

    updated_history = conversation_history + [feedback_user_message]

    logger.info("=== APPENDING FEEDBACK TO CONVERSATION ===")
    logger.info(f"Feedback message: {feedback_message[:200]}...")
    logger.info(f"Full feedback user message: {feedback_user_message['content'][:300]}...")
    logger.info(f"Conversation history now has {len(updated_history)} messages")

    return updated_history


def create_hallucination_feedback(verification_result: Dict[str, Any], original_transcript: str) -> Optional[str]:
    """
    Create a feedback message for the LLM about hallucinated quotes.

    Args:
        verification_result: Result from verify_quotes_in_completion
        original_transcript: The original transcript text

    Returns:
        Feedback message for the LLM, or None if no hallucinations
    """
    if not verification_result['hallucinated_quotes']:
        return None

    feedback_parts = []

    # Main feedback message
    feedback_parts.append("Your previous completion contained quotes that do not appear in the transcript.")

    # List hallucinated quotes
    if len(verification_result['hallucinated_quotes']) == 1:
        feedback_parts.append(f"This quote was NOT found in the transcript: \"{verification_result['hallucinated_quotes'][0]}\"")
    else:
        feedback_parts.append("These quotes were NOT found in the transcript:")
        for quote in verification_result['hallucinated_quotes']:
            feedback_parts.append(f"- \"{quote}\"")

    # List verified quotes if any
    if verification_result['verified_quotes']:
        feedback_parts.append("\nThese quotes were correctly found in the transcript:")
        for quote in verification_result['verified_quotes']:
            feedback_parts.append(f"- \"{quote}\"")

    # Instructions for improvement
    feedback_parts.append("""
CRITICAL: You must only use quotes that appear EXACTLY in the transcript.
- Reread the transcript carefully
- Only quote text that appears word-for-word in the transcript
- If you need to reference something, paraphrase instead of creating fake quotes
- Double-check every quote before including it

RETRY STRATEGY: To avoid quote verification issues:
- Use SHORTER quotes (5-10 words max instead of full sentences)
- Use FEWER quotes (1-2 key quotes instead of multiple quotes)
- Focus on the most essential words that support your reasoning
- Prefer paraphrasing over quoting when possible""")

    return "\n".join(feedback_parts)


def create_no_quotes_feedback() -> str:
    """
    Create a feedback message instructing the LLM to generate a completion without any quotes.
    This is used as a last-ditch effort to save examples that repeatedly fail quote verification.

    Returns:
        Feedback message instructing no quotes usage
    """
    feedback = """
FINAL ATTEMPT - NO QUOTES STRATEGY:

Your previous attempts included quotes that could not be verified in the transcript.
As a final attempt to generate a valid completion, please:

CRITICAL INSTRUCTIONS:
- Generate your completion WITHOUT using any direct quotes at all
- Do NOT use quotation marks (" or ') anywhere in your response
- Paraphrase and summarize instead of quoting
- Refer to what was said without using exact quoted text
- Focus on your analysis and reasoning without quoted evidence

Example approach:
Instead of: The customer said "they are 20 years old"
Use: The customer indicated the windows were approximately 20 years old

Your response should still follow the completion template format and provide the correct classification, but entirely avoid direct quotation marks.
"""

    return feedback.strip()


def contains_disagreement(completion_text: str) -> bool:
    """
    Check if the completion contains a disagreement with the gold standard.

    Args:
        completion_text: The generated completion text

    Returns:
        True if the completion indicates disagreement
    """
    # More precise patterns that indicate the LLM is disagreeing with the classification
    disagreement_patterns = [
        r'\bDISAGREE\b',  # Standalone DISAGREE
        r'\bI disagree\b',  # LLM stating disagreement
        r'\bI strongly disagree\b',  # Strong disagreement
        r'\bI must disagree\b',  # Must disagree
        r'\bI respectfully disagree\b',  # Polite disagreement
        r'\bdisagree with.*gold standard\b',  # Disagreeing with gold standard
        r'\bdisagree with.*classification\b',  # Disagreeing with classification
        r'\bdisagree with.*provided\b',  # Disagreeing with provided answer
    ]

    completion_lower = completion_text.lower()

    # Check each pattern
    for pattern in disagreement_patterns:
        if re.search(pattern, completion_lower):
            return True

    return False


def verify_quotes_in_completion(completion_text: str, original_transcript: str,
                                fuzzy_threshold: float = 0.8, enable_fuzzy: bool = True,
                                debug: bool = False) -> Dict[str, Any]:
    """
    Verify that all quotes in the completion exist in the original transcript.

    Args:
        completion_text: The generated completion text
        original_transcript: The original transcript text
        fuzzy_threshold: Threshold for fuzzy matching (0.0-1.0)
        enable_fuzzy: Whether to enable fuzzy matching
        debug: Whether to enable detailed debug logging

    Returns:
        Dictionary with verification results containing:
            - verified_quotes: list of quotes found in transcript
            - hallucinated_quotes: list of quotes NOT found in transcript
            - fuzzy_matched_quotes: list of quotes matched with fuzzy logic
            - is_valid: boolean indicating if all quotes are valid
            - verification_details: detailed information about each quote
    """
    if debug:
        logger.info("=== QUOTE VERIFICATION DEBUG ===")
        logger.info(f"Completion text: {completion_text}")
        logger.info(f"Transcript length: {len(original_transcript)} characters")
        logger.info(f"Fuzzy matching enabled: {enable_fuzzy}, threshold: {fuzzy_threshold}")

    # Extract quoted text (handle both straight and curly quotes)
    quote_patterns = [
        r'"([^"]*)"',           # straight quotes
        r'"([^"]*)"',           # curly quotes
        r"'([^']*)'",           # single curly quotes
        r'\'([^\']*)\'',        # single straight quotes
    ]

    extracted_quotes = []
    for pattern in quote_patterns:
        matches = re.findall(pattern, completion_text)
        extracted_quotes.extend([match.strip() for match in matches if match.strip()])

    # Remove duplicates while preserving order
    extracted_quotes = list(dict.fromkeys(extracted_quotes))

    if debug:
        logger.info(f"Extracted {len(extracted_quotes)} quotes: {extracted_quotes}")

    hallucinated_quotes = []
    verified_quotes = []
    fuzzy_matched_quotes = []
    verification_details = []

    for quote in extracted_quotes:
        # Skip very short quotes (likely not meaningful)
        if len(quote) < 3:
            verification_details.append({
                'quote': quote,
                'status': 'skipped',
                'reason': 'too short (< 3 characters)',
                'match_type': None,
                'similarity': None
            })
            continue

        quote_detail = {
            'quote': quote,
            'status': 'unknown',
            'reason': '',
            'match_type': None,
            'similarity': None
        }

        # Try exact matching first
        if quote in original_transcript:
            verified_quotes.append(quote)
            quote_detail.update({
                'status': 'verified',
                'reason': 'exact match found',
                'match_type': 'exact',
                'similarity': 1.0
            })
        # Try case-insensitive matching
        elif quote.lower() in original_transcript.lower():
            verified_quotes.append(quote)
            quote_detail.update({
                'status': 'verified',
                'reason': 'case-insensitive match found',
                'match_type': 'case_insensitive',
                'similarity': 1.0
            })
        # Try fuzzy matching if enabled
        elif enable_fuzzy:
            best_similarity = 0.0
            best_match = None

            # Split transcript into sentences/phrases for more targeted matching
            transcript_parts = re.split(r'[.!?;]\s+', original_transcript)
            transcript_parts.extend(original_transcript.split('\n'))

            for part in transcript_parts:
                part = part.strip()
                if len(part) < 3:
                    continue

                # Calculate similarity
                similarity = SequenceMatcher(None, quote.lower(), part.lower()).ratio()
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = part

            quote_detail['similarity'] = best_similarity

            if best_similarity >= fuzzy_threshold:
                fuzzy_matched_quotes.append(quote)
                verified_quotes.append(quote)  # Count as verified
                quote_detail.update({
                    'status': 'verified',
                    'reason': f'fuzzy match found (similarity: {best_similarity:.3f})',
                    'match_type': 'fuzzy',
                    'best_match': best_match
                })
            else:
                hallucinated_quotes.append(quote)
                quote_detail.update({
                    'status': 'hallucinated',
                    'reason': f'no match found (best similarity: {best_similarity:.3f})',
                    'match_type': None,
                    'best_match': best_match
                })
        else:
            # Fuzzy matching disabled, mark as hallucinated
            hallucinated_quotes.append(quote)
            quote_detail.update({
                'status': 'hallucinated',
                'reason': 'no exact match found, fuzzy matching disabled',
                'match_type': None
            })

        verification_details.append(quote_detail)

        if debug:
            logger.info(f"Quote: '{quote}' -> {quote_detail['status']} ({quote_detail['reason']})")

    result = {
        'verified_quotes': verified_quotes,
        'hallucinated_quotes': hallucinated_quotes,
        'fuzzy_matched_quotes': fuzzy_matched_quotes,
        'is_valid': len(hallucinated_quotes) == 0,
        'total_quotes': len(extracted_quotes),
        'verification_details': verification_details
    }

    if debug:
        logger.info(f"=== VERIFICATION SUMMARY ===")
        logger.info(f"Total quotes: {result['total_quotes']}")
        logger.info(f"Verified: {len(verified_quotes)} (exact: {len([d for d in verification_details if d['match_type'] == 'exact'])}, case-insensitive: {len([d for d in verification_details if d['match_type'] == 'case_insensitive'])}, fuzzy: {len(fuzzy_matched_quotes)})")
        logger.info(f"Hallucinated: {len(hallucinated_quotes)}")
        logger.info(f"Overall valid: {result['is_valid']}")
        logger.info("=== END VERIFICATION DEBUG ===")

    return result


def generate_llm_completion(score_instance, row: Dict[str, Any], completion_template: str,
                           conversation_history: Optional[List[Dict[str, str]]] = None) -> tuple:
    """
    Generate completion using an LLM with full context and gold standard labels.

    Args:
        score_instance: The score instance containing configuration
        row: The data row containing transcript and other information
        completion_template: The Jinja2 template with label interpolation for the LLM
        conversation_history: Optional list of previous messages for iterative improvement

    Returns:
        Tuple of (completion_text, updated_conversation_history)
    """
    try:
        # Get LLM configuration from score parameters
        node_config = score_instance.parameters.graph[0]
        model_name = node_config.get('completion_llm_model', 'gpt-4o-mini-2024-07-18')
        model_provider = node_config.get('completion_llm_provider', 'ChatOpenAI')

        # Initialize the LLM based on provider
        if model_provider == 'ChatOpenAI':
            llm = ChatOpenAI(model=model_name, temperature=0)
        elif model_provider == 'ChatAnthropic':
            llm = ChatAnthropic(model=model_name, temperature=0)
        else:
            logger.warning(f"Unknown LLM provider: {model_provider}, defaulting to ChatOpenAI")
            llm = ChatOpenAI(model=model_name, temperature=0)

        # Get the original system and user messages for context
        original_system_message = node_config['system_message']
        original_user_message = node_config['user_message']

        # Format the original user message with the transcript
        formatted_user_message = PromptTemplate.from_template(
            original_user_message,
            template_format="jinja2"
        ).format(**{"text": row['text']})

        # Prepare labels for interpolation (same as original template approach)
        labels = row.copy()

        # Apply massage_labels if present
        if 'massage_labels' in node_config:
            massage_labels_code = node_config['massage_labels']
            massage_labels_func = f"""
def massage_labels(labels):
    # Debug prints before transformation
    print("\\nBefore massage:")
    print(f"Good Call = {{labels.get('Good Call')}}")
    print(f"Good Call comment = {{labels.get('Good Call comment')}}")
    print(f"Non-Qualified Reason = {{labels.get('Non-Qualified Reason')}}")
    print(f"Bad Call Reason = {{labels.get('Bad Call Reason')}}")

{textwrap.indent(massage_labels_code, '    ')}

    # Debug prints after transformation
    print("\\nAfter massage:")
    print(f"Bad Call Reason = {{labels.get('Bad Call Reason')}}")
    return labels
"""
            local_vars = {}
            exec(massage_labels_func, local_vars)
            labels = local_vars['massage_labels'](labels)

        # Interpolate the completion template with labels (Jinja2 format)
        interpolated_completion_template = PromptTemplate.from_template(
            completion_template,
            template_format="jinja2"
        ).format(labels=labels, **row)

        logger.info(f"Interpolated completion template: {interpolated_completion_template}")

        # Construct the comprehensive prompt for LLM completion generation
        system_prompt = f"""You are generating training completions for a fine-tuning dataset. Your task is to analyze the transcript and generate an appropriate completion that follows the original scoring criteria.

Original System Message (Scoring Criteria):
{original_system_message}

Original User Message (Analysis Task):
{formatted_user_message}

Completion Instructions with Gold Standard Labels:
{interpolated_completion_template}

IMPORTANT:
- Any quotes you include must be EXACT quotes from the transcript. Do not paraphrase or create new quotes.
- The completion instructions above include the correct gold standard labels - use this information to generate an accurate completion.
- Your response should match the format and content suggested by the completion instructions.
- If you genuinely disagree with the gold standard classification after careful analysis, you may respond with "DISAGREE" instead of the expected classification. This should be rare and only when you have strong evidence the gold standard is incorrect."""

        # Build conversation messages
        if conversation_history is None:
            # First attempt - create initial conversation
            user_prompt = f"""Based on the scoring criteria and completion instructions above, generate the appropriate completion for this transcript:

<transcript>
{row['text']}
</transcript>

Generate your completion now (following the format and content from the completion instructions):"""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            logger.info("=== INITIAL LLM CONVERSATION ===")
            logger.info(f"System message: {system_prompt[:200]}...")
            logger.info(f"User message: {user_prompt[:200]}...")

        else:
            # Retry attempt - use existing conversation history
            messages = conversation_history.copy()
            logger.info(f"=== RETRY LLM CONVERSATION (appending to {len(messages)} existing messages) ===")
            for i, msg in enumerate(messages):
                logger.info(f"Message {i+1} ({msg['role']}): {msg['content'][:100]}...")
            logger.info("=== END EXISTING CONVERSATION HISTORY ===")

        response = llm.invoke(messages)
        completion = response.content.strip()

        # Add the assistant's response to the conversation history
        updated_messages = messages + [{"role": "assistant", "content": completion}]

        logger.info(f"=== LLM RESPONSE ===")
        logger.info(f"Generated completion: {completion}")
        logger.info(f"Updated conversation now has {len(updated_messages)} messages")

        return completion, updated_messages

    except Exception as e:
        logger.error(f"Error generating LLM completion: {str(e)}")
        # Fallback to original template-based approach
        labels = row.copy()

        # Apply massage_labels if present in fallback
        if 'massage_labels' in score_instance.parameters.graph[0]:
            massage_labels_code = score_instance.parameters.graph[0]['massage_labels']
            massage_labels_func = f"""
def massage_labels(labels):
{textwrap.indent(massage_labels_code, '    ')}
    return labels
"""
            local_vars = {}
            exec(massage_labels_func, local_vars)
            labels = local_vars['massage_labels'](labels)

        # Use Jinja2 template format for fallback completion
        prompt = PromptTemplate.from_template(
            completion_template,
            template_format="jinja2"
        )
        fallback_completion = prompt.format(labels=labels, **row).strip()
        logger.info(f"Using fallback template completion: {fallback_completion}")

        # Return empty conversation history for fallback
        return fallback_completion, []
