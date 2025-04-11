"""
Module for performing BERTopic analysis on transformed transcripts.
"""

import os
import stat
import logging
from typing import List, Optional, Tuple
from bertopic import BERTopic

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def ensure_directory(path: str) -> None:
    """Create directory with appropriate permissions if it doesn't exist."""
    try:
        os.makedirs(path, mode=0o755, exist_ok=True)
        logger.debug(f"Created or verified directory: {path}")
    except Exception as e:
        logger.error(f"Failed to create directory {path}: {e}", exc_info=True)
        raise

def save_visualization(fig, filepath: str) -> None:
    """Save visualization with error handling."""
    try:
        # Ensure the parent directory exists
        os.makedirs(os.path.dirname(filepath), mode=0o755, exist_ok=True)
        
        # Save the visualization
        fig.write_html(filepath)
        
        # Set appropriate permissions
        os.chmod(filepath, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
        
        logger.debug(f"Successfully saved visualization to {filepath}")
    except Exception as e:
        logger.error(f"Failed to save visualization to {filepath}: {e}", exc_info=True)
        raise

def analyze_topics(
    text_file_path: str,
    output_dir: str,
    nr_topics: Optional[int] = None,
    n_gram_range: Tuple[int, int] = (1, 2),
    min_topic_size: int = 10,
    top_n_words: int = 10
) -> None:
    """
    Perform BERTopic analysis on transformed transcripts.
    
    Args:
        text_file_path: Path to text file containing speaking turns
        output_dir: Directory to save analysis results
        nr_topics: Target number of topics after reduction (default: None, no reduction)
        n_gram_range: The lower and upper boundary of the n-gram range (default: (1, 2))
        min_topic_size: Minimum size of topics (default: 10)
        top_n_words: Number of words to represent each topic (default: 10)
    """
    # Create output directory if it doesn't exist
    ensure_directory(output_dir)
    
    # Load text data
    logger.info(f"Loading text data from {text_file_path}")
    try:
        with open(text_file_path, 'r') as f:
            docs = [line.strip() for line in f if line.strip()]
        logger.debug(f"Loaded {len(docs)} documents")
    except Exception as e:
        logger.error(f"Failed to load text data from {text_file_path}: {e}", exc_info=True)
        raise
    
    # Initialize BERTopic model with n-gram range and other parameters
    logger.info(f"Initializing BERTopic model with n-gram range {n_gram_range}")
    topic_model = BERTopic(
        n_gram_range=n_gram_range,
        min_topic_size=min_topic_size,
        top_n_words=top_n_words,
        verbose=True
    )
    
    # Fit and transform
    logger.info("Performing topic modeling")
    try:
        topics, probs = topic_model.fit_transform(docs)
    except Exception as e:
        logger.error("Failed to perform topic modeling", exc_info=True)
        raise
    
    # Log initial topic info
    n_topics = len(set(topics)) - 1  # Subtract 1 to exclude the -1 outlier topic
    logger.info(f"Found {n_topics} initial topics in the data")
    
    # Reduce topics if requested
    if nr_topics is not None and nr_topics < n_topics:
        logger.info(f"Reducing topics from {n_topics} to {nr_topics}")
        try:
            topic_model.reduce_topics(docs, nr_topics=nr_topics)
            topics = topic_model.topics_
            n_topics = len(set(topics)) - 1
            logger.info(f"Reduced to {n_topics} topics")
        except Exception as e:
            logger.error("Failed to reduce topics", exc_info=True)
            raise
    
    # Save visualizations
    logger.info("Generating and saving visualizations")
    
    try:
        # Topic distribution
        logger.info("Generating topic distribution visualization...")
        fig = topic_model.visualize_topics()
        dist_path = os.path.join(output_dir, "topic_distribution.html")
        save_visualization(fig, dist_path)
        logger.info(f"Saved topic distribution to {dist_path}")
    except Exception as e:
        logger.error(f"Failed to generate topic distribution: {e}", exc_info=True)
    
    try:
        # Topic hierarchy
        logger.info("Generating topic hierarchy visualization...")
        fig = topic_model.visualize_hierarchy()
        hier_path = os.path.join(output_dir, "topic_hierarchy.html")
        save_visualization(fig, hier_path)
        logger.info(f"Saved topic hierarchy to {hier_path}")
    except Exception as e:
        logger.error(f"Failed to generate topic hierarchy: {e}", exc_info=True)
    
    # Topic word clouds
    logger.info("Generating topic word clouds...")
    word_cloud_count = 0
    for topic in set(topics):
        if topic != -1:  # Skip outliers
            try:
                logger.debug(f"Generating word cloud for topic {topic}")
                fig = topic_model.visualize_barchart(topics=[topic])
                cloud_path = os.path.join(output_dir, f"topic_{topic}_words.html")
                save_visualization(fig, cloud_path)
                word_cloud_count += 1
            except Exception as e:
                logger.error(f"Failed to generate word cloud for topic {topic}: {e}", exc_info=True)
    
    logger.info(f"Generated {word_cloud_count} word clouds")
    logger.info(f"Analysis complete. Results saved to {output_dir}") 