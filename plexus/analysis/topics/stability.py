"""
Module for assessing topic stability using bootstrap sampling.

This module provides functionality to evaluate how stable topics are
across multiple runs of the topic modeling process with different
data samples.
"""

import logging
import numpy as np
from typing import List, Dict, Any, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)


def calculate_jaccard_similarity(set1: set, set2: set) -> float:
    """
    Calculate Jaccard similarity between two sets.
    
    Args:
        set1: First set of items
        set2: Second set of items
    
    Returns:
        Jaccard similarity score (0-1)
    """
    if len(set1) == 0 and len(set2) == 0:
        return 1.0
    
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    
    if union == 0:
        return 0.0
    
    return intersection / union


def assess_topic_stability(
    docs: List[str],
    n_runs: int = 10,
    sample_fraction: float = 0.8,
    random_seed: int = 42,
    **bertopic_params
) -> Dict[str, Any]:
    """
    Assess topic stability using bootstrap sampling.
    
    This function runs BERTopic multiple times with different random samples
    of the data and measures how consistently topics emerge across runs.
    
    Args:
        docs: List of documents to analyze
        n_runs: Number of bootstrap runs to perform (default: 10)
        sample_fraction: Fraction of data to sample each run (default: 0.8)
        random_seed: Random seed for reproducibility (default: 42)
        **bertopic_params: Additional parameters to pass to BERTopic
    
    Returns:
        Dictionary containing:
            - n_runs: Number of runs performed
            - sample_fraction: Fraction of data sampled per run
            - mean_stability: Overall mean stability score across all topics
            - per_topic_stability: Dict mapping topic_id to stability score
            - topic_consistency_matrix: Matrix of topic similarities across runs
            - methodology: Description of the methodology used
    """
    # Lazy import to avoid loading PyTorch unless needed
    from bertopic import BERTopic
    
    logger.info(f"Starting topic stability assessment with {n_runs} runs")
    logger.info(f"Sample fraction: {sample_fraction}, Random seed: {random_seed}")
    
    # Set random seed for reproducibility
    np.random.seed(random_seed)
    
    # Store topic keywords from each run
    run_topics = []
    
    sample_size = int(len(docs) * sample_fraction)
    
    for run_idx in range(n_runs):
        logger.info(f"Running stability assessment iteration {run_idx + 1}/{n_runs}")
        
        # Bootstrap sample
        sample_indices = np.random.choice(len(docs), sample_size, replace=True)
        sample_docs = [docs[i] for i in sample_indices]
        
        try:
            # Create and fit BERTopic model
            # Use simplified parameters for stability assessment
            nr_topics = bertopic_params.get('nr_topics', None)  # Get nr_topics (don't pop to preserve for next iteration)
            top_n_words = bertopic_params.get('top_n_words', 10)  # Get top_n_words for keyword extraction
            
            # Create params without nr_topics (BERTopic doesn't accept it as init param)
            model_params = {k: v for k, v in bertopic_params.items() if k != 'nr_topics'}
            
            topic_model = BERTopic(**model_params)
            topics, _ = topic_model.fit_transform(sample_docs)
            
            # Reduce topics if nr_topics is specified (matching main analysis behavior)
            if nr_topics is not None:
                try:
                    topic_model.reduce_topics(sample_docs, nr_topics=nr_topics)
                    logger.debug(f"Run {run_idx + 1}: Reduced topics to {nr_topics}")
                except Exception as e:
                    logger.warning(f"Run {run_idx + 1}: Failed to reduce topics: {e}")
            
            # Extract topic keywords using top_n_words parameter
            topic_info = topic_model.get_topic_info()
            run_topic_keywords = {}
            
            for _, row in topic_info.iterrows():
                topic_id = row.get('Topic', -1)
                if topic_id != -1:  # Skip outlier topic
                    # Get top N keywords for this topic (using configured top_n_words)
                    topic_words = topic_model.get_topic(topic_id)
                    if topic_words:
                        keywords = set([word for word, _ in topic_words[:top_n_words]])
                        run_topic_keywords[topic_id] = keywords
            
            run_topics.append(run_topic_keywords)
            logger.info(f"Run {run_idx + 1} completed: {len(run_topic_keywords)} topics found")
            
        except Exception as e:
            logger.error(f"Error in stability run {run_idx + 1}: {e}")
            # Continue with other runs
            run_topics.append({})
    
    # Calculate stability metrics
    logger.info("Calculating stability metrics...")
    
    # Build topic consistency matrix
    # For each pair of runs, calculate how similar the topics are
    consistency_scores = []
    
    for i in range(len(run_topics)):
        for j in range(i + 1, len(run_topics)):
            run_i_topics = run_topics[i]
            run_j_topics = run_topics[j]  # Fixed typo: was run_j_topics[j]
            
            if not run_i_topics or not run_j_topics:
                continue
            
            # Calculate best match similarities between topics in different runs
            # For each topic in run i, find the most similar topic in run j
            for topic_id_i, keywords_i in run_i_topics.items():
                max_similarity = 0.0
                for topic_id_j, keywords_j in run_j_topics.items():
                    similarity = calculate_jaccard_similarity(keywords_i, keywords_j)
                    max_similarity = max(max_similarity, similarity)
                
                consistency_scores.append(max_similarity)
    
    # Calculate overall mean stability
    if consistency_scores:
        mean_stability = float(np.mean(consistency_scores))
        std_stability = float(np.std(consistency_scores))
    else:
        mean_stability = 0.0
        std_stability = 0.0
        logger.warning("No consistency scores calculated - insufficient valid runs")
    
    # Calculate per-topic stability
    # With consistent topic counts (via nr_topics), we can compare topics directly by ID
    per_topic_stability = {}
    
    # Collect all unique topic IDs across runs
    all_topic_ids = set()
    for run_topic_dict in run_topics:
        all_topic_ids.update(run_topic_dict.keys())
    
    for topic_id in all_topic_ids:
        # Get keywords for this topic across all runs where it appears
        topic_keywords_across_runs = []
        for run_topic_dict in run_topics:
            if topic_id in run_topic_dict:
                topic_keywords_across_runs.append(run_topic_dict[topic_id])
        
        if len(topic_keywords_across_runs) >= 2:
            # Calculate pairwise similarities
            similarities = []
            for i in range(len(topic_keywords_across_runs)):
                for j in range(i + 1, len(topic_keywords_across_runs)):
                    sim = calculate_jaccard_similarity(
                        topic_keywords_across_runs[i],
                        topic_keywords_across_runs[j]
                    )
                    similarities.append(sim)
            
            if similarities:
                per_topic_stability[int(topic_id)] = float(np.mean(similarities))
        else:
            # Topic only appeared in one run - low stability
            per_topic_stability[int(topic_id)] = 0.0
    
    logger.info(f"Per-topic stability calculated for {len(per_topic_stability)} topics")
    
    logger.info(f"Stability assessment complete. Mean stability: {mean_stability:.3f}")
    
    # Get top_n_words for methodology description
    top_n_words_for_display = bertopic_params.get('top_n_words', 10)
    
    return {
        "n_runs": n_runs,
        "sample_fraction": sample_fraction,
        "mean_stability": mean_stability,
        "std_stability": std_stability,
        "per_topic_stability": per_topic_stability,
        "consistency_scores": consistency_scores,
        "methodology": f"Bootstrap sampling with Jaccard similarity of top-{top_n_words_for_display} keywords",
        "interpretation": {
            "high": "> 0.7 (topics are very stable and consistent)",
            "medium": "0.5 - 0.7 (topics are moderately stable)",
            "low": "< 0.5 (topics are unstable, consider adjusting parameters)"
        }
    }

