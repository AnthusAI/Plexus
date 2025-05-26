"""
Module for transforming call transcripts into BERTopic-compatible format.
"""

import os
import logging
import pandas as pd
from typing import List, Tuple, Optional, Dict, Any
import re
from pathlib import Path
import json
import time
import asyncio
import gc
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field, ValidationError
from langchain.output_parsers.retry import RetryWithErrorOutputParser
from langchain.globals import set_llm_cache
from langchain.cache import SQLiteCache

# Configure logging
logger = logging.getLogger(__name__)

# Initialize and set the Langchain LLM cache globally
# Cache file will be stored inside the project's tmp directory
cache_dir_path = Path("tmp/langchain.db")
cache_db_file_path = cache_dir_path / "topics_llm_cache.db"

try:
    # Ensure the cache directory exists
    cache_dir_path.mkdir(parents=True, exist_ok=True)
    logger.info(f"Attempting to initialize Langchain LLM SQLite cache at {cache_db_file_path}")
    set_llm_cache(SQLiteCache(database_path=str(cache_db_file_path))) # Pass the full file path
    logger.info(f"Langchain LLM SQLite cache initialized successfully at {cache_db_file_path}.")
except Exception as e:
    logger.warning(f"Could not initialize Langchain LLM SQLite cache (\'{cache_db_file_path}\'): {e}. LLM calls will not be cached across runs.")

def inspect_data(df: pd.DataFrame, content_column: str, num_samples: int = 5) -> None:
    """
    Print sample content from the DataFrame for inspection.
    
    Args:
        df: DataFrame containing transcript data
        content_column: Name of column containing transcript content
        num_samples: Number of samples to print
    """
    logging.info(f"\nInspecting first {num_samples} samples:")
    logging.info(f"DataFrame columns: {df.columns.tolist()}")
    logging.info(f"Total rows: {len(df)}")
    
    for i, (_, row) in enumerate(df.head(num_samples).iterrows()):
        logging.info(f"\nSample {i+1}:")
        logging.info(f"Content length: {len(row[content_column])} characters")
        logging.info("Content preview:")
        logging.info(row[content_column][:500] + "..." if len(row[content_column]) > 500 else row[content_column])

def extract_speaking_turns(text: str) -> List[str]:
    """
    Extract customer speaking turns from transcript text.
    
    Args:
        text: Raw transcript text
        
    Returns:
        List of customer speaking turns
    """
    # Split text into turns using "Agent:" and "Customer:" markers
    turns = []
    current_turn = ""
    current_speaker = None
    
    # Add spaces around "Agent:" and "Customer:" for consistent splitting
    text = re.sub(r'(?<![\s])(Agent:|Customer:)', r' \1', text)
    text = re.sub(r'(Agent:|Customer:)(?![\s])', r'\1 ', text)
    
    for line in text.split():
        if line == "Agent:":
            if current_speaker == "Customer" and current_turn.strip():
                turns.append(current_turn.strip())
            current_speaker = "Agent"
            current_turn = ""
        elif line == "Customer:":
            if current_speaker == "Customer" and current_turn.strip():
                turns.append(current_turn.strip())
            current_speaker = "Customer"
            current_turn = ""
        else:
            if current_speaker == "Customer":
                current_turn += " " + line
    
    # Add the last turn if it's from the customer
    if current_speaker == "Customer" and current_turn.strip():
        turns.append(current_turn.strip())
    
    # Filter out very short turns (less than 2 words)
    turns = [turn for turn in turns if len(turn.split()) > 1]
    
    return turns

def extract_customer_only(text: str) -> str:
    """
    Extract only the customer utterances from transcript text.
    
    Args:
        text: Raw transcript text
        
    Returns:
        String containing only customer utterances concatenated together
    """
    # Add spaces around "Agent:" and "Customer:" for consistent splitting
    text = re.sub(r'(?<![\s])(Agent:|Customer:)', r' \1', text)
    text = re.sub(r'(Agent:|Customer:)(?![\s])', r'\1 ', text)
    
    # Split on Agent/Customer markers
    parts = re.split(r'\s+(Agent:|Customer:)\s+', text)
    
    # First part might be empty or contain text before any marker
    if parts and not (parts[0].startswith('Agent:') or parts[0].startswith('Customer:')):
        parts = parts[1:]
    
    # Process in pairs (marker + text)
    customer_parts = []
    for i in range(0, len(parts), 2):
        if i+1 < len(parts):
            marker = parts[i]
            content = parts[i+1]
            if marker == 'Customer:':
                customer_parts.append(content.strip())
    
    # Join customer parts with a space
    return " ".join(customer_parts)

def apply_customer_only_filter(df: pd.DataFrame, content_column: str, customer_only: bool) -> pd.DataFrame:
    """
    Apply customer-only filter to a DataFrame of transcripts if requested.
    
    Args:
        df: DataFrame containing transcript data
        content_column: Name of column containing transcript content
        customer_only: Whether to filter for customer utterances only
        
    Returns:
        DataFrame with filtered content if customer_only is True, otherwise original DataFrame
    """
    if not customer_only:
        return df
    
    logging.info("Applying customer-only filter to transcripts")
    filtered_df = df.copy()
    
    for i, row in filtered_df.iterrows():
        try:
            text = row[content_column]
            if pd.isna(text) or not text:
                continue
                
            filtered_text = extract_customer_only(text)
            filtered_df.at[i, content_column] = filtered_text
            
            # Log a sample for verification (first few rows only)
            if i < 2:
                logging.info(f"Original text sample: {text[:100]}...")
                logging.info(f"Filtered text sample: {filtered_text[:100]}...")
        except Exception as e:
            logging.error(f"Error filtering customer utterances in row {i}: {e}")
    
    return filtered_df

