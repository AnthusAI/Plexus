import os
import re
import json
import time
import httpx
import logging
import requests
import functools
import litellm
import openai
from openai import OpenAI
from decimal import Decimal
from openai_cost_calculator.openai_cost_calculator import calculate_cost
from requests.exceptions import HTTPError
from tenacity import retry, retry_if_exception_type, wait_random_exponential, stop_after_attempt, retry_if_exception_type, before_sleep_log
from jinja2 import Environment, PackageLoader, select_autoescape

from plexus.CompositeScore import CompositeScore
from plexus.Score import Score
from plexus.ScoreResult import ScoreResult
from plexus.Registries import scorecard_registry

# logging.getLogger("openai._base_client").setLevel(logging.INFO)

litellm.set_verbose=True

class ToolCallProcessingError(Exception):
    def __init__(self, exception, message, tool_arguments, *args):
        super().__init__(message, *args)
        self.tool_arguments = tool_arguments
        self.message = message
        self.exception = exception

class OpenAICompositeScore(CompositeScore):
    """
    Concrete implementation of the CompositeScoreBase class using OpenAI's API.
    """
    def __init__(self, *, transcript):
        super().__init__(transcript=transcript)
        # self.model_name = 'gpt-3.5-turbo-0125'
        self.model_name = 'gpt-3.5-turbo-16k-0613'
        # self.model_name = 'gpt-4-turbo-preview'

    # Define the tool for yes/no answer.
    yes_no_tool = [
        {
            "type": "function",
            "function": {
            "name": "classify_yes_no_with_reasoning",
            "description": "Provide a clear 'yes', 'no' as structured data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "answer": {
                        "type": "string",
                        "enum": ["yes", "no"],
                        "description": "Valid values: 'yes', 'no'.  Required."
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "The reasoning behind the answer. Required!"
                    },
                    "relevant_quote": {
                        "type": "string",
                        "description": "Any relevant quote from the transcript that supports the answer. Optional."
                    }
                },
                "required": ["answer", "reasoning"]
                }
            }
        }
    ]

    @retry(
        wait=wait_random_exponential(multiplier=1, max=600),
        retry=retry_if_exception_type(ValueError),
        stop=stop_after_attempt(4),
        before_sleep=before_sleep_log(logging, logging.INFO)
    )
    def compute_element_for_chunk(self, *, name, element_type, previous_messages=None, prompt, chunk):
        """
        The orchestration framework in CompositeScore calls this function to do the OpenAI work.
        """

        loggers = [logging.getLogger(name) for name in logging.root.manager.loggerDict]
        openai_loggers = [logger for logger in loggers if logger.name.startswith("openai")]

        # formatted_messages = ''
        # for message in transcript_and_prompt:
        #     formatted_messages += f"{message['role']}:\n{message['content']}\n\n"
        # logging.info(f"Messages to OpenAI:\n{formatted_messages}")

        new_message = self.construct_element_prompt(prompt=prompt, transcript=chunk)
        messages = [
            self.construct_system_prompt(transcript=chunk),
            new_message            
        ]
        if previous_messages is not None:
            messages = previous_messages + [new_message]

        for message in messages:
            logging.debug(f"{message['role']}:\n{message['content']}\n")

        score_result_metadata = {
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'input_cost':  Decimal('0.0'),
            'output_cost': Decimal('0.0'),
            'total_cost':  Decimal('0.0')
        }

        # The element name and prompt.
        score_result_metadata['element_name'] = name
        score_result_metadata['element_type'] = element_type

        element = self.get_element_by_name(name=name)
        if element is None:
            raise ValueError(f"No element found with the name: {name}")
        score_result_metadata['prompt'] = element['prompt']

        # Add this response to the chat history.
        # self.chat_history.append(
        #     self.construct_element_response_prompt(
        #         element_response=tool_results))

        # We need the filtered transcript also, for the report.
        score_result_metadata['transcript'] = chunk

        try:
            response = self.openai_api_request(
                name=name,
                element_type=element_type,
                messages=messages,
                # tools=self.yes_no_tool
            )

            response_content = response.choices[0].message.content
            logging.debug(f"Raw response content: {response_content}")
        except openai.APIError as e:
            logging.error(f"OpenAI API Error: {str(e)}")
            
            # Return 'No' if there are any errors processing this chunk.
            # For example: 'Safety' guardrail errors from the model concluding that the transcript chunk is
            # about suicide or sex or something.
            # TODO: Make this more robust, possibly by breaking the chunk into sub-chunks and attempting to process
            # each sub-chunk separately, so that we will discard less transcript data if any sub-chunk fails.
            score_result_metadata['value'] = "No"
            return ScoreResult(value="No", metadata=score_result_metadata)

        if response.choices[0]['finish_reason'] == 'content_filter':
            score_result_metadata['value'] = "No"
            return ScoreResult(value="No", metadata=score_result_metadata)

        # Add a log of this chat history including the response to the score result metadata.
        messages.append(
            {
                "role": "assistant",
                "content": response_content
            }
        )
        score_result_metadata['chat_history'] = messages

        # Extract the first word from the response content, accounting for punctuation
        first_word = re.split(r'\W+', response_content)[0].lower()

        # We might need these too, if the first word thing doesn't work out.
        first_no_index = response_content.lower().find("no")
        first_yes_index = response_content.lower().find("yes")

        # If the first word is a yes/no then call that the answer.
        if first_word in ["yes", "no"]:
            answer = first_word
            reasoning = response_content[len(first_word):].strip()

            answer = response_content[:3].lower()
            reasoning = response_content[3:].lstrip(", ")

            if reasoning and reasoning[0].islower():
                reasoning = reasoning.capitalize()

        # If not then ask for clarification.
        else:
            reasoning = response_content
            yes_or_no = self.clarify_yes_or_no(name=name, messages=messages)
            answer = yes_or_no['answer']
            messages.extend(yes_or_no['messages'])

        logging.info(f"Response:  {response_content}")
        logging.info(f"Value:     {answer}")
        logging.info(f"Reasoning: {reasoning}")

        # The answer result and the reasoning.
        score_result_metadata['response_content'] = response_content
        score_result_metadata['value'] =     answer
        
        score_result_metadata['reasoning'] = reasoning

        # The API tokens used.
        score_result_metadata['prompt_tokens'] =     response.usage.prompt_tokens
        score_result_metadata['completion_tokens'] = response.usage.completion_tokens
        score_result_metadata['total_tokens'] =      response.usage.total_tokens

        # Calculate costs
        cost_details = calculate_cost(
            model_name =    self.model_name,
            input_tokens =  score_result_metadata['prompt_tokens'],
            output_tokens = score_result_metadata['completion_tokens']
        )
        logging.info(f"Token counts:  Input: {score_result_metadata['prompt_tokens']}, Output: {score_result_metadata['completion_tokens']}")
        logging.info(f"Costs:  Input: {cost_details['input_cost']}, Output: {cost_details['output_cost']}, Total: {cost_details['total_cost']}")
        score_result_metadata['input_cost'] = cost_details['input_cost']
        score_result_metadata['output_cost'] = cost_details['output_cost']
        score_result_metadata['total_cost'] = cost_details['total_cost']
        
        # Record these costs in the accumulators in this instance.
        self.prompt_tokens     += score_result_metadata['prompt_tokens']
        self.completion_tokens += score_result_metadata['completion_tokens']
        self.input_cost        += score_result_metadata['input_cost']
        self.output_cost       += score_result_metadata['output_cost']
        self.total_cost        += score_result_metadata['total_cost']

        logging.info(f"Total token counts:  Input: {self.prompt_tokens}  Output: {self.completion_tokens}")
        logging.info(f"Total costs for score:  Input: {self.input_cost}, Output: {self.output_cost}, Total: {self.total_cost}")

        return ScoreResult(value=score_result_metadata['value'], metadata=score_result_metadata)

    def clarify_yes_or_no(self, *, name, messages, top_p=0.2):
        """
        Used to ask for clarification when the answer is not clear.
        This function will continue to repeat the question using increasing LLM randomness parameters until the answer is clear.
        Returns a dictionary with the answer and with the extra chat history messages that it took to get it.
        """
        yes_or_no_question = {
                "role": "user",
                "content": "Please summarize your answer with only the word \"Yes\" or the word \"No\"."
            }
        messages_with_yes_or_no_question = messages[-2:]
        messages_with_yes_or_no_question.append(yes_or_no_question)

        response = self.openai_api_request(
            name=name,
            element_type='clarify_yes_or_no',
            messages=messages_with_yes_or_no_question,
            top_p=top_p,
            max_tokens=1, # Only enough room for "yes" or "no".
            seed=None
        )

        response_content = response.choices[0].message.content
        logging.info(f"Yes-or-no clarification response: {response_content}")

        new_messages = [
            yes_or_no_question,
            {
                "role": "assistant",
                "content": response_content
            }
        ]

        if response_content in ["Yes", "No"]:
            return {
                "answer": response_content,
                "messages": new_messages
            }
        else:
            # If we still can't get a yes or a no after all that work then just call it a "No".
            if top_p >= 0.9:
                return {
                    "answer": "no",
                    "messages": new_messages
                }
            # Recurse with more randomness and try again.
            return self.clarify_yes_or_no(name=name, messages=messages, top_p=top_p + 0.1)

    @retry(
        wait=wait_random_exponential(multiplier=1, max=600),  # Exponential backoff with random jitter
        retry=retry_if_exception_type((openai.RateLimitError, openai.APIConnectionError, openai.InternalServerError, httpx.HTTPStatusError)),
        stop=stop_after_attempt(100),
        before_sleep=before_sleep_log(logging, logging.INFO)
    )
    def openai_api_request(self, name, element_type, messages, tools=None, tool_choice=None, top_p=0.05, seed=None, max_tokens=768):

        logging.debug("Messages to OpenAI:\n%s", json.dumps(messages, indent=4))

        # Construct the dictionary for the arguments
        request_arguments = {
            # "model": self.model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "timeout": 45,
            
            # Set top_p or temperature but not both. They're two ways to do the same thing.
            "top_p": top_p,
            "seed": seed,
            # "temperature": 0,
        }

        # Conditionally add 'tool_choice' if tools are provided and have the required structure
        if tools and isinstance(tools, list) and 'function' in tools[0]:
            request_arguments["tools"] = tools
            request_arguments["tool_choice"] = {"type": "function", "function": {"name": tools[0]['function']['name']}}

        # Use the constructed dictionary as **kwargs to pass to the function
        response = litellm.completion("azure/CallCriteriaGPT35Turbo16k", **request_arguments)

        self.llm_request_count += 1

        # Calculate costs
        cost_details = calculate_cost(
            model_name =    self.model_name,
            input_tokens =  response['usage']['prompt_tokens'],
            output_tokens = response['usage']['completion_tokens']
        )
        logging.info(f"Token counts:  Input: {response['usage']['prompt_tokens']}, Output: {response['usage']['completion_tokens']}")
        logging.info(f"Costs:  Input: {cost_details['input_cost']}, Output: {cost_details['output_cost']}, Total: {cost_details['total_cost']}")

        self.llm_request_history.append({
            'name': name,
            'element_type': element_type,
            'request': request_arguments,
            'response': response,
            'prompt_tokens': response['usage']['prompt_tokens'],
            'completion_tokens': response['usage']['completion_tokens'],
            'total_tokens': response['usage']['total_tokens'],
            'input_cost': cost_details['input_cost'],
            'output_cost': cost_details['output_cost'],
            'total_cost': cost_details['total_cost']
        })

        return response

    def construct_system_prompt(self, *, transcript):

        context = self.get_element_by_name(name='context')['prompt']
 
        system_prompt_template = Environment().from_string(context)
        context = system_prompt_template.render(transcript=transcript)

        return {
            "role": "system",
            "content": f"""
You're part of a text classification system for call center audio transcriptions.

Goal:
Your job is to examine chunks of text and make yes-or-no classifications, and also to provide your reasoning in terms of the question and the rules presented to you, and also to extract relevant quotes when applicable.

Background:
The system transcribes phone calls that are about 25 minutes long, filters them to find chunks that might possibly be relevant.  The chunks will be out of context and that might start with someone confusingly speaking an answer to a question that was trimmed out of the chunk of text.  Not all parts of the filtered transcript will necessarily apply to the question, you will almost always see extra noise.  Don't assume that statements you see without clear context are relevant to the question.  If you see a "Yes, we do", or, "No, I don't", then don't assume that it's about the question we're asking.  If you see someone talk about a question, don't assume it's about the question we're asking.  The agent will be filling out a form so they will be talking about questions in the call but that's different from our question that we're trying to answer here.  There will be a lot of irrelevant distractions in the transcripts, so understand that you'll hear stray things, and disregard anything without clear applicability to the question at hand.

Context:
{context}
"""
    }

    # Construct the message for the request
    def construct_element_prompt(self, *, prompt, transcript):

        system_prompt_template = Environment().from_string(prompt)
        prompt = system_prompt_template.render(transcript=transcript)

        return {
            "role": "user",
            "content": prompt
        }

    def construct_element_response_prompt(self, *, element_response):
        """
        Construct the message for a response.  We need to add those to the chat history also.
        We might want to reformat them instead of storing the actual, original response, so that
        appends here.

        Args:
            element_response: The response from the user to the element prompt.  A dictionary
                              with the elements: "answer", "reasoning", "relevant_quote".
        """

        if 'relevant_quote' not in element_response:
            element_response['relevant_quote'] = ""
        if element_response['relevant_quote'] is None:
            element_response['relevant_quote'] = ""

        return {
            "role": "assistant",
            "content": f"""
{element_response['answer']}
{element_response['reasoning']}
Relevant quote: "{element_response['relevant_quote']}"
"""
    }

    # Define the tool for yes/no answer.
    reasoning_and_relevant_quote_tool = [
        {
            "type": "function",
            "function": {
            "name": "provide_reasoning_and_relevant_quote",
            "description": "Provide the reasoning for the overall answer and if possible also a relevant quote from the transcript.",
            "parameters": {
                "type": "object",
                "properties": {
                        "reasoning": {
                        "type": "string",
                        "description": "The reasoning behind the answer. Required!"
                    },
                    "relevant_quote": {
                        "type": "string",
                        "description": "Any relevant quote from the transcript that supports the answer. Optional."
                    }
                },
                "required": ["reasoning", "relevant_quote"]
                }
            }
        }
    ]
    def _compute_reasoning_and_relevant_quote_implementation(self, *, chat_history, value, result_index):
        """
        Computes the reasoning and relevant quote for a specific result at a given index.

        This method is designed to handle a single result and should be called with the
        value of the result and the index of that result in the context of the overall
        assessment. It supports handling both single overall questions and a list of
        questions.

        Args:
            value: The result for which reasoning and quote are to be computed.
            result_index: The index of the result. This is used to select the corresponding
                        overall question if there are multiple. For a single overall question,
                        this should be 0.

        Returns:
            A tuple containing the reasoning and the relevant quote for the specific result.

        Raises:
            AttributeError: If the 'overall_question' attribute is not defined.
            IndexError: If 'result_index' is out of bounds for the 'overall_question' list.
            ValueError: If 'result_index' is not 0 when 'overall_question' is a single value.

        Note:
            This method updates the 'reasoning' and 'relevant_quotes' lists with the new
            computed values for the specific result.
        """        
        # Check if overall_question is a list and the result_index is valid
        if isinstance(self.overall_questions, list):
            if not (0 <= result_index < len(self.overall_questions)):
                raise IndexError(f"The result_index {result_index} is out of bounds for the 'overall_question' list.")
            question = self.overall_questions[result_index]
        else:
            if result_index != 0:
                raise ValueError("The 'result_index' must be 0 when 'overall_question' is a single value.")
            question = self.overall_questions[0]

        # Compute the reasoning and relevant quote for the specific result
        self.compute_single_reasoning_and_relevant_quote(
            chat_history=chat_history,
            question=question,
            result=value)

        # Return the reasoning and relevant quote for this specific result
        return self.reasoning[-1], self.relevant_quotes[-1]

    def compute_single_reasoning_and_relevant_quote(self, *, chat_history, question, result):
        # Define the before_retry function within this function for better organization
        def before_sleep(retry_state):
            # This function now acts after a failure but before the next attempt
            attempt_count = retry_state.kwargs.get('attempt_count', 0) + 1
            is_retry = attempt_count > 0

            # Accessing the exception from the last attempt
            if retry_state.outcome:
                exception = retry_state.outcome.exception()
                if exception:
                    logging.info(f"Handling exception from attempt {attempt_count}: {exception}")
                    retry_state.kwargs['error'] = exception.message
                    retry_state.kwargs['original_message'] = exception.tool_arguments
                    retry_state.kwargs['exception'] = exception.exception

            retry_state.kwargs['attempt_count'] = attempt_count
            retry_state.kwargs['is_retry'] = is_retry

        # Configure retry decorator with the before_retry function
        @retry(
            retry=retry_if_exception_type(ToolCallProcessingError),
            stop=stop_after_attempt(10),
            before_sleep=before_sleep
        )
        def inner_function(*,
            chat_history, question, result,
            is_retry=False,attempt_count=0, error=None, original_message=None, exception=None):

            return self._compute_single_reasoning_and_relevant_quote(
                chat_history=chat_history,
                question=question,
                result=result,
                is_retry=is_retry,
                attempt_count=attempt_count,
                error=error,
                original_message=original_message,
                exception=exception
            )

        # Call the inner function with initial parameters
        inner_function(chat_history=chat_history, question=question, result=result)

    def _compute_single_reasoning_and_relevant_quote(self, *,
         chat_history, question, result,
         is_retry=False, attempt_count=0, error=None, original_message=None, exception=None):
        """
        Use the accumulated chat history to ask the model a new question, asking
        it to condense the reasoning into a single sentence and to provide one
        relevant quote, in a structured format.  The end result is to set
        # self.reasoning and self.relevant_quote.
        """
 
        # Compute the next prompt in the chat history and add it to the history.
        prompts = [{
        "role": "user",
        "content": f"""
The overall question we're trying to answer through those previous questions is:
{question}

Our logic concludes, based on the sub-questions, that the overall answer is: {result}.

Provide your reasoning for that answer and if possible a breif relevant quote from the transcript using the `reasoning_and_relevant_quote_tool()` function.

You have some hints in your responses to the sub-questions.

The relevant quotes should be short, succinct.  Just one or two lines.  Don't provide any quotes if the answer is no.
"""
}]

        # This defaults to 'prompt' but it becomes 'request_valid_json' when it's a retry after a broken JSON response.
        element_type = 'prompt'

        if attempt_count > 1:
            if error:
                prompts.extend([
                    {
                        'role': 'assistant',
                        'content': original_message
                    },
                    {
                        'role': 'user',
                        'content': (
                            "I had an error parsing the JSON from your last response.  Please try again.  "
                            f"This is attempt number {attempt_count}.\n"
                            f"Error:\n{exception}"
                        )
                    }
                ])
            element_type = 'request_valid_json'
            logging.info("Retry prompts:\n%s", json.dumps(prompts, indent=4))
        else:
            logging.info("Prompt:\n%s", json.dumps(prompts[0], indent=4))

        new_chat_history = (
            chat_history +
            prompts
        )

        logging.debug("Summarization chat history:\n%s", json.dumps(new_chat_history, indent=4))

        response = self.openai_api_request(
            name='summary',
            element_type=element_type,
            messages=new_chat_history,
            tools=self.reasoning_and_relevant_quote_tool,
            max_tokens=2048
        )

        logging.info(f"Response: {response}")

        try:
            tool_calls = response.choices[0].message.tool_calls
            tool_call = tool_calls[0]
            tool_results = json.loads(tool_call.function.arguments)
        except Exception as e:
            try:
                repaired_json = tool_call.function.arguments + '"}'
                tool_results = json.loads(repaired_json)
            except json.JSONDecodeError:
                raise ToolCallProcessingError(
                    message="Failed to process tool call arguments after attempting to repair JSON",
                    exception=e,
                    tool_arguments=tool_call.function.arguments
                )

            raise ToolCallProcessingError(
                message="Failed to process tool call arguments",
                exception=e,
                tool_arguments=tool_call.function.arguments
            )
        logging.info(f"Reasoning: {tool_results.get('reasoning', '')}")
        logging.info(f"Relevant quote: {tool_results.get('relevant_quote', '')}")

        # Store the reasoning and quote.
        reasoning = tool_results.get('reasoning', "")
        self.reasoning.append(reasoning)
        relevant_quotes = tool_results.get('relevant_quote', "")
        self.relevant_quotes.append(relevant_quotes)

        # Calculate costs
        cost_details = calculate_cost(
            model_name =    self.model_name,
            input_tokens =  response.usage.prompt_tokens,
            output_tokens = response.usage.completion_tokens
        )

        result_metadata = {
            'element_name':      'summary',
            'value':             'summarized',
            'prompt':            prompts[0]['content'],
            'prompt_tokens':     response.usage.prompt_tokens,
            'completion_tokens': response.usage.completion_tokens,
            'input_cost':        cost_details['input_cost'],
            'output_cost':       cost_details['output_cost'],
            'total_cost':        cost_details['total_cost'],
            'reasoning':         reasoning,
            'relevant_quotes':   relevant_quotes,
            'chat_history':      new_chat_history
        }

        logging.info(f"Token counts:  Input: {result_metadata['prompt_tokens']}, Output: {result_metadata['completion_tokens']}")
        logging.info(f"Costs:  Input: {cost_details['input_cost']}, Output: {cost_details['output_cost']}, Total: {cost_details['total_cost']}")
        result_metadata['input_cost'] = cost_details['input_cost']
        result_metadata['output_cost'] = cost_details['output_cost']
        result_metadata['total_cost'] = cost_details['total_cost']

        # Record these costs in the accumulators in this instance.
        self.prompt_tokens     += result_metadata['prompt_tokens']
        self.completion_tokens += result_metadata['completion_tokens']
        self.input_cost        += result_metadata['input_cost']
        self.output_cost       += result_metadata['output_cost']
        self.total_cost        += result_metadata['total_cost']

        logging.info(f"Total token counts:  Input: {self.prompt_tokens}  Output: {self.completion_tokens}")
        logging.info(f"Total costs for score:  Input: {self.input_cost}, Output: {self.output_cost}, Total: {self.total_cost}")

        self.element_results.append(
            ScoreResult(value='summarized', metadata=result_metadata)
        )
