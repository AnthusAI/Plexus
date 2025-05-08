import click
import logging
import pandas as pd
from plexus.Scorecard import Scorecard
from plexus.Registries import scorecard_registry
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import ResponseSchema, StructuredOutputParser
from pyairtable import Api
from pyairtable.formulas import match
import dotenv
import os
import re
from pathlib import Path
from plexus.cli.bertopic.transformer import transform_transcripts, inspect_data, transform_transcripts_llm, transform_transcripts_itemize
from plexus.cli.bertopic.analyzer import analyze_topics
from plexus.cli.bertopic.ollama_test import test_ollama_chat
from typing import Optional
import asyncio

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

dotenv.load_dotenv('.env', override=True)

@click.group()
def analyze():
    """
    Analysis commands for evaluating scorecard configurations and feedback.
    """
    pass

@analyze.command()
@click.option('--scorecard-name', required=True, help='Name of the scorecard to analyze')
@click.option('--base-id', required=True, help='Airtable base ID, Example: app87FkAzXqAcmxyC')
@click.option('--table-name', required=True, help='Airtable table name, Example: Scorecard Data')
@click.option('--score-name', default='', help='Score name to analyze')
def feedback(
    scorecard_name: str,
    base_id: str,
    table_name: str,
    score_name: str,
):
    """
    Analyze mismatches between predictions and feedback to generate prompt improvement suggestions.
    """
    logging.info(f"Starting mistake analysis for Scorecard {scorecard_name}")
    
    # Load scorecard
    Scorecard.load_and_register_scorecards('scorecards/')
    scorecard_class = scorecard_registry.get(scorecard_name)
    if scorecard_class is None:
        logging.error(f"Scorecard with name '{scorecard_name}' not found.")
        return

    # Initialize LLM and Airtable
    llm = ChatOpenAI(
        model="gpt-4o-mini-2024-07-18",
        api_key=os.getenv("OPENAI_API_KEY"),
        max_tokens=500,
        temperature=0.3,
    )
    
    # Initialize the PromptAnalyzer
    prompt_analyzer = PromptAnalyzer(llm)
    
    airtable = Api(os.getenv("AIRTABLE_API_KEY"))
    table = airtable.table(base_id, table_name)
    
    try:
        # First, let's get records where question matches our score_name
        formula = f"AND(question = '{score_name}', Comments != '')"
        records = table.all(formula=formula)
        df = pd.DataFrame([record['fields'] for record in records])
        
        required_columns = ['TranscriptText', 'Comments', 'QA SCORE']
        if not all(col in df.columns for col in required_columns):
            logging.error(f"Airtable table must contain fields: {required_columns}")
            return
            
        logging.info(f"Found {len(df)} records for question: {score_name}")
        
        if len(df) == 0:
            logging.error(f"No records found for question: {score_name}")
            return
            
    except Exception as e:
        logging.error(f"Error fetching data from Airtable: {e}")
        return

    scores_to_analyze = [score_name]
    score_data = df  # Already filtered for the specific question
    
    # Analyze each score type
    for score in scores_to_analyze:
        if len(score_data) == 0:
            logging.warning(f"No data found for score: {score}")
            continue
            
        logging.info(f"\nAnalyzing {score} score:")
        scorecard_instance = scorecard_class(scorecard=scorecard_name)
        current_prompt = ""
        
        # Get prompt from scorecard configuration
        for score_config in scorecard_instance.scores:
            if score_config['name'] == score:
                # Extract both system message and user message from the first graph node
                if score_config.get('graph') and len(score_config['graph']) > 0:
                    graph_node = score_config['graph'][0]
                    current_prompt = (
                        f"System Message:\n{graph_node.get('system_message', '')}\n\n"
                        f"User Message:\n{graph_node.get('user_message', '')}"
                    )
                break
                
        if not current_prompt:
            logging.warning(f"No prompt found for score: {score}")
            continue
            
        analyze_score_feedback(score_data, prompt_analyzer, current_prompt)