def transform_transcripts(
    input_file: str,
    content_column: str = 'content',
    customer_only: bool = False,
    fresh: bool = False,
    inspect: bool = True,
    sample_size: Optional[int] = None
) -> Tuple[str, str, Dict[str, Any]]:
    """
    Transform transcript data into BERTopic-compatible format.
    
    Args:
        input_file: Path to input Parquet file
        content_column: Name of column containing transcript content
        customer_only: Whether to filter for customer utterances only
        fresh: Whether to force regeneration of cached files
        inspect: Whether to print sample data for inspection
        sample_size: Number of transcripts to sample from the dataset
        
    Returns:
        Tuple of (cached_parquet_path, text_file_path, preprocessing_info)
    """
    # Generate output file paths
    base_path = os.path.splitext(input_file)[0]
    suffix = "-customer-only" if customer_only else ""
    # Use temporary file for caching results
    import tempfile
    temp_dir = tempfile.mkdtemp(prefix=f"plexus_transform_{Path(input_file).stem}_")
    temp_base = Path(temp_dir) / Path(input_file).stem
    cached_parquet_path = f"{temp_base}-bertopic{suffix}.parquet"
    text_file_path = f"{temp_base}-bertopic{suffix}-text.txt"
    logging.info(f"Using temporary directory for output: {temp_dir}")
    
    # Check if cached files exist and fresh is False
    if not fresh and os.path.exists(cached_parquet_path) and os.path.exists(text_file_path):
        logging.info(f"Using cached files: {cached_parquet_path} and {text_file_path}")
        return cached_parquet_path, text_file_path
    
    # Load input data
    logging.info(f"Loading transcript data from {input_file}")
    df = pd.read_parquet(input_file)
    
    # Sample data if sample_size is provided
    if sample_size is not None and sample_size > 0 and sample_size < len(df):
        logging.info(f"Sampling {sample_size} transcripts from the dataset.")
        df = df.sample(n=sample_size, random_state=42)
    
    # Inspect data if requested
    if inspect:
        inspect_data(df, content_column)
    
    # Apply customer-only filter if requested
    if customer_only:
        df = apply_customer_only_filter(df, content_column, customer_only)
    
    # Extract speaking turns and create new rows
    transformed_rows = []
    for _, row in df.iterrows():
        speaking_turns = extract_speaking_turns(row[content_column])
        for turn in speaking_turns:
            # Create new row with speaking turn
            new_row = row.copy()
            new_row[content_column] = turn
            transformed_rows.append(new_row)
    
    # Create transformed DataFrame
    transformed_df = pd.DataFrame(transformed_rows)
    
    # Save cached Parquet file
    logging.info(f"Saving transformed data to {cached_parquet_path}")
    transformed_df.to_parquet(cached_parquet_path)
    
    # Save text file for BERTopic
    logging.info(f"Saving BERTopic text file to {text_file_path}")
    with open(text_file_path, 'w') as f:
        for turn in transformed_df[content_column]:
            f.write(f"{turn}\n")
    
    # Show first 20 examples of preprocessing output
    examples = []
    for i in range(min(20, len(transformed_df))):
        processed_row = transformed_df.iloc[i]
        example = processed_row[content_column][:500] + ("..." if len(processed_row[content_column]) > 500 else "")
        examples.append(example)
    
    preprocessing_info = {
        "method": "chunk",
        "examples": examples
    }
    
    return cached_parquet_path, text_file_path, preprocessing_info

async def _process_transcript_async(
    llm, prompt, text, provider, i, total_count
):
    """
    Process a single transcript asynchronously using LLM.
    
    Args:
        llm: Language model
        prompt: Prompt template
        text: Transcript text
        provider: LLM provider
        i: Transcript index
        total_count: Total number of transcripts
        
    Returns:
        LLM response text
    """
    logging.info(f"Processing transcript {i+1}/{total_count} for LLM transformation (non-itemize)")
    
    start_time = time.perf_counter()
    # Run LLM on transcript
    response = await llm.ainvoke(prompt.format(text=text))
    end_time = time.perf_counter()
    duration = end_time - start_time
    
    # Handle different response types based on provider
    if provider.lower() == 'openai' and hasattr(response, 'content'):
        response_text = response.content
    else:
        response_text = str(response) # Ensure string for Ollama like responses
    
    # Log the response (truncate if too long)
    max_log_length = 1000  # Limit log length to avoid flooding
    log_response = response_text
    if len(log_response) > max_log_length:
        log_response = log_response[:max_log_length] + "... [truncated]"
    
    logging.info(f"LLM Response {i+1}/{total_count} (took {duration:.2f}s):\n{log_response}")
    if duration < 0.1 and duration > 0: # Heuristic for likely cache hit, ignore 0 time for true first calls if super fast
        logging.info(f"  (Response for transcript {i+1}/{total_count} was very fast - likely from cache)")
    
    return response_text

