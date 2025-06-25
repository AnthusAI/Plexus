import re
import rich
from rich import print
from rich.panel import Panel
from rich.columns import Columns
import click
import plexus
import os
import json
import pandas as pd
from openpyxl.styles import Font
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import BaseOutputParser
from langchain_community.chat_models import ChatOpenAI
from langchain_anthropic import ChatAnthropic
import tiktoken
import concurrent.futures
from functools import partial
from random import sample
import textwrap

from plexus.CustomLogging import logging
from plexus.Registries import scorecard_registry
from plexus.scores.Score import Score

@click.group()
def tuning():
    """Commands for fine-tuning models."""
    pass

def get_output_dir(scorecard_name, score_name, subsampled=False, max_tokens=None):
    base_dir = f"tuning/{scorecard_name}/{score_name}"
    if subsampled and max_tokens:
        return f"{base_dir}/{max_tokens}_tokens"
    return base_dir

def get_file_path(output_dir, file_type):
    return f"{output_dir}/{file_type}.jsonl"

def get_id_file_path(output_dir, file_type):
    return f"{output_dir}/{file_type}_ids.txt"

def append_feedback_to_conversation(conversation_history, feedback_message):
    """
    Append feedback message to conversation history as a user message.
    
    Args:
        conversation_history (list): Existing conversation messages
        feedback_message (str): Feedback message to append
        
    Returns:
        list: Updated conversation history with feedback appended
    """
    if not conversation_history:
        logging.error("Cannot append feedback to empty conversation history")
        return conversation_history
    
    feedback_user_message = {
        "role": "user", 
        "content": f"""FEEDBACK ON YOUR PREVIOUS RESPONSE:

{feedback_message}

Please generate an improved completion that addresses this feedback:"""
    }
    
    updated_history = conversation_history + [feedback_user_message]
    
    logging.info("=== APPENDING FEEDBACK TO CONVERSATION ===")
    logging.info(f"Feedback message: {feedback_message[:200]}...")
    logging.info(f"Full feedback user message: {feedback_user_message['content'][:300]}...")
    logging.info(f"Conversation history now has {len(updated_history)} messages")
    
    return updated_history

def create_hallucination_feedback(verification_result, original_transcript):
    """
    Create a feedback message for the LLM about hallucinated quotes.
    
    Args:
        verification_result (dict): Result from verify_quotes_in_completion
        original_transcript (str): The original transcript text
        
    Returns:
        str: Feedback message for the LLM
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

def create_no_quotes_feedback():
    """
    Create a feedback message instructing the LLM to generate a completion without any quotes.
    This is used as a last-ditch effort to save examples that repeatedly fail quote verification.
    
    Returns:
        str: Feedback message instructing no quotes usage
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

def contains_disagreement(completion_text):
    """
    Check if the completion contains a disagreement with the gold standard.
    
    Args:
        completion_text (str): The generated completion text
        
    Returns:
        bool: True if the completion indicates disagreement
    """
    import re
    
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

def verify_quotes_in_completion(completion_text, original_transcript, fuzzy_threshold=0.8, enable_fuzzy=True, debug=False):
    """
    Verify that all quotes in the completion exist in the original transcript.
    
    Args:
        completion_text (str): The generated completion text
        original_transcript (str): The original transcript text
        fuzzy_threshold (float): Threshold for fuzzy matching (0.0-1.0)
        enable_fuzzy (bool): Whether to enable fuzzy matching
        debug (bool): Whether to enable detailed debug logging
        
    Returns:
        dict: Contains verification results with keys:
            - verified_quotes: list of quotes found in transcript
            - hallucinated_quotes: list of quotes NOT found in transcript
            - fuzzy_matched_quotes: list of quotes matched with fuzzy logic
            - is_valid: boolean indicating if all quotes are valid
            - verification_details: detailed information about each quote
    """
    import re
    from difflib import SequenceMatcher
    
    if debug:
        logging.info("=== QUOTE VERIFICATION DEBUG ===")
        logging.info(f"Completion text: {completion_text}")
        logging.info(f"Transcript length: {len(original_transcript)} characters")
        logging.info(f"Fuzzy matching enabled: {enable_fuzzy}, threshold: {fuzzy_threshold}")
    
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
        logging.info(f"Extracted {len(extracted_quotes)} quotes: {extracted_quotes}")
    
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
            logging.info(f"Quote: '{quote}' -> {quote_detail['status']} ({quote_detail['reason']})")
    
    result = {
        'verified_quotes': verified_quotes,
        'hallucinated_quotes': hallucinated_quotes,
        'fuzzy_matched_quotes': fuzzy_matched_quotes,
        'is_valid': len(hallucinated_quotes) == 0,
        'total_quotes': len(extracted_quotes),
        'verification_details': verification_details
    }
    
    if debug:
        logging.info(f"=== VERIFICATION SUMMARY ===")
        logging.info(f"Total quotes: {result['total_quotes']}")
        logging.info(f"Verified: {len(verified_quotes)} (exact: {len([d for d in verification_details if d['match_type'] == 'exact'])}, case-insensitive: {len([d for d in verification_details if d['match_type'] == 'case_insensitive'])}, fuzzy: {len(fuzzy_matched_quotes)})")
        logging.info(f"Hallucinated: {len(hallucinated_quotes)}")
        logging.info(f"Overall valid: {result['is_valid']}")
        logging.info("=== END VERIFICATION DEBUG ===")
    
    return result

