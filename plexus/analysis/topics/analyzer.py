"""
Module for performing BERTopic analysis on transformed transcripts.
"""

import os
import stat
import logging
import re
import time
from typing import List, Tuple, Dict, Any, Optional
import pandas as pd
import numpy as np
from bertopic import BERTopic
import plotly.express as px
from umap import UMAP
from bertopic.representation import OpenAI, LangChain
import openai
from pathlib import Path

# Configure logging
logger = logging.getLogger(__name__)

# LangChain imports
from langchain.prompts import ChatPromptTemplate
from langchain.chains import LLMChain
from langchain.chains.question_answering import load_qa_chain
from langchain_openai import ChatOpenAI

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

def create_topics_per_class_visualization(
    topic_model, 
    topics, 
    docs, 
    output_dir=None
):
    """
    Create a visualization showing topic distribution across different classes.
    
    Args:
        topic_model: Fitted BERTopic model
        topics: List of topic assignments
        docs: List of documents
        output_dir: Directory to save the visualization
        
    Returns:
        Path to saved visualization or None if generation fails
    """
    logger.info("Generating Topics per Class visualization...")
    
    try:
        # Extract class labels from document text
        class_labels = []
        for doc in docs:
            # Try to extract class from document (e.g., "comp.sys.mac.hardware: text...")
            match = re.match(r'^([a-zA-Z0-9_\.]+)[\s\:]+', doc)
            if match:
                class_labels.append(match.group(1))
            else:
                class_labels.append("unknown")
        
        # Get topic information
        topic_info = topic_model.get_topic_info()
        
        # Filter out the -1 outlier topic
        topic_info = topic_info[topic_info["Topic"] != -1]
        
        # Create dataframe to hold topic-class relationships
        topic_class_data = []
        for doc_idx, (topic_idx, doc) in enumerate(zip(topics, docs)):
            if topic_idx != -1:  # Skip outlier topics
                # Get class for this document
                class_label = class_labels[doc_idx]
                
                # Get topic representation
                topic_words = topic_model.get_topic(topic_idx)
                if topic_words:  # Make sure we have words for this topic
                    # Create a readable topic label
                    topic_label = f"{topic_idx}_" + "_".join([word for word, _ in topic_words[:3]])
                    
                    # Add to our dataset
                    topic_class_data.append({
                        "Class": class_label,
                        "Topic": topic_label,
                        "Frequency": 1
                    })
        
        # Convert to DataFrame
        df = pd.DataFrame(topic_class_data)
        
        # If empty, return early
        if len(df) == 0:
            logger.warning("No valid topic-class data found for visualization")
            return None
        
        # Aggregate by Class and Topic
        agg_df = df.groupby(["Class", "Topic"]).sum().reset_index()
        
        # Create the visualization
        fig = px.bar(
            agg_df,
            x="Frequency",
            y="Class",
            color="Topic",
            orientation='h',
            title="Topics per Class",
            labels={"Frequency": "Frequency", "Class": "Class"},
            height=800,  # Adjust based on number of classes
        )
        
        # Update layout
        fig.update_layout(
            xaxis_title="Frequency",
            yaxis_title="Class",
            legend_title="Global Topic Representation",
            barmode='stack'
        )
        
        # Save visualization
        if output_dir:
            output_path = os.path.join(output_dir, "topics_per_class.html")
            save_visualization(fig, output_path)
            logger.info(f"Saved Topics per Class visualization to {output_path}")
            return output_path
        
        return fig
    
    except Exception as e:
        logger.error(f"Failed to generate Topics per Class visualization: {e}", exc_info=True)
        return None

