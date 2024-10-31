import click
import logging
import pandas as pd
from plexus.Scorecard import Scorecard
from plexus.Registries import scorecard_registry
from langchain_community.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import ResponseSchema, StructuredOutputParser
import os

@click.group()
def analyze():
    """
    Analysis commands for evaluating scorecard configurations and feedback.
    """
    pass

@analyze.command()
@click.option('--scorecard-name', required=True, help='Name of the scorecard to analyze')
@click.option('--csv-path', required=True, help='Path to the CSV file containing feedback')
@click.option('--score-name', default='', help='Comma-separated list of score names to analyze')
def feedback(
    scorecard_name: str,
    csv_path: str,
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

    # Initialize LLM
    llm = ChatOpenAI(
        model="gpt-4o-mini-2024-07-18",
        api_key=os.environ.get("OPENAI_API_KEY"),
        max_tokens=500,
        temperature=0.3,
    )
    prompt_analyzer = PromptAnalyzer(llm)

    # Load CSV data
    try:
        df = pd.read_csv(csv_path)
        required_columns = ['form_id', 'TranscriptText', 'Comments']
        if not all(col in df.columns for col in required_columns):
            logging.error(f"CSV must contain columns: {required_columns}")
            return
    except Exception as e:
        logging.error(f"Error loading CSV file: {e}")
        return

    # Use the provided score name directly
    if not score_name:
        logging.error("score-name is required")
        return
        
    scores_to_analyze = [score_name]
    score_data = df  # Use all rows since we're already looking at score-specific CSV
    
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