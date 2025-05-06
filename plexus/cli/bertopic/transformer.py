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
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field, ValidationError
from langchain.output_parsers.retry import RetryWithErrorOutputParser

# Configure logging
logger = logging.getLogger(__name__)

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

def transform_transcripts(
    input_file: str,
    content_column: str = 'content',
    fresh: bool = False,
    inspect: bool = True
) -> Tuple[str, str]:
    """
    Transform transcript data into BERTopic-compatible format.
    
    Args:
        input_file: Path to input Parquet file
        content_column: Name of column containing transcript content
        fresh: Whether to force regeneration of cached files
        inspect: Whether to print sample data for inspection
        
    Returns:
        Tuple of (cached_parquet_path, text_file_path)
    """
    # Generate output file paths
    base_path = os.path.splitext(input_file)[0]
    cached_parquet_path = f"{base_path}-bertopic.parquet"
    text_file_path = f"{base_path}-bertopic-text.txt"
    
    # Check if cached files exist and fresh is False
    if not fresh and os.path.exists(cached_parquet_path) and os.path.exists(text_file_path):
        logging.info(f"Using cached files: {cached_parquet_path} and {text_file_path}")
        return cached_parquet_path, text_file_path
    
    # Load input data
    logging.info(f"Loading transcript data from {input_file}")
    df = pd.read_parquet(input_file)
    
    # Inspect data if requested
    if inspect:
        inspect_data(df, content_column)
    
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
    
    return cached_parquet_path, text_file_path

def transform_transcripts_llm(
    input_file: str,
    content_column: str = 'content',
    prompt_template_file: str = None,
    model: str = 'gemma3:27b',
    fresh: bool = False,
    inspect: bool = True
) -> Tuple[str, str]:
    """
    Transform transcript data using a language model.
    
    This function processes each transcript through a language model (Ollama)
    to extract key information or summarize content before topic analysis.
    
    Args:
        input_file: Path to input Parquet file
        content_column: Name of column containing transcript content
        prompt_template_file: Path to LangChain prompt template file (JSON)
        model: Ollama model to use for transformation
        fresh: Whether to force regeneration of cached files
        inspect: Whether to print sample data for inspection
        
    Returns:
        Tuple of (cached_parquet_path, text_file_path)
    """
    # Generate output file paths with llm suffix to distinguish from chunking method
    base_path = os.path.splitext(input_file)[0]
    cached_parquet_path = f"{base_path}-bertopic-llm.parquet"
    text_file_path = f"{base_path}-bertopic-llm-text.txt"
    
    # Check if cached files exist and fresh is False
    if not fresh and os.path.exists(cached_parquet_path) and os.path.exists(text_file_path):
        logging.info(f"Using cached files: {cached_parquet_path} and {text_file_path}")
        return cached_parquet_path, text_file_path
    
    # Load input data
    logging.info(f"Loading transcript data from {input_file}")
    df = pd.read_parquet(input_file)
    
    # Inspect data if requested
    if inspect:
        inspect_data(df, content_column)
    
    # Load prompt template
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
            logging.error(f"Error loading prompt template: {e}. Using default template.")
            template = """Summarize the key topics in this transcript in 3-5 concise bullet points:
            
            {text}
            
            Key topics:"""
    else:
        template = """Summarize the key topics in this transcript in 3-5 concise bullet points:
        
        {text}
        
        Key topics:"""
    
    # Create prompt
    prompt = ChatPromptTemplate.from_template(template)
    
    # Import ollama here to avoid dependency issues if not needed
    try:
        from langchain.llms import Ollama
        llm = Ollama(model=model)
    except ImportError:
        logging.error("Ollama package not installed. Install with: pip install ollama")
        raise
    
    # Process each transcript with the LLM
    transformed_rows = []
    with open(text_file_path, 'w') as f:
        for i, (_, row) in enumerate(df.iterrows()):
            try:
                # Get transcript text
                text = row[content_column]
                
                # Skip empty transcripts
                if not text or pd.isna(text):
                    continue
                
                logging.info(f"Processing transcript {i+1}/{len(df)}")
                
                # Run LLM on transcript
                response = llm.invoke(prompt.format(text=text))
                
                # Log the response (truncate if too long)
                max_log_length = 1000  # Limit log length to avoid flooding
                log_response = response
                if len(log_response) > max_log_length:
                    log_response = log_response[:max_log_length] + "... [truncated]"
                logging.info(f"LLM Response {i+1}/{len(df)}:\n{log_response}\n")
                
                # Create new row with LLM response
                new_row = row.copy()
                new_row[content_column] = response
                transformed_rows.append(new_row)
                
                # Write to text file
                f.write(f"{response}\n")
                
            except Exception as e:
                logging.error(f"Error processing transcript {i+1}: {e}")
    
    # Create transformed DataFrame
    transformed_df = pd.DataFrame(transformed_rows)
    
    # Save cached Parquet file
    logging.info(f"Saving transformed data to {cached_parquet_path}")
    transformed_df.to_parquet(cached_parquet_path)
    
    logging.info(f"Saved LLM-processed text to {text_file_path}")
    
    return cached_parquet_path, text_file_path 