async def _process_transcript_batch_async(
    llm, prompt, texts, rows, provider, batch_indices, total_count
):
    """
    Process a batch of transcripts asynchronously using LLM.
    
    Args:
        llm: Language model
        prompt: Prompt template
        texts: List of transcript texts
        rows: List of DataFrame rows
        provider: LLM provider
        batch_indices: List of indices for the batch
        total_count: Total number of transcripts
        
    Returns:
        List of (response text, row) pairs
    """
    results = []
    
    logging.info(f"Concurrently processing {len(texts)} transcripts in this batch call.")
    
    tasks = []
    for j, (text, idx) in enumerate(zip(texts, batch_indices)):
        task = _process_transcript_async(llm, prompt, text, provider, idx, total_count)
        tasks.append(task)
    
    responses = await asyncio.gather(*tasks, return_exceptions=True)
    
    for response, row in zip(responses, rows):
        results.append((response, row))
    
    gc.collect()
    return results

async def transform_transcripts_llm(
    input_file: str,
    content_column: str = 'content',
    prompt_template_file: str = None,
    prompt_template: str = None,
    model: str = 'gemma3:27b',
    provider: str = 'ollama',
    customer_only: bool = False,
    fresh: bool = False,
    inspect: bool = True,
    openai_api_key: str = None,
    sample_size: Optional[int] = None
) -> Tuple[str, str, Dict[str, Any]]:
    """
    Transform transcript data using a language model.
    
    This function processes each transcript through a language model
    to extract key information or summarize content before topic analysis.
    
    Args:
        input_file: Path to input Parquet file
        content_column: Name of column containing transcript content
        prompt_template_file: Path to LangChain prompt template file (JSON)
        model: Model to use for transformation (depends on provider)
        provider: LLM provider to use ('ollama' or 'openai')
        customer_only: Whether to filter for customer utterances only
        fresh: Whether to force regeneration of cached files
        inspect: Whether to print sample data for inspection
        openai_api_key: OpenAI API key (if provider is 'openai')
        sample_size: Number of transcripts to sample from the dataset
        
    Returns:
        Tuple of (cached_parquet_path, text_file_path, preprocessing_info)
    """
    result = await _transform_transcripts_llm_async(
        input_file=input_file, 
        content_column=content_column, 
        prompt_template_file=prompt_template_file,
        prompt_template=prompt_template, 
        model=model, 
        provider=provider, 
        customer_only=customer_only, 
        fresh=fresh, 
        inspect=inspect,
        openai_api_key=openai_api_key,
        sample_size=sample_size
    )
    return result

