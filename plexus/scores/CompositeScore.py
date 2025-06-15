import os
import re
import json
import yaml
import importlib
from decimal import Decimal
from abc import ABC, abstractmethod
import tiktoken
from pydantic import BaseModel
import pandas as pd

from plexus.processors.RelevantWindowsTranscriptFilter import RelevantWindowsTranscriptFilter
from plexus.scores.Score import Score
from plexus.Registries import scorecard_registry
from plexus.scores.KeywordClassifier import KeywordClassifier
from plexus.PromptTemplateLoader import PromptTemplateLoader
from plexus.CustomLogging import logging

class CompositeScore(Score):
    """
    A composite score is a score that is composed of multiple elements, each of which is a score.
    This class handles the work of computing the values of each individual element and then
    combining them into a single composite score.  It also handles the work of computing the
    costs of the individual elements and the composite score.
    """

    def __init__(self, **parameters):
        """
        Initializes a new instance of the CompositeScore class.

        This constructor sets up the initial state of the CompositeScore object, including initializing
        token accumulators for tracking API usage costs and preparing the list to store individual
        element results.
        """
        super().__init__(**parameters)

        self.explanation = []
        self.quote = []

        self.input_cost =  Decimal('0.0')
        self.output_cost = Decimal('0.0')
        self.total_cost =  Decimal('0.0')    
        self.prompt_tokens     = 0
        self.completion_tokens = 0
        self.llm_request_count = 0
        self.llm_request_history = []

        self.element_results = []

        self.chat_history = []

    def to_dict(self):
        return {
            'text': self.text,
            'explanation': self.explanation,
            'quote': self.quote,
            'llm_request_count': self.llm_request_count,
            'prompt_tokens': self.prompt_tokens,
            'completion_tokens': self.completion_tokens,
            'input_cost': str(self.input_cost),
            'output_cost': str(self.output_cost),
            'total_cost': str(self.total_cost),
            'element_results': [result.to_dict() for result in self.element_results],
            'filtered_text': self.filtered_text,
            'chat_history': self.chat_history
        }

    def save_results_to_json(self, session_id, output_directory_path):
        os.makedirs(output_directory_path, exist_ok=True)
        output_file_path = os.path.join(output_directory_path, f"{session_id}.json")
        with open(output_file_path, 'w') as file:
            json.dump(self.to_dict(), file)

    @classmethod
    def load_results_from_json(cls, session_id, input_directory_path):
        input_file_path = os.path.join(input_directory_path, f"{session_id}.json")

        with open(input_file_path, 'r') as file:
            data = json.load(file)

        instance = cls(scorecard_name=data['scorecard_name'], score_name=data['score_name'])
        instance.explanation = data['explanation']
        instance.quote = data['quote']
        instance.llm_request_count = data['llm_request_count']
        instance.prompt_tokens = data['prompt_tokens']
        instance.completion_tokens = data['completion_tokens']
        instance.input_cost = Decimal(data['input_cost'])
        instance.output_cost = Decimal(data['output_cost'])
        instance.total_cost = Decimal(data['total_cost'])
        instance.element_results = [Score.Result.from_dict(result) for result in data['element_results']]
        instance.filtered_text = data['filtered_text']
        instance.chat_history = data['chat_history']

        return instance

    @classmethod
    def extract_yaml_section(cls, markdown_content, section_name):
        lines = markdown_content.split('\n')
        section_lines = []
        in_section = False

        for line in lines:
            if line.startswith("```"):
                continue
            if f'# {section_name}' in line:
                in_section = True
                continue
            elif '#' in line and in_section:
                break
        
            if in_section:
                section_lines.append(line)
    
        yaml_content = '\n'.join(section_lines).lstrip().rstrip()

        # Define a custom constructor for handling `!regex` tags in YAML
        def regex_constructor(loader, node):
            value = loader.construct_scalar(node)
            try:
                return re.compile(value)
            except re.error as exc:
                raise yaml.constructor.ConstructorError(f"Could not compile regex: {value}") from exc

        yaml.SafeLoader.add_constructor('!regex', regex_constructor)

        return yaml.safe_load(yaml_content)

    @classmethod
    def create_from_markdown(cls, *, scorecard, score_name, markdown_file_path):
        if not os.path.exists(markdown_file_path):
            return None

        with open(markdown_file_path, 'r') as file:
            markdown_content = file.read()

        config = cls.extract_yaml_section(markdown_content, 'Configuration') or {}
        preprocessing_config = cls.extract_yaml_section(markdown_content, 'Preprocessing')
        decision_tree_config = cls.extract_yaml_section(markdown_content, 'Decision Tree')

        llm_model_name = config.get('model', 'gpt-3.5-turbo-16k-0613')
        completion_name = config.get('completion', 'azure/CallCriteriaGPT35Turbo16k')
        chunking = config.get('chunking', True)

        base_module_path = 'plexus.scores'

        try:
            module = importlib.import_module(f"{base_module_path}.LLMClassifier")
            base_class = getattr(module, 'LLMClassifier')
        except (ImportError, AttributeError) as e:
            base_class = CompositeScore
            print(f"Warning: Could not dynamically import from {base_module_path}.LLMClassifier. Defaulting to OpenAICompositeScore. Error: {e}")

        # Create a new subclass of CompositeScore
        class CompositeScoreFromMarkdown(base_class):
            def __init__(self, **parameters):
                parameters['model_name'] = llm_model_name
                parameters['completion_name'] = completion_name
                super().__init__(**parameters)
                self.preprocessing_config = preprocessing_config
                self.chunking = chunking
                self.decision_tree = decision_tree_config
                self.prompt_template_loader = PromptTemplateLoader(markdown_content=markdown_content)
                self.name = score_name

                self.elements = self.generate_elements_from_markdown()
                self.overall_questions = self.elements[0]['prompt'].strip().split('\n')
            
            def load_context(self, context):
                """
                Load any necessary artifacts or models based on the context.
                """
                pass

            class Result(Score.Result):
                """
                This Score has an additional output attribute, explanation, which is a string
                """
                explanation: str
                quote: str
                
            def predict(self, context, model_input: Score.Input) -> Score.Result:
                """
                Make predictions on the input data.

                :param context: Context for the prediction.
                :param model_input: The input data for making predictions.
                :return: The predictions.
                """
                # Get the text from the model input dataframe.
                text = model_input.text

                self.filtered_text = self.process_text(text=text)

                # Run the decision tree.
                return self.compute_result()

            def process_text(self, *, text):
                if not self.chunking:
                    return text

                keyword_patterns = []

                for preprocessing_step in self.preprocessing_config:
                    if 'processor' in preprocessing_step and preprocessing_step['processor'] == 'keyword_filter':
                        keywords = preprocessing_step['keywords']
                        for keyword in keywords:
                            if isinstance(keyword, str):
                                if keyword.startswith('!regex '):
                                    pattern = keyword[7:]
                                    keyword_patterns.append(re.compile(pattern))
                                else:
                                    keyword_patterns.append(keyword)
                            elif isinstance(keyword, re.Pattern):
                                keyword_patterns.append(keyword)

                text_df = pd.DataFrame({'text': [text]})

                # Use the KeywordClassifier with the combined list of strings and regex patterns
                filtered_text_df = RelevantWindowsTranscriptFilter(
                    classifier=KeywordClassifier(keyword_patterns, self.parameters.scorecard_name, self.parameters.score_name)
                ).process(text_df)

                filtered_text = filtered_text_df['text'].iloc[0]

                return filtered_text

            def generate_elements_from_markdown(self):
                elements = []
                for section_name in self.prompt_template_loader.sections:
                    prompt = self.prompt_template_loader.get_template(section_name=section_name, content_type='prompt')
                    try:
                        rules = self.prompt_template_loader.get_template(section_name=section_name, content_type='rules')
                    except ValueError:
                        rules = None

                    element = {
                        'name': CompositeScore.normalize_element_name(section_name),
                        'prompt': prompt,
                        'rules': rules,
                    }
                    elements.append(element)
                return elements
            
            def predict_validation(self):
                pass
            def register_model(self):
                pass
            def save_model(self):
                pass

        scorecard.score_registry.register(
            cls=CompositeScoreFromMarkdown,
            properties=config,
            name=score_name,
        )

        return CompositeScoreFromMarkdown

    @abstractmethod
    def construct_system_prompt(self, *, text):
        """
        Defines the system prompt used at the start of the chat history.  This system prompt
        includes minimal, basic instructions, and the text.
        """

    @abstractmethod
    def compute_element_for_chunk(self, *, name, element_type, previous_messages=None, prompt, chunk):
        """
        The orchestration framework in CompositeScore calls this function to do the work specific to a composite score element.
        
        This method must be implemented by subclasses.
        """
        pass

    @abstractmethod
    def compute_element(self, *, name, text=None):
        """
        Compute the result for a single element of the composite score.  This method is
        called by the `element` method and should be implemented by concrete subclasses.

        Args:
            name (str): The name of the element to compute the result for.
            text (str): The text text to use for computing the result.

        Returns:
            Score.Result: The result of the element classification.
        """
        pass

    # The next three functions are for crafting the chat history.
    # They are used to group the element results by name, select the element results to include,
    # and then remove the system messages and concatenate the chat history.

    def group_element_results_by_name(self):
        grouped_results = {}
        for result in self.element_results:
            element_name = result.name
            if element_name not in grouped_results:
                grouped_results[element_name] = []
            grouped_results[element_name].append(result)
        return grouped_results

    def select_element_results_to_include(self, grouped_results):
        selected_results = []
        for element_name, results in grouped_results.items():
            yes_results = [result for result in results if result.value == 'Yes']
            if yes_results:
                selected_results.extend(yes_results)
            else:
                # If there are no 'Yes' results, include the first result
                selected_results.append(results[0])
        return selected_results

    def concatenate_chat_history(self, selected_results):
        # Correcting the model version based on the latest guidance
        encoder = tiktoken.encoding_for_model("gpt-3.5")
        concatenated_chat_history = []
        current_token_count = 0
        token_limit = 15000

        for result in selected_results:
            for message in result.metadata['chat_history']:
                if message['role'] in ['user', 'assistant']:
                    # Encode the message content and count tokens
                    encoded_message = encoder.encode(message['content'])
                    message_token_count = len(encoded_message)

                    # Check if adding this message exceeds the token limit
                    if current_token_count + message_token_count <= token_limit:
                        concatenated_chat_history.append(message)
                        current_token_count += message_token_count
                    else:
                        # Stop adding messages if we reach the token limit
                        return concatenated_chat_history
        return concatenated_chat_history

    def get_total_token_count(self, chat_history):
        encoder = tiktoken.encoding_for_model("gpt-3.5")
        # This method might not be necessary if the count is maintained during concatenation
        total_token_count = 0
        for message in chat_history:
            encoded_message = encoder.encode(message['content'])
            total_token_count += len(encoded_message.tokens)
        return total_token_count

    def compute_explanation_and_relevant_quote(compute_result_method):
        def wrapper(self, *, value, result_index=0, **kwargs):
            
            grouped_results = self.group_element_results_by_name()
            selected_results = self.select_element_results_to_include(grouped_results)
            concatenated_chat_history = self.concatenate_chat_history(selected_results)
  
            # Accumulate the explanation and relevant quotes.
            self._compute_explanation_and_relevant_quote_implementation(
                chat_history=concatenated_chat_history,
                value=value,
                result_index=result_index)
            
            # Return the result for the current element
            return compute_result_method(self, value=value, result_index=result_index, **kwargs)
        return wrapper

    def _compute_explanation_and_relevant_quote_implementation(self, *, chat_history, value, result_index):
        # This method should be implemented by subclasses if they need to compute explanation and quote.
        # The underscore prefix indicates that it's an internal method.
        pass

    def break_text_into_chunks(self, text, max_chunk_size=2000):
        chunks = []
        while len(text) > max_chunk_size:
            # Find the last occurrence of the delimiter before the max_chunk_size
            break_point = text.rfind("\n...\n", 0, max_chunk_size)
            if break_point != -1:
                # If found, split the text at the delimiter, excluding it from the chunk
                chunk = text[:break_point]
            else:
                # If no delimiter is found, split the text at max_chunk_size
                chunk = text[:max_chunk_size]
            
            # Trim the chunk to ensure no trailing spaces are included
            chunk = chunk.rstrip()
            chunks.append(chunk)
            
            # Update the text to start after the delimiter or the chunk
            text = text[break_point + 5:] if break_point != -1 else text[max_chunk_size:]
        
        # Ensure the last part of the text is also trimmed before adding
        if text:
            chunks.append(text.rstrip())
        return chunks

    def _process_text_chunk(self, name, text_chunk):
        """
        Process a single chunk of text and compute the score result.

        Args:
            name (str): The name of the element to compute the score for.
            text (str): The chunk of text text to use for computing the score.

        Returns:
            The score result for the chunk.
        """
        truncated_text_preview = text_chunk[:64] + "..." if len(text_chunk) > 64 else text_chunk
        logging.debug(f"Transcript chunk:\n{truncated_text_preview}")

        element = self.get_element_by_name(name=name)
        prompt = element['prompt']
        logging.debug(f"Prompt:\n{prompt}")

        score_result = self.compute_element_for_chunk(
            name=name,
            element_type='prompt',
            prompt=prompt,
            chunk=text_chunk
        )

        rules = element.get('rules')
        if score_result.is_yes() and rules is not None:
            logging.debug(f"Rules:\n{rules}")
            if not self.chunking:
                previous_messages=score_result.metadata['chat_history'][-2:]
            else:
                previous_messages=score_result.metadata['chat_history']

            clarification_result = self.compute_element_for_chunk(
                name=name,
                element_type='clarification',
                
                previous_messages=previous_messages,
                prompt=rules,
                chunk=text_chunk
            )

            logging.debug(f'Clarification result for {name} rules: {score_result}')

            if clarification_result.is_no():
                clarification_result.explanation = clarification_result.explanation
                clarification_result.quote = clarification_result.quote
                self.element_results.append(clarification_result)
                return clarification_result

            score_result.metadata['chat_history'] = clarification_result.metadata['chat_history']
            score_result.explanation = clarification_result.explanation
            score_result.quote = clarification_result.quote

        logging.debug(f'Element result for {name}: {score_result}')

        self.element_results.append(score_result)
        return score_result

    def compute_element(self, *, name, text=None):
        """
        Compute the result for a single element of the composite score by processing
        the filtered text in chunks and aggregating the results.

        Args:
            name (str): The name of the element to compute the score for.
            text (str, optional): The text text to use for computing the score.

        Returns:
            A boolean value that indicates whether the score result was "Yes" or not.
        """
        print("\n---\n")
        logging.info(f'Classifying {name} for {self.name}')

        element = self.get_element_by_name(name=name)
        if callable(element):
            return element()

        logging.info(f"Chunking: {self.chunking}")
        if not self.chunking:
            chunks = [self.filtered_text]
        else:
            chunks = self.break_text_into_chunks(self.filtered_text)

        logging.debug(f"Filtered text:\n{self.filtered_text}")
        logging.info(f"Number of text chunks: {len(chunks)}")
        for index, chunk in enumerate(chunks, start=1):
            logging.debug(f"Chunk {index}:\n{chunk}")

        from concurrent.futures import ThreadPoolExecutor, as_completed

        total_chunks = len(chunks)
        chunk_results = []
        futures = []

        # Process the chunks in parallel. Set to 1 for sequential processing that short-circuits
        max_threads = 20

        if max_threads > 1:
            with ThreadPoolExecutor(max_workers=max_threads) as executor:
                futures = [executor.submit(self._process_text_chunk, name, chunk) for chunk in chunks]
                for future in as_completed(futures):
                    result = future.result()
                    chunk_results.append(result)
                    if result.is_yes():
                        return True
        else:
            for chunk in chunks:
                result = self._process_text_chunk(name, chunk)
                chunk_results.append(result)
                if result.is_yes():
                    return True

        for chunk_result in chunk_results:
            if "completion_explanation" in chunk_result.metadata:
                return chunk_result.is_yes()

        return chunk_results[0].is_yes()

    @staticmethod
    def normalize_element_name(name):
        return re.sub(r"\W+", "_", name).lower().strip("_")

    def compute_result(self, *, tree=None):
        tree = tree if tree is not None else self.decision_tree

        if isinstance(tree, list) and all(isinstance(item, dict) and 'score' in item and 'value' in item for item in tree):
            ordered_results = {item['score']: item['value'] for item in tree}
            return self.multiple(ordered_results)
        elif isinstance(tree, str):
            method_result = getattr(self, tree)()
            return [method_result]

        element_name = CompositeScore.normalize_element_name(tree["element"])
        decision_result = self.compute_element(name=element_name)

        next_step = tree.get(decision_result)
        return self.compute_result(tree=next_step)
    
    def get_element_by_name(self, *, name):
        """
        Get the element by name from the list of elements or a function pointer if the name matches a whitelist of allowed function names.
        If the name does not match an element or an allowed function name, return None.

        Args:
            name (str): The name of the element to retrieve from the composite score's elements or the name of the function.

        Returns:
            dict or function or None: The element dictionary if an element with the given name exists, a function pointer if a valid function name is specified and found, or None if no match is found.
        """
        allowed_function_names = ['filtered_text_is_empty']
        
        for element in self.elements:
            if element['name'] == name:
                return element

        if name in allowed_function_names:
            return getattr(self, name, None)
        return None

    def filtered_text_is_empty(self):
        """
        A common decision used at the start of decision trees.  If the filtered text is blank
        then it means that nothing in the text was judged to be relevant to the classification,
        and we can skip any further processing for that chunk.
        """
        return not self.filtered_text

    def get_accumulated_costs(self):
        """
        Get the expenses that have been accumulated over all the computed elements.

        Returns:
            dict: A dictionary containing the accumulated expenses:
                  'llm_request_count', 'prompt_tokens', 'completion_tokens', 'input_cost', 'output_cost', 'total_cost'
        """
        return {
            'llm_request_count': self.llm_request_count,
            'prompt_tokens': self.prompt_tokens,
            'completion_tokens': self.completion_tokens,
            'input_cost': self.input_cost,
            'output_cost': self.output_cost,
            'total_cost': self.total_cost
        }

    # These functions help implement an elegant, DSL-like interface for the compositing
    # logic in the `compute_score_result()` functions in the concrete implementations.
    # They are not strictly necessary, but they make the code more readable.

    @compute_explanation_and_relevant_quote
    def return_result_with_context(self, *, value, name=None, result_index=0):
        """
        Return the result with the explanation and relevant quote.
        """

        # Find the name unless the `multiple()` function needed to explicitly set it.
        if name is None:
            name = self.name

        # This stuff only goes into the first result or else
        # costs and stuff could get double-counted.
        element_results = []
        llm_request_history = []
        decision_tree = None
        if result_index == 0:
            element_results = self.element_results
            llm_request_history = self.llm_request_history
            decision_tree = self.decision_tree

        return self.Result(
            name        = name,
            value       = value,
            explanation = self.explanation[result_index],
            quote       = self.quote[result_index],
            metadata = {
                "overall_question": self.overall_questions[result_index],
                "element_results": element_results,
                "llm_request_history": llm_request_history,
                "decision_tree": decision_tree

            },
        )

    def yes(self):
        """
        A shorthand function for returning a 'Yes' score result, with the element results
        for the individual elements of the composite score.  This helps keep the code minimal
        in the concrete implementations.
        """

        chat_history_pretty_format = json.dumps(self.chat_history, indent=4)

        return self.return_result_with_context(value='Yes')
    
    def no(self):
        """
        A shorthand function for returning a 'No' score result, with the element results
        for the individual elements of the composite score.  This helps keep the code minimal
        in the concrete implementations.
        """

        chat_history_pretty_format = json.dumps(self.chat_history, indent=4)

        return self.return_result_with_context(value='No')

    def na(self):
        """
        A shorthand function for returning a 'NA' score result, with the element results
        for the individual elements of the composite score.  This helps keep the code minimal
        in the concrete implementations.
        """

        chat_history_pretty_format = json.dumps(self.chat_history, indent=4)

        return self.return_result_with_context(value='NA')

    def multiple(self, ordered_results):
        results = []
        for index, (key, value) in enumerate(ordered_results.items()):            
            results.append(
                self.return_result_with_context(
                    name=key,
                    value=value,
                    result_index=index
                )
            )
        
        chat_history_pretty_format = json.dumps(self.chat_history, indent=4)

        return results