class TranscriptItem(BaseModel):
    """Model for a single item extracted from a transcript."""
    quote: str = Field(description="A direct question asked by the customer, quoted verbatim")

class TranscriptItems(BaseModel):
    """Model for a list of items extracted from a transcript."""
    items: List[TranscriptItem] = Field(description="List of items extracted from the transcript")

def transform_transcripts_itemize(
    input_file: str,
    content_column: str = 'content',
    prompt_template_file: str = None,
    model: str = 'gemma3:27b',
    fresh: bool = False,
    inspect: bool = True,
    max_retries: int = 2,
    retry_delay: float = 1.0
) -> Tuple[str, str]:
    """
    Transform transcript data using a language model with itemization.
    
    This function processes each transcript through a language model (Ollama)
    to extract structured items, creating multiple rows per transcript.
    
    Args:
        input_file: Path to input Parquet file
        content_column: Name of column containing transcript content
        prompt_template_file: Path to LangChain prompt template file (JSON)
        model: Ollama model to use for transformation
        fresh: Whether to force regeneration of cached files
        inspect: Whether to print sample data for inspection
        max_retries: Maximum number of retries for parsing failures
        retry_delay: Delay between retries in seconds
        
    Returns:
        Tuple of (cached_parquet_path, text_file_path)
    """
    # Generate output file paths with itemize suffix
    base_path = os.path.splitext(input_file)[0]
    cached_parquet_path = f"{base_path}-bertopic-itemize.parquet"
    text_file_path = f"{base_path}-bertopic-itemize-text.txt"
    
    # Check if cached files exist and fresh is False
    if not fresh and os.path.exists(cached_parquet_path) and os.path.exists(text_file_path):
        logging.info(f"Using cached files: {cached_parquet_path} and {text_file_path}")
        return cached_parquet_path, text_file_path
    
    # Load input data
    logging.info(f"Loading transcript data from {input_file}")
    df = pd.read_parquet(input_file)
    
    # Inspect data if requested
    if inspect:
        inspect_data(df, content_column)
    
    # Create Pydantic parser
    parser = PydanticOutputParser(pydantic_object=TranscriptItems)
    logging.info(f"Parser format instructions:\n{parser.get_format_instructions()}")
    
    # Initialize Ollama LLM first before creating the retry parser
    try:
        from langchain.llms import Ollama
        llm = Ollama(model=model)
        logging.info(f"Successfully initialized Ollama LLM with model: {model}")
    except ImportError:
        logging.error("Ollama package not installed. Install with: pip install ollama")
        raise
    
    # Create retry parser after LLM is initialized
    retry_parser = RetryWithErrorOutputParser.from_llm(
        parser=parser,
        llm=llm,  # Now we're passing the initialized LLM
        max_retries=max_retries
    )
    
    # Load prompt template
    if prompt_template_file:
        try:
            with open(prompt_template_file, 'r') as f:
                template_data = json.load(f)
                template = template_data.get('template', 
                    """Extract the main topics from this transcript. For each topic, provide a concise description.

{text}

{format_instructions}"""
                )
        except Exception as e:
            logging.error(f"Error loading prompt template: {e}. Using default template.")
            template = """Extract the main topics from this transcript. For each topic, provide a concise description.

{text}

{format_instructions}"""
    else:
        template = """Extract the main topics from this transcript. For each topic, provide a concise description.

{text}

{format_instructions}"""
    
    # Create prompt with format instructions
    prompt = ChatPromptTemplate.from_template(template)
    
    # Log the template being used
    logging.info(f"Using prompt template:\n{template}")
    
    # Process each transcript with the LLM
    transformed_rows = []
    with open(text_file_path, 'w') as f:
        for i, (_, row) in enumerate(df.iterrows()):
            try:
                # Get transcript text
                text = row[content_column]
                
                # Skip empty transcripts
                if not text or pd.isna(text):
                    continue
                
                logging.info(f"========= Processing transcript {i+1}/{len(df)} =========")
                
                # Format the prompt with parser instructions
                formatted_prompt = prompt.format(
                    text=text, 
                    format_instructions=parser.get_format_instructions()
                )
                
                # Run LLM on transcript
                retry_count = 0
                success = False
                
                while not success and retry_count <= max_retries:
                    try:
                        if retry_count > 0:
                            logging.info(f"Retry {retry_count}/{max_retries} for transcript {i+1}")
                            time.sleep(retry_delay)
                            
                        # Log before sending to LLM
                        logging.info(f"SENDING PROMPT TO LLM FOR TRANSCRIPT {i+1}")
                        
                        # Get raw response
                        raw_response = llm.invoke(formatted_prompt)
                        
                        # Log the complete raw response to the console
                        logging.info(f"COMPLETE RAW LLM RESPONSE FOR TRANSCRIPT {i+1}:\n{raw_response}\n")
                        
                        # Try to parse the JSON directly first
                        try:
                            # Try direct JSON parsing
                            json_data = json.loads(raw_response)
                            logging.info(f"PARSED JSON: {json_data}")
                            parsed_items = TranscriptItems(**json_data)
                            logging.info(f"SUCCESSFULLY CREATED PYDANTIC MODEL: {parsed_items}")
                            success = True
                        except json.JSONDecodeError:
                            # Try to extract JSON from markdown code blocks
                            logging.info("JSON PARSING FAILED, TRYING TO EXTRACT JSON FROM RESPONSE")
                            
                            # Look for JSON in code blocks
                            if "```json" in raw_response:
                                import re
                                match = re.search(r'```json\s*(.*?)\s*```', raw_response, re.DOTALL)
                                if match:
                                    extracted = match.group(1).strip()
                                    logging.info(f"EXTRACTED JSON FROM CODE BLOCK:\n{extracted}")
                                    try:
                                        json_data = json.loads(extracted)
                                        logging.info(f"PARSED EXTRACTED JSON: {json_data}")
                                        parsed_items = TranscriptItems(**json_data)
                                        success = True
                                    except Exception as je:
                                        logging.error(f"FAILED TO PARSE EXTRACTED JSON: {je}")
                            
                            # If still not successful, try the retry parser
                            if not success:
                                logging.info("ATTEMPTING RETRY PARSER")
                                parsed_items = retry_parser.parse_with_prompt(raw_response, formatted_prompt)
                                logging.info("RETRY PARSER SUCCEEDED")
                                success = True
                        except ValidationError as ve:
                            logging.error(f"VALIDATION ERROR: {ve}")
                            logging.info("ATTEMPTING RETRY PARSER")
                            parsed_items = retry_parser.parse_with_prompt(raw_response, formatted_prompt)
                            logging.info("RETRY PARSER SUCCEEDED")
                            success = True
                        
                    except Exception as e:
                        logging.error(f"ERROR PROCESSING TRANSCRIPT {i+1} (attempt {retry_count+1}): {type(e).__name__}: {e}")
                        import traceback
                        logging.error(f"TRACEBACK:\n{traceback.format_exc()}")
                        retry_count += 1
                        if retry_count > max_retries:
                            logging.error(f"FAILED TO PROCESS AFTER {max_retries} RETRIES")
                            # Create a single row with error message
                            new_row = row.copy()
                            new_row[content_column] = f"ERROR: Failed to parse transcript after {max_retries} retries"
                            transformed_rows.append(new_row)
                            f.write(f"ERROR: Failed to parse transcript {i+1}\n")
                            break
                
                if success:
                    # Debug output for the successfully parsed items
                    logging.info(f"SUCCESSFULLY PARSED {len(parsed_items.items)} ITEMS:")
                    for idx, item in enumerate(parsed_items.items):
                        logging.info(f"ITEM {idx+1}: {item.quote}")
                    
                    # Create a new row for each item
                    for item in parsed_items.items:
                        new_row = row.copy()
                        combined_text = f"{item.quote}"
                        new_row[content_column] = combined_text
                        transformed_rows.append(new_row)
                        
                        # Write to text file
                        f.write(f"{combined_text}\n")
                
            except Exception as e:
                logging.error(f"CRITICAL ERROR PROCESSING TRANSCRIPT {i+1}: {type(e).__name__}: {e}")
                import traceback
                logging.error(f"TRACEBACK:\n{traceback.format_exc()}")
                # Add a fallback row to avoid losing data
                new_row = row.copy()
                new_row[content_column] = f"ERROR: {str(e)}"
                transformed_rows.append(new_row)
                f.write(f"ERROR processing transcript {i+1}: {str(e)}\n")
    
    # Create transformed DataFrame
    transformed_df = pd.DataFrame(transformed_rows)
    
    # Save cached Parquet file
    logging.info(f"Saving transformed data to {cached_parquet_path}")
    transformed_df.to_parquet(cached_parquet_path)
    
    logging.info(f"Saved itemized text to {text_file_path}")
    
    return cached_parquet_path, text_file_path 