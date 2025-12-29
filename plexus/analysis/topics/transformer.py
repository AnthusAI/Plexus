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
from tqdm.asyncio import tqdm
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field, ValidationError
# Import retry parser - use OutputFixingParser as RetryWithErrorOutputParser is deprecated
from langchain.output_parsers import OutputFixingParser
from langchain_core.globals import set_llm_cache
from langchain_community.cache import SQLiteCache

# Load environment variables from .env file
try:
    import dotenv
    # Try to find .env file in common locations
    env_paths = [
        '.env',
        os.path.join(os.path.dirname(__file__), '../../../.env'),  # From topics/ to project root
        '/Users/ryan.porter/Projects/Plexus/.env'  # Absolute path as fallback
    ]
    
    for env_path in env_paths:
        if os.path.exists(env_path):
            dotenv.load_dotenv(env_path, override=True)
            break
except ImportError:
    pass  # dotenv not available, environment variables must be set externally

# Configure logging
logger = logging.getLogger(__name__)

# Silence HTTP request logging from OpenAI/httpx
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("openai._base_client").setLevel(logging.WARNING)

# Initialize and set the Langchain LLM cache globally
# Cache file will be stored inside the project's tmp directory
cache_dir_path = Path("tmp/langchain.db")
cache_db_file_path = cache_dir_path / "topics_llm_cache.db"

