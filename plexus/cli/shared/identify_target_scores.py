"""Functions to identify which scores should be evaluated."""

import logging
from typing import List, Dict, Any, Optional

def identify_target_scores(scorecard_structure: Dict[str, Any], score_names: Optional[Any] = None) -> List[Dict[str, Any]]:
    """Identify which scores should be targeted for evaluation.
    
    Args:
        scorecard_structure: The scorecard structure retrieved from the API
        score_names: Optional score names to evaluate. Can be:
                    - None or empty: all scores in the scorecard will be evaluated
                    - str: comma-separated list of score names
                    - list: list of score names
    
    Returns:
        List of score objects to be evaluated with their metadata
    """
    if not scorecard_structure:
        logging.error("Cannot identify target scores: No scorecard structure provided")
        return []
        
    # Extract all scores from all sections
    all_scores = []
    for section in scorecard_structure.get('sections', {}).get('items', []):
        for score in section.get('scores', {}).get('items', []):
            all_scores.append(score)
            
    if not all_scores:
        logging.warning(f"No scores found in scorecard: {scorecard_structure.get('name')}")
        return []
        
    # If no specific score names provided, return all scores
    if not score_names:
        logging.info(f"No specific scores requested. Using all {len(all_scores)} scores in the scorecard.")
        return all_scores
    
    # Convert score_names to a list of target names
    target_score_names = []
    if isinstance(score_names, str):
        # Parse the comma-separated list of score names
        target_score_names = [name.strip() for name in score_names.split(',') if name.strip()]
    elif isinstance(score_names, list):
        # Already a list, just copy it
        target_score_names = [name for name in score_names if name]
    else:
        logging.warning(f"Unexpected type for score_names: {type(score_names)}. Using all scores.")
        return all_scores
    
    if not target_score_names:
        logging.info(f"Empty score names list. Using all {len(all_scores)} scores in the scorecard.")
        return all_scores
        
    # Find scores matching the requested names
    target_scores = []
    for target_name in target_score_names:
        found = False
        for score in all_scores:
            # Match by name, key, or ID
            if (score.get('name') == target_name or 
                score.get('key') == target_name or 
                score.get('id') == target_name or
                score.get('externalId') == target_name):
                target_scores.append(score)
                found = True
                logging.info(f"Found target score: {score.get('name')}")
                break
                
        if not found:
            logging.warning(f"Could not find score matching '{target_name}' in scorecard")
            
    if not target_scores:
        logging.warning(f"None of the requested scores were found in the scorecard. Falling back to all scores.")
        return all_scores
        
    return target_scores 