def analyze_topics(
    text_file_path: str,
    output_dir: str,
    nr_topics: Optional[int] = None,
    n_gram_range: Tuple[int, int] = (1, 2),
    min_topic_size: int = 10,
    top_n_words: int = 10,
    use_representation_model: bool = True,
    openai_api_key: Optional[str] = None,
    use_langchain: bool = False,
    representation_model_provider: str = "openai",
    representation_model_name: str = "gpt-4o-mini"
) -> Optional[BERTopic]:
    """
    Perform BERTopic analysis on transformed transcripts.
    
    Args:
        text_file_path: Path to text file containing speaking turns
        output_dir: Directory to save analysis results
        nr_topics: Target number of topics after reduction (default: None, no reduction)
        n_gram_range: The lower and upper boundary of the n-gram range (default: (1, 2))
        min_topic_size: Minimum size of topics (default: 10)
        top_n_words: Number of words per topic (default: 10)
        use_representation_model: Whether to use LLM for better topic naming (default: True)
        openai_api_key: OpenAI API key for representation model (default: None, uses env var)
        use_langchain: Whether to use LangChain for representation model (default: False)
        representation_model_provider: LLM provider for topic naming (default: "openai")
        representation_model_name: Specific model name for topic naming (default: "gpt-4o-mini")
        
    Returns:
        BERTopic: The fitted topic model with discovered topics, or None if analysis fails
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

    # Initialize representation model if requested
    representation_model = None
    if use_representation_model:
        try:
            # Use provided API key or environment variable
            api_key = openai_api_key or os.environ.get("OPENAI_API_KEY")
            if not api_key:
                logger.warning("OpenAI API key not provided. Continuing without representation model.")
            else:
                if use_langchain:
                    # Using simplified LangChain integration directly from docs
                    logger.info(f"Initializing LangChain representation model with {representation_model_name} from {representation_model_provider}...")
                    
                    # Create a llm for LangChain
                    if representation_model_provider.lower() == "openai":
                        llm = ChatOpenAI(
                            model=representation_model_name,
                            temperature=0.0,
                            openai_api_key=api_key
                        )
                    else:
                        logger.warning(f"Provider {representation_model_provider} not supported for LangChain integration, falling back to OpenAI")
                        llm = ChatOpenAI(
                            model=representation_model_name,
                            temperature=0.0,
                            openai_api_key=api_key
                        )
                    
                    # Create a simple QA chain  
                    chain = load_qa_chain(llm, chain_type="stuff")
                    
                    # Simple prompt as shown in the docs
                    simple_prompt = """
                    I have a topic from call center transcripts that is described by the following keywords: [KEYWORDS]

                    What is a short, descriptive label for this topic in customer service context? Return only the label, no other text or formatting.
                    """
                    
                    # Create the representation model with the simple prompt
                    representation_model = LangChain(chain=chain, prompt=simple_prompt)
                    logger.info("LangChain representation model initialized successfully.")
                else:
                    # Using direct OpenAI integration
                    logger.info(f"Initializing OpenAI representation model with {representation_model_name} from {representation_model_provider}...")
                    
                    if representation_model_provider.lower() == "openai":
                        client = openai.OpenAI(api_key=api_key)
                    else:
                        logger.warning(f"Provider {representation_model_provider} not supported for direct integration, falling back to OpenAI")
                        client = openai.OpenAI(api_key=api_key)
                    
                    # Custom prompt for OpenAI
                    summarization_prompt = """
                    I have a topic from call center transcripts that is described by the following keywords: [KEYWORDS]
                    In this topic, these customer-agent conversations are representative examples:
                    [DOCUMENTS]

                    Based on the information above, provide a short, descriptive label for this topic in this format:
                    topic: <concise label that describes what this topic represents in customer interactions>
                    """
                    
                    representation_model = OpenAI(
                        client=client, 
                        model=representation_model_name, 
                        prompt=summarization_prompt,
                        delay_in_seconds=1
                    )
                    logger.info("OpenAI representation model initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize representation model: {e}", exc_info=True)
            logger.warning("Continuing without representation model.")
            representation_model = None

    # Initialize BERTopic model with n-gram range and other parameters
    logger.info(f"Initializing BERTopic model with n-gram range {n_gram_range} and custom UMAP model.")
    topic_model = BERTopic(
        n_gram_range=n_gram_range,
        min_topic_size=min_topic_size,
        top_n_words=top_n_words,
        umap_model=umap_model,
        representation_model=representation_model,
        verbose=True
    )
    logger.debug("BERTopic model initialized successfully.")
    
    # Fit and transform
    logger.info(f"Starting topic modeling process with BERTopic (n_gram_range={n_gram_range}, min_topic_size={min_topic_size}, nr_topics={nr_topics or 'auto'})...")
    start_time = time.time()
    
    try:
        topics, probs = topic_model.fit_transform(docs)
        logger.info(f"BERTopic fit_transform completed in {time.time() - start_time:.2f} seconds.")
        logger.info(f"Found {len(topic_model.get_topic_info())-1} topics initially (before any reduction).") # -1 for outlier topic
    except Exception as e:
        logger.error(f"Error during BERTopic fit_transform: {e}", exc_info=True)
        raise

    # --- Generate and Save Visualizations (including new PNGs) ---
    try:
        logger.info("Generating BERTopic visualizations...")
        
        # Get number of topics (excluding the outlier topic -1)
        num_topics = len(topic_model.get_topic_info()) - 1
        logger.info(f"Found {num_topics} topics for visualization")
        
        # Visualize Topics (HTML and PNG) - only if we have enough topics
        if num_topics >= 2:
            try:
                fig_topics = topic_model.visualize_topics()
                save_visualization(fig_topics, str(Path(output_dir) / "topic_visualization.html"))
                try:
                    topics_png_path = str(Path(output_dir) / "topics_visualization.png")
                    fig_topics.write_image(topics_png_path)
                    os.chmod(topics_png_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
                    logger.info(f"Saved topics visualization to {topics_png_path}")
                except Exception as e:
                    logger.error(f"Failed to save topics visualization as PNG: {e}", exc_info=True)
            except Exception as e:
                logger.error(f"Error during visualization generation: {e}")
                logger.info("Continuing without topic visualization due to insufficient data diversity for UMAP embedding")
        else:
            logger.warning(f"Skipping topics visualization as there are fewer than 2 topics ({num_topics} found). Need at least 2 topics for 2D visualization.")

        # Visualize Heatmap (HTML and PNG)
        # Check if there are enough topics to generate a heatmap (BERTopic requires at least 2 topics for heatmap)
        if num_topics >= 2:
            fig_heatmap = topic_model.visualize_heatmap()
            save_visualization(fig_heatmap, str(Path(output_dir) / "heatmap.html"))
            try:
                heatmap_png_path = str(Path(output_dir) / "heatmap_visualization.png")
                fig_heatmap.write_image(heatmap_png_path)
                os.chmod(heatmap_png_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
                logger.info(f"Saved heatmap visualization to {heatmap_png_path}")
            except Exception as e:
                logger.error(f"Failed to save heatmap visualization as PNG: {e}", exc_info=True)
        else:
            logger.warning(f"Skipping heatmap visualization as there are fewer than 2 topics ({num_topics} found).")

        # Visualize Documents (HTML only, as it's highly interactive and large)
        # Check if there are enough documents and topics for document visualization
        if len(docs) >= umap_n_neighbors and num_topics >= 1:
            try:
                fig_documents = topic_model.visualize_documents(docs, topics=topics) # Pass topics, remove umap_model
                save_visualization(fig_documents, str(Path(output_dir) / "document_visualization.html"))
            except Exception as e:
                # Log error but continue, as this is a non-critical visualization
                logger.error(f"Failed to generate or save document visualization: {e}", exc_info=True)
        else:
            logger.warning(f"Skipping document visualization due to insufficient documents ({len(docs)} docs, need {umap_n_neighbors}) or topics ({num_topics} topics, need 1).")


        # Visualize Topic Hierarchy (HTML only)
        try:
            hierarchical_topics_df = topic_model.hierarchical_topics(docs) # Renamed for clarity
            if hierarchical_topics_df is not None and not hierarchical_topics_df.empty:
                fig_hierarchy = topic_model.visualize_hierarchy(hierarchical_topics=hierarchical_topics_df, orientation='left') # Pass as keyword arg
                save_visualization(fig_hierarchy, str(Path(output_dir) / "hierarchy.html"))
            else:
                logger.warning("Skipping topic hierarchy visualization as hierarchical_topics_df is empty or None.")
        except Exception as e:
            logger.error(f"Failed to generate or save topic hierarchy visualization: {e}", exc_info=True)
            
        # Visualize Topics per Class (if applicable, HTML only)
        # Note: This requires class labels which are not directly available here unless passed in.
        # For now, we'll skip this, but it's an example of how it could be added if `classes` were an argument.
        # topics_per_class_fig = create_topics_per_class_visualization(topic_model, topics, docs, output_dir)
        # if topics_per_class_fig:
        #     logger.info("Topics per class visualization generated.")

    except Exception as e:
        logger.error(f"Error during visualization generation: {e}", exc_info=True)
        # Continue even if visualizations fail, as core topic data might still be useful.
        
    # --- Save Topic Information ---
    logger.info("Saving topic information...")
    
    # Log initial topic info
    n_topics = len(set(topics)) - 1  # Subtract 1 to exclude the -1 outlier topic
    logger.info(f"Found {n_topics} initial topics in the data")
    
    # Save original topic info
    try:
        topic_info = topic_model.get_topic_info()
        topic_info_path = os.path.join(output_dir, "topic_info.csv")
        topic_info.to_csv(topic_info_path, index=False)
        logger.info(f"Saved topic info to {topic_info_path}")
    except Exception as e:
        logger.error(f"Failed to save topic info: {e}", exc_info=True)
    
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
    
    logger.info(f"Analysis complete. Results saved to {output_dir}")
    
    # Return the topic model for further use
    return topic_model 