async def _transform_transcripts_llm_async(
    input_file: str,
    content_column: str = 'content',
    prompt_template_file: str = None,
    prompt_template: str = None,
    model: str = 'gemma3:27b',
    provider: str = 'ollama',
    customer_only: bool = False,
    fresh: bool = False,
    inspect: bool = True,
    openai_api_key: str = None,
    sample_size: Optional[int] = None
) -> Tuple[str, str, Dict[str, Any]]:
    """
    Async implementation of transform_transcripts_llm.
    """
    base_path = os.path.splitext(input_file)[0]
    suffix = "-customer-only" if customer_only else ""
    # Use temporary file for caching results
    import tempfile
    temp_dir = tempfile.mkdtemp(prefix=f"plexus_transform_llm_{Path(input_file).stem}_")
    temp_base = Path(temp_dir) / Path(input_file).stem
    cached_parquet_path = f"{temp_base}-bertopic-llm-{provider}{suffix}.parquet"
    text_file_path = f"{temp_base}-bertopic-llm-{provider}{suffix}-text.txt"
    logging.info(f"Using temporary directory for output: {temp_dir}")
    
    if not fresh and os.path.exists(cached_parquet_path) and os.path.exists(text_file_path):
        logging.info(f"Using cached files: {cached_parquet_path} and {text_file_path}")
        
        # Even when using cached data, we can still capture examples
        # by reading the preprocessed data and showing what the LLM output looks like
        try:
            # Load original data to show what was actually processed, not the LLM output
            try:
                original_df = pd.read_parquet(input_file)
                if customer_only:
                    original_df = apply_customer_only_filter(original_df, content_column, customer_only)
                if sample_size is not None and sample_size > 0 and sample_size < len(original_df):
                    original_df = original_df.sample(n=sample_size, random_state=42)
                
                examples = []
                for i in range(min(20, len(original_df))):
                    original_row = original_df.iloc[i]
                    example = original_row[content_column][:500] + ("..." if len(original_row[content_column]) > 500 else "")
                    examples.append(example)
            except Exception as e:
                logging.warning(f"Could not load original data for examples: {e}")
                # Fallback: Load processed data but clearly mark what it is
                cached_df = pd.read_parquet(cached_parquet_path)
                examples = []
                for i in range(min(5, len(cached_df))):
                    cached_row = cached_df.iloc[i]
                    example = f"[PROCESSED OUTPUT]: {cached_row[content_column][:200]}..."
                    examples.append(example)
            
            # Always determine what template was used, even from cached data
            if prompt_template_file:
                try:
                    with open(prompt_template_file, 'r') as f:
                        template_data = json.load(f)
                        template = template_data.get('template', 
                            """Summarize the key topics in this transcript in 3-5 concise bullet points:
                            
                            {text}
                            
                            Key topics:"""
                        )
                except Exception as e:
                    template = f"Error loading template from {prompt_template_file}: {e}"
            elif prompt_template:
                # Use inline prompt template if provided
                template = prompt_template
            else:
                template = """Summarize the key topics in this transcript in 3-5 concise bullet points:
                
                {text}
                
                Key topics:"""
            
            # Build preprocessing info from cached context
            preprocessing_info = {
                "method": "llm",
                "prompt_used": template,
                "llm_provider": provider,
                "llm_model": model,
                "examples": examples
            }
            
            return cached_parquet_path, text_file_path, preprocessing_info
            
        except Exception as e:
            logging.warning(f"Could not extract examples from cached data: {e}")
            # Fallback to minimal preprocessing info
            preprocessing_info = {
                "method": "llm", 
                "prompt_used": "Unknown (cached)",
                "llm_provider": provider,
                "llm_model": model,
                "examples": []
            }
            return cached_parquet_path, text_file_path, preprocessing_info
    
    logging.info(f"Loading transcript data from {input_file}")
    df = pd.read_parquet(input_file)
    
    # Apply customer-only filter if requested
    if customer_only:
        df = apply_customer_only_filter(df, content_column, customer_only)
    
    if sample_size is not None and sample_size > 0 and sample_size < len(df):
        logging.info(f"Sampling {sample_size} transcripts from the dataset.")
        df = df.sample(n=sample_size, random_state=42)
    
    if inspect:
        inspect_data(df, content_column)
    
    # Determine template: inline prompt takes precedence over file
    if prompt_template:
        # Convert Jinja2 template syntax to Python format string syntax
        template = prompt_template.replace('{{text}}', '{text}').replace('{{format_instructions}}', '{format_instructions}')
        logging.info("Using inline prompt template (converted from Jinja2 to Python format)")
    elif prompt_template_file:
        try:
            with open(prompt_template_file, 'r') as f:
                template_data = json.load(f)
                template = template_data.get('template', 
                    """Summarize the key topics in this transcript in 3-5 concise bullet points:
                    
                    {text}
                    
                    Key topics:"""
                )
            logging.info(f"Using prompt template from file: {prompt_template_file}")
        except Exception as e:
            logging.error(f"Error loading prompt template: {e}. Using default template.")
            template = """Summarize the key topics in this transcript in 3-5 concise bullet points:
            
            {text}
            
            Key topics:"""
    else:
        template = """Summarize the key topics in this transcript in 3-5 concise bullet points:
        
        {text}
        
        Key topics:"""
        logging.info("Using default prompt template")
    
    prompt = ChatPromptTemplate.from_template(template)
    
    if provider.lower() == 'ollama':
        try:
            from langchain.llms import Ollama
            llm = Ollama(model=model)
            logging.info(f"Initialized Ollama LLM with model: {model}")
        except ImportError:
            logging.error("Ollama package not installed. Install with: pip install ollama")
            raise
    elif provider.lower() == 'openai':
        try:
            from langchain_openai import ChatOpenAI
            api_key = openai_api_key or os.environ.get("OPENAI_API_KEY")
            if not api_key:
                logging.error("OpenAI API key not provided. Set OPENAI_API_KEY environment variable or pass openai_api_key parameter.")
                raise ValueError("OpenAI API key not provided")
            llm = ChatOpenAI(model=model, openai_api_key=api_key)
            logging.info(f"Initialized OpenAI LLM with model: {model}")
        except ImportError:
            logging.error("OpenAI package not installed. Install with: pip install langchain-openai")
            raise
    else:
        logging.error(f"Unsupported provider: {provider}. Use 'ollama' or 'openai'.")
        raise ValueError(f"Unsupported provider: {provider}. Use 'ollama' or 'openai'.")

    valid_texts = []
    valid_rows = []
    valid_indices = []
    
    for i, (_, row) in enumerate(df.iterrows()):
        text = row[content_column]
        if not text or pd.isna(text):
            continue
        valid_texts.append(text)
        valid_rows.append(row)
        valid_indices.append(i)
    
    transformed_rows = []
    preprocessing_examples = []
    
    if valid_texts:
        logging.info(f"Processing all {len(valid_texts)} valid transcripts concurrently.")
        
        all_results = await _process_transcript_batch_async(
            llm, prompt, valid_texts, valid_rows, provider, valid_indices, len(df)
        )
        
        with open(text_file_path, 'w') as f:
            for i, (response, row) in enumerate(all_results):
                if isinstance(response, Exception):
                    logging.error(f"Error processing transcript: {response}")
                    continue
                
                # Format the response text
                if provider.lower() == 'openai' and hasattr(response, 'content'):
                    response_text = response.content
                else:
                    response_text = response
                
                # Capture first 20 examples for preprocessing info
                if i < 20:
                    preprocessing_examples.append(response_text[:500] + ("..." if len(response_text) > 500 else ""))
                
                # Create new row with LLM response
                new_row = row.copy()
                new_row[content_column] = response_text
                transformed_rows.append(new_row)
                
                # Write to the file
                f.write(f"{response_text}\n")
    else:
        logging.info("No valid transcripts found to process.")
        with open(text_file_path, 'w') as f:
            pass 
    
    transformed_df = pd.DataFrame(transformed_rows)
    logging.info(f"Saving transformed data to {cached_parquet_path}")
    transformed_df.to_parquet(cached_parquet_path)
    logging.info(f"Saved LLM-processed text to {text_file_path}")
    
    # Create preprocessing info with examples and prompt
    preprocessing_info = {
        "method": "llm",
        "prompt_used": template,
        "llm_provider": provider,
        "llm_model": model,
        "examples": preprocessing_examples
    }
    
    gc.collect()
    return cached_parquet_path, text_file_path, preprocessing_info