@analyze.command()
@click.option('--input-file', required=True, help='Path to input Parquet file containing transcripts')
@click.option('--output-dir', default='.', help='Base directory for output files (default: current directory)')
@click.option('--min-words', default=2, help='Minimum number of words for a speaking turn to be included')
@click.option('--content-column', default='text', help='Name of column containing transcript content (default: text)')
@click.option('--inspect', is_flag=True, help='Inspect the data before processing')
@click.option('--skip-analysis', is_flag=True, help='Skip BERTopic analysis, only transform transcripts')
@click.option('--num-topics', type=int, help='Target number of topics (default: auto-determined)')
@click.option('--min-ngram', type=int, default=1, help='Minimum n-gram size (default: 1)')
@click.option('--max-ngram', type=int, default=2, help='Maximum n-gram size (default: 2)')
@click.option('--min-topic-size', type=int, default=10, help='Minimum size of topics (default: 10)')
@click.option('--top-n-words', type=int, default=10, help='Number of words to represent each topic (default: 10)')
@click.option('--transform', type=click.Choice(['chunk', 'llm', 'itemize']), default='chunk', 
              help='Transformation method: chunk (default), llm, or itemize')
@click.option('--prompt-template', type=str, help='Path to prompt template file for LLM transformation (JSON format)')
@click.option('--llm-model', default='gemma3:27b', help='LLM model to use for transformation (default: gemma3:27b)')
@click.option('--provider', default='ollama', type=click.Choice(['ollama', 'openai']), 
              help='LLM provider to use (default: ollama)')
@click.option('--openai-api-key', help='OpenAI API key (if provider is openai)')
@click.option('--fresh', is_flag=True, help='Force regeneration of cached files')
@click.option('--max-retries', type=int, default=2, help='Maximum number of retries for parsing failures (itemize mode only)')
@click.option('--sample-size', type=int, default=None, help='Number of transcripts to sample (default: process all)')
@click.option('--customer-only', is_flag=True, default=False, help='Filter transcripts to include only customer utterances before processing')
@click.option('--use-representation-model', is_flag=True, default=False, 
              help='Use OpenAI to generate better topic representations (requires API key)')
