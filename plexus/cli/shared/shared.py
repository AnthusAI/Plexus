"""Shared functions between BatchCommands and PredictionCommands."""
import os
import json
import pandas as pd
import re
from pathlib import Path
from plexus.CustomLogging import logging

def get_score_yaml_path(scorecard_name: str, score_name: str) -> Path:
    """Compute the YAML file path for a score based on scorecard and score names.
    
    This function follows the convention:
    ./scorecards/[scorecard_name]/[score_name].yaml
    
    where both scorecard_name and score_name are sanitized for use in file paths.
    
    Args:
        scorecard_name: The name of the scorecard
        score_name: The name of the score
        
    Returns:
        A Path object pointing to the YAML file location
        
    Example:
        >>> get_score_yaml_path("My Scorecard", "Call Quality Score")
        Path('scorecards/my_scorecard/call_quality_score.yaml')
    """
    # Create the scorecards directory if it doesn't exist
    # Allow override via environment variable for Lambda compatibility
    scorecards_base = os.environ.get('SCORECARD_CACHE_DIR', 'scorecards')
    scorecards_dir = Path(scorecards_base)
    
    # Handle case where 'scorecards' exists as a file instead of directory
    if scorecards_dir.exists() and not scorecards_dir.is_dir():
        # Remove the file if it exists
        scorecards_dir.unlink()
    
    scorecards_dir.mkdir(exist_ok=True)
    
    # Create sanitized directory names
    scorecard_dir = scorecards_dir / sanitize_path_name(scorecard_name)
    
    # Handle case where scorecard dir exists as a file instead of directory  
    if scorecard_dir.exists() and not scorecard_dir.is_dir():
        scorecard_dir.unlink()
    
    scorecard_dir.mkdir(exist_ok=True)
    
    # Create the YAML file path
    return scorecard_dir / f"{sanitize_path_name(score_name)}.yaml"

def get_score_guidelines_path(scorecard_name: str, score_name: str) -> Path:
    """Compute the guidelines markdown file path for a score based on scorecard and score names.

    This function follows the convention:
    ./scorecards/[scorecard_name]/guidelines/[score_name].md

    where both scorecard_name and score_name are sanitized for use in file paths.

    Args:
        scorecard_name: The name of the scorecard
        score_name: The name of the score

    Returns:
        A Path object pointing to the guidelines file location

    Example:
        >>> get_score_guidelines_path("My Scorecard", "Call Quality Score")
        Path('scorecards/my_scorecard/guidelines/call_quality_score.md')
    """
    # Create the scorecards directory if it doesn't exist
    # Allow override via environment variable for Lambda compatibility
    scorecards_base = os.environ.get('SCORECARD_CACHE_DIR', 'scorecards')
    scorecards_dir = Path(scorecards_base)

    # Handle case where 'scorecards' exists as a file instead of directory
    if scorecards_dir.exists() and not scorecards_dir.is_dir():
        # Remove the file if it exists
        scorecards_dir.unlink()

    scorecards_dir.mkdir(exist_ok=True)

    # Create sanitized directory names
    scorecard_dir = scorecards_dir / sanitize_path_name(scorecard_name)

    # Handle case where scorecard dir exists as a file instead of directory
    if scorecard_dir.exists() and not scorecard_dir.is_dir():
        scorecard_dir.unlink()

    scorecard_dir.mkdir(exist_ok=True)

    # Create guidelines subdirectory
    guidelines_dir = scorecard_dir / "guidelines"

    # Handle case where guidelines dir exists as a file instead of directory
    if guidelines_dir.exists() and not guidelines_dir.is_dir():
        guidelines_dir.unlink()

    guidelines_dir.mkdir(exist_ok=True)

    # Create the guidelines markdown file path
    return guidelines_dir / f"{sanitize_path_name(score_name)}.md"

def sanitize_path_name(name: str) -> str:
    """
    Sanitize a string to be safe for use as a path name while preserving readability.
    Only replaces characters that are unsafe for paths.
    
    Args:
        name: The string to sanitize
        
    Returns:
        A sanitized string that is safe to use as a path name
        
    Example:
        >>> sanitize_path_name("Patient Interest")
        'Patient Interest'
        >>> sanitize_path_name("Call/Response*Test")
        'Call-Response-Test'
        >>> sanitize_path_name("Special: Score (with) [chars]")
        'Special- Score (with) -chars-'
    """
    # Replace slashes, backslashes, and other filesystem-unsafe characters with dashes
    # Keep spaces and most punctuation intact
    # Make sure to escape the square brackets in the regex pattern since they're special in regex
    sanitized = re.sub(r'[<>:"/\\|?*\[\]]', '-', name)
    
    # Remove or replace any other control characters
    sanitized = "".join(char if char.isprintable() else '-' for char in sanitized)
    
    # Remove leading/trailing whitespace and dashes
    sanitized = sanitized.strip('- ')
    
    # Replace multiple consecutive dashes with a single dash
    sanitized = re.sub(r'-+', '-', sanitized)
    
    return sanitized

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
    account_key = os.getenv('PLEXUS_ACCOUNT_KEY')
    if not account_key:
        raise ValueError("PLEXUS_ACCOUNT_KEY environment variable must be set")
    
    metadata = {
        "content_id": str(used_content_id),
        "account_key": account_key,
        "scorecard_key": scorecard_key,
        "score_name": "accuracy"
    }
    sample_row['metadata'] = json.dumps(metadata)
    
    return sample_row, used_content_id 