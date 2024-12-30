"""Shared functions between BatchCommands and PredictionCommands."""
import os
import json
import pandas as pd
from plexus.CustomLogging import logging

async def get_scoring_jobs_for_batch(client, batch_job_id):
    """Get scoring jobs associated with a batch job."""
    query = """
    query GetScoringJobsForBatch($batchJobId: ID!) {
        getBatchJob(id: $batchJobId) {
            scoringJobs {
                items {
                    id
                    scoringJob {
                        id
                        itemId
                        status
                        metadata
                    }
                }
            }
        }
    }
    """
    result = client.execute(query, {'batchJobId': batch_job_id})
    batch_job_scoring_jobs = result.get('getBatchJob', {}).get('scoringJobs', {}).get('items', [])
    
    # Extract the actual scoring jobs from the BatchJobScoringJob links
    scoring_jobs = [
        bj_sj['scoringJob'] 
        for bj_sj in batch_job_scoring_jobs 
        if bj_sj.get('scoringJob')
    ]
    
    return scoring_jobs

def select_sample_data_driven(scorecard_class, score_name, content_id, score_configuration, fresh):
    """Select a sample using data-driven approach."""
    # ... implementation ...

def select_sample_csv(csv_path, content_id):
    """Select a sample from CSV file."""
    if not os.path.exists(csv_path):
        logging.error(f"labeled-samples.csv not found at {csv_path}")
        raise FileNotFoundError(f"labeled-samples.csv not found at {csv_path}")

    df = pd.read_csv(csv_path)
    if content_id:
        sample_row = df[df['id'] == content_id]
        if sample_row.empty:
            logging.warning(f"ID '{content_id}' not found in {csv_path}. Selecting a random sample.")
            sample_row = df.sample(n=1)
    else:
        sample_row = df.sample(n=1)
    
    used_content_id = sample_row.iloc[0]['id']
    
    # Get scorecard key from the csv_path
    # Path format is 'scorecards/<scorecard_key>/experiments/labeled-samples.csv'
    scorecard_key = csv_path.split('/')[1]
    
    # Add required metadata for batch processing
    metadata = {
        "content_id": str(used_content_id),
        "account_key": "call-criteria",
        "scorecard_key": scorecard_key,
        "score_name": "accuracy"
    }
    sample_row['metadata'] = json.dumps(metadata)
    
    return sample_row, used_content_id 