def topics(
    input_file: str,
    output_dir: str,
    min_words: int,
    content_column: str,
    inspect: bool,
    skip_analysis: bool,
    num_topics: int,
    min_ngram: int,
    max_ngram: int,
    min_topic_size: int,
    top_n_words: int,
    transform: str,
    prompt_template: str,
    llm_model: str,
    provider: str,
    openai_api_key: str,
    fresh: bool,
    max_retries: int,
    sample_size: Optional[int],
    customer_only: bool,
    use_representation_model: bool,
):
    """
    Analyze topics in call transcripts using BERTopic.
    
    This command processes call transcripts from a Parquet file, transforms them using 
    one of several methods, and performs topic modeling using BERTopic.
    The results are saved in the specified output directory.
    
    Transformation methods:
      - chunk: Split transcripts into chunks by speaker turns (default)
      - llm: Use a language model to transform/summarize transcripts
      - itemize: Use a language model to extract structured items, creating multiple rows per transcript
    
    LLM Providers:
      - ollama: Use local Ollama models (default)
      - openai: Use OpenAI API models (requires API key)
    
    Examples:
        # Default chunking transformation
        python3 -m plexus.cli.CommandLineInterface analyze topics --input-file path/to/transcripts.parquet
        
        # LLM-based transformation with Ollama
        python3 -m plexus.cli.CommandLineInterface analyze topics --input-file path/to/transcripts.parquet --transform llm --llm-model gemma3:27b
        
        # LLM-based transformation with OpenAI
        python3 -m plexus.cli.CommandLineInterface analyze topics --input-file path/to/transcripts.parquet --transform llm --provider openai --llm-model gpt-3.5-turbo
        
        # Extract only customer utterances for analysis
        python3 -m plexus.cli.CommandLineInterface analyze topics --input-file path/to/transcripts.parquet --customer-only
        
        # Itemized extraction with structured output
        python3 -m plexus.cli.CommandLineInterface analyze topics --input-file path/to/transcripts.parquet --transform itemize --max-retries 3

        # Process only 100 random transcripts
        python3 -m plexus.cli.CommandLineInterface analyze topics --input-file path/to/transcripts.parquet --sample-size 100
        
        # Use OpenAI to generate better topic representations
        python3 -m plexus.cli.CommandLineInterface analyze topics --input-file path/to/transcripts.parquet --use-representation-model --openai-api-key YOUR_API_KEY
    """
    logging.info(f"Starting topic analysis for file: {input_file}")
    
    if customer_only:
        logging.info("Customer-only mode: Will extract and process only customer utterances")
    
    input_path = Path(input_file)
    output_path = Path(output_dir)
    
    if not input_path.exists():
        logging.error(f"Input file not found: {input_file}")
        return
        
    if inspect:
        logging.info("Inspecting data before processing...")
        df = pd.read_parquet(input_path)
        inspect_data(df, content_column)
        return
    
    try:
        text_file_path = None
        transform_suffix = ""

        if transform == 'itemize':
            logging.info(f"Using itemized LLM transformation with {provider} model: {llm_model}")
            if prompt_template:
                logging.info(f"Using prompt template from: {prompt_template}")
            try:
                _, text_file_path = asyncio.run(transform_transcripts_itemize(
                    input_file=str(input_path),
                    content_column=content_column,
                    prompt_template_file=prompt_template,
                    model=llm_model,
                    provider=provider,
                    customer_only=customer_only,
                    fresh=fresh,
                    max_retries=max_retries,
                    openai_api_key=openai_api_key,
                    sample_size=sample_size
                ))
            except Exception as e:
                logging.error(f"Error during itemize transformation: {str(e)}", exc_info=True)
                raise 
            transform_suffix = f"itemize-{provider}"
            if customer_only:
                transform_suffix += "-customer-only"
        elif transform == 'llm':
            logging.info(f"Using LLM transformation with {provider} model: {llm_model}")
            if prompt_template:
                logging.info(f"Using prompt template from: {prompt_template}")
            try:
                _, text_file_path = asyncio.run(transform_transcripts_llm(
                    input_file=str(input_path),
                    content_column=content_column,
                    prompt_template_file=prompt_template,
                    model=llm_model,
                    provider=provider,
                    customer_only=customer_only,
                    fresh=fresh,
                    openai_api_key=openai_api_key,
                    sample_size=sample_size
                ))
            except Exception as e:
                logging.error(f"Error during LLM transformation: {str(e)}", exc_info=True)
                raise
            transform_suffix = f"llm-{provider}"
            if customer_only:
                transform_suffix += "-customer-only"
        else:  # Default chunking method (transform == 'chunk')
            logging.info("Using default chunking transformation")
            try:
                _, text_file_path = transform_transcripts(
                    input_file=str(input_path),
                    content_column=content_column,
                    customer_only=customer_only,
                    fresh=fresh,
                    sample_size=sample_size
                )
            except Exception as e:
                logging.error(f"Error during chunk transformation: {str(e)}", exc_info=True)
                raise
            transform_suffix = "chunk"
            if customer_only:
                transform_suffix += "-customer-only"
            
        logging.info("Transcript transformation completed successfully")
        
        if not skip_analysis:
            if not text_file_path:
                logging.error("Text file path not generated from transformation step. Skipping analysis.")
                return
            
            # Define the hidden base directory for all plexus bertopic results
            hidden_base_output_dirname = ".plexus_bertopic_results"
            # The parent directory for the analysis folder
            analysis_parent_dir = output_path / hidden_base_output_dirname

            # Ensure the parent directory exists
            analysis_parent_dir.mkdir(parents=True, exist_ok=True)

            # Use descriptive naming scheme based on parameters
            analysis_dir_name = f"topics_{transform_suffix}_{min_ngram}-{max_ngram}gram_{num_topics if num_topics else 'auto'}"
            if use_representation_model:
                analysis_dir_name += "_with_representation"
            
            # Construct the full path for the specific analysis output
            final_output_dir = analysis_parent_dir / analysis_dir_name
            output_dir_str = str(final_output_dir)
            
            logging.info(f"Preparing to start BERTopic analysis directly in the main process.")
            logging.info(f"Output directory for analysis: {output_dir_str}")
            
            # Set OpenMP environment variables before calling analyze_topics
            logging.info("Setting OpenMP environment variables for BERTopic analysis.")
            os.environ["OMP_NUM_THREADS"] = "1"
            os.environ["OPENBLAS_NUM_THREADS"] = "1"
            os.environ["MKL_NUM_THREADS"] = "1"
            os.environ["NUMEXPR_NUM_THREADS"] = "1"
            logging.info(f"OMP_NUM_THREADS set to: {os.environ.get('OMP_NUM_THREADS')}")

            try:
                analyze_topics(
                    text_file_path=text_file_path,
                    output_dir=output_dir_str,
                    nr_topics=num_topics,
                    n_gram_range=(min_ngram, max_ngram),
                    min_topic_size=min_topic_size,
                    top_n_words=top_n_words,
                    use_representation_model=use_representation_model,
                    openai_api_key=openai_api_key
                )
                logging.info("BERTopic analysis completed successfully.")
            except Exception as e:
                logging.error(f"BERTopic analysis failed: {str(e)}", exc_info=True)
                raise
        else:
            logging.info("Skipping BERTopic analysis as requested")
        
    except Exception as e:
        # This will catch errors re-raised from transformation or analysis steps
        logging.error(f"Topic analysis command failed: {e}")
        return # Exit gracefully

