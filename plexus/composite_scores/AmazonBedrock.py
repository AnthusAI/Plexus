import os
import re
import json
import time
import logging
import requests
import functools
import litellm
from openai import OpenAI, RateLimitError, APIConnectionError, APIError as InternalServerError
from requests.exceptions import HTTPError
from tenacity import retry, retry_if_exception_type, wait_random_exponential, stop_after_attempt, before_sleep_log

from plexus.CompositeScore import CompositeScore
from plexus.Score import Score
from plexus.ScoreResult import ScoreResult
from plexus.Registries import scorecard_registry

litellm.set_verbose=True

class AmazonBedrockCompositeScore(CompositeScore):
    @retry(
        retry=retry_if_exception_type((RateLimitError, APIConnectionError, InternalServerError)),
        wait=wait_random_exponential(min=1, max=60),
        stop=stop_after_attempt(5),
        before_sleep=before_sleep_log(logging, logging.INFO)
    )
    def some_method(self):
        pass 