class TranscriptItem(BaseModel):
    """Model for a single item extracted from a transcript."""
    question: str = Field(description="A direct question asked by the customer, quoted verbatim")
    category: str = Field(default="OTHER", description="Category of the question (SCHEDULING, PRICING, PRODUCT, SERVICE, CONTACT, OTHER)")

class TranscriptItems(BaseModel):
    """Model for a list of items extracted from a transcript."""
    items: List[TranscriptItem] = Field(description="List of items extracted from the transcript")

async def transform_transcripts_itemize(
    input_file: str,
    content_column: str = 'content',
    prompt_template_file: str = None,
    prompt_template: str = None,
    model: str = 'gemma3:27b',
    provider: str = 'ollama',
    customer_only: bool = False,
    fresh: bool = False,
    inspect: bool = True,
    max_retries: int = 2,
    retry_delay: float = 1.0,
    openai_api_key: str = None,
    sample_size: Optional[int] = None
) -> Tuple[str, str, Dict[str, Any]]:
    """
    Transform transcript data using a language model with itemization.
    
    This function processes each transcript through a language model
    to extract structured items, creating multiple rows per transcript.
    
    Args:
        input_file: Path to input Parquet file
        content_column: Name of column containing transcript content
        prompt_template_file: Path to LangChain prompt template file (JSON)
        model: Model to use for transformation (depends on provider)
        provider: LLM provider to use ('ollama' or 'openai')
        customer_only: Whether to filter for customer utterances only
        fresh: Whether to force regeneration of cached files
        inspect: Whether to print sample data for inspection
        max_retries: Maximum number of retries for parsing failures
        retry_delay: Delay between retries in seconds
        openai_api_key: OpenAI API key (if provider is 'openai')
        sample_size: Number of transcripts to sample from the dataset
        
    Returns:
        Tuple of (cached_parquet_path, text_file_path, preprocessing_info)
    """
    return await _transform_transcripts_itemize_async(
        input_file=input_file, 
        content_column=content_column, 
        prompt_template_file=prompt_template_file,
        prompt_template=prompt_template, 
        model=model, 
        provider=provider, 
        customer_only=customer_only,
        fresh=fresh, 
        inspect=inspect,
        max_retries=max_retries, 
        retry_delay=retry_delay, 
        openai_api_key=openai_api_key, 
        sample_size=sample_size
    )

