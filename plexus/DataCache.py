import os
import boto3
import json
from tqdm import tqdm
import pandas as pd
from io import StringIO
from plexus.logging import logging
from plexus.cli.console import console
from rich.progress import Progress
from rich.console import Console
from rich.table import Table
from rich.columns import Columns
from functools import partial

class DataCache:
    def __init__(self,
        athena_database,
        athena_results_bucket,
        s3_bucket,
        local_cache_directory="./.plexus_training_data_cache/"):

        self.aws_region = os.environ['AWS_REGION_NAME']
        self.athena_client = boto3.client('athena', region_name=self.aws_region)
        self.s3_client = boto3.client('s3', region_name=self.aws_region)
        self.athena_database = athena_database
        self.athena_results_bucket = athena_results_bucket
        self.s3_bucket = s3_bucket
        self.local_cache_directory = local_cache_directory

        os.makedirs(self.local_cache_directory, exist_ok=True)
        logging.info("Initialized DataCache with local cache directory at [purple][b]{}[/b][/purple]".format(self.local_cache_directory), extra={"highlighter": None})

    def execute_athena_query(self, query):
        query_execution_response = self.athena_client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={'Database': self.athena_database},
            ResultConfiguration={
                'OutputLocation': f's3://{self.athena_results_bucket}/',
                'EncryptionConfiguration': {'EncryptionOption': 'SSE_S3'}
            }
        )
        logging.info("Executed Athena query, received QueryExecutionId: {}".format(query_execution_response['QueryExecutionId']))
        return query_execution_response['QueryExecutionId']

    def get_query_results(self, query_execution_id):
        import time
        
        query_execution_response = self.athena_client.get_query_execution(QueryExecutionId=query_execution_id)
        query_execution_state = query_execution_response['QueryExecution']['Status']['State']

        with console.status(f"Query in state '{query_execution_state}', waiting for completion...", spinner_style="boxBounce2"):
            while query_execution_state in ['QUEUED', 'RUNNING']:
                time.sleep(5)
                query_execution_response = self.athena_client.get_query_execution(QueryExecutionId=query_execution_id)
                query_execution_state = query_execution_response['QueryExecution']['Status']['State']

        if query_execution_state == 'SUCCEEDED':
            query_results_paginator = self.athena_client.get_paginator('get_query_results')
            query_results_iterator = query_results_paginator.paginate(QueryExecutionId=query_execution_id)
            
            all_query_results = []
            for query_results_page in query_results_iterator:
                all_query_results.extend(query_results_page['ResultSet']['Rows'])
            
            logging.info("Query succeeded and all results retrieved")
            return all_query_results
        elif query_execution_state in ['FAILED', 'CANCELLED']:
            error_message = query_execution_response['QueryExecution']['Status']['StateChangeReason']
            logging.error(f"Query failed with state: {query_execution_state}. Error: {error_message}")
            raise Exception(f"Query failed with state: {query_execution_state}. Error: {error_message}")

    def download_report(self, scorecard_id, report_id):
        metadata_key = f"scorecard_id={scorecard_id}/report_id={report_id}/metadata.json"
        transcript_key = f"scorecard_id={scorecard_id}/report_id={report_id}/transcript.json"
        transcript_txt_key = f"scorecard_id={scorecard_id}/report_id={report_id}/transcript.txt"

        metadata_local_path = os.path.join(self.local_cache_directory, metadata_key)
        transcript_local_path = os.path.join(self.local_cache_directory, transcript_key)
        transcript_txt_local_path = os.path.join(self.local_cache_directory, transcript_txt_key)

        if os.path.exists(metadata_local_path):
            logging.info("Metadata already exists locally at {}".format(metadata_local_path))
            with open(metadata_local_path, 'r') as metadata_file:
                metadata = json.load(metadata_file)
        else:
            logging.info("Downloading metadata from S3 bucket {}".format(self.s3_bucket))
            metadata_obj = self.s3_client.get_object(Bucket=self.s3_bucket, Key=metadata_key)
            metadata = json.loads(metadata_obj['Body'].read().decode('utf-8'))
            os.makedirs(os.path.dirname(metadata_local_path), exist_ok=True)
            with open(metadata_local_path, 'w') as metadata_file:
                json.dump(metadata, metadata_file)

        # if os.path.exists(transcript_local_path):
        #     logging.info("Transcript already exists locally at {}".format(transcript_local_path))
        #     with open(transcript_local_path, 'r') as transcript_file:
        #         transcript = json.load(transcript_file)
        # else:
        #     logging.info("Downloading transcript from S3 bucket {}".format(self.s3_bucket))
        #     transcript_obj = self.s3_client.get_object(Bucket=self.s3_bucket, Key=transcript_key)
        #     transcript = json.loads(transcript_obj['Body'].read().decode('utf-8'))
        #     os.makedirs(os.path.dirname(transcript_local_path), exist_ok=True)
        #     with open(transcript_local_path, 'w') as transcript_file:
        #         json.dump(transcript, transcript_file)

        if os.path.exists(transcript_txt_local_path):
            logging.info("Transcript text already exists locally at {}".format(transcript_txt_local_path))
            with open(transcript_txt_local_path, 'r') as transcript_txt_file:
                transcript_txt = transcript_txt_file.read()
        else:
            logging.info("Downloading transcript text from S3 bucket {}".format(self.s3_bucket))
            transcript_txt_obj = self.s3_client.get_object(Bucket=self.s3_bucket, Key=transcript_txt_key)
            transcript_txt = transcript_txt_obj['Body'].read().decode('utf-8')
            os.makedirs(os.path.dirname(transcript_txt_local_path), exist_ok=True)
            with open(transcript_txt_local_path, 'w') as transcript_txt_file:
                transcript_txt_file.write(transcript_txt)

        # return metadata, transcript, transcript_txt
        return metadata, transcript_txt

    def load_dataframe(self, *, scorecard_id):
        dataframe_cache_filename = os.path.join(self.local_cache_directory, f"scorecard_id={scorecard_id}.h5")
        if os.path.exists(dataframe_cache_filename):
            logging.info(f"Loading dataframe from cache at [purple][b]{dataframe_cache_filename}[/b][/purple]", extra={"highlighter": None})
            return pd.read_hdf(dataframe_cache_filename, key='df')

        scorecard_query = f"""
            SELECT DISTINCT report_id
            FROM "{self.athena_database}"
            WHERE scorecard_id = '{scorecard_id}'
        """
        scorecard_query_execution_id = self.execute_athena_query(scorecard_query)
        scorecard_query_results = self.get_query_results(scorecard_query_execution_id)

        report_ids = [row['Data'][0]['VarCharValue'] for row in scorecard_query_results[1:]]

        from concurrent.futures import ThreadPoolExecutor
        import functools

        def process_report(report_id, progress, downloading_progress):
            report_metadata, report_transcript_txt = self.download_report(scorecard_id, report_id)
            progress.update(downloading_progress, advance=1)
            report_row = {'report_id': report_id}
            for score in report_metadata.get('scores', []):
                report_row[score['name']] = score['answer']
            report_row['Transcription'] = report_transcript_txt
            return report_row

        with Progress() as progress:
            downloading_progress = progress.add_task("[magenta]Downloading report files from training data lake...[magenta]", total=len(report_ids))
            process_report_with_progress = partial(process_report, progress=progress, downloading_progress=downloading_progress)

            with ThreadPoolExecutor() as executor:
                report_data = list(executor.map(process_report_with_progress, report_ids))

        scorecard_dataframe = pd.DataFrame(report_data)
        scorecard_dataframe.to_hdf(dataframe_cache_filename, key='df', mode='w')

        logging.info(f"Loaded dataframe for scorecard {scorecard_id} with {len(scorecard_dataframe)} rows and columns: {', '.join(scorecard_dataframe.columns)}")

        return scorecard_dataframe
