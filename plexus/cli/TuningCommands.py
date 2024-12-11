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

        num_training_samples = maximum_number
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
        row_indices = set(range(total_rows))

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
                labels = row.copy()
                
                if 'massage_labels' in score_instance.parameters.graph[0]:
                    massage_labels_code = score_instance.parameters.graph[0]['massage_labels']
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
                
                prompt = PromptTemplate(
                    input_types     = {"labels" : dict},
                    input_variables = ["labels"],
                    template        = score_instance.parameters.graph[0]['completion_template'])
                completion = prompt.format(labels=labels).strip()
                completion = re.sub(r'\s+$', '', completion)
            else:
                completion = row[score_instance.get_label_score_name()]
            logging.info(f"Completion: {completion}")

            # Construct the messages for the JSON-L file
            messages = [
                {"role": "system", "content": score_instance.parameters.graph[0]['system_message']},
                {"role": "user", "content": PromptTemplate.from_template(user_message, template_format = "jinja2").format(**{"text": row['text']})},
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
                    row_indices -= set(batch_indices)

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