try:
    # Ensure the cache directory exists
    cache_dir_path.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Attempting to initialize Langchain LLM SQLite cache at {cache_db_file_path}")
    set_llm_cache(SQLiteCache(database_path=str(cache_db_file_path))) # Pass the full file path
    logger.debug(f"Langchain LLM SQLite cache initialized successfully at {cache_db_file_path}.")
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
) -> Tuple[str, str, Dict[str, Any], Optional[pd.DataFrame]]:
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
        Tuple of (cached_parquet_path, text_file_path, preprocessing_info, transformed_df)
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
        # Load the cached dataframe and return it
        transformed_df = pd.read_parquet(cached_parquet_path)
        # Return minimal preprocessing info for cached chunk method
        preprocessing_info = {
            "method": "chunk",
            "examples": [],
            "hit_rate_stats": {
                "total_processed": 0,
                "successful_extractions": 0,
                "failed_extractions": 0,
                "hit_rate_percentage": 0.0
            }
        }
        return cached_parquet_path, text_file_path, preprocessing_info, transformed_df
    
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
            # Preserve ids column if it exists
            if 'ids' in row.index and pd.notna(row.get('ids')):
                new_row['ids'] = row['ids']
                logging.debug(f"🔍 ID_DEBUG: Preserved ID '{row['ids']}' for speaking turn")
            transformed_rows.append(new_row)
    
    # Create transformed DataFrame
    transformed_df = pd.DataFrame(transformed_rows)
    logging.info(f"🔍 ALIGNMENT_CHECK: Created transformed_df with {len(transformed_df)} rows from {len(df)} original transcripts")
    
    # Check for ID column
    has_ids = 'ids' in transformed_df.columns
    logging.info(f"🔍 ID_DEBUG: transformed_df has ID column: {has_ids}")
    if has_ids:
        non_null_ids = transformed_df['ids'].notna().sum()
        logging.info(f"🔍 ID_DEBUG: {non_null_ids}/{len(transformed_df)} rows have non-null IDs")
    
    # Ensure content column is consistently named 'text' for BERTopic compatibility
    if content_column != 'text':
        transformed_df = transformed_df.rename(columns={content_column: 'text'})
        logging.info(f"Renamed content column from '{content_column}' to 'text' for consistency")
    
    logging.info(f"🔍 ALIGNMENT_CHECK: Final transformed_df columns: {list(transformed_df.columns)}")
    
    # Save cached Parquet file
    logging.info(f"Saving transformed data to {cached_parquet_path}")
    transformed_df.to_parquet(cached_parquet_path)
    
    # Save text file for BERTopic
    logging.info(f"Saving BERTopic text file to {text_file_path}")
    with open(text_file_path, 'w') as f:
        for turn in transformed_df['text']:  # Use 'text' column consistently
            f.write(f"{turn}\n")
    
    # Additional debugging: verify alignment between parquet and text file
    logging.info("🔍 DEBUGGING: Verifying alignment between parquet and text file...")
    with open(text_file_path, 'r') as f:
        text_file_lines = [line.strip() for line in f if line.strip()]
    
    logging.info(f"🔍 DEBUGGING: Parquet has {len(transformed_df)} rows, text file has {len(text_file_lines)} lines")
    
    # Check first few entries for alignment
    alignment_ok = True
    for i in range(min(3, len(transformed_df), len(text_file_lines))):
        parquet_text = str(transformed_df.iloc[i]['text']).strip()
        file_text = text_file_lines[i].strip()
        if parquet_text != file_text:
            logging.error(f"🔍 DEBUGGING: Alignment mismatch at index {i}")
            logging.error(f"   Parquet: '{parquet_text[:100]}...'")
            logging.error(f"   File:    '{file_text[:100]}...'")
            alignment_ok = False
            break
    
    if alignment_ok:
        logging.info("🔍 DEBUGGING: ✅ Parquet and text file alignment verified")
    else:
        logging.error("🔍 DEBUGGING: ❌ Parquet and text file are misaligned!")
    
    # Show first 20 examples of preprocessing output
    examples = []
    for i in range(min(20, len(transformed_df))):
        processed_row = transformed_df.iloc[i]
        example = processed_row['text'][:500] + ("..." if len(processed_row['text']) > 500 else "")
        examples.append(example)
    
    # Calculate hit rate statistics for chunk method
    # For chunk method, we consider all non-empty speaking turns as successful
    total_processed = len(df)
    successful_extractions = len(transformed_df)
    failed_extractions = 0  # Chunk method doesn't really fail, it just extracts speaking turns
    hit_rate = (successful_extractions / total_processed * 100) if total_processed > 0 else 0
    
    preprocessing_info = {
        "method": "chunk",
        "examples": examples,
        "hit_rate_stats": {
            "total_processed": total_processed,
            "successful_extractions": successful_extractions,
            "failed_extractions": failed_extractions,
            "hit_rate_percentage": round(hit_rate, 1)
        }
    }
    
    return cached_parquet_path, text_file_path, preprocessing_info, transformed_df

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
    logger.debug(f"Processing transcript {i+1}/{total_count} for LLM transformation (non-itemize)")
    
    start_time = time.perf_counter()
    # Run LLM on transcript - always use Jinja2 template formatting
    formatted_prompt_obj = prompt.format_prompt(text=text)
    formatted_prompt = formatted_prompt_obj.to_string()
    response = await llm.ainvoke(formatted_prompt)
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
    
    logger.debug(f"LLM Response {i+1}/{total_count} (took {duration:.2f}s): {len(response_text)} chars")
    if duration < 0.1 and duration > 0: # Heuristic for likely cache hit, ignore 0 time for true first calls if super fast
        logger.debug(f"  (Response for transcript {i+1}/{total_count} was very fast - likely from cache)")
    
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
    
    logger.info(f"Processing batch of {len(texts)} transcripts ({batch_indices[0]+1}-{batch_indices[-1]+1} of {total_count})")
    
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
) -> Tuple[str, str, Dict[str, Any], Optional[pd.DataFrame]]:
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
        Tuple of (cached_parquet_path, text_file_path, preprocessing_info, transformed_df)
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
) -> Tuple[str, str, Dict[str, Any], Optional[pd.DataFrame]]:
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
        
        # Load cached dataframe
        transformed_df = pd.read_parquet(cached_parquet_path)

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
                for i in range(min(20, len(cached_df))):
                    cached_row = cached_df.iloc[i]
                    example = f"[PROCESSED OUTPUT]: {cached_row[content_column][:500]}..."
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
            
            # Try to load hit rate stats from metadata file
            hit_rate_stats = {
                "total_processed": 0,
                "successful_extractions": 0,
                "failed_extractions": 0,
                "hit_rate_percentage": 0.0
            }
            
            try:
                metadata_path = f"{cached_parquet_path}.metadata.json"
                if os.path.exists(metadata_path):
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                        if "hit_rate_stats" in metadata:
                            hit_rate_stats = metadata["hit_rate_stats"]
                            logging.info(f"Loaded hit rate stats from metadata: {hit_rate_stats['hit_rate_percentage']}% success rate")
            except Exception as e:
                logging.warning(f"Failed to load hit rate metadata: {e}")
            
            # Build preprocessing info from cached context
            preprocessing_info = {
                "method": "llm",
                "prompt_used": template,
                "llm_provider": provider,
                "llm_model": model,
                "examples": examples,
                "hit_rate_stats": hit_rate_stats
            }
            
            return cached_parquet_path, text_file_path, preprocessing_info, transformed_df
            
        except Exception as e:
            logging.warning(f"Could not extract examples from cached data: {e}")
            # Fallback to minimal preprocessing info
            preprocessing_info = {
                "method": "llm", 
                "prompt_used": "Unknown (cached)",
                "llm_provider": provider,
                "llm_model": model,
                "examples": [],
                "hit_rate_stats": {
                    "total_processed": 0,
                    "successful_extractions": 0,
                    "failed_extractions": 0,
                    "hit_rate_percentage": 0.0
                }
            }
            return cached_parquet_path, text_file_path, preprocessing_info, transformed_df
    
    logging.info(f"Loading transcript data from {input_file}")
    df = pd.read_parquet(input_file)
    
    # Apply customer-only filter if requested
    if customer_only:
        df = apply_customer_only_filter(df, content_column, customer_only)
    
    if sample_size is not None and sample_size > 0 and sample_size < len(df):
        logging.info(f"Sampling {sample_size} transcripts from the dataset.")
        df = df.sample(n=sample_size, random_state=42).reset_index(drop=True)
    
    if inspect:
        inspect_data(df, content_column)
    
    # Use the template from configuration
    if prompt_template:
        template = prompt_template
        logging.info("Using inline prompt template from configuration")
    elif prompt_template_file:
        try:
            with open(prompt_template_file, 'r') as f:
                template_data = json.load(f)
                template = template_data.get('template')
                if not template:
                    raise ValueError("Template file must contain a 'template' key")
            logging.info(f"Using prompt template from file: {prompt_template_file}")
        except Exception as e:
            logging.error(f"Error loading prompt template: {e}")
            raise
    else:
        raise ValueError("No prompt template provided. Must specify either prompt_template or prompt_template_file")
    
    # Always use Jinja2 templates
    logging.info("Using Jinja2 template format")
    prompt = ChatPromptTemplate.from_template(template, template_format="jinja2")
    
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
                # Preserve ids column if it exists
                if 'ids' in row.index and pd.notna(row.get('ids')):
                    new_row['ids'] = row['ids']
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
    # Calculate hit rate statistics for LLM method
    total_processed = len(all_results) if valid_texts else 0
    successful_extractions = 0
    failed_extractions = 0
    
    for response, row in all_results:
        if isinstance(response, Exception):
            failed_extractions += 1
        else:
            # For LLM method, consider any non-empty response as successful
            if provider.lower() == 'openai' and hasattr(response, 'content'):
                response_text = response.content
            else:
                response_text = str(response)
            
            if response_text and response_text.strip():
                successful_extractions += 1
            else:
                failed_extractions += 1
    
    hit_rate = (successful_extractions / total_processed * 100) if total_processed > 0 else 0
    
    preprocessing_info = {
        "method": "llm",
        "prompt_used": template,
        "llm_provider": provider,
        "llm_model": model,
        "examples": preprocessing_examples,
        "hit_rate_stats": {
            "total_processed": total_processed,
            "successful_extractions": successful_extractions,
            "failed_extractions": failed_extractions,
            "hit_rate_percentage": round(hit_rate, 1)
        }
    }
    
    # Save hit rate stats to a metadata file for future cached runs
    try:
        metadata_path = f"{cached_parquet_path}.metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump({
                "hit_rate_stats": preprocessing_info["hit_rate_stats"],
                "method": "llm",
                "llm_provider": provider,
                "llm_model": model,
                "prompt_used": template
            }, f, indent=2)
        logging.info(f"Saved hit rate metadata to {metadata_path}")
    except Exception as e:
        logging.warning(f"Failed to save hit rate metadata: {e}")
    
    gc.collect()
    return cached_parquet_path, text_file_path, preprocessing_info, transformed_df