async def _process_itemize_transcript_async(
    llm, prompt, formatted_prompt, text, parser, retry_parser, provider, i, total_count, max_retries, retry_delay
):
    """
    Process a single transcript asynchronously for itemization.
    
    Args:
        llm: Language model
        prompt: Prompt template
        formatted_prompt: Formatted prompt with instructions
        text: Transcript text
        parser: Pydantic parser
        retry_parser: Retry parser for handling errors
        provider: LLM provider
        i: Transcript index
        total_count: Total number of transcripts
        max_retries: Maximum number of retries for parsing failures
        retry_delay: Delay between retries in seconds
        
    Returns:
        Tuple of (success flag, parsed items or error message)
    """
    logging.info(f"========= Processing transcript {i+1}/{total_count} for itemization =========")
    
    retry_count = 0
    success = False
    parsed_items = None
    error_message = None
    
    while not success and retry_count <= max_retries:
        try:
            if retry_count > 0:
                logging.info(f"Retry {retry_count}/{max_retries} for transcript {i+1}")
                await asyncio.sleep(retry_delay)
                
            logging.info(f"SENDING PROMPT TO LLM FOR TRANSCRIPT {i+1}")
            
            start_time = time.perf_counter()
            raw_response = await llm.ainvoke(formatted_prompt)
            end_time = time.perf_counter()
            duration = end_time - start_time
            
            logging.info(f"COMPLETE RAW LLM RESPONSE FOR TRANSCRIPT {i+1} (took {duration:.2f}s):\n{raw_response}\n")
            if duration < 0.1 and duration > 0: # Heuristic for likely cache hit
                logging.info(f"  (LLM call for transcript {i+1}/{total_count} was very fast - likely from cache)")

            try:
                if provider.lower() == 'openai' and hasattr(raw_response, 'content'):
                    response_text = raw_response.content
                    logging.info(f"Extracted content from AIMessage: {response_text[:200]}...")
                else:
                    response_text = str(raw_response)
                    logging.info(f"Raw response content: {response_text[:200]}...")
                
                # First attempt: direct JSON parsing
                try:
                    json_data = json.loads(response_text)
                    logging.info(f"PARSED JSON DIRECTLY: {json_data}")
                    parsed_items = TranscriptItems(**json_data)
                    logging.info(f"SUCCESSFULLY CREATED PYDANTIC MODEL: {parsed_items}")
                    success = True
                except json.JSONDecodeError as json_err:
                    # If direct parsing fails, try extraction methods
                    logging.info(f"DIRECT JSON PARSING FAILED: {str(json_err)}")
                    
                    # The response text might already be in the current_response_text variable
                    # but let's make sure we're using the right one
                    current_response_text = response_text
                    
                    # Try multiple patterns for extracting JSON
                    json_extracted = False
                    
                    # Pattern 1: Standard markdown code block with json
                    if "```json" in current_response_text:
                        import re
                        match = re.search(r'```json\s*(.*?)\s*```', current_response_text, re.DOTALL)
                        if match:
                            extracted = match.group(1).strip()
                            logging.info(f"EXTRACTED JSON FROM CODE BLOCK: {extracted[:100]}...")
                            try:
                                json_data = json.loads(extracted)
                                logging.info(f"PARSED EXTRACTED JSON: {json_data}")
                                parsed_items = TranscriptItems(**json_data)
                                success = True
                                json_extracted = True
                            except Exception as je:
                                logging.error(f"FAILED TO PARSE EXTRACTED JSON: {je}")
                    
                    # Pattern 2: Any markdown code block (without specifying json)
                    if not json_extracted and "```" in current_response_text:
                        matches = re.findall(r'```(?:.*?)\s*(.*?)\s*```', current_response_text, re.DOTALL)
                        for match in matches:
                            try:
                                json_data = json.loads(match.strip())
                                logging.info(f"PARSED JSON FROM GENERIC CODE BLOCK: {json_data}")
                                parsed_items = TranscriptItems(**json_data)
                                success = True
                                json_extracted = True
                                break
                            except Exception:
                                continue
                    
                    # Pattern 3: Try to find JSON-like structure with curly braces
                    if not json_extracted:
                        try:
                            # Look for content between outermost curly braces
                            match = re.search(r'({.*})', current_response_text, re.DOTALL)
                            if match:
                                potential_json = match.group(1)
                                json_data = json.loads(potential_json)
                                logging.info(f"PARSED JSON FROM CURLY BRACES: {json_data}")
                                parsed_items = TranscriptItems(**json_data)
                                success = True
                                json_extracted = True
                        except Exception:
                            pass
                    
                    # Fall back to retry parser if all extraction attempts fail
                    if not json_extracted:
                        logging.info("ALL JSON EXTRACTION ATTEMPTS FAILED, ATTEMPTING RETRY PARSER")
                        parsed_items = await retry_parser.aparse_with_prompt(response_text, formatted_prompt)
                        logging.info("RETRY PARSER SUCCEEDED")
                        success = True
                
            except ValidationError as ve:
                logging.error(f"VALIDATION ERROR: {ve}")
                logging.info("ATTEMPTING RETRY PARSER")
                parsed_items = await retry_parser.aparse_with_prompt(response_text, formatted_prompt)
                logging.info("RETRY PARSER SUCCEEDED")
                success = True
            
        except Exception as e:
            logging.error(f"ERROR PROCESSING TRANSCRIPT {i+1} (attempt {retry_count+1}): {type(e).__name__}: {e}")
            # import traceback # Keep for debugging if needed, but can be noisy
            # logging.error(f"TRACEBACK:\\n{traceback.format_exc()}")
            retry_count += 1
            if retry_count > max_retries:
                logging.error(f"FAILED TO PROCESS AFTER {max_retries} RETRIES")
                error_message = f"ERROR: Failed to parse transcript after {max_retries} retries"
                break
    
    if success:
        # Enhanced debugging: Log the parsed items to detect repetition
        items_str = str(parsed_items)
        logging.info(f"SUCCESSFULLY PARSED ITEMS FOR TRANSCRIPT {i+1}: {items_str[:200]}...")
        
        # Check if this looks like template examples
        if "What type of program are you looking for" in items_str or "What did you mean by that" in items_str:
            logging.warning(f"⚠️ TRANSCRIPT {i+1} OUTPUT CONTAINS TEMPLATE EXAMPLES - POSSIBLE EXTRACTION FAILURE")
        
        return True, parsed_items
    else:
        return False, error_message

async def _process_itemize_batch_async(
    llm, prompt, rows, indices, parser, retry_parser, provider, total_count, max_retries, retry_delay, content_column
):
    """
    Process a batch of transcripts asynchronously for itemization.
    Args:
        llm: Language model
        prompt: Prompt template
        rows: List of DataFrame rows
        indices: List of indices for the batch
        parser: Pydantic parser
        retry_parser: Retry parser for handling errors
        provider: LLM provider
        total_count: Total number of transcripts
        max_retries: Maximum number of retries for parsing failures
        retry_delay: Delay between retries in seconds
        content_column: Name of column containing transcript content
    Returns:
        List of results
    """
    results = []
    logging.info(f"Concurrently processing {len(rows)} transcripts for itemization in this batch call.")

    tasks = []
    for j, (row, idx) in enumerate(zip(rows, indices)):
        text = row[content_column]
        
        # Enhanced debugging: Log the actual transcript content being processed
        logging.info(f"TRANSCRIPT {idx+1} CONTENT (first 200 chars): {text[:200]}...")
        if len(text) < 50:
            logging.warning(f"TRANSCRIPT {idx+1} IS VERY SHORT ({len(text)} chars): '{text}'")
        
        formatted_prompt = prompt.format(
            text=text, 
            format_instructions=parser.get_format_instructions()
        )
        
        # Enhanced debugging: Log the formatted prompt to see if transcript is included
        logging.info(f"FORMATTED PROMPT FOR TRANSCRIPT {idx+1} (first 300 chars): {formatted_prompt[:300]}...")
        
        task = _process_itemize_transcript_async(
            llm, prompt, formatted_prompt, text, parser, retry_parser, 
            provider, idx, total_count, max_retries, retry_delay
        )
        tasks.append(task)
    
    batch_results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Enhanced debugging: Check for identical outputs across transcripts
    successful_outputs = []
    for result_pair, row_item in zip(batch_results, rows):
        results.append((result_pair, row_item))
        
        # Collect successful outputs for comparison
        if isinstance(result_pair, tuple) and result_pair[0] == True:
            successful_outputs.append(str(result_pair[1]))
    
    # Check for repetition in outputs
    if len(successful_outputs) > 1:
        unique_outputs = set(successful_outputs)
        if len(unique_outputs) == 1:
            logging.error(f"🚨 CRITICAL ISSUE: ALL {len(successful_outputs)} TRANSCRIPTS PRODUCED IDENTICAL OUTPUT!")
            logging.error(f"Identical output: {successful_outputs[0][:300]}...")
        elif len(unique_outputs) < len(successful_outputs) * 0.5:  # If more than 50% repetition
            logging.warning(f"⚠️ HIGH REPETITION: {len(successful_outputs)} outputs, only {len(unique_outputs)} unique")
    
    gc.collect()
    return results

