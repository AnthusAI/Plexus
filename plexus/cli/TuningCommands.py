import re
import rich
import click
import plexus
import os
import json
import pandas as pd
from openpyxl.styles import Font
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.output_parsers import BaseOutputParser
from langchain_openai import ChatOpenAI
import tiktoken
import concurrent.futures
from functools import partial

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
@click.option('--score-name', help='The name of the score to generate JSON-L for. If not provided, all scores will be processed.')
@click.option('--maximum-number', type=int, default=100, help='Maximum number of samples, total.')
@click.option('--generate-completions', is_flag=True, help='Generate completions using an LLM.')
@click.option('--completion-model', default='gpt-4o-mini-2024-07-18', help='The model to use for generating completions.')
@click.option('--retry-mismatches', is_flag=True, help='Retry when generated answer does not match the label.')
@click.option('--fresh', is_flag=True, help='Pull fresh, non-cached data from the data lake.')
@click.option('--verbose', is_flag=True, help='Verbose output.')
def generate_examples(scorecard_name, score_name, maximum_number, generate_completions, completion_model, retry_mismatches, fresh, verbose):
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
        sample_rows = None
        score_instance = score_class(**score_configuration)
        score_instance.load_data(data=score_configuration['data'], fresh=fresh)
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

        def process_row(row, nodes, example_refinement_nodes, generate_completions, completion_model, retry_mismatches, verbose):
            formatted_messages = []
            for node_templates, example_refinement_template in zip(nodes, example_refinement_nodes):
                for template in node_templates:
                    if isinstance(template, ChatPromptTemplate):
                        try:
                            messages = template.format_messages(text=row['text'])
                            formatted_messages.extend(messages)  # Keep original message objects
                        except Exception as e:
                            logging.error(f"Error formatting messages for row {row.name}: {e}")
                            return None

            if not formatted_messages:
                logging.warning(f"No formatted messages for row {row.name}. Skipping.")
                return None

            if verbose:
                logging.info(f"Formatted messages for row {row.name}: {formatted_messages}")

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
                    model = ChatOpenAI(model_name=completion_model, temperature=temperature)
                    
                    prompt = ChatPromptTemplate.from_messages(messages)
                    answer_chain = prompt | model | output_parser
                    result = answer_chain.invoke({"text": row['text']})

                    # Use the example_refinement_template to refine the answer, if there is one.
                    if example_refinement_template:
                        logging.info(f"Refining completion with template: {example_refinement_template}")
                        logging.info(f"Raw completion: {result['completion']}")
                        prompt.extend([
                            AIMessage(content=result['completion']),
                            HumanMessage(content=example_refinement_template)
                        ])
                        refinement_chain = prompt | model | output_parser
                        refined_result = refinement_chain.invoke({"text": row['text']})
                        result['completion'] = re.sub(r'\n+', '\n', refined_result['completion'])
                        logging.info(f"Refined completion: {result['completion']}")

                    if result['answer'].lower() == correct_answer.lower():
                        return result['completion']
                    
                    if not retry_mismatches:
                        if verbose:
                            logging.info(f"Generated answer '{result['answer']}' does not match correct answer '{correct_answer}'. Skipping.")
                        return None

                    if verbose:
                        logging.info(f"Attempt {attempt + 1}: Generated answer '{result['answer']}' "
                                     f"does not match correct answer '{correct_answer}'. "
                                     f"Retrying with temperature {temperature:.2f}")
                
                logging.warning(f"Failed to generate matching completion after {max_attempts} attempts. "
                                f"Skipping item.")
                return None

            if generate_completions:
                messages_with_hint = formatted_messages + [
                    HumanMessage(content=f"<hint>The correct answer is {row[current_score_name]}</hint>")
                ]
                completion = generate_completion_with_retry(messages_with_hint, row[current_score_name])
                if completion is None:
                    return None
            else:
                completion = row[current_score_name]

            formatted_messages.append(AIMessage(content=completion))

            # Convert messages to dict format for JSON serialization
            serializable_messages = [
                {"role": "system" if isinstance(msg, SystemMessage) else "user" if isinstance(msg, HumanMessage) else "assistant",
                 "content": msg.content}
                for msg in formatted_messages
            ]

            return {"messages": serializable_messages, "content_id": row['content_id']}

        # Create a partial function with fixed arguments
        process_row_partial = partial(
            process_row,
            nodes=nodes,
            example_refinement_nodes=example_refinement_nodes,
            generate_completions=generate_completions,
            completion_model=completion_model,
            retry_mismatches=retry_mismatches,
            verbose=verbose
        )

        # Open files at the beginning
        output_dir = get_output_dir(scorecard_name, current_score_name)
        os.makedirs(output_dir, exist_ok=True)
        
        train_file = open(get_file_path(output_dir, "training"), "w")
        val_file = open(get_file_path(output_dir, "validation"), "w")
        train_id_file = open(get_id_file_path(output_dir, "training"), "w")
        val_id_file = open(get_id_file_path(output_dir, "validation"), "w")

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                future_to_row = {executor.submit(process_row_partial, row): row for _, row in sample_rows.iterrows()}
                
                processed_count = 0
                for future in concurrent.futures.as_completed(future_to_row):
                    row = future_to_row[future]
                    try:
                        result = future.result()
                        if result is not None:
                            message, content_id = result['messages'], result['content_id']
                            
                            if len(training_data) < num_training_samples:
                                json.dump({"messages": message}, train_file)
                                train_file.write("\n")
                                train_file.flush()
                                train_id_file.write(f"{content_id}\n")
                                train_id_file.flush()
                                training_data.append(message)
                                training_ids.append(content_id)
                            else:
                                json.dump({"messages": message}, val_file)
                                val_file.write("\n")
                                val_file.flush()
                                val_id_file.write(f"{content_id}\n")
                                val_id_file.flush()
                                validation_data.append(message)
                                validation_ids.append(content_id)
                            
                            processed_count += 1
                            if processed_count >= maximum_number:
                                break
                    except Exception as exc:
                        logging.error(f"Processing row {row.name} generated an exception: {exc}")

            logging.info(f"Number of training samples: {len(training_data)}")
            logging.info(f"Number of validation samples: {len(validation_data)}")

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
@click.option('--maximum-tokens', type=int, default=2000000, help='Maximum number of tokens.')
@click.option('--verbose', is_flag=True, help='Verbose output.')
def subsample_examples(scorecard_name, score_name, maximum_tokens, verbose):
    logging.info(f"Subsampling examples for [magenta1][b]{score_name}[/b][/magenta1] on [magenta1][b]{scorecard_name}[/b][/magenta1] with a max token limit of {maximum_tokens}...")

    encoder = tiktoken.encoding_for_model("gpt-4o")
    
    def load_jsonl(file_path):
        with open(file_path, 'r') as file:
            return [json.loads(line) for line in file]

    if score_name:
        score_names = [score_name]
    else:
        # Get all score directories
        base_dir = f"tuning/{scorecard_name}"
        score_names = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]
        logging.info(f"Processing all scores: {score_names}")

    score_files = []
    for score in score_names:
        input_dir = get_output_dir(scorecard_name, score)
        training_file_path = get_file_path(input_dir, "training")
        if os.path.exists(training_file_path):
            score_files.append((score, training_file_path))
        else:
            logging.warning(f"Training file not found for score {score} in {input_dir}.")

    if not score_files:
        logging.error("No valid training files found.")
        return

    subsampled_data = []
    current_tokens = 0
    file_iterators = [iter(load_jsonl(file_path)) for _, file_path in score_files]

    while current_tokens < maximum_tokens and file_iterators:
        for i, iterator in enumerate(file_iterators):
            try:
                entry = next(iterator)
                entry_tokens = sum(len(encoder.encode(message['content'])) for message in entry['messages'])
                
                if current_tokens + entry_tokens <= maximum_tokens:
                    subsampled_data.append(entry)
                    current_tokens += entry_tokens
                    if verbose:
                        logging.info(f"Added entry from {score_files[i][0]}. "
                                     f"Entry tokens: [magenta1]{entry_tokens:>10,}[/magenta1]   "
                                     f"Current tokens: [magenta1]{current_tokens:>10,}[/magenta1]")
                else:
                    if verbose:
                        logging.info(f"Reached token limit. Stopping.")
                    break
            except StopIteration:
                file_iterators.pop(i)
                if verbose:
                    logging.info(f"Finished processing {score_files[i][0]}")
                break
        else:
            continue
        break

    output_dir = get_output_dir(scorecard_name, "combined" if len(score_names) > 1 else score_names[0], subsampled=True, max_tokens=maximum_tokens)
    os.makedirs(output_dir, exist_ok=True)

    output_file_path = get_file_path(output_dir, "training")
    with open(output_file_path, 'w') as file:
        for entry in subsampled_data:
            json.dump(entry, file)
            file.write('\n')

    logging.info(f"Subsampled JSON-L file saved in {output_file_path}")
    logging.info(f"Total tokens: {current_tokens:,}")
    logging.info(f"Total examples: {len(subsampled_data)}")