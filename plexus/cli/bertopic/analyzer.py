"""
Module for performing BERTopic analysis on transformed transcripts.
"""

import os
import stat
import logging
from typing import List, Optional, Tuple
from bertopic import BERTopic
from umap import UMAP

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
        logger.debug(f"Loaded {len(docs)} documents from {text_file_path}")
        
        # Check if enough documents are loaded for analysis
        min_docs_for_umap = 3 # UMAP generally needs n_neighbors < n_samples, and n_neighbors >= 2
        if len(docs) < min_docs_for_umap:
            error_msg = (
                f"Insufficient number of documents ({len(docs)}) for BERTopic/UMAP analysis. "
                f"Need at least {min_docs_for_umap} documents. "
                f"This can happen if --sample-size is too small or input data is sparse."
            )
            logger.error(error_msg)
            raise ValueError(error_msg)
            
        logger.info(f"Successfully loaded {len(docs)} documents.")
    except Exception as e:
        logger.error(f"Failed to load text data from {text_file_path}: {e}", exc_info=True)
        raise
    
    # Determine n_neighbors for UMAP dynamically
    # Default desired n_neighbors is 15, but it must be < len(docs) and >= 2.
    umap_n_neighbors = min(15, len(docs) - 1)
    # Ensure n_neighbors is at least 2 (it will be if len(docs) >= 3 from check above)
    umap_n_neighbors = max(2, umap_n_neighbors) 

    logger.info(f"Initializing UMAP model with dynamically set n_neighbors={umap_n_neighbors} (and n_jobs=1).")
    try:
        umap_model = UMAP(
            n_neighbors=umap_n_neighbors, 
            n_components=5, 
            min_dist=0.0, 
            metric='cosine', 
            random_state=42, 
            n_jobs=1
        )
        logger.debug("UMAP model initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize UMAP model: {e}", exc_info=True)
        raise

    # Initialize BERTopic model with n-gram range and other parameters
    logger.info(f"Initializing BERTopic model with n-gram range {n_gram_range} and custom UMAP model.")
    topic_model = BERTopic(
        n_gram_range=n_gram_range,
        min_topic_size=min_topic_size,
        top_n_words=top_n_words,
        umap_model=umap_model,
        verbose=True
    )
    logger.debug("BERTopic model initialized successfully.")
    
    # Fit and transform
    logger.info("Performing topic modeling")
    try:
        topics, probs = topic_model.fit_transform(docs)
    except ValueError as ve:
        logger.error(f"ValueError during topic_model.fit_transform: {ve}", exc_info=True)
        logger.error(f"Number of documents at the time of error: {len(docs)}")
        if docs:
            logger.error(f"First few documents: {docs[:5]}")
        # Potentially add check for n_neighbors vs len(docs) here if UMAP is the cause
        # This check is now handled by dynamic n_neighbor setting and early exit for too few docs.
        # if hasattr(topic_model, 'umap_model') and topic_model.umap_model.n_neighbors > len(docs):
        #    logger.error(f"UMAP n_neighbors ({topic_model.umap_model.n_neighbors}) is greater than the number of documents ({len(docs)}). This can cause errors.")
        raise
    except Exception as e:
        logger.error(f"Failed to perform topic modeling: {e}", exc_info=True)
        raise
    
    # Log initial topic info
    n_topics = len(set(topics)) - 1  # Subtract 1 to exclude the -1 outlier topic
    logger.info(f"Found {n_topics} initial topics in the data")
    
    # Reduce topics if requested
    if nr_topics is not None and n_topics > 0 and nr_topics < n_topics: # Also check n_topics > 0 before reducing
        logger.info(f"Reducing topics from {n_topics} to {nr_topics}")
        try:
            topic_model.reduce_topics(docs, nr_topics=nr_topics)
            topics = topic_model.topics_ # Update topics after reduction
            n_topics = len(set(topics)) - 1 # Update n_topics after reduction
            logger.info(f"Reduced to {n_topics} topics")
        except Exception as e:
            logger.error("Failed to reduce topics", exc_info=True)
            # Do not re-raise here, allow to proceed with unreduced topics if reduction fails
            logger.warning("Proceeding with unreduced topics after reduction failure.")
    
    # Save visualizations
    logger.info("Generating and saving visualizations")
    
    if n_topics == 0:
        logger.warning("No topics found. Skipping most visualizations.")
        logger.warning(
            "This might be due to the input data, the 'min_topic_size' parameter (currently set or defaulted in BERTopic), "
            "or other BERTopic/HDBSCAN settings. Consider adjusting these or increasing --sample-size if more diverse data might help."
        )
    else:
        # Minimum topics needed for visualize_topics scatter plot (due to internal UMAP n_neighbors=2)
        min_topics_for_scatter_plot = 3
        
        if n_topics >= min_topics_for_scatter_plot:
            try:
                # Topic distribution
                logger.info(f"Generating topic distribution visualization ({n_topics} topics >= {min_topics_for_scatter_plot})...")
                fig = topic_model.visualize_topics()
                dist_path = os.path.join(output_dir, "topic_distribution.html")
                save_visualization(fig, dist_path)
                logger.info(f"Saved topic distribution to {dist_path}")
            except Exception as e:
                logger.error(f"Failed to generate topic distribution: {e}", exc_info=True)
        else:
            logger.warning(
                f"Skipping topic distribution visualization because the number of topics ({n_topics}) "
                f"is less than the minimum required ({min_topics_for_scatter_plot}) for this specific plot."
            )
        
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
        # Ensure topics are correctly referenced, especially after potential reduction
        unique_topics = set(topic_model.topics_ if hasattr(topic_model, 'topics_') and topic_model.topics_ is not None else topics)
        for topic_num in unique_topics:
            if topic_num != -1:  # Skip outliers
                try:
                    logger.debug(f"Generating word cloud for topic {topic_num}")
                    fig = topic_model.visualize_barchart(topics=[topic_num]) # Pass as a list
                    cloud_path = os.path.join(output_dir, f"topic_{topic_num}_words.html")
                    save_visualization(fig, cloud_path)
                    word_cloud_count += 1
                except Exception as e:
                    logger.error(f"Failed to generate word cloud for topic {topic_num}: {e}", exc_info=True)
        logger.info(f"Generated {word_cloud_count} word clouds")

    logger.info(f"Analysis complete. Results saved to {output_dir}") 