class TranscriptItem(BaseModel):
    """Model for a single item extracted from a transcript."""
    question: str = Field(description="A direct question asked by the customer, quoted verbatim")
    category: str = Field(default="OTHER", description="Category of the question (SCHEDULING, PRICING, PRODUCT, SERVICE, CONTACT, OTHER)")

class TranscriptItems(BaseModel):
    """Model for a list of items extracted from a transcript."""
    items: List[TranscriptItem] = Field(description="List of items extracted from the transcript")

class SimpleTranscriptItems(BaseModel):
    """Model for a simple list of strings extracted from a transcript."""
    items: List[str] = Field(description="List of questions/items extracted from the transcript")

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
    simple_format: bool = True,
    retry_delay: float = 1.0,
    openai_api_key: str = None,
    sample_size: Optional[int] = None,
    max_workers: Optional[int] = None
) -> Tuple[str, str, Dict[str, Any], Optional[pd.DataFrame]]:
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
        Tuple of (cached_parquet_path, text_file_path, preprocessing_info, transformed_df)
    """
    result = await _transform_transcripts_itemize_async(
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
        simple_format=simple_format,
        retry_delay=retry_delay, 
        openai_api_key=openai_api_key, 
        sample_size=sample_size,
        max_workers=max_workers
    )
    return result

async def _process_itemize_transcript_async(
    llm, prompt, formatted_prompt, text, parser, retry_parser, provider, i, total_count, max_retries, retry_delay, simple_format
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
    logger.debug(f"Processing transcript {i+1}/{total_count} for itemization")
    
    retry_count = 0
    success = False
    parsed_items = None
    error_message = None
    
    while not success and retry_count <= max_retries:
        try:
            if retry_count > 0:
                logging.info(f"Retry {retry_count}/{max_retries} for transcript {i+1}")
                await asyncio.sleep(retry_delay)
                
            logger.debug(f"Sending prompt to LLM for transcript {i+1}")
            
            try:
                start_time = time.perf_counter()
                raw_response = await llm.ainvoke(formatted_prompt)
                end_time = time.perf_counter()
                duration = end_time - start_time
                logger.debug(f"LLM call completed successfully for transcript {i+1}")
            except Exception as e:
                logger.error(f"Error in LLM call for transcript {i+1}: {type(e).__name__}: {e}")
                raise
            
            logger.debug(f"LLM response for transcript {i+1} (took {duration:.2f}s): {len(str(raw_response))} chars")
            if duration < 0.1 and duration > 0: # Heuristic for likely cache hit
                logger.debug(f"  (LLM call for transcript {i+1}/{total_count} was very fast - likely from cache)")

            try:
                if provider.lower() == 'openai' and hasattr(raw_response, 'content'):
                    response_text = raw_response.content
                    logger.debug(f"Extracted content from AIMessage: {len(response_text)} chars")
                else:
                    response_text = str(raw_response)
                    logger.debug(f"Raw response content: {len(response_text)} chars")
                
                # First attempt: direct JSON parsing
                try:
                    json_data = json.loads(response_text)
                    logger.debug(f"Parsed JSON directly with {len(json_data)} keys")
                    logger.debug(f"simple_format flag: {simple_format}")
                    logger.debug(f"First few items in response: {json_data.get('items', [])[:3] if 'items' in json_data else 'No items key'}")
                    
                    # Auto-detect format by checking the structure of the first item
                    if 'items' in json_data and len(json_data['items']) > 0:
                        first_item = json_data['items'][0]
                        is_simple_format = isinstance(first_item, str)
                        logger.debug(f"Auto-detected format: {'simple' if is_simple_format else 'complex'} (first item type: {type(first_item).__name__})")
                        
                        if is_simple_format:
                            # Simple format: items are strings
                            parsed_items = SimpleTranscriptItems(**json_data)
                            logger.debug(f"Successfully created simple Pydantic model")
                            success = True
                        else:
                            # Complex format: items are objects with category/question
                            if simple_format:
                                # User wanted simple but got complex - convert it
                                # Try to extract meaningful text from complex objects
                                simple_items = []
                                for item in json_data['items']:
                                    if isinstance(item, dict):
                                        # Try multiple possible text fields
                                        text_content = None
                                        for field in ['question', 'customer_needs', 'customer_question', 'text', 'content', 'summary']:
                                            if field in item and item[field]:
                                                text_content = str(item[field])
                                                break
                                        
                                        # If no specific field found, try to create a meaningful string
                                        if not text_content:
                                            # Join all string values from the object
                                            text_parts = []
                                            for key, value in item.items():
                                                if isinstance(value, str) and value.strip():
                                                    text_parts.append(value.strip())
                                            text_content = " | ".join(text_parts) if text_parts else str(item)
                                        
                                        simple_items.append(text_content)
                                    else:
                                        simple_items.append(str(item))
                                
                                parsed_items = SimpleTranscriptItems(items=simple_items)
                                logger.debug(f"Successfully converted complex to simple format: {len(simple_items)} items")
                                success = True
                            else:
                                # User wanted complex and got complex - use as is
                                parsed_items = TranscriptItems(**json_data)
                                logger.debug(f"Successfully created complex Pydantic model")
                                success = True
                    else:
                        logger.debug("No items found in JSON data")
                        # Try with the requested format
                        if simple_format:
                            parsed_items = SimpleTranscriptItems(**json_data)
                        else:
                            parsed_items = TranscriptItems(**json_data)
                        success = True
                except json.JSONDecodeError as json_err:
                    # If direct parsing fails, try extraction methods
                    logger.debug(f"Direct JSON parsing failed: {str(json_err)}")
                    
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
                            logger.debug(f"Extracted JSON from code block: {len(extracted)} chars")
                            try:
                                json_data = json.loads(extracted)
                                logger.debug(f"Parsed extracted JSON with {len(json_data)} keys")
                                
                                # Auto-detect format by checking the structure of the first item
                                if 'items' in json_data and len(json_data['items']) > 0:
                                    first_item = json_data['items'][0]
                                    is_simple_format = isinstance(first_item, str)
                                    
                                    if is_simple_format:
                                        parsed_items = SimpleTranscriptItems(**json_data)
                                        logger.debug(f"Successfully created simple Pydantic model from extracted JSON")
                                    else:
                                        if simple_format:
                                            # Convert complex to simple
                                            # Try to extract meaningful text from complex objects
                                            simple_items = []
                                            for item in json_data['items']:
                                                if isinstance(item, dict):
                                                    # Try multiple possible text fields
                                                    text_content = None
                                                    for field in ['question', 'customer_needs', 'customer_question', 'text', 'content', 'summary']:
                                                        if field in item and item[field]:
                                                            text_content = str(item[field])
                                                            break
                                                    
                                                    # If no specific field found, try to create a meaningful string
                                                    if not text_content:
                                                        # Join all string values from the object
                                                        text_parts = []
                                                        for key, value in item.items():
                                                            if isinstance(value, str) and value.strip():
                                                                text_parts.append(value.strip())
                                                        text_content = " | ".join(text_parts) if text_parts else str(item)
                                                    
                                                    simple_items.append(text_content)
                                                else:
                                                    simple_items.append(str(item))
                                            
                                            parsed_items = SimpleTranscriptItems(items=simple_items)
                                            logger.debug(f"Successfully converted complex to simple format from extracted JSON: {len(simple_items)} items")
                                        else:
                                            parsed_items = TranscriptItems(**json_data)
                                            logger.debug(f"Successfully created complex Pydantic model from extracted JSON")
                                else:
                                    # No items, try with requested format
                                    if simple_format:
                                        parsed_items = SimpleTranscriptItems(**json_data)
                                    else:
                                        parsed_items = TranscriptItems(**json_data)
                                
                                success = True
                                json_extracted = True
                            except Exception as je:
                                logger.debug(f"Failed to parse extracted JSON: {je}")
                    
                    # Pattern 2: Any markdown code block (without specifying json)
                    if not json_extracted and "```" in current_response_text:
                        matches = re.findall(r'```(?:.*?)\s*(.*?)\s*```', current_response_text, re.DOTALL)
                        for match in matches:
                            try:
                                json_data = json.loads(match.strip())
                                logger.debug(f"Parsed JSON from generic code block with {len(json_data)} keys")
                                
                                # Auto-detect format by checking the structure of the first item
                                if 'items' in json_data and len(json_data['items']) > 0:
                                    first_item = json_data['items'][0]
                                    is_simple_format = isinstance(first_item, str)
                                    
                                    if is_simple_format:
                                        parsed_items = SimpleTranscriptItems(**json_data)
                                        logger.debug(f"Successfully created simple Pydantic model from generic code block")
                                    else:
                                        if simple_format:
                                            # Convert complex to simple
                                            # Try to extract meaningful text from complex objects
                                            simple_items = []
                                            for item in json_data['items']:
                                                if isinstance(item, dict):
                                                    # Try multiple possible text fields
                                                    text_content = None
                                                    for field in ['question', 'customer_needs', 'customer_question', 'text', 'content', 'summary']:
                                                        if field in item and item[field]:
                                                            text_content = str(item[field])
                                                            break
                                                    
                                                    # If no specific field found, try to create a meaningful string
                                                    if not text_content:
                                                        # Join all string values from the object
                                                        text_parts = []
                                                        for key, value in item.items():
                                                            if isinstance(value, str) and value.strip():
                                                                text_parts.append(value.strip())
                                                        text_content = " | ".join(text_parts) if text_parts else str(item)
                                                    
                                                    simple_items.append(text_content)
                                                else:
                                                    simple_items.append(str(item))
                                            
                                            parsed_items = SimpleTranscriptItems(items=simple_items)
                                            logger.debug(f"Successfully converted complex to simple format from generic code block: {len(simple_items)} items")
                                        else:
                                            parsed_items = TranscriptItems(**json_data)
                                            logger.debug(f"Successfully created complex Pydantic model from generic code block")
                                else:
                                    # No items, try with requested format
                                    if simple_format:
                                        parsed_items = SimpleTranscriptItems(**json_data)
                                    else:
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
                                logger.debug(f"Parsed JSON from curly braces with {len(json_data)} keys")
                                
                                # Auto-detect format by checking the structure of the first item
                                if 'items' in json_data and len(json_data['items']) > 0:
                                    first_item = json_data['items'][0]
                                    is_simple_format = isinstance(first_item, str)
                                    
                                    if is_simple_format:
                                        parsed_items = SimpleTranscriptItems(**json_data)
                                        logger.debug(f"Successfully created simple Pydantic model from curly braces")
                                    else:
                                        if simple_format:
                                            # Convert complex to simple
                                            # Try to extract meaningful text from complex objects
                                            simple_items = []
                                            for item in json_data['items']:
                                                if isinstance(item, dict):
                                                    # Try multiple possible text fields
                                                    text_content = None
                                                    for field in ['question', 'customer_needs', 'customer_question', 'text', 'content', 'summary']:
                                                        if field in item and item[field]:
                                                            text_content = str(item[field])
                                                            break
                                                    
                                                    # If no specific field found, try to create a meaningful string
                                                    if not text_content:
                                                        # Join all string values from the object
                                                        text_parts = []
                                                        for key, value in item.items():
                                                            if isinstance(value, str) and value.strip():
                                                                text_parts.append(value.strip())
                                                        text_content = " | ".join(text_parts) if text_parts else str(item)
                                                    
                                                    simple_items.append(text_content)
                                                else:
                                                    simple_items.append(str(item))
                                            
                                            parsed_items = SimpleTranscriptItems(items=simple_items)
                                            logger.debug(f"Successfully converted complex to simple format from curly braces: {len(simple_items)} items")
                                        else:
                                            parsed_items = TranscriptItems(**json_data)
                                            logger.debug(f"Successfully created complex Pydantic model from curly braces")
                                else:
                                    # No items, try with requested format
                                    if simple_format:
                                        parsed_items = SimpleTranscriptItems(**json_data)
                                    else:
                                        parsed_items = TranscriptItems(**json_data)
                                
                                success = True
                                json_extracted = True
                        except Exception:
                            pass
                    
                    # Fall back to retry parser if all extraction attempts fail
                    if not json_extracted:
                        logger.debug("All JSON extraction attempts failed, attempting retry parser")
                        # Create a proper prompt value for retry parser
                        from langchain_core.prompt_values import StringPromptValue
                        prompt_value = StringPromptValue(text=formatted_prompt)
                        parsed_items = retry_parser.parse_with_prompt(response_text, prompt_value)
                        logger.debug("Retry parser succeeded")
                        success = True
                
            except ValidationError as ve:
                logger.debug(f"Validation error: {ve}")
                logger.debug("Attempting retry parser")
                # Create a proper prompt value for retry parser
                from langchain_core.prompt_values import StringPromptValue
                prompt_value = StringPromptValue(text=formatted_prompt)
                parsed_items = retry_parser.parse_with_prompt(response_text, prompt_value)
                logger.debug("Retry parser succeeded")
                success = True
            
        except Exception as e:
            logging.error(f"ERROR PROCESSING TRANSCRIPT {i+1} (attempt {retry_count+1}): {type(e).__name__}: {e}")
            import traceback # Keep for debugging if needed, but can be noisy
            logging.error(f"TRACEBACK:\n{traceback.format_exc()}")
            retry_count += 1
            if retry_count > max_retries:
                logging.error(f"FAILED TO PROCESS AFTER {max_retries} RETRIES")
                error_message = f"ERROR: Failed to parse transcript after {max_retries} retries"
                break
    
    if success:
        # Enhanced debugging: Log the parsed items to detect repetition
        items_str = str(parsed_items)
        logger.debug(f"Successfully parsed items for transcript {i+1}: {len(items_str)} chars")
        
        # Check if this looks like template examples
        if "What type of program are you looking for" in items_str or "What did you mean by that" in items_str:
            logger.warning(f"⚠️ Transcript {i+1} output contains template examples - possible extraction failure")
        
        return True, parsed_items
    else:
        return False, error_message

async def _process_itemize_batch_async(
    llm, prompt, rows, indices, parser, retry_parser, provider, total_count, max_retries, retry_delay, content_column, simple_format, max_workers=None
):
    """Process a batch of transcripts asynchronously with concurrency limits to prevent deadlocks.
    
    Args:
        max_workers: Maximum number of concurrent workers. If None, uses provider-specific defaults.
                     For OpenAI: default 50 (can handle high concurrency with rate limits)
                     For others: default 100 (local providers like Ollama)
    """
    
    # Set concurrency limits based on provider or use custom value
    if max_workers is not None:
        max_concurrent = max_workers
        batch_delay = 0.05
        logger.info(f"Using custom max_workers: {max_concurrent}")
    elif provider.lower() == 'openai':
        max_concurrent = 50  # OpenAI can handle much higher concurrency with rate limiting
        batch_delay = 0.1    # Small delay between batches to respect rate limits
    else:
        max_concurrent = 100  # Higher limit for local providers like Ollama
        batch_delay = 0.05
    
    logger.info(f"Processing {len(rows)} transcripts with max concurrency of {max_concurrent}")

    # Helper coroutine to keep result and row paired
    async def process_and_pair(coro, row_data, transcript_index):
        try:
            result = await coro
            return result, row_data, transcript_index
        except Exception as e:
            logger.error(f"An exception was caught from transcript {transcript_index} processing coroutine: {e}")
            return {'error': str(e)}, row_data, transcript_index

    # Prepare all work items
    work_items = []
    for i, row in zip(indices, rows):
        text_to_process = row[content_column]

        if not isinstance(text_to_process, str):
            text_to_process = str(text_to_process) if text_to_process is not None else ""
        
        try:
            # The key for format_prompt MUST match the placeholder in the template string (e.g., {{text}})
            formatted_prompt = prompt.format_prompt(text=text_to_process).to_string()

            # Debugging to ensure interpolation is working
            if "{{text}}" in formatted_prompt:
                logger.error(f"PROMPT INTERPOLATION FAILED for transcript index {i}. '{{text}}' still present.")
                logger.debug(f"Formatted prompt preview: {formatted_prompt[:500]}...")
            else:
                logger.debug(f"Prompt for transcript {i} formatted successfully.")

        except KeyError as e:
            logger.error(f"Error formatting prompt for transcript index {i}. Missing key: {e}")
            continue

        # Create the work item
        work_coro = _process_itemize_transcript_async(
            llm, prompt, formatted_prompt, text_to_process, parser, retry_parser, provider, i, total_count, max_retries, retry_delay, simple_format
        )
        
        work_items.append((work_coro, row, i))

    # Process in controlled batches
    all_results = []
    processed_count = 0
    total_items = len(work_items)
    last_log_time = time.time()

    # Use asyncio.Semaphore to limit concurrency
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_with_semaphore(work_coro, row_data, transcript_index):
        async with semaphore:
            return await process_and_pair(work_coro, row_data, transcript_index)

    # Create all tasks but let semaphore control concurrency
    tasks = [
        asyncio.create_task(process_with_semaphore(work_coro, row, transcript_index))
        for work_coro, row, transcript_index in work_items
    ]

    # Initialize progress bar
    pbar = tqdm(total=total_items, desc="Processing transcripts", unit="transcript")
    
    # Process results as they complete
    for future in asyncio.as_completed(tasks):
        processed_count += 1
        try:
            result_pair, row_data, transcript_index = await future
            all_results.append((result_pair, row_data))
        except Exception as e:
            logger.error(f"An unexpected exception occurred when awaiting a completed task: {e}")
            # Add error result to maintain order
            all_results.append(({'error': str(e)}, None))

        # Update progress bar
        if 'pbar' in locals():
            pbar.update(1)
        
        # Log progress less frequently - every 100 transcripts or every 10 seconds
        current_time = time.time()
        if processed_count % 100 == 0 or current_time - last_log_time > 10 or processed_count == total_items:
            logger.info(f"Itemization progress: {processed_count}/{total_items} transcripts processed...")
            last_log_time = current_time
            
        # Add small delay every batch to prevent overwhelming the system
        if processed_count % max_concurrent == 0:
            await asyncio.sleep(batch_delay)
    
    # Close progress bar
    pbar.close()
    
    return all_results

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
    simple_format: bool = True,
    retry_delay: float = 1.0,
    openai_api_key: str = None,
    sample_size: Optional[int] = None,
    max_workers: Optional[int] = None
) -> Tuple[str, str, Dict[str, Any], Optional[pd.DataFrame]]:
    """
    Async implementation of transform_transcripts_itemize.
    
    Args:
        max_workers: Maximum number of concurrent workers for parallel processing.
                     If None, uses provider-specific defaults (OpenAI: 50, others: 100).
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
        
        # Load cached dataframe
        transformed_df = pd.read_parquet(cached_parquet_path)

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
                for i in range(min(20, len(cached_df))):
                    cached_row = cached_df.iloc[i]
                    example = f"[PROCESSED OUTPUT]: {cached_row[content_column][:500]}..."
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
            
            # Try to load hit rate stats from metadata file
            hit_rate_stats = {
                "total_processed": 0,
                "successful_extractions": 0,
                "failed_extractions": 0,
                "hit_rate_percentage": 0.0
            }
            
            try:
                metadata_path = f"{cached_parquet_path}.metadata.json"
                if os.path.exists(metadata_path):
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                        if "hit_rate_stats" in metadata:
                            hit_rate_stats = metadata["hit_rate_stats"]
                            logging.info(f"Loaded hit rate stats from metadata: {hit_rate_stats['hit_rate_percentage']}% success rate")
            except Exception as e:
                logging.warning(f"Failed to load hit rate metadata: {e}")
            
            # Build preprocessing info from cached context
            preprocessing_info = {
                "method": "itemize",
                "prompt_used": template,
                "llm_provider": provider,
                "llm_model": model,
                "examples": examples,
                "hit_rate_stats": hit_rate_stats
            }
            
            return cached_parquet_path, text_file_path, preprocessing_info, transformed_df
            
        except Exception as e:
            logging.warning(f"Could not extract examples from cached data: {e}")
            # Fallback to minimal preprocessing info
            preprocessing_info = {
                "method": "itemize",
                "prompt_used": "Unknown (cached)",
                "llm_provider": provider,
                "llm_model": model,
                "examples": [],
                "hit_rate_stats": {
                    "total_processed": 0,
                    "successful_extractions": 0,
                    "failed_extractions": 0,
                    "hit_rate_percentage": 0.0
                }
            }
            return cached_parquet_path, text_file_path, preprocessing_info, transformed_df
    
    logging.info(f"Loading transcript data from {input_file}")
    df = pd.read_parquet(input_file)
    
    # Apply customer-only filter if requested
    if customer_only:
        df = apply_customer_only_filter(df, content_column, customer_only)
    
    if sample_size is not None and sample_size > 0 and sample_size < len(df):
        logging.info(f"Sampling {sample_size} transcripts from the dataset.")
        df = df.sample(n=sample_size, random_state=42).reset_index(drop=True)
    
    if inspect:
        inspect_data(df, content_column)

    # Choose parser based on format preference
    if simple_format:
        parser = PydanticOutputParser(pydantic_object=SimpleTranscriptItems)
        logging.info("Using simple format parser for string lists")
    else:
        parser = PydanticOutputParser(pydantic_object=TranscriptItems)
        logging.info("Using complex format parser with categories")
    
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

    retry_parser = OutputFixingParser.from_llm(
        parser=parser,
        llm=llm
    )

    # Use the template from configuration
    if prompt_template:
        template = prompt_template
        logging.info("Using inline prompt template from configuration")
    elif prompt_template_file:
        try:
            with open(prompt_template_file, 'r') as f:
                template_data = json.load(f)
                template = template_data.get('template')
                if not template:
                    raise ValueError("Template file must contain a 'template' key")
            logging.info(f"Using prompt template from file: {prompt_template_file}")
        except Exception as e:
            logging.error(f"Error loading prompt template: {e}")
            raise
    else:
        raise ValueError("No prompt template provided. Must specify either prompt_template or prompt_template_file")
    
    # Use Jinja2 template format for consistency
    logging.info("Using Jinja2 template format")
    prompt = ChatPromptTemplate.from_template(template, template_format="jinja2")
    
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
    all_results = []  # Initialize to empty list
    
    if valid_rows:
        logging.info(f"Processing all {len(valid_rows)} valid transcripts concurrently for itemization.")
        
        all_results = await _process_itemize_batch_async(
            llm, prompt, valid_rows, valid_indices, parser, retry_parser, 
            provider, len(df), max_retries, retry_delay, content_column, simple_format, max_workers
        )
        
        with open(text_file_path, 'w') as f:
            processed_count = 0
            last_log_time = time.time()
            
            for i, (result_pair, row) in enumerate(all_results):
                # Get item ID from the original row and parse it if it's a JSON string
                item_id_str = row.get('id') or row.get('IDs')
                item_id_obj = None
                
                logging.debug(f"🔍 ID_DEBUG: Processing row {valid_indices[i]}, found ID: {item_id_str} (type: {type(item_id_str)})")
                
                if item_id_str and isinstance(item_id_str, str):
                    try:
                        item_id_obj = json.loads(item_id_str)
                        logging.debug(f"🔍 ID_DEBUG: Successfully parsed JSON ID: {item_id_obj}")
                    except json.JSONDecodeError:
                        logging.warning(f"⚠️ ID_DEBUG: Could not parse ID JSON for row {valid_indices[i]}: {item_id_str}")
                        item_id_obj = item_id_str # Keep as string if not valid JSON
                else:
                    item_id_obj = item_id_str # It might already be an object/list
                    logging.debug(f"🔍 ID_DEBUG: Using ID as-is: {item_id_obj}")

                if isinstance(result_pair, Exception):
                    logging.error(f"Error processing transcript: {result_pair}")
                    error_text = f"ERROR: Unexpected error: {str(result_pair)}"
                    new_row = row.copy()
                    new_row[content_column] = error_text
                    if item_id_obj:
                        new_row['id'] = item_id_obj
                    transformed_rows.append(new_row)
                    f.write(f"{error_text}\n")
                    continue

                success, data = result_pair
                
                # After processing, we have 'success' and 'data' (parsed items)
                if success and data and hasattr(data, 'items') and data.items:
                    items_to_process = []
                    if isinstance(data, SimpleTranscriptItems):
                        items_to_process = data.items
                    elif isinstance(data, TranscriptItems):
                        items_to_process = [item.question for item in data.items]
                    
                    # Capture examples for the first few successful extractions
                    for item_text in items_to_process:
                        if len(preprocessing_examples) < 20:
                            example_text = item_text[:500] + ("..." if len(item_text) > 500 else "")
                            preprocessing_examples.append({"id": item_id_obj, "text": example_text})

                        # Create a new row in transformed_df for each extracted item
                        new_row = row.copy()
                        new_row[content_column] = item_text
                        if item_id_obj:
                            new_row['id'] = item_id_obj # Add the parsed object to the new row
                            logging.debug(f"🔍 ID_DEBUG: Added ID {item_id_obj} to extracted item")
                        else:
                            logging.debug(f"🔍 ID_DEBUG: No ID available for extracted item")
                        transformed_rows.append(new_row)
                        f.write(f"{item_text}\n")
                
                elif not success:
                    # Handle failed extraction for hit rate stats
                    logging.warning(f"Itemization failed for transcript index {valid_indices[i]}")
                    if len(preprocessing_examples) < 20:
                        example_text = row.get(content_column, "")[:500] + ("..." if len(row.get(content_column, "")) > 500 else "")
                        preprocessing_examples.append({
                            "id": item_id_obj,
                            "text": f"[EXTRACTION FAILED] Original text: {example_text}",
                            "error": str(data) # 'data' contains error message on failure
                        })

    else:
        logging.info("No valid transcripts found to process.")
        with open(text_file_path, 'w') as f:
            pass

    transformed_df = pd.DataFrame(transformed_rows)
    logging.info(f"🔍 ALIGNMENT_CHECK: Itemize created transformed_df with {len(transformed_df)} rows from {len(valid_rows)} valid transcripts")
    
    # Check for ID column
    has_ids = 'id' in transformed_df.columns
    logging.info(f"🔍 ID_DEBUG: itemized transformed_df has ID column: {has_ids}")
    if has_ids:
        non_null_ids = transformed_df['id'].notna().sum()
        logging.info(f"🔍 ID_DEBUG: {non_null_ids}/{len(transformed_df)} itemized rows have non-null IDs")
        # Sample some IDs for verification
        sample_ids = transformed_df['id'].dropna().head(3).tolist()
        logging.info(f"🔍 ID_DEBUG: Sample itemized IDs: {sample_ids}")
    
    logging.info(f"🔍 ALIGNMENT_CHECK: Final itemized transformed_df columns: {list(transformed_df.columns)}")
    
    logging.info(f"Saving transformed data to {cached_parquet_path}")
    transformed_df.to_parquet(cached_parquet_path)
    logging.info(f"Saved itemized text to {text_file_path}")
    
    # Create preprocessing info with examples and prompt
    # Calculate hit rate statistics
    total_processed = len(all_results) if all_results else 0
    successful_extractions = 0
    failed_extractions = 0
    
    if all_results:
        for result_pair, row in all_results:
            if isinstance(result_pair, Exception):
                failed_extractions += 1
            else:
                success, data = result_pair
                if success:
                    # Check if any items were actually extracted
                    if isinstance(data, SimpleTranscriptItems):
                        if data.items and len(data.items) > 0:
                            successful_extractions += 1
                        else:
                            failed_extractions += 1
                    elif hasattr(data, 'items'):
                        if data.items and len(data.items) > 0:
                            successful_extractions += 1
                        else:
                            failed_extractions += 1
                    else:
                        failed_extractions += 1
                else:
                    failed_extractions += 1
    
    hit_rate = (successful_extractions / total_processed * 100) if total_processed > 0 else 0
    
    preprocessing_info = {
        "method": "itemize",
        "prompt_used": template,
        "llm_provider": provider,
        "llm_model": model,
        "examples": preprocessing_examples,
        "hit_rate_stats": {
            "total_processed": total_processed,
            "successful_extractions": successful_extractions,
            "failed_extractions": failed_extractions,
            "hit_rate_percentage": round(hit_rate, 1)
        }
    }
    
    # Save hit rate stats and examples to a metadata file for future cached runs
    try:
        metadata_path = f"{cached_parquet_path}.metadata.json"
        with open(metadata_path, 'w') as f:
            # Convert examples to be JSON serializable
            serializable_examples = []
            for ex in preprocessing_examples:
                # The 'id' field is now an object, which is directly serializable by JSON
                serializable_ex = {
                    'id': ex.get('id'),
                    'text': ex.get('text', '')
                }
                if 'error' in ex:
                    serializable_ex['error'] = ex['error']
                serializable_examples.append(serializable_ex)

            json.dump({
                "hit_rate_stats": preprocessing_info["hit_rate_stats"],
                "method": "itemize",
                "llm_provider": provider,
                "llm_model": model,
                "prompt_used": template,
                "examples": serializable_examples # Save examples here
            }, f, indent=2)
        logging.info(f"Saved metadata to {metadata_path}")
    except Exception as e:
        logging.warning(f"Failed to save metadata: {e}")

    gc.collect()
    return cached_parquet_path, text_file_path, preprocessing_info, transformed_df 