@analyze.command()
@click.option('--model', default='gemma3:27b', help='Model to use (default: gemma3:27b)')
@click.option('--prompt', default='Why is the sky blue?', help='Prompt to send to the model')
@click.option('--provider', default='ollama', type=click.Choice(['ollama', 'openai']), 
              help='LLM provider to use (default: ollama)')
@click.option('--openai-api-key', help='OpenAI API key (if provider is openai)')
def test_ollama(
    model: str,
    prompt: str,
    provider: str,
    openai_api_key: str
):
    """
    Test LLM integration.
    
    This command sends a test request to the specified LLM provider to verify it's working correctly.
    The response from the model will be printed to the console.
    
    Example:
        # Test with Ollama
        plexus analyze test-ollama --model gemma3:27b --prompt "Explain quantum computing in simple terms"
        
        # Test with OpenAI
        plexus analyze test-ollama --provider openai --model gpt-3.5-turbo --prompt "Explain quantum computing in simple terms"
    """
    logging.info(f"Testing LLM integration with {provider} model: {model}")
    
    try:
        if provider.lower() == 'ollama':
            # Call the Ollama test function
            response = test_ollama_chat(model=model, prompt=prompt)
        elif provider.lower() == 'openai':
            # We need to use OpenAI via LangChain for consistency
            try:
                from langchain_openai import ChatOpenAI
                
                # Use provided API key or environment variable
                api_key = openai_api_key or os.environ.get("OPENAI_API_KEY")
                if not api_key:
                    logging.error("OpenAI API key not provided. Set OPENAI_API_KEY environment variable or pass --openai-api-key")
                    return
                
                from langchain.prompts import ChatPromptTemplate
                
                # Create a simple prompt
                prompt_template = ChatPromptTemplate.from_template("{text}")
                
                # Format the prompt
                formatted_prompt = prompt_template.format(text=prompt)
                
                # Log the complete formatted prompt
                logging.info(f"COMPLETE FORMATTED PROMPT FOR TEST:\n{formatted_prompt}\n")
                
                # Initialize the OpenAI LLM
                llm = ChatOpenAI(model=model, openai_api_key=api_key)
                
                # Run LLM on the prompt
                response = llm.invoke(formatted_prompt)
                
                # Extract content from AIMessage for OpenAI responses
                if hasattr(response, 'content'):
                    response = response.content
                
            except ImportError:
                logging.error("OpenAI package not installed. Install with: pip install langchain-openai")
                return
            except Exception as e:
                logging.error(f"Error calling OpenAI API: {e}")
                return
        else:
            logging.error(f"Unsupported provider: {provider}")
            return
        
        # Print the response
        print(f"\n--- {provider.capitalize()} Response ---")
        print(response)
        print("----------------------\n")
        
        logging.info(f"{provider.capitalize()} test completed successfully")
    except Exception as e:
        logging.error(f"Error testing {provider}: {e}")
        return