def generate_llm_completion(score_instance, row, completion_template, conversation_history=None):
    """
    Generate completion using an LLM with full context and gold standard labels.
    
    Args:
        score_instance: The score instance containing configuration
        row: The data row containing transcript and other information
        completion_template: The Jinja2 template with label interpolation for the LLM
        conversation_history: Optional list of previous messages for iterative improvement
        
    Returns:
        tuple: (completion_text, updated_conversation_history)
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
            logging.warning(f"Unknown LLM provider: {model_provider}, defaulting to ChatOpenAI")
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
        
        logging.info(f"Interpolated completion template: {interpolated_completion_template}")
        
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
            
            logging.info("=== INITIAL LLM CONVERSATION ===")
            logging.info(f"System message: {system_prompt[:200]}...")
            logging.info(f"User message: {user_prompt[:200]}...")
            
        else:
            # Retry attempt - use existing conversation history
            messages = conversation_history.copy()
            logging.info(f"=== RETRY LLM CONVERSATION (appending to {len(messages)} existing messages) ===")
            for i, msg in enumerate(messages):
                logging.info(f"Message {i+1} ({msg['role']}): {msg['content'][:100]}...")
            logging.info("=== END EXISTING CONVERSATION HISTORY ===")
        
        response = llm.invoke(messages)
        completion = response.content.strip()
        
        # Add the assistant's response to the conversation history
        updated_messages = messages + [{"role": "assistant", "content": completion}]
        
        logging.info(f"=== LLM RESPONSE ===")
        logging.info(f"Generated completion: {completion}")
        logging.info(f"Updated conversation now has {len(updated_messages)} messages")
        
        return completion, updated_messages
        
    except Exception as e:
        logging.error(f"Error generating LLM completion: {str(e)}")
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
        logging.info(f"Using fallback template completion: {fallback_completion}")
        
        # Return empty conversation history for fallback
        return fallback_completion, []

@tuning.command(help="Generate JSON-L files for training and validation.")
@click.option('--scorecard-name', required=True, help='The name of the scorecard.')
@click.option('--score-name', help='The name of the score to generate JSON-L for. If not provided, all scores will be processed.')
@click.option('--maximum-number', type=int, default=100, help='Maximum number of samples, total.')
@click.option('--train-ratio', type=float, default=0.8, help='Ratio of training samples to total samples.')
@click.option('--clean-existing', is_flag=True, help='Clean existing JSON-L files before generating new ones.')
@click.option('--fresh', is_flag=True, help='Pull fresh, non-cached data from the data lake.')
@click.option('--threads', type=int, default=20, help='Number of threads to use.')
@click.option('--verbose', is_flag=True, help='Verbose output.')
def generate_examples(scorecard_name, score_name,
                      maximum_number, train_ratio, clean_existing, fresh, verbose, threads):
    """
    Generate JSON-L files that include a specified number of examples, using the prompt templates
    from the score configuration combined with data and ground-truth labels.

    :param scorecard_name: The name of the scorecard.
    :type scorecard_name: str
    :param score_name: The name of the score to generate JSON-L for.
    :type score_name: str
    :param maximum_number: Maximum number of samples, total.
    :type maximum_number: int
    :param train_ratio: Ratio of training samples to total samples.
    :type train_ratio: float
    :param verbose: Verbose output.
    :type verbose: bool
    """
    logging.info(f"Generating JSON-L for [magenta1][b]{score_name}[/b][/magenta1] on [magenta1][b]{scorecard_name}[/b][/magenta1]...")

    # Find the scorecard
    plexus.Scorecard.load_and_register_scorecards('scorecards/')
    scorecard_class = scorecard_registry.get(scorecard_name)
    if scorecard_class is None:
        logging.error(f"No scorecard named [magenta1][b]{scorecard_name}[/b][/magenta1] found.")
        return
    
    # If no score_name is provided, process all scores in the scorecard
    if not score_name:
        score_names = list(scorecard_class.scores.keys())
        logging.info(f"Processing all scores: {score_names}")
    else:
        score_names = [score_name]

    for current_score_name in score_names:
        logging.info(f"Processing score: [magenta1][b]{current_score_name}[/b][/magenta1]")
        
        # Instantiate the score class using the configuration parameters.
        score_configuration = next((score for score in scorecard_class.scores if score['name'] == current_score_name), {})
        logging.info(f"Score Configuration: {rich.pretty.pretty_repr(score_configuration)}")
        score_class = scorecard_class.score_registry.get(current_score_name)
        if score_class is None:
            logging.error(f"Score class for '{current_score_name}' not found in the registry.")
            continue
        score_configuration['scorecard_name'] = scorecard_class.name
        score_configuration['score_name'] = current_score_name
        try:
            score_instance = score_class(**score_configuration)
        except Exception as e:
            logging.error(f"Failed to instantiate score class for '{current_score_name}': {str(e)}")
            continue

        # Get data
        score_instance = score_class(**score_configuration)
        score_instance.load_data(data=score_configuration['data'], fresh=fresh)
        score_instance.process_data()

        num_training_samples = round(maximum_number * train_ratio)
        num_validation_samples = round(maximum_number * (1 - train_ratio))

        logging.info(f"Aiming for {num_training_samples} training samples and {num_validation_samples} validation samples.")

        output_dir = get_output_dir(scorecard_name, current_score_name)
        os.makedirs(output_dir, exist_ok=True)

        train_file_path = get_file_path(output_dir, "training")
        val_file_path = get_file_path(output_dir, "validation")
        train_id_file_path = get_id_file_path(output_dir, "training")
        val_id_file_path = get_id_file_path(output_dir, "validation")

        # Clean existing JSON-L files if requested
        if clean_existing:
            for file_path in [train_file_path, val_file_path, train_id_file_path, val_id_file_path]:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logging.info(f"Removed existing file: {file_path}")

        existing_train_samples = sum(1 for _ in open(train_file_path)) if os.path.exists(train_file_path) else 0
        existing_val_samples = sum(1 for _ in open(val_file_path)) if os.path.exists(val_file_path) else 0

        logging.info(f"Found {existing_train_samples} existing training samples and {existing_val_samples} existing validation samples.")

        train_samples_to_generate = max(0, num_training_samples - existing_train_samples)
        val_samples_to_generate = max(0, num_validation_samples - existing_val_samples)

        logging.info(f"Will generate {train_samples_to_generate} additional training samples and {val_samples_to_generate} additional validation samples.")

        total_rows = len(score_instance.dataframe)
        row_indices = list(range(total_rows))

        training_data = []
        validation_data = []
        training_ids = []
        validation_ids = []

        # Get templates
        nodes = score_instance.get_prompt_templates()
        logging.info(f"Nodes: {nodes}")

        def process_row(scorecard_name, row, score_instance, score_configuration):
            # Get the original user message from the score configuration
            user_message = score_instance.parameters.graph[0]['user_message']

            if 'completion_template' in score_instance.parameters.graph[0]:
                node_config = score_instance.parameters.graph[0]
                
                # Check if LLM-based completion is enabled
                if node_config.get('llm_completion_enabled', False):
                    logging.info("Using LLM-based completion generation")
                    completion, conversation_history = generate_llm_completion(
                        score_instance=score_instance,
                        row=row,
                        completion_template=node_config['completion_template']
                    )
                    
                    # Check for disagreement with gold standard
                    if contains_disagreement(completion):
                        logging.warning(f"LLM disagreed with gold standard classification. Skipping example.")
                        logging.info(f"Disagreement completion: {completion}")
                        logging.info(f"Expected gold standard: {row.get(score_instance.get_label_score_name(), 'Unknown')}")
                        logging.info(f"Content ID: {row.get('content_id', 'Unknown')}")
                        return None  # Skip this example
                    
                    # Apply quote verification if enabled
                    if node_config.get('completion_quote_verification', True):
                        # Get fuzzy matching configuration
                        fuzzy_enabled = node_config.get('quote_verification_fuzzy_matching', True)
                        fuzzy_threshold = node_config.get('quote_verification_fuzzy_threshold', 0.8)
                        debug_mode = node_config.get('quote_verification_debug', False)
                        
                        verification = verify_quotes_in_completion(
                            completion, 
                            row['text'], 
                            fuzzy_threshold=fuzzy_threshold,
                            enable_fuzzy=fuzzy_enabled,
                            debug=debug_mode
                        )
                        
                        if not verification['is_valid']:
                            logging.warning(f"Quote verification failed - {len(verification['hallucinated_quotes'])} hallucinated quotes detected")
                            logging.info(f"Hallucinated quotes: {verification['hallucinated_quotes']}")
                            logging.info(f"Verified quotes: {len(verification['verified_quotes'])} total ({len(verification.get('fuzzy_matched_quotes', []))} fuzzy matched)")
                            logging.info(f"Total quotes found: {verification['total_quotes']}")
                            
                            # Log detailed verification results for debugging
                            for detail in verification['verification_details']:
                                if detail['status'] == 'hallucinated':
                                    logging.info(f"  FAILED: '{detail['quote']}' - {detail['reason']}")
                                    if detail.get('best_match'):
                                        logging.info(f"    Best match: '{detail['best_match']}' (similarity: {detail['similarity']:.3f})")
                                elif detail['status'] == 'verified' and detail['match_type'] == 'fuzzy':
                                    logging.info(f"  FUZZY: '{detail['quote']}' - {detail['reason']}")
                            
                            # Handle quote verification failure based on configuration
                            failure_action = node_config.get('quote_verification_failure_action', 'skip')
                            
                            if failure_action == 'skip':
                                logging.info("Skipping example due to hallucinated quotes (quote_verification_failure_action: skip)")
                                return None  # Skip this example entirely
                            elif failure_action == 'retry':
                                max_retries = node_config.get('quote_verification_max_retries', 3)
                                logging.info(f"Retrying LLM completion generation with iterative feedback (max_retries: {max_retries})")
                                
                                current_verification = verification
                                current_completion = completion
                                current_conversation_history = conversation_history
                                
                                for retry_count in range(max_retries):
                                    logging.info(f"Retry attempt {retry_count + 1}/{max_retries}")
                                    
                                    # Create feedback message about the hallucinations
                                    feedback_message = create_hallucination_feedback(current_verification, row['text'])
                                    logging.info(f"Providing feedback to LLM: {len(current_verification['hallucinated_quotes'])} hallucinated quotes detected")
                                    
                                    # Append feedback to conversation history
                                    updated_conversation_history = append_feedback_to_conversation(
                                        current_conversation_history, 
                                        feedback_message
                                    )
                                    
                                    # Generate new completion with conversation history
                                    retry_completion, new_conversation_history = generate_llm_completion(
                                        score_instance=score_instance,
                                        row=row,
                                        completion_template=node_config['completion_template'],
                                        conversation_history=updated_conversation_history
                                    )
                                    
                                    # Verify the new completion with same settings
                                    retry_verification = verify_quotes_in_completion(
                                        retry_completion, 
                                        row['text'],
                                        fuzzy_threshold=fuzzy_threshold,
                                        enable_fuzzy=fuzzy_enabled,
                                        debug=debug_mode
                                    )
                                    
                                    if retry_verification['is_valid']:
                                        logging.info(f"🎉 Iterative feedback successful on attempt {retry_count + 1}!")
                                        logging.info(f"   Final verification: {len(retry_verification['verified_quotes'])} quotes verified ({len(retry_verification.get('fuzzy_matched_quotes', []))} fuzzy matched)")
                                        logging.info(f"   Final conversation history has {len(new_conversation_history)} messages")
                                        completion = retry_completion
                                        conversation_history = new_conversation_history
                                        break
                                    else:
                                        logging.warning(f"❌ Retry {retry_count + 1} with feedback failed:")
                                        logging.warning(f"   Still has {len(retry_verification['hallucinated_quotes'])} hallucinated quotes: {retry_verification['hallucinated_quotes']}")
                                        
                                        # Log what improved vs what's still failing
                                        previous_failed = set(current_verification['hallucinated_quotes'])
                                        current_failed = set(retry_verification['hallucinated_quotes'])
                                        improved = previous_failed - current_failed
                                        new_failures = current_failed - previous_failed
                                        
                                        if improved:
                                            logging.info(f"   ✅ Improved: Fixed {len(improved)} quotes: {list(improved)}")
                                        if new_failures:
                                            logging.info(f"   ⚠️  New issues: {len(new_failures)} new hallucinated quotes: {list(new_failures)}")
                                        
                                        # Log detailed breakdown for this retry
                                        for detail in retry_verification['verification_details']:
                                            if detail['status'] == 'hallucinated':
                                                logging.info(f"     STILL FAILING: '{detail['quote']}' - {detail['reason']}")
                                        
                                        # Update for next iteration
                                        current_verification = retry_verification
                                        current_completion = retry_completion
                                        current_conversation_history = new_conversation_history
                                
                                # If all retries failed, try one final attempt with no quotes
                                if not retry_verification['is_valid']:
                                    logging.warning(f"All {max_retries} iterative feedback attempts failed - trying final no-quotes attempt")
                                    
                                    # Create no-quotes feedback message
                                    no_quotes_feedback = create_no_quotes_feedback()
                                    logging.info("🔄 Final attempt: Advising LLM to generate completion without any quotes")
                                    
                                    # Append no-quotes feedback to conversation history
                                    final_conversation_history = append_feedback_to_conversation(
                                        current_conversation_history, 
                                        no_quotes_feedback
                                    )
                                    
                                    # Generate final completion with no-quotes strategy
                                    final_completion, final_conversation_history = generate_llm_completion(
                                        score_instance=score_instance,
                                        row=row,
                                        completion_template=node_config['completion_template'],
                                        conversation_history=final_conversation_history
                                    )
                                    
                                    # Still verify the final completion (LLM might still include quotes despite instructions)
                                    final_verification = verify_quotes_in_completion(
                                        final_completion, 
                                        row['text'],
                                        fuzzy_threshold=fuzzy_threshold,
                                        enable_fuzzy=fuzzy_enabled,
                                        debug=debug_mode
                                    )
                                    
                                    if final_verification['is_valid']:
                                        logging.info(f"🎉 Final no-quotes attempt successful!")
                                        logging.info(f"   Final verification: {len(final_verification['verified_quotes'])} quotes verified ({len(final_verification.get('fuzzy_matched_quotes', []))} fuzzy matched)")
                                        logging.info(f"   Final conversation history has {len(final_conversation_history)} messages")
                                        completion = final_completion
                                        conversation_history = final_conversation_history
                                    else:
                                        logging.warning(f"❌ Final no-quotes attempt also failed:")
                                        logging.warning(f"   Still has {len(final_verification['hallucinated_quotes'])} hallucinated quotes: {final_verification['hallucinated_quotes']}")
                                        
                                        # Now decide what to do after all attempts (including no-quotes) have failed
                                        retry_fallback = node_config.get('quote_verification_retry_fallback', 'skip')
                                        if retry_fallback == 'skip':
                                            logging.warning(f"All {max_retries + 1} attempts (including no-quotes) failed - skipping example")
                                            return None
                                        elif retry_fallback == 'use_template':
                                            logging.warning(f"All {max_retries + 1} attempts (including no-quotes) failed - falling back to original template completion")
                                            # Fall through to template-based completion below
                                            completion = None  # Will trigger template fallback
                                        else:  # 'use_anyway'
                                            logging.warning(f"All {max_retries + 1} attempts (including no-quotes) failed - using final attempt anyway")
                                            completion = final_completion
                            elif failure_action == 'use_template':
                                logging.warning("Quote verification failed - falling back to original template completion")
                                completion = None  # Will trigger template fallback below
                            else:  # 'use_anyway'
                                logging.warning("Quote verification failed - using completion anyway (quote_verification_failure_action: use_anyway)")
                        else:
                            logging.info(f"Quote verification passed: {verification['total_quotes']} quotes verified")
                    
                    # If completion was set to None due to quote verification failure with template fallback
                    if completion is None:
                        logging.info("Generating template-based completion as fallback")
                        labels = row.copy()
                        
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
                        
                        # Use Jinja2 template format for fallback completion
                        prompt = PromptTemplate.from_template(
                            node_config['completion_template'],
                            template_format="jinja2"
                        )
                        completion = prompt.format(labels=labels, **row).strip()
                        completion = re.sub(r'\s+$', '', completion)
                else:
                    # Original template-based approach
                    labels = row.copy()
                    
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
                    
                    # Use Jinja2 template format for completion
                    prompt = PromptTemplate.from_template(
                        node_config['completion_template'],
                        template_format="jinja2"
                    )
                    completion = prompt.format(labels=labels, **row).strip()
                    completion = re.sub(r'\s+$', '', completion)
            else:
                completion = row[score_instance.get_label_score_name()]
            logging.info(f"Completion: {completion}")

            # Construct the messages for the JSON-L file
            messages = [
                {"role": "system", "content": score_instance.parameters.graph[0]['system_message']},
                {"role": "user", "content": PromptTemplate.from_template(user_message, template_format="jinja2").format(**{"text": row['text']})},
                {"role": "assistant", "content": completion}
            ]

            return {"messages": messages, "content_id": row['content_id']}

        # Update the partial function call
        process_row_partial = partial(
            process_row,
            score_instance=score_instance,
            score_configuration=score_configuration
        )

        train_file = open(train_file_path, "a")
        val_file = open(val_file_path, "a")
        train_id_file = open(train_id_file_path, "a")
        val_id_file = open(val_id_file_path, "a")

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
                futures = []
                processed_count = 0
                total_samples_to_generate = train_samples_to_generate + val_samples_to_generate

                while row_indices and processed_count < total_samples_to_generate:
                    batch_size = min(threads, len(row_indices), total_samples_to_generate - processed_count)
                    batch_indices = sample(row_indices, batch_size)
                    # Remove the sampled indices from the list
                    for idx in batch_indices:
                        row_indices.remove(idx)

                    batch_rows = score_instance.dataframe.iloc[batch_indices]
                    futures.extend([executor.submit(process_row_partial, scorecard_name, row) 
                                     for _, row in batch_rows.iterrows()])

                    for future in concurrent.futures.as_completed(futures):
                        result = future.result()
                        if result is not None:
                            message, content_id = result['messages'], result['content_id']
                            
                            if len(training_data) < train_samples_to_generate:
                                json.dump({"messages": message}, train_file)
                                train_file.write("\n")
                                train_file.flush()
                                train_id_file.write(f"{content_id}\n")
                                train_id_file.flush()
                                training_data.append(message)
                                training_ids.append(content_id)
                            elif len(validation_data) < val_samples_to_generate:
                                json.dump({"messages": message}, val_file)
                                val_file.write("\n")
                                val_file.flush()
                                val_id_file.write(f"{content_id}\n")
                                val_id_file.flush()
                                validation_data.append(message)
                                validation_ids.append(content_id)
                            
                            processed_count += 1
                            if processed_count >= total_samples_to_generate:
                                break

                    futures = []  # Clear processed futures

            logging.info(f"Total training samples: {existing_train_samples + len(training_data)}")
            logging.info(f"Total validation samples: {existing_val_samples + len(validation_data)}")

        finally:
            # Close files
            train_file.close()
            val_file.close()
            train_id_file.close()
            val_id_file.close()

        logging.info(f"Generated JSON-L and ID files in {output_dir}")

        # After processing all files, before the final logging messages:
        completion_counts = {}
        for file_path in [train_file_path, val_file_path]:
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    for line in f:
                        entry = json.loads(line)
                        completion = entry['messages'][-1]['content'].replace('\n', '\\n')
                        completion_counts[completion] = completion_counts.get(completion, 0) + 1
        
        if completion_counts:
            max_count = max(completion_counts.values())
            max_label_length = max(len(label) for label in completion_counts.keys())
            scale_factor = 50 / max_count  # Scale to max width of 50 characters
            
            logging.info("\nCompletion Distribution:")
            for completion, count in sorted(completion_counts.items(), 
                                         key=lambda x: (-x[1], x[0])):
                bar_length = int(count * scale_factor)
                bar = '█' * bar_length
                logging.info(f"{completion:<{max_label_length}} | {bar} ({count})")

    logging.info("Finished processing all scores.")

@tuning.command(help="Subsample JSON-L files based on token count estimates.")
@click.option('--scorecard-name', required=True, help='The name of the scorecard.')
@click.option('--score-name', help='The name of the score to subsample JSON-L for. If not provided, all scores will be processed.')
@click.option('--maximum-tokens', type=int, default=2000000, help='Maximum number of tokens for each of training and validation.')
@click.option('--verbose', is_flag=True, help='Verbose output.')
def subsample_examples(scorecard_name, score_name, maximum_tokens, verbose):
    logging.info(f"Subsampling examples for [magenta1][b]{scorecard_name}[/b][/magenta1] with a max token limit of {maximum_tokens} for each of training and validation...")

    encoder = tiktoken.encoding_for_model("gpt-4o")
    
    def load_jsonl(file_path):
        with open(file_path, 'r') as file:
            return [json.loads(line) for line in file]

    if score_name:
        score_names = [score_name]
    else:
        base_dir = f"tuning/{scorecard_name}"
        # Exclude 'combined' and any directories that don't contain both training and validation files
        score_names = []
        for d in os.listdir(base_dir):
            if d != 'combined' and os.path.isdir(os.path.join(base_dir, d)):
                input_dir = get_output_dir(scorecard_name, d)
                if (os.path.exists(get_file_path(input_dir, "training")) and 
                    os.path.exists(get_file_path(input_dir, "validation"))):
                    score_names.append(d)
        logging.info(f"Processing scores: {score_names}")

    score_files = []
    for score in score_names:
        input_dir = get_output_dir(scorecard_name, score)
        for file_type in ["training", "validation"]:
            file_path = get_file_path(input_dir, file_type)
            if os.path.exists(file_path):
                score_files.append((score, file_path, file_type))
            else:
                logging.warning(f"{file_type.capitalize()} file not found for score {score} in {input_dir}.")

    if not score_files:
        logging.error("No valid files found.")
        return

    subsampled_data = {"training": [], "validation": []}
    current_tokens = {"training": 0, "validation": 0}
    file_iterators = [iter(load_jsonl(file_path)) for _, file_path, _ in score_files]

    while file_iterators:
        for i in range(len(file_iterators)):
            if i >= len(file_iterators):
                break
            try:
                entry = next(file_iterators[i])
                file_type = score_files[i][2]
                
                if current_tokens[file_type] >= maximum_tokens:
                    continue  # Skip this file type if we've reached its limit
                
                entry_tokens = sum(len(encoder.encode(message['content'])) for message in entry['messages'])
                
                if current_tokens[file_type] + entry_tokens <= maximum_tokens:
                    subsampled_data[file_type].append(entry)
                    current_tokens[file_type] += entry_tokens
                    if verbose:
                        logging.info(f"Added {file_type} entry from {score_files[i][0]}. "
                                     f"Entry tokens: [magenta1]{entry_tokens:>10,}[/magenta1]   "
                                     f"Current {file_type} tokens: [magenta1]{current_tokens[file_type]:>10,}[/magenta1]")
                else:
                    if verbose:
                        logging.info(f"Reached token limit for {file_type}. Skipping further {file_type} entries.")
            except StopIteration:
                if verbose:
                    logging.info(f"Finished processing {score_files[i][0]} {score_files[i][2]}")
                file_iterators.pop(i)
                score_files.pop(i)
                i -= 1  # Adjust index after removal
        
        # Check if we've reached the limit for both types
        if current_tokens["training"] >= maximum_tokens and current_tokens["validation"] >= maximum_tokens:
            if verbose:
                logging.info("Reached token limit for both training and validation. Stopping.")
            break

    output_dir = get_output_dir(scorecard_name, "combined" if len(score_names) > 1 else score_names[0], subsampled=True, max_tokens=maximum_tokens)
    os.makedirs(output_dir, exist_ok=True)

    for file_type in ["training", "validation"]:
        output_file_path = get_file_path(output_dir, file_type)
        with open(output_file_path, 'w') as file:
            for entry in subsampled_data[file_type]:
                json.dump(entry, file)
                file.write('\n')
        logging.info(f"Subsampled {file_type} JSON-L file saved in {output_file_path}")
        logging.info(f"Total {file_type} examples: {len(subsampled_data[file_type])}")
        logging.info(f"Total {file_type} tokens: {current_tokens[file_type]:,}")

    logging.info(f"Total examples: {sum(len(data) for data in subsampled_data.values())}")