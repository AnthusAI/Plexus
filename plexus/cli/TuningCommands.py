import re
import rich
import click
import plexus
import os
import json
import pandas as pd
from openpyxl.styles import Font
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import BaseOutputParser
from langchain_openai import ChatOpenAI
import tiktoken

from plexus.CustomLogging import logging
from plexus.Registries import scorecard_registry

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

@tuning.command(help="Generate JSON-L files for training and validation.")
@click.option('--scorecard-name', required=True, help='The name of the scorecard.')
@click.option('--score-name', help='The name of the score to generate JSON-L for.')
@click.option('--maximum-number', type=int, default=100, help='Maximum number of samples, total.')
@click.option('--generate-completions', is_flag=True, help='Generate completions using an LLM.')
@click.option('--verbose', is_flag=True, help='Verbose output.')
def generate_examples(scorecard_name, score_name, maximum_number, generate_completions, verbose):
    """
    Generate JSON-L files that include a specified number of examples, using the prompt templates
    from the score configuration combined with data and ground-truth labels.

    :param scorecard_name: The name of the scorecard.
    :type scorecard_name: str
    :param score_name: The name of the score to generate JSON-L for.
    :type score_name: str
    :param maximum_number: Maximum number of samples, total.
    :type maximum_number: int
    :param generate_completions: Generate completions using an LLM.
    :type generate_completions: bool
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
    
    # Instantiate the score class using the configuration parameters.
    score_configuration = scorecard_class.scores.get(score_name, {})
    logging.info(f"Score Configuration: {rich.pretty.pretty_repr(score_configuration)}")
    score_class = scorecard_class.score_registry.get(score_name)
    if score_class is None:
        logging.error(f"Score class for '{score_name}' not found in the registry.")
        return
    score_configuration['scorecard_name'] = scorecard_class.name
    score_configuration['score_name'] = score_name
    try:
        score_instance = score_class(**score_configuration)
    except Exception as e:
        logging.error(f"Failed to instantiate score class for '{score_name}': {str(e)}")
        return

    # Get data
    sample_rows = None
    score_instance = score_class(**score_configuration)
    score_instance.load_data(queries=score_configuration['data'].get('queries'))
    score_instance.process_data()

    total_rows = len(score_instance.dataframe)
    if maximum_number > total_rows:
        logging.warning(f"Requested sample size ({maximum_number}) is larger than available data ({total_rows}). Using all available data.")
        sample_rows = score_instance.dataframe
    else:
        sample_rows = score_instance.dataframe.sample(n=maximum_number)

    if verbose:
        logging.info(f"First few sample rows: {sample_rows.to_dict('records')[:5]}")

    # Calculate the number of training samples
    num_training_samples = int(len(sample_rows) * 0.8)

    training_data = []
    validation_data = []
    training_ids = []
    validation_ids = []

    # Get templates
    nodes = score_instance.get_prompt_templates()
    example_refinement_nodes = score_instance.get_example_refinement_templates()
    logging.info(f"Nodes: {nodes}")

    # Loop through the sample rows and generate JSON-L
    for index, row in sample_rows.iterrows():
        formatted_messages = []
        for node_templates, example_refinement_template in zip(nodes, example_refinement_nodes):
            for template in node_templates:
                if isinstance(template, ChatPromptTemplate):
                    try:
                        messages = template.format_messages(text=row['text'])
                        formatted_messages.extend([
                            {
                                "role": "user" if message.type == "human" else message.type, 
                                "content": message.content
                            }
                            for message in messages
                        ])
                    except Exception as e:
                        logging.error(f"Error formatting messages for row {index}: {e}")

        if not formatted_messages:
            logging.warning(f"No formatted messages for row {index}. Skipping.")
            continue

        if verbose:
            logging.info(f"Formatted messages for row {index}: {formatted_messages}")

        def generate_completion_with_retry(messages, correct_answer, max_attempts=5):
            class CompletionOutputParser(BaseOutputParser[dict]):
                def parse(self, output: str) -> dict:
                    def extract_last_word(text):
                        cleaned_text = re.sub(r'[^\w\s]', '', text)
                        words = cleaned_text.split()
                        return words[-1] if words else ""

                    answer = extract_last_word(output)
                    return {
                        "answer": answer,
                        "completion": output.strip(),
                    }

            output_parser = CompletionOutputParser()
            
            for attempt in range(max_attempts):
                temperature = min(0.2 * attempt, 1.0)
                model = ChatOpenAI(model_name="gpt-4o-2024-08-06", temperature=temperature)
                
                prompt = ChatPromptTemplate.from_messages(messages)
                answer_chain = prompt | model | output_parser
                result = answer_chain.invoke({"text": row['text']})

                # Use the example_refinement_template to refine the answer, if there is one.
                if example_refinement_template:
                    prompt.append(
                        HumanMessage(content=example_refinement_template)
                    )
                    refinement_chain = prompt | model | output_parser
                    result = refinement_chain.invoke({"text": row['text']})

                if result['answer'].lower() == correct_answer.lower():
                    return result
                
                if verbose:
                    logging.info(f"Attempt {attempt + 1}: Generated answer '{result['answer']}' "
                                 f"does not match correct answer '{correct_answer}'. "
                                 f"Retrying with temperature {temperature:.2f}")
            
            logging.warning(f"Failed to generate matching completion after {max_attempts} attempts. "
                            f"Using the last generated completion.")
            return result

        if generate_completions:
            messages_with_hint = messages + [
                HumanMessage(content=f"<hint>The correct answer is {row[score_name]}</hint>")
            ]
            completion = generate_completion_with_retry(messages_with_hint, row[score_name])
        else:
            completion = row[score_name]

        formatted_messages.append({"role": "assistant", "content": completion})

        message = {"messages": formatted_messages}

        if len(training_data) < num_training_samples:
            training_data.append(message)
            training_ids.append(row['content_id'])
        else:
            validation_data.append(message)
            validation_ids.append(row['content_id'])

    logging.info(f"Number of training samples: {len(training_data)}")
    logging.info(f"Number of validation samples: {len(validation_data)}")

    # Ensure the directory exists
    output_dir = get_output_dir(scorecard_name, score_name)
    os.makedirs(output_dir, exist_ok=True)
    
    # Save to JSON-L files
    with open(get_file_path(output_dir, "training"), "w") as train_file:
        for entry in training_data:
            train_file.write(f"{json.dumps(entry)}\n")
    
    with open(get_file_path(output_dir, "validation"), "w") as val_file:
        for entry in validation_data:
            val_file.write(f"{json.dumps(entry)}\n")

    # Save content IDs to txt files
    with open(get_id_file_path(output_dir, "training"), "w") as train_id_file:
        for content_id in training_ids:
            train_id_file.write(f"{content_id}\n")

    with open(get_id_file_path(output_dir, "validation"), "w") as val_id_file:
        for content_id in validation_ids:
            val_id_file.write(f"{content_id}\n")

    logging.info(f"Generated JSON-L and ID files in {output_dir}")

@tuning.command(help="Subsample JSON-L files based on token count estimates.")
@click.option('--scorecard-name', required=True, help='The name of the scorecard.')
@click.option('--score-name', help='The name of the score to subsample JSON-L for.')
@click.option('--maximum-tokens', type=int, default=2000000, help='Maximum number of tokens.')
@click.option('--verbose', is_flag=True, help='Verbose output.')
def subsample_examples(scorecard_name, score_name, maximum_tokens, verbose):
    logging.info(f"Subsampling examples for [magenta1][b]{score_name}[/b][/magenta1] on [magenta1][b]{scorecard_name}[/b][/magenta1] with a max token limit of {maximum_tokens}...")

    input_dir = get_output_dir(scorecard_name, score_name)
    training_file_path = get_file_path(input_dir, "training")

    if not os.path.exists(training_file_path):
        logging.error(f"Training file not found in {input_dir}.")
        return

    def load_jsonl(file_path):
        with open(file_path, 'r') as file:
            return [json.loads(line) for line in file]

    training_data = load_jsonl(training_file_path)

    if verbose:
        logging.info(f"Loaded {len(training_data)} training examples.")

    def subsample_data(data, max_tokens):
        encoder = tiktoken.encoding_for_model("gpt-4o")
        subsampled_data = []
        current_tokens = 0

        for entry in data:
            entry_tokens = sum(len(encoder.encode(message['content'])) for message in entry['messages'])
            if current_tokens + entry_tokens > max_tokens:
                break
            subsampled_data.append(entry)
            current_tokens += entry_tokens
            if verbose:
                logging.info(f"Subsampled entry tokens: [magenta1]{entry_tokens:>10,}[/magenta1]   "
                             f"Current tokens: [magenta1]{current_tokens:>10,}[/magenta1]")

        return subsampled_data

    training_data = subsample_data(training_data, maximum_tokens)

    output_dir = get_output_dir(scorecard_name, score_name, subsampled=True, max_tokens=maximum_tokens)
    os.makedirs(output_dir, exist_ok=True)

    def save_jsonl(data, file_path):
        with open(file_path, 'w') as file:
            for entry in data:
                file.write(f"{json.dumps(entry)}\n")

    save_jsonl(training_data, get_file_path(output_dir, "training"))

    logging.info(f"Subsampled JSON-L files saved in {output_dir}")