async def _transform_transcripts_itemize_async(
    input_file: str,
    content_column: str = 'content',
    prompt_template_file: str = None,
    prompt_template: str = None,
    model: str = 'gemma3:27b',
    provider: str = 'ollama',
    customer_only: bool = False,
    fresh: bool = False,
    inspect: bool = True,
    max_retries: int = 2,
    retry_delay: float = 1.0,
    openai_api_key: str = None,
    sample_size: Optional[int] = None
) -> Tuple[str, str, Dict[str, Any]]:
    """
    Async implementation of transform_transcripts_itemize.
    """
    base_path = os.path.splitext(input_file)[0]
    suffix = "-customer-only" if customer_only else ""
    # Use temporary file for caching results
    import tempfile
    temp_dir = tempfile.mkdtemp(prefix=f"plexus_transform_itemize_{Path(input_file).stem}_")
    temp_base = Path(temp_dir) / Path(input_file).stem
    cached_parquet_path = f"{temp_base}-bertopic-itemize-{provider}{suffix}.parquet"
    text_file_path = f"{temp_base}-bertopic-itemize-{provider}{suffix}-text.txt"
    logging.info(f"Using temporary directory for output: {temp_dir}")

    if not fresh and os.path.exists(cached_parquet_path) and os.path.exists(text_file_path):
        logging.info(f"Using cached files: {cached_parquet_path} and {text_file_path}")
        
        # Even when using cached data, we can still capture examples
        # by reading the original input data and showing what was actually processed
        try:
            # Load original data to show what was actually processed, not the LLM output
            try:
                original_df = pd.read_parquet(input_file)
                if customer_only:
                    original_df = apply_customer_only_filter(original_df, content_column, customer_only)
                if sample_size is not None and sample_size > 0 and sample_size < len(original_df):
                    original_df = original_df.sample(n=sample_size, random_state=42)
                
                examples = []
                for i in range(min(20, len(original_df))):
                    original_row = original_df.iloc[i]
                    example = original_row[content_column][:500] + ("..." if len(original_row[content_column]) > 500 else "")
                    examples.append(example)
            except Exception as e:
                logging.warning(f"Could not load original data for examples: {e}")
                # Fallback: Load processed data but clearly mark what it is
                cached_df = pd.read_parquet(cached_parquet_path)
                examples = []
                for i in range(min(5, len(cached_df))):
                    cached_row = cached_df.iloc[i]
                    example = f"[PROCESSED OUTPUT]: {cached_row[content_column][:200]}..."
                    examples.append(example)
            
            # Always determine what template was used, even from cached data
            if prompt_template_file:
                try:
                    with open(prompt_template_file, 'r') as f:
                        template_data = json.load(f)
                        template = template_data.get('template', 
                            """Summarize the key topics in this transcript in 3-5 concise bullet points:
                            
                            {text}
                            
                            Key topics:"""
                        )
                except Exception as e:
                    template = f"Error loading template from {prompt_template_file}: {e}"
            elif prompt_template:
                # Use inline prompt template if provided
                template = prompt_template
            else:
                template = """Summarize the key topics in this transcript in 3-5 concise bullet points:
                
                {text}
                
                Key topics:"""
            
            # Build preprocessing info from cached context
            preprocessing_info = {
                "method": "itemize",
                "prompt_used": template,
                "llm_provider": provider,
                "llm_model": model,
                "examples": examples
            }
            
            return cached_parquet_path, text_file_path, preprocessing_info
            
        except Exception as e:
            logging.warning(f"Could not extract examples from cached data: {e}")
            # Fallback to minimal preprocessing info
            preprocessing_info = {
                "method": "itemize",
                "prompt_used": "Unknown (cached)",
                "llm_provider": provider,
                "llm_model": model,
                "examples": []
            }
            return cached_parquet_path, text_file_path, preprocessing_info

    logging.info(f"Loading transcript data from {input_file}")
    df = pd.read_parquet(input_file)

    # Apply customer-only filter if requested
    if customer_only:
        df = apply_customer_only_filter(df, content_column, customer_only)
    
    if sample_size is not None and sample_size > 0 and sample_size < len(df):
        logging.info(f"Sampling {sample_size} transcripts from the dataset.")
        df = df.sample(n=sample_size, random_state=42)

    if inspect:
        inspect_data(df, content_column)

    parser = PydanticOutputParser(pydantic_object=TranscriptItems)
    logging.info(f"Parser format instructions:\n{parser.get_format_instructions()}")

    if provider.lower() == 'ollama':
        try:
            from langchain.llms import Ollama
            llm = Ollama(model=model)
            logging.info(f"Initialized Ollama LLM with model: {model}")
        except ImportError:
            logging.error("Ollama package not installed. Install with: pip install ollama")
            raise
    elif provider.lower() == 'openai':
        try:
            from langchain_openai import ChatOpenAI
            api_key = openai_api_key or os.environ.get("OPENAI_API_KEY")
            if not api_key:
                logging.error("OpenAI API key not provided. Set OPENAI_API_KEY environment variable or pass openai_api_key parameter.")
                raise ValueError("OpenAI API key not provided")
            llm = ChatOpenAI(model=model, openai_api_key=api_key)
            logging.info(f"Initialized OpenAI LLM with model: {model}")
        except ImportError:
            logging.error("OpenAI package not installed. Install with: pip install langchain-openai")
            raise
    else:
        logging.error(f"Unsupported provider: {provider}. Use 'ollama' or 'openai'.")
        raise ValueError(f"Unsupported provider: {provider}. Use 'ollama' or 'openai'.")

    retry_parser = RetryWithErrorOutputParser.from_llm(
        parser=parser,
        llm=llm,
        max_retries=max_retries
    )

    # Determine template: inline prompt takes precedence over file
    if prompt_template:
        # Convert Jinja2 template syntax to Python format string syntax
        template = prompt_template.replace('{{text}}', '{text}').replace('{{format_instructions}}', '{format_instructions}')
        logging.info("Using inline prompt template for itemization (converted from Jinja2 to Python format)")
    elif prompt_template_file:
        try:
            with open(prompt_template_file, 'r') as f:
                template_data = json.load(f)
                template = template_data.get('template', 
                    """Extract the main topics from this transcript. For each topic, provide a concise description.

{text}

{format_instructions}"""
                )
            logging.info(f"Using prompt template from file: {prompt_template_file}")
        except Exception as e:
            logging.error(f"Error loading prompt template: {e}. Using default template.")
            template = """Extract the main topics from this transcript. For each topic, provide a concise description.

{text}

{format_instructions}"""
    else:
        template = """Extract the main topics from this transcript. For each topic, provide a concise description.

{text}

{format_instructions}"""
        logging.info("Using default prompt template for itemization")
    
    prompt = ChatPromptTemplate.from_template(template)
    logging.info(f"Using prompt template:\n{template}")

    valid_rows = []
    valid_indices = []
    
    for i, (_, row) in enumerate(df.iterrows()):
        text = row[content_column]
        if not text or pd.isna(text):
            continue
        valid_rows.append(row)
        valid_indices.append(i)
    
    transformed_rows = []
    preprocessing_examples = []
    
    if valid_rows:
        logging.info(f"Processing all {len(valid_rows)} valid transcripts concurrently for itemization.")
        
        all_results = await _process_itemize_batch_async(
            llm, prompt, valid_rows, valid_indices, parser, retry_parser, 
            provider, len(df), max_retries, retry_delay, content_column
        )
        
        with open(text_file_path, 'w') as f:
            for i, (result_pair, row) in enumerate(all_results):
                if isinstance(result_pair, Exception):
                    logging.error(f"Error processing transcript: {result_pair}")
                    error_text = f"ERROR: Unexpected error: {str(result_pair)}"
                    new_row = row.copy()
                    new_row[content_column] = error_text
                    transformed_rows.append(new_row)
                    f.write(f"{error_text}\n")
                    continue
                success, data = result_pair
                
                # Capture first 20 examples for preprocessing info
                if i < 20:
                    if success:
                        # For successful itemization, show the parsed items
                        after_text = "\n".join([f"{item.category}: {item.question}" for item in data.items])
                    else:
                        # For failed itemization, show the error
                        after_text = str(data)
                    preprocessing_examples.append(after_text[:500] + ("..." if len(after_text) > 500 else ""))
                
                if success:
                    logging.info(f"SUCCESSFULLY PARSED {len(data.items)} ITEMS:")
                    for idx, item in enumerate(data.items):
                        logging.info(f"ITEM {idx+1}: {item.category}: {item.question}")
                    for item in data.items:
                        # Create new row with item data
                        new_row = row.copy()
                        new_row['category'] = item.category
                        new_row['question'] = item.question
                        combined_text = item.category + ": " + item.question
                        new_row[content_column] = combined_text
                        transformed_rows.append(new_row)
                        
                        # Write to the text file
                        f.write(f"{item.category}: {item.question}\n")
                else:
                    new_row = row.copy()
                    new_row[content_column] = data
                    transformed_rows.append(new_row)
                    f.write(f"{data}\n")
    else:
        logging.info("No valid transcripts found to process for itemization.")
        with open(text_file_path, 'w') as f:
            pass

    transformed_df = pd.DataFrame(transformed_rows)
    logging.info(f"Saving transformed data to {cached_parquet_path}")
    transformed_df.to_parquet(cached_parquet_path)
    logging.info(f"Saved itemized text to {text_file_path}")
    
    # Create preprocessing info with examples and prompt
    preprocessing_info = {
        "method": "itemize",
        "prompt_used": template,
        "llm_provider": provider,
        "llm_model": model,
        "examples": preprocessing_examples
    }
    
    gc.collect()
    return cached_parquet_path, text_file_path, preprocessing_info 