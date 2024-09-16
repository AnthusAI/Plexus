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
@click.option('--generate-completions', is_flag=True, help='Generate completions using an LLM.')
@click.option('--completion-model', default='gpt-4o-mini-2024-07-18', help='The model to use for generating completions.')
@click.option('--retry-mismatches', is_flag=True, help='Retry when generated answer does not match the label.')
@click.option('--clean-existing', is_flag=True, help='Clean existing JSON-L files before generating new ones.')
@click.option('--fresh', is_flag=True, help='Pull fresh, non-cached data from the data lake.')
@click.option('--threads', type=int, default=20, help='Number of threads to use.')
@click.option('--verbose', is_flag=True, help='Verbose output.')
def generate_examples(scorecard_name, score_name,
                      maximum_number, train_ratio, generate_completions,
                      completion_model, retry_mismatches, clean_existing, fresh, verbose, threads):
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
    :param generate_completions: Generate completions using an LLM.
    :type generate_completions: bool
    :param completion_model: The model to use for generating completions.
    :type completion_model: str
    :param retry_mismatches: Retry when generated answer does not match the label.
    :type retry_mismatches: bool
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
        score_configuration = scorecard_class.scores.get(current_score_name, {})
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

        def process_row(scorecard_name, row, score_instance, score_configuration, generate_completions, completion_model, retry_mismatches, verbose):
            # Get the original user message from the score configuration
            user_message = score_instance.parameters.graph[0]['user_message']
            
            def generate_completion_with_retry(score_instance, row, correct_answer, max_attempts=5):
                # Strip ending punctuation from the correct answer
                cleaned_answer = re.sub(r'[.,?!]+$', '', correct_answer.strip())
                hint = f"\n\n<hint>The correct answer is: \"{cleaned_answer}\"</hint>"    

                # Create a temporary copy of the score instance for generating completions
                score_class = score_instance.__class__
                temp_score_configuration = score_configuration.copy()
                temp_score_configuration['graph'][0]['user_message'] = user_message + hint
                temp_score_instance = score_class(**temp_score_configuration)

                logging.info(f"System message: {temp_score_instance.parameters.graph[0]['system_message']}")
                logging.info(f"User message: {temp_score_instance.parameters.graph[0]['user_message']}")
                logging.info(f"Hint: {hint}")

                for attempt in range(max_attempts):
                    # Adjust temperature based on the attempt number
                    # temperature = min(0.2 * attempt, 1.0)
                    # temp_score_instance.parameters.graph[0]['model_provider'].temperature = temperature

                    # Use the predict method of the Score class
                    result = temp_score_instance.predict(context=None, model_input=Score.Input(text=row['text']))
                    if re.sub(r'[.,?!]+$', '', result[0].value.strip()).lower() == cleaned_answer.lower():
                        
                        # Use the example_refinement_template to refine the answer, if there is one.
                        example_refinement_nodes = score_instance.get_example_refinement_templates()
                        if example_refinement_nodes and example_refinement_nodes[0]:
                            model = ChatOpenAI(model_name=completion_model)
                            class CompletionOutputParser(BaseOutputParser[dict]):
                                def parse(self, output: str) -> dict:
                                    def extract_last_word(text):
                                        cleaned_text = re.sub(r'[^\w\s]', '', text)
                                        words = cleaned_text.split()
                                        return words[-1] if words else ""
                                    def extract_last_line(text):
                                        lines = text.split("\n")
                                        return lines[-1] if lines else ""
                                    def extract_first_word(text):
                                        cleaned_text = re.sub(r'[^\w\s]', '', text)
                                        words = cleaned_text.split()
                                        return words[0] if words else ""
                                    def extract_first_line(text):
                                        lines = text.split("\n")
                                        return lines[0] if lines else ""
                                    return {
                                        "first_word": extract_first_word(output),
                                        "first_line": extract_first_line(output),
                                        "last_word": extract_last_word(output),
                                        "last_line": extract_last_line(output),
                                        "completion": output.strip(),
                                    }
                            output_parser = CompletionOutputParser()
                            logging.info(f"Refining completion with template: {example_refinement_nodes}")
                            logging.info(f"Raw completion: {result[0].explanation}")
                            prompt = PromptTemplate(template=example_refinement_nodes[0], input_variables=["reformat"])
                            refinement_chain = prompt | model | output_parser
                            refined_result = refinement_chain.invoke({"reformat": result[0].explanation})
                            refined_result['completion'] = refined_result['completion'].replace('\n\n', '\n').strip()

                            # Remove quotes from the last line of the refined completion
                            lines = refined_result['completion'].split('\n')
                            last_line = lines[-1].strip()
                            if last_line.startswith('"') and last_line.endswith('"'):
                                lines[-1] = last_line[1:-1]
                            refined_result['completion'] = '\n'.join(lines)

                            original_panel = Panel(
                                result[0].explanation,
                                title="Original Completion",
                                border_style="royal_blue1",
                                expand=False,
                                width=100
                            )
                            refined_panel = Panel(
                                refined_result['completion'],
                                title="Refined Completion",
                                border_style="magenta1",
                                expand=False,
                                width=100
                            )
                            print(Columns([original_panel, refined_panel]))

                            if (refined_result['last_word'].lower() == result[0].value.strip().lower()) or \
                                (refined_result['last_line'].lower() == result[0].value.strip().lower()) or \
                                (refined_result['last_line'].lower() in result[0].explanation.strip().lower().split('\n')[-1]):
                                if verbose:
                                    logging.info(f"Refined answer '{refined_result['completion']}' matches original answer '{result[0].value}'.")
                                return refined_result['completion']
                            else:
                                if verbose:
                                    logging.info(f"Refined answer '{refined_result['answer']}' does not match original answer '{result[0].value}'. Skipping.")
                                return None

                        return result[0].explanation

                    if not retry_mismatches:
                        if verbose:
                            logging.info(f"Generated answer '{result[0].value}' does not match correct answer '{correct_answer}'. Skipping.")
                        return None

                    if verbose:
                        logging.info(f"Attempt {attempt + 1}: Generated answer '{result[0].value}' "
                                     f"does not match correct answer '{correct_answer}'.")
                
                logging.warning(f"Failed to generate matching completion after {max_attempts} attempts. "
                                f"Skipping item.")
                return None

            if generate_completions:
                
                # Determine the correct score name
                score_name = score_instance.parameters.score_name
                if hasattr(score_instance.parameters, 'label_field') and score_instance.parameters.label_field:
                    score_name = f"{score_name} {score_instance.get_label_score_name()}"

                completion = generate_completion_with_retry(score_instance, row, row[score_name])
                if completion is None:
                    return None
            else:

                if 'completion_template' in score_instance.parameters.graph[0]:
                    labels = row.copy()
                    
                    if 'massage_labels' in score_instance.parameters.graph[0]:
                        massage_labels_code = score_instance.parameters.graph[0]['massage_labels']
                        massage_labels_func = f"""
def massage_labels(labels):
    print("Executing massage_labels function")
{textwrap.indent(massage_labels_code, '    ')}
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

            # Construct the messages for the JSON-L file without the hint
            messages = [
                {"role": "system", "content": score_instance.parameters.graph[0]['system_message']},
                {"role": "user", "content": user_message.format(text=row['text'])},
                {"role": "assistant", "content": completion}
            ]

            return {"messages": messages, "content_id": row['content_id']}

        # Update the partial function call
        process_row_partial = partial(
            process_row,
            score_instance=score_instance,
            score_configuration=score_configuration,
            generate_completions=generate_completions,
            completion_model=completion_model,
            retry_mismatches=retry_mismatches,
            verbose=verbose
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