class PromptAnalyzer:
    def __init__(self, llm):
        self.llm = llm
        self.output_parser = self._create_output_parser()
        self.prompt = self._create_prompt()

    def _create_output_parser(self):
        schemas = [
            ResponseSchema(name="common_mistakes", 
                         description="Common patterns of mistakes identified in the scoring"),
            ResponseSchema(name="missing_criteria", 
                         description="Important criteria that seem to be missing from the current prompt"),
            ResponseSchema(name="prompt_suggestion", 
                         description="Specific suggestions for improving the prompt, including new or modified criteria")
        ]
        return StructuredOutputParser.from_response_schemas(schemas)

    def _create_prompt(self):
        template = """Analyze these scoring examples and suggest improvements for the scoring prompt:

Current Prompt:
{current_prompt}

Feedback Examples:
{examples}

Based on these examples, please provide:
1. Common patterns in scoring mistakes
2. Important criteria that seem to be missing from the current prompt
3. Specific suggestions for improving the prompt to prevent these mistakes

{format_instructions}"""

        return ChatPromptTemplate.from_template(template)

    def analyze_feedback(self, current_prompt: str, examples: list):
        format_instructions = self.output_parser.get_format_instructions()
        examples_text = "\n\n".join([
            f"Example {i+1}:\n"
            f"Transcript: {ex['transcript']}\n"
            f"Score Given: {ex['score']}\n"
            f"Feedback: {ex['feedback']}"
            for i, ex in enumerate(examples)
        ])
        
        prompt_value = self.prompt.format(
            current_prompt=current_prompt,
            examples=examples_text,
            format_instructions=format_instructions
        )
        logging.info(f"current prompt: {current_prompt}")
        
        response = self.llm.predict(prompt_value)
        return self.output_parser.parse(response)

def analyze_score_feedback(score_data: pd.DataFrame, prompt_analyzer: PromptAnalyzer, current_prompt: str):
    """
    Analyze feedback for a specific score type and suggest prompt improvements.
    """
    samples_with_feedback = score_data[score_data['Comments'].notna()]
    feedback_count = len(samples_with_feedback)
    
    if feedback_count == 0:
        logging.info("No feedback samples found for analysis")
        return

    # Prepare examples for analysis
    examples = []
    for _, row in samples_with_feedback.iterrows():
        if pd.notna(row['Comments']) and row['Comments'].strip():
            examples.append({
                'transcript': row['TranscriptText'],
                'score': row.get('QA SCORE', 'Unknown'),
                'feedback': row['Comments']
            })

    # Get prompt improvement suggestions
    analysis = prompt_analyzer.analyze_feedback(current_prompt, examples)

    logging.info("\nPrompt Analysis Results:")
    logging.info("\nCommon Mistakes Identified:")
    logging.info(analysis['common_mistakes'])
    logging.info("\nMissing Criteria:")
    logging.info(analysis['missing_criteria'])
    logging.info("\nPrompt Improvement Suggestion:")
    logging.info(analysis['prompt_suggestion'])