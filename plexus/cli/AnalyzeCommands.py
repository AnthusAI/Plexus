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
from pathlib import Path
from plexus.cli.bertopic.transformer import transform_transcripts, inspect_data
from plexus.cli.bertopic.analyzer import analyze_topics
from plexus.cli.bertopic.ollama_test import test_ollama_chat

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
):
    """
    Analyze topics in call transcripts using BERTopic.
    
    This command processes call transcripts from a Parquet file, extracts customer speaking turns,
    and performs topic modeling using BERTopic. The results are saved in the specified output directory.
    
    Example:
        plexus analyze topics --input-file ~/projects/Call-Criteria-Python/.plexus_training_data_cache/dataframes/1039_no_score_id_Start-Date_csv.parquet
    """
    logging.info(f"Starting topic analysis for file: {input_file}")
    
    # Convert paths to Path objects
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
        # Process the transcripts
        _, text_file_path = transform_transcripts(
            input_file=str(input_path),
            content_column=content_column
        )
        logging.info("Transcript transformation completed successfully")
        
        if not skip_analysis:
            # Create descriptive output directory
            analysis_dir = f"topics_{min_ngram}-{max_ngram}gram_{num_topics if num_topics else 'auto'}"
            output_dir = str(output_path / analysis_dir)
            
            logging.info("Starting BERTopic analysis...")
            analyze_topics(
                text_file_path=text_file_path,
                output_dir=output_dir,
                nr_topics=num_topics,
                n_gram_range=(min_ngram, max_ngram),
                min_topic_size=min_topic_size,
                top_n_words=top_n_words
            )
            logging.info("BERTopic analysis completed successfully")
        else:
            logging.info("Skipping BERTopic analysis as requested")
        
    except Exception as e:
        logging.error(f"Error during topic analysis: {e}")
        return

@analyze.command()
@click.option('--model', default='gemma3:27b', help='Ollama model to use (default: gemma3:27b)')
@click.option('--prompt', default='Why is the sky blue?', help='Prompt to send to the model')
def test_ollama(
    model: str,
    prompt: str
):
    """
    Test Ollama LLM integration.
    
    This command sends a test request to the Ollama API to verify it's working correctly.
    The response from the model will be printed to the console.
    
    Example:
        plexus analyze test-ollama --model gemma3:27b --prompt "Explain quantum computing in simple terms"
    """
    logging.info(f"Testing Ollama integration with model: {model}")
    
    try:
        # Call the test function
        response = test_ollama_chat(model=model, prompt=prompt)
        
        # Print the response
        print("\n--- Ollama Response ---")
        print(response)
        print("----------------------\n")
        
        logging.info("Ollama test completed successfully")
    except Exception as e:
        logging.error(f"Error testing Ollama: {e}")
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