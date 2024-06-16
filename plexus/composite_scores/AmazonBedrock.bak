import os
import re
import json
import time
import logging
import requests
import functools
import litellm
from openai import OpenAI
from requests.exceptions import HTTPError
from tenacity import retry, retry_if_exception_type, wait_random_exponential, stop_after_attempt, retry_if_exception_type, before_sleep_log

from plexus.CompositeScore import CompositeScore
from plexus.Score import Score
from plexus.ScoreResult import ScoreResult
from plexus.Registries import scorecard_registry

litellm.set_verbose=True

class AmazonBedrockCompositeScore(CompositeScore):
    """
    Concrete implementation of the CompositeScoreBase class using OpenAI's API.
    """

    def __init__(self, *, transcript):
        super().__init__(transcript=transcript)
        self.model_name = 'bedrock/meta.llama2-70b-chat-v1'

    @retry(
        wait=wait_random_exponential(multiplier=1, max=60),
        retry=retry_if_exception_type(json.JSONDecodeError),
        stop=stop_after_attempt(3),
        before_sleep=before_sleep_log(logging, logging.INFO)
    )
    def compute_element(self, *, name, transcript=None):
        try:
            prompt = self.construct_prompt(element_name=name, transcript=transcript)
            response = self.amazon_bedrock_api_request(
                messages=[prompt],
            )
        except Exception as e:
            logging.error(f"An error occurred during the chat completion request: {e}")
            return None

        score_result_metadata = {
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'input_cost': 0.0,
            'output_cost': 0.0,
            'total_cost': 0.0
        }

        response_json = response.json()
        logging.info(f"Full response JSON: {response_json}")

        element_answer_json_string = \
            self.extract_json_response(response_json['choices'][0]['message']['content'])

        try:
            tool_results = json.loads(element_answer_json_string)
            logging.info(f"Successfully parsed JSON response: {tool_results}")
        except json.JSONDecodeError as json_error:
            logging.error(f"Failed to parse JSON response: {json_error}")
            raise

        # The element name and prompt.
        score_result_metadata['element_name'] = name
        element = self.get_element_by_name(name=name)
        if element is None:
            raise ValueError(f"No element found with the name: {name}")
        score_result_metadata['prompt'] = element['prompt']

        # We need the filtered transcript also, for the report.
        score_result_metadata['transcript'] = transcript

        # The classification result and the reasoning.
        score_result_metadata['value'] =          tool_results['answer']
        score_result_metadata['reasoning'] =      tool_results.get('reasoning', "")
        score_result_metadata['relevant_quote'] = tool_results.get('relevant_quote', "")

        # The API tokens used.
        score_result_metadata['prompt_tokens'] =     response_json['usage']['prompt_tokens']
        score_result_metadata['completion_tokens'] = response_json['usage']['completion_tokens']
        score_result_metadata['total_tokens'] =      response_json['usage']['total_tokens']

        # Calculate costs
        score_result_metadata['input_cost'] = \
            score_result_metadata['prompt_tokens'] * self.token_prices()['prompt_tokens']
        score_result_metadata['output_cost'] = \
            score_result_metadata['completion_tokens'] * self.token_prices()['completion_tokens']
        score_result_metadata['total_cost'] = \
            score_result_metadata['input_cost'] + score_result_metadata['output_cost']
        
        # Record these costs in the accumulators in this instance.
        self.prompt_tokens     += score_result_metadata['prompt_tokens']
        self.completion_tokens += score_result_metadata['completion_tokens']
        self.input_cost        += score_result_metadata['input_cost']
        self.output_cost       += score_result_metadata['output_cost']
        self.total_cost        += score_result_metadata['total_cost']

        return ScoreResult(value=score_result_metadata['value'], metadata=score_result_metadata)

    @retry(
        wait=wait_random_exponential(multiplier=1, max=60),  # Exponential backoff with random jitter
        retry=retry_if_exception_type((openai.RateLimitError, openai.APIConnectionError, openai.InternalServerError)),
        stop=stop_after_attempt(5),  # Stop after 5 attempts
        before_sleep=before_sleep_log(logging, logging.INFO)
    )
    def amazon_bedrock_api_request(self, messages, tools=None, tool_choice=None):
        return litellm.completion(
            model=self.model_name,
            messages=messages,

            top_p=1,
            temperature=0.5,

            max_tokens=512,

            timeout=45
        )

    # Construct the message for the request
    def construct_prompt(self, *, element_name=None, transcript):
        element = self.get_element_by_name(name=element_name)
        if element is None:
            raise ValueError(f"No element found with the name: {element_name}")
        prompt = element['prompt']
        logging.debug(f"Prompt:\n{prompt}")

        return {
            "role": "user",
            "content": f"""
This is a transcript of a call between a customer and a call center agent:

```
{transcript}
```

{prompt}

Valid answer options: "Yes", or "No".  Only answer one time for the one question.
Provide the answer and your reasoning and a relevant quote from the transcript in JSON format as a hash with three keys: "answer", "reasoning", and "relevant_quote".  (Relevant quote is optional, since it won't always make sense.)
Provide ONLY the JSON response and nothing else.
"""
    }

    def extract_json_response(self, response_content):
        # Regular expression pattern to find JSON within Markdown code block
        json_pattern = re.compile(r'```json(.+?)```', re.DOTALL)
        match = json_pattern.search(response_content)
        if match:
            return match.group(1).strip()
        else:
            # If no JSON code block is found, return the original response content
            return response_content

    @functools.lru_cache(maxsize=None)
    def token_prices(self):

        # Define the prices for each model and variant
        prices = {
            'bedrock/amazon.titan-text-express-v1': {
                'prompt_tokens': 0.0008 / 1000,
                'completion_tokens': 0.0016 / 1000
            },
            'bedrock/meta.llama2-13b-chat-v1': {
                'prompt_tokens': 0.00075 / 1000,
                'completion_tokens': 0.00100 / 1000
            },
            'bedrock/meta.llama2-70b-chat-v1': {
                'prompt_tokens': 0.00195 / 1000,
                'completion_tokens': 0.00256 / 1000
            },
            'bedrock/anthropic.claude-v2': {
                'prompt_tokens': 0.00800 / 1000,
                'completion_tokens': 0.02400 / 1000
            }
        }

        # Return the prices for the matched model
        return prices.get(self.model_name, {'prompt_tokens': 0, 'completion_tokens': 0})

