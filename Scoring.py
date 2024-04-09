import os
import json
import copy
import base64
import pandas as pd
import logging
import requests
import random
import time
import pprint
from decimal import Decimal
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from tenacity import retry, wait_fixed, stop_after_attempt, before_log, retry_if_exception_type
from requests.exceptions import Timeout, RequestException
import mlflow
from concurrent.futures import ThreadPoolExecutor
import concurrent.futures

import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import ListedColormap

from graphviz import Digraph
from jinja2 import Template

from call_criteria_database.database import DB
from call_criteria_database.report import Report
from call_criteria_database.transcript import Transcript
from call_criteria_database.anthus_scorecard_request import AnthusScorecardRequest
from call_criteria_database.anthus_scorecard_job import AnthusScorecardJob
from call_criteria_database.anthus_scorecard_response import AnthusScorecardResponse

from .CompositeScore import CompositeScore
from .ScoreResult import ScoreResult
from .Scorecard import Scorecard
from .ScorecardResults import ScorecardResults
from .ScorecardResultsAnalysis import ScorecardResultsAnalysis

from .storage.FileStorageBackend import FileStorageBackend

from dotenv import load_dotenv
load_dotenv()
server_name   = os.getenv('DB_SERVER')
database_name = os.getenv('DB_NAME')
user_name     = os.getenv('DB_USER')
password      = os.getenv('DB_PASS')

DB.set_current(server_name, database_name, user_name, password)
session = DB.get_current()

class Scoring:
    def __init__(self, *,
        scorecard: Scorecard,
    ):
        self.scorecard = scorecard
        self.subset_of_score_names = None # ['Total loss to family']

        self.session = DB.get_current()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def score_names(self):
        return self.subset_of_score_names if self.subset_of_score_names is not None else self.scorecard.score_names()

    def score_names_to_process(self):
        all_score_names_to_process = self.scorecard.score_names_to_process()
        if self.subset_of_score_names is not None:
            return [score_name for score_name in self.subset_of_score_names if score_name in all_score_names_to_process]
        else:
            return all_score_names_to_process

    def time_execution(func):
        def wrapper(self, *args, **kwargs):
            start_time = time.time()
            result = func(self, *args, **kwargs)
            end_time = time.time()
            execution_time = end_time - start_time
            print(f"{func.__name__} executed in {execution_time:.2f} seconds.")
            return result
        return wrapper

    @time_execution
    def run(self):

        # Configure logging
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

        # Fetch any scoring requests that don't already have associated jobs from the database.
        logging.info("Fetching scoring requests...")
        requests = AnthusScorecardRequest.new_requests(session)
        # requests = session.query(AnthusScorecardRequest).all()

        # Limit to just the first request.
        requests = requests[:1]

        if len(requests) == 0:
            logging.warn(f"No new requests.")
            exit()

        logging.info(f"Scoring the first new request: {requests[0].report_id}")

        results = []
        max_thread_pool_size = 10

        # Create a thread pool executor
        with ThreadPoolExecutor(max_workers=max_thread_pool_size) as executor:
            # Submit tasks to the executor to score each transcript in parallel
            future_to_request = {executor.submit(self.score_request, request=request): request for request in requests}

            for future in concurrent.futures.as_completed(future_to_request):
                request = future_to_request[future]
                try:
                    result = future.result()

                    print("Result:\n", result)

                    results.append(result)
                except Exception as exc:
                    print(f"Request generated an exception: {request}, {exc}")

        if not os.path.exists("./tmp/"):
            os.makedirs("./tmp/")

        logging.info(f"Scoring completed for job ID: {results[0]['job_id']}")
        logging.info("Writing reports...")

        # Generate JSON log from scoring that batch.
        scorecard_results = ScorecardResults(results)
        analysis = ScorecardResultsAnalysis(
            scorecard_results=scorecard_results
        )
        scorecard_results.save_to_file("tmp/scorecard_results.json")

        # Generate HTML scoring report from that same thing.
        html_report_content = analysis.generate_html_report(include_evaluation=False)
        with open("tmp/scorecard_report_with_costs.html", "w") as file:
            file.write(html_report_content)

        html_report_content = analysis.generate_html_report(include_evaluation=False, redact_cost_information=True)
        with open("tmp/scorecard_report.html", "w") as file:
            file.write(html_report_content)

        # Move the artifacts into place on the storage backend.
        if not os.path.exists("./results/"):
            os.makedirs("./results/")
        storage = FileStorageBackend(base_path='./results')
        json_file_path = storage.compute_file_path(
            scorecard_id = results[0]['scorecard_id'],
            report_id =    results[0]['report_id'],
            job_id =       results[0]['job_id'],
            extension =    "json"
        )
        storage.save_file(tmp_path="tmp/scorecard_results.json", target_path=json_file_path)

        html_file_path = storage.compute_file_path(
            scorecard_id = results[0]['scorecard_id'],
            report_id =    results[0]['report_id'],
            job_id =       results[0]['job_id'],
            suffix =       '-with-costs',
            extension =    'html'
        )
        storage.save_file(tmp_path="tmp/scorecard_report_with_costs.html", target_path=html_file_path)

        html_file_path = storage.compute_file_path(
            scorecard_id = results[0]['scorecard_id'],
            report_id =    results[0]['report_id'],
            job_id =       results[0]['job_id'],
            extension =    'html'
        )
        storage.save_file(tmp_path="tmp/scorecard_report.html", target_path=html_file_path)

        logging.info("Wrote reports.")

        # Commit the DB transaction after successfully writing the artifact files to the data lake.
        self.session.commit()

        logging.info("Triggering Call Criteria processing...")

        job_id = results[0]['job_id']
        job = session.query(AnthusScorecardJob).filter_by(job_id=job_id).first()
        # job.reset_call_criteria_processing()
        job.trigger_call_criteria_processing()

        job.job_status = 'processed'
        self.session.commit()

        logging.info("Done.")

    # Function to classify a single transcript and collect metrics
    @retry(
        wait=wait_fixed(2),          # wait 2 seconds between attempts
        stop=stop_after_attempt(5),  # stop after 5 attempts
        before=before_log(logging.getLogger(), logging.INFO),       # log before retry
        retry=retry_if_exception_type((Timeout, RequestException))  # retry on specific exceptions
    )
    def score_request(self, *, request):
        report = request.report

        job = AnthusScorecardJob(
            report_id=report.id,
            job_status='pending'
        )
        self.session.add(job)

        transcript = request.transcript()
        logging.debug(f"Transcript content: {transcript}")
        
        # Some of our test data has escaped newlines, so we need to replace them with actual newlines.
        transcript = transcript.replace("\\n", "\n")

        logging.debug(f"Fixed transcript content: {transcript}")

        scorecard_results = self.scorecard.score_entire_transcript(
            transcript=transcript,
            # subset_of_score_names=["Total loss to family"]
        )

        for question_name in scorecard_results.keys():
            score_result = scorecard_results[question_name]

            result = AnthusScorecardResponse(
                job_id=job.job_id,
                report_id=report.id,
                question_name = question_name,
                answer = score_result['value'],
                reasoning = score_result['metadata']['reasoning'],
                quote = score_result['metadata']['relevant_quote']
            )
            self.session.add(result)

            # Add the full transcript to the score result, for the reports.
            score_result['transcript'] = transcript

        job.job_status = 'scored'
        session.flush() # Flush the session without committing to get a UUID for the job.

        return {
            'report_id':    report.id,
            'scorecard_id': request.scorecard_id,
            'job_id':       job.job_id,
            'session_id':   report.session_id,
            'results':      scorecard_results,
        }
