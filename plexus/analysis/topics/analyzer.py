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
import json

# Load environment variables from .env file
try:
    import dotenv
    # Try to find .env file in common locations
    env_paths = [
        '.env',
        os.path.join(os.path.dirname(__file__), '../../../.env'),  # From topics/ to project root
        '/Users/ryan.porter/Projects/Plexus/.env'  # Absolute path as fallback
    ]
    
    for env_path in env_paths:
        if os.path.exists(env_path):
            dotenv.load_dotenv(env_path, override=True)
            break
except ImportError:
    pass  # dotenv not available, environment variables must be set externally

# Configure logging
logger = logging.getLogger(__name__)

# LangChain imports
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains import LLMChain
from langchain.chains.question_answering import load_qa_chain
from langchain_openai import ChatOpenAI
from langchain.globals import set_llm_cache
from langchain_community.cache import SQLiteCache

# Initialize LLM cache for representation model (fine-tuning) - same cache as transformer
cache_dir_path = Path("tmp/langchain.db")
cache_db_file_path = cache_dir_path / "topics_llm_cache.db"

try:
    # Ensure the cache directory exists
    cache_dir_path.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Initializing Langchain LLM SQLite cache for analyzer at {cache_db_file_path}")
    set_llm_cache(SQLiteCache(database_path=str(cache_db_file_path)))
    logger.debug(f"Langchain LLM SQLite cache initialized successfully for fine-tuning phase.")
except Exception as e:
    logger.warning(f"Could not initialize Langchain LLM SQLite cache for analyzer: {e}. Fine-tuning LLM calls will not be cached.")

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

def save_topic_info(topic_model, output_dir: str, docs: List[str], topics: List[int]) -> None:
    """Save topic information to JSON files."""
    try:
        # Ensure the output directory exists
        os.makedirs(output_dir, mode=0o755, exist_ok=True)
        
        # Get topic information
        topic_info = topic_model.get_topic_info()
        
        # Save topic info as JSON
        topic_info_path = os.path.join(output_dir, "topic_info.json")
        topic_info_dict = topic_info.to_dict(orient='records')
        with open(topic_info_path, 'w', encoding='utf-8') as f:
            json.dump(topic_info_dict, f, indent=2, ensure_ascii=False)
        
        # Set appropriate permissions
        os.chmod(topic_info_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
        
        logger.info(f"Saved topic information to {topic_info_path}")
        
    except Exception as e:
        logger.error(f"Failed to save topic information: {e}", exc_info=True)
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
    representation_model_provider: str = "openai",
    representation_model_name: str = "gpt-4o-mini",
    transformed_df: Optional[pd.DataFrame] = None,
    prompt: Optional[str] = None,
    system_prompt: Optional[str] = None,
    force_single_representation: bool = True,
    # New configurable parameters for document selection
    nr_docs: int = 100,
    diversity: float = 0.1,
    doc_length: int = 500,
    tokenizer: str = "whitespace"
) -> Optional[Tuple[BERTopic, pd.DataFrame, List[int], List[str]]]:
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
        representation_model_provider: LLM provider for topic naming (default: "openai")
        representation_model_name: Specific model name for topic naming (default: "gpt-4o-mini")
        transformed_df: DataFrame with transformed data including ids column
        prompt: Custom prompt for topic naming (user prompt)
        system_prompt: Custom system prompt for topic naming context
        force_single_representation: Use only one representation model to avoid duplicate titles
        nr_docs: Number of representative documents to select per topic (default: 100)
        diversity: Diversity factor for document selection, 0-1 (default: 0.1)
        doc_length: Maximum characters per document (default: 500)
        tokenizer: Tokenization method for documents (default: "whitespace")
        
    Returns:
        BERTopic: The fitted topic model with discovered topics, or None if analysis fails
    """
    # Create output directory if it doesn't exist
    ensure_directory(output_dir)
    
    # Default prompts
    default_prompt = """
    I have a topic from call center transcripts that is described by the following keywords: [KEYWORDS]
    In this topic, these customer-agent conversations are representative examples:
    [DOCUMENTS]

    Based on the keywords and representative examples above, provide a short, descriptive label for this topic in customer service context. Return only the label, no other text or formatting.
    """
    
    # Use provided prompt or default
    prompt = prompt or default_prompt
    
    # Load text data
    logger.info(f"Loading text data from {text_file_path}")
    try:
        with open(text_file_path, 'r') as f:
            all_lines = f.readlines()
            docs = [line.strip() for line in all_lines if line.strip()]
        logger.debug(f"Loaded {len(docs)} documents from {text_file_path}")
        logger.info(f"🔍 ALIGNMENT_DEBUG: Total lines in file: {len(all_lines)}")
        logger.info(f"🔍 ALIGNMENT_DEBUG: Non-empty lines (docs): {len(docs)}")
        if transformed_df is not None:
            logger.info(f"🔍 ALIGNMENT_DEBUG: transformed_df rows: {len(transformed_df)}")
            length_diff = len(docs) - len(transformed_df)
            if length_diff != 0:
                logger.warning(f"⚠️ ALIGNMENT_WARNING: Length mismatch detected: docs({len(docs)}) vs transformed_df({len(transformed_df)}) = difference of {length_diff}")
                logger.warning("⚠️ ALIGNMENT_WARNING: This may cause misalignment issues later")
        
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
        logger.info("🔍 Initializing OpenAI representation model for topic naming...")
        logger.info(f"   • Provider: {representation_model_provider}")
        logger.info(f"   • Model: {representation_model_name}")
        logger.info(f"   • Document selection: {nr_docs} docs, diversity={diversity}")
        try:
            # Use provided API key or environment variable
            api_key = openai_api_key or os.environ.get("OPENAI_API_KEY")
            
            if not api_key:
                logger.error("❌ OpenAI API key not found. Continuing without representation model.")
                logger.error("   This will result in keyword-based topic names instead of LLM-generated names.")
                representation_model = None
            else:
                client = openai.OpenAI(api_key=api_key)
                logger.info(f"🔥 REPR_DEBUG: Creating OpenAI representation model with:")
                logger.info(f"🔥 REPR_DEBUG:   - model: {representation_model_name}")
                logger.info(f"🔥 REPR_DEBUG:   - nr_docs: {nr_docs}")
                logger.info(f"🔥 REPR_DEBUG:   - diversity: {diversity}")
                logger.info(f"🔥 REPR_DEBUG:   - prompt length: {len(prompt) if prompt else 0}")
                
                # Prepare parameters for OpenAI representation model
                openai_params = {
                    "client": client,
                    "model": representation_model_name,
                    "prompt": prompt,
                    "delay_in_seconds": 1,
                    "nr_docs": nr_docs,
                    "diversity": diversity,
                    "doc_length": doc_length,
                    "tokenizer": tokenizer
                }
                
                # Add system prompt if provided (for task-based context)
                if system_prompt:
                    openai_params["system_prompt"] = system_prompt
                    logger.info(f"🔥 REPR_DEBUG: Using task-based system prompt: '{system_prompt[:100]}...'")
                
                representation_model = OpenAI(**openai_params)
                logger.info("✅ OpenAI representation model initialized successfully")
                
                        
        except Exception as e:
            logger.error(f"❌ Failed to initialize representation model: {e}")
            logger.error("   Continuing without representation model - topics will use keyword-based names.")
            representation_model = None
    else:
        logger.info("ℹ️  Representation model disabled - topics will use keyword-based names")

    # Initialize BERTopic model with n-gram range and other parameters
    logger.info(f"Initializing BERTopic model with n-gram range {n_gram_range} and custom UMAP model.")
    
    # SIMPLIFIED APPROACH: Create a single BERTopic model without complex state tracking
    # This prevents topic assignment corruption that happens with update_topics()
    logger.info("🔍 REPR_DEBUG: Using SIMPLIFIED representation model approach")
    
    # Always start without representation model to avoid wasteful LLM calls during topic reduction
    logger.info("ℹ️  Creating BERTopic model with keyword-based topic naming (representation model applied after reduction)")
    topic_model = BERTopic(
        n_gram_range=n_gram_range,
        min_topic_size=min_topic_size,
        top_n_words=top_n_words,
        umap_model=umap_model,
        representation_model=None,  # Applied later after reduction
        verbose=True
    )
    
    # Store representation model for later application
    saved_representation_model = representation_model if use_representation_model else None
    
    logger.debug("BERTopic model initialized successfully.")
    
    # Fit and transform - SIMPLIFIED SINGLE-STAGE APPROACH
    logger.info(f"🔍 REPR_DEBUG: Starting SIMPLIFIED topic modeling process")
    logger.info(f"🔍 REPR_DEBUG: Parameters - n_gram_range={n_gram_range}, min_topic_size={min_topic_size}, nr_topics={nr_topics or 'auto'}")
    start_time = time.time()
    
    try:
        logger.info(f"Running BERTopic analysis on {len(docs)} documents...")
        logger.info("   • Using keyword-based topic naming (LLM naming applied after reduction)")
        if saved_representation_model is not None:
            logger.info("   • LLM representation model will be applied after topic reduction")
        
        topics, probs = topic_model.fit_transform(docs)
        
        logger.info(f"✅ BERTopic analysis completed in {time.time() - start_time:.2f} seconds")
        
        # EXPECTED: No custom labels during initial discovery (representation model applied later)
        logger.info("🔍 REPR_DEBUG: Initial discovery completed with keyword-based naming")
        if hasattr(topic_model, 'custom_labels_') and topic_model.custom_labels_:
            logger.warning(f"🔍 REPR_DEBUG: Unexpected custom labels found: {len(topic_model.custom_labels_)}")
        else:
            logger.info("🔍 REPR_DEBUG: No custom labels during initial discovery (as expected)")
        
        # Log topic discovery results
        topic_info = topic_model.get_topic_info()
        num_topics = len(topic_info[topic_info.Topic != -1])
        logger.info(f"📊 Discovered {num_topics} topics (excluding outlier topic)")
        
        # Show initial keyword-based topic names
        if not topic_info.empty and 'Name' in topic_info.columns:
            sample_names = topic_info['Name'].head(3).tolist()
            logger.info(f"🎯 Initial keyword-based topic names: {sample_names}")
            
            # These should be keyword concatenation at this stage
            for i, name in enumerate(sample_names):
                if '_' in name and len(name.split('_')) > 2:
                    logger.info(f"🔍 REPR_DEBUG: Topic {i} name '{name}' - keyword concatenation (expected)")
                else:
                    logger.warning(f"🔍 REPR_DEBUG: Topic {i} name '{name}' - unexpected format for initial discovery")
        
    except Exception as e:
        logger.error(f"❌ Error during BERTopic fit_transform: {e}", exc_info=True)
        raise

    # --- Post-fitting Analysis and Visualization ---

    # Get topic information
    topic_info = topic_model.get_topic_info()
    num_topics = len(topic_info[topic_info.Topic != -1])
    logger.info(f"Found {num_topics} topics (excluding the outlier topic).")

    # If no topics were found, skip visualizations and return early
    if num_topics == 0:
        logger.warning("No topics were discovered. Skipping all visualizations.")
        save_topic_info(topic_model, output_dir, docs, topics)
        return topic_model, topic_model.get_topic_info(), topics, docs

    # --- Visualizations ---
    logger.info("Generating visualizations...")

    # Visualize Topics
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
        logger.warning(f"Skipping term score decline visualization as it requires at least one topic.")

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
        hierarchical_topics_df = topic_model.hierarchical_topics(docs) # Rename for clarity
        if hierarchical_topics_df is not None and not hierarchical_topics_df.empty:
            fig_hierarchy = topic_model.visualize_hierarchy(hierarchical_topics=hierarchical_topics_df, orientation='left') # Pass as keyword arg
            save_visualization(fig_hierarchy, str(Path(output_dir) / "hierarchy.html"))
        else:
            logger.warning("No hierarchical topics found to visualize.")
    except Exception as e:
        logger.error(f"Failed to generate or save topic hierarchy visualization: {e}", exc_info=True)

    # Visualize Topic Similarity (Heatmap)
    try:
        fig_similarity = topic_model.visualize_heatmap()
        save_visualization(fig_similarity, str(Path(output_dir) / "topic_similarity.html"))
        try:
            similarity_png_path = str(Path(output_dir) / "topic_similarity_visualization.png")
            fig_similarity.write_image(similarity_png_path)
            os.chmod(similarity_png_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
            logger.info(f"Saved topic similarity visualization to {similarity_png_path}")
        except Exception as e:
            logger.error(f"Failed to save topic similarity visualization as PNG: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Error during topic similarity visualization: {e}", exc_info=True)
        logger.warning(f"Skipping topic similarity visualization as it requires at least two topics.")

    # Visualize Topics per Class (if applicable, HTML only)
    # Note: This requires class labels which are not directly available here unless passed in.
    # For now, we'll skip this, but it's an example of how it could be added if `classes` were an argument.
    # topics_per_class_fig = create_topics_per_class_visualization(topic_model, topics, docs, output_dir)
    # if topics_per_class_fig:
    #     logger.info("Topics per class visualization generated.")

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
    
    # Reduce topics if requested (safe since no representation model attached yet)
    if nr_topics is not None and n_topics > 0 and nr_topics < n_topics:
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

    # Apply representation model to final topics (after reduction)
    if saved_representation_model is not None:
        final_topic_count = len(set(topics)) - 1  # Excluding -1 outlier topic
        logger.info(f"🔍 REPR_DEBUG: Applying LLM representation model to {final_topic_count} final topics")
        
        # Capture "before" state for fine-tuning comparison
        try:
            before_topic_info = topic_model.get_topic_info()
            before_topics_data = {}
            
            # Store keyword-based topic info for comparison
            for _, row in before_topic_info.iterrows():
                topic_id = row.get('Topic', -1)
                if topic_id != -1:  # Skip outlier topic
                    # Get the keyword-based words for this topic
                    topic_words = topic_model.get_topic(topic_id)
                    if topic_words:
                        keywords = [word for word, _ in topic_words[:8]]  # Top 8 keywords
                        before_topics_data[str(topic_id)] = {
                            "name": row.get('Name', f'Topic {topic_id}'),
                            "keywords": keywords
                        }
            
            logger.info(f"🔍 REPR_DEBUG: Captured 'before' state for {len(before_topics_data)} topics")
            
            # Save before state to JSON file for later use
            before_topics_path = os.path.join(output_dir, "topics_before_fine_tuning.json")
            with open(before_topics_path, 'w', encoding='utf-8') as f:
                json.dump(before_topics_data, f, indent=2, ensure_ascii=False)
            logger.info(f"🔍 REPR_DEBUG: Saved 'before' topics to {before_topics_path}")
            
        except Exception as e:
            logger.error(f"Failed to capture 'before' state: {e}", exc_info=True)
            before_topics_data = {}
        
        # Apply the representation model
        try:
            topic_model.update_topics(docs, representation_model=saved_representation_model)
            logger.info("✅ Successfully applied LLM representation model to final topics")
        except Exception as e:
            logger.error(f"Failed to apply representation model: {e}", exc_info=True)
            logger.warning("Continuing with keyword-based topic names")
    
    # Final topic assignments are stable after optional reduction and representation model application
    logger.info("🔍 REPR_DEBUG: Topic modeling pipeline completed")
    logger.info(f"🔍 REPR_DEBUG: Final topic assignments - total: {len(topics)}, unique: {sorted(set(topics))}")

    # --- Extract and Save Representative Documents ---
    # IMPORTANT: This must happen AFTER representation model is applied since topic assignments may change
    logger.info("Extracting representative documents for each topic...")
    logger.info(f"🔍 ALIGNMENT_CHECK: Starting representative docs extraction")
    logger.info(f"🔍 ALIGNMENT_CHECK: topics array length = {len(topics)}")
    logger.info(f"🔍 ALIGNMENT_CHECK: unique topic IDs = {sorted(set(topics))}")
    
    try:
        representative_docs = {}
        if transformed_df is not None and not transformed_df.empty:
            logger.info(f"🔍 ALIGNMENT_CHECK: transformed_df provided with {len(transformed_df)} rows")
            logger.info(f"🔍 ALIGNMENT_CHECK: transformed_df columns = {list(transformed_df.columns)}")
            
            # Check if we have text column
            if 'text' not in transformed_df.columns:
                logger.error(f"❌ VALIDATION_FAIL: transformed_df missing 'text' column")
                logger.error(f"❌ VALIDATION_FAIL: available columns = {list(transformed_df.columns)}")
            else:
                logger.info(f"✅ VALIDATION_PASS: transformed_df has 'text' column")
            
            try:
                # The topics list corresponds to lines in the text file, which should match the dataframe
                logger.info(f"🔍 ALIGNMENT_CHECK: Checking length alignment: transformed_df({len(transformed_df)}) vs topics({len(topics)})")
                
                # CRITICAL FIX: The topics array should ALWAYS match the transformed_df length
                # because BERTopic processes the text file that was generated from transformed_df
                if len(transformed_df) == len(topics):
                    logger.info(f"✅ VALIDATION_PASS: DataFrame and topics arrays have matching lengths")
                    transformed_df['topic'] = topics
                elif len(topics) > 0:
                    # If there's a mismatch, it's likely a bug in our pipeline
                    # The topics should match the text file, which was generated from transformed_df
                    logger.error(f"❌ VALIDATION_FAIL: CRITICAL ALIGNMENT ISSUE")
                    logger.error(f"❌ VALIDATION_FAIL: transformed_df has {len(transformed_df)} rows")
                    logger.error(f"❌ VALIDATION_FAIL: topics array has {len(topics)} assignments")
                    logger.error(f"❌ VALIDATION_FAIL: These SHOULD be the same since topics come from the text file")
                    
                    # Try to salvage the situation by using the smaller length
                    min_length = min(len(transformed_df), len(topics))
                    logger.warning(f"⚠️ ALIGNMENT_CHECK: Attempting to salvage by using first {min_length} entries")
                    
                    if min_length > 0:
                        salvaged_df = transformed_df.head(min_length).copy()
                        salvaged_topics = topics[:min_length]
                        salvaged_df['topic'] = salvaged_topics
                        
                        logger.warning(f"⚠️ ALIGNMENT_CHECK: Using salvaged dataframe with {len(salvaged_df)} rows")
                        transformed_df = salvaged_df
                        topics = salvaged_topics
                    else:
                        logger.error(f"❌ VALIDATION_FAIL: Cannot salvage - no valid entries found")
                        # Continue with empty representative docs
                        pass
                else:
                    logger.error(f"❌ VALIDATION_FAIL: No topics found in BERTopic analysis")
                
                # Only proceed if we have valid alignment
                if 'topic' in transformed_df.columns:
                    logger.info(f"✅ VALIDATION_PASS: Proceeding with aligned dataframe")
                    
                    # Check for ids column (case insensitive)
                    ids_column_name = None
                    for col in transformed_df.columns:
                        if col.lower() in ['id', 'ids']:
                            ids_column_name = col
                            break
                    
                    if ids_column_name:
                        logger.info(f"🔍 ID_DEBUG: Found ID column '{ids_column_name}' in transformed_df")
                        # Sample some ID values to check format
                        sample_ids = transformed_df[ids_column_name].head(3).tolist()
                        logger.info(f"🔍 ID_DEBUG: Sample ID values = {sample_ids}")
                    else:
                        logger.warning(f"⚠️ ID_DEBUG: No ID column found in transformed_df. Available columns: {list(transformed_df.columns)}")
                    
                    unique_topics = sorted(transformed_df['topic'].unique())
                    logger.info(f"🔍 TOPIC_DEBUG: Found {len(unique_topics)} unique topics in transformed_df: {unique_topics}")
                    
                    for topic_id in unique_topics:
                        if topic_id == -1:
                            logger.info(f"🔍 TOPIC_DEBUG: Skipping outlier topic -1")
                            continue
                        
                        topic_docs_df = transformed_df[transformed_df['topic'] == topic_id].head(20)
                        logger.info(f"🔍 TOPIC_DEBUG: Topic {topic_id} has {len(topic_docs_df)} documents (limited to 20)")
                        
                        if len(topic_docs_df) > 0:
                            topic_examples = []
                            docs_with_ids = 0
                            
                            for idx, row in topic_docs_df.iterrows():
                                doc_data = {"text": row['text']}
                                if ids_column_name and pd.notna(row[ids_column_name]):
                                    # Parse JSON string IDs into proper YAML structure
                                    id_value = row[ids_column_name]
                                    if isinstance(id_value, str):
                                        try:
                                            # Try to parse as JSON
                                            parsed_id = json.loads(id_value)
                                            doc_data["id"] = parsed_id
                                            logger.debug(f"🔍 ID_DEBUG: Parsed JSON ID: {parsed_id}")
                                        except json.JSONDecodeError:
                                            # If not valid JSON, store as string
                                            doc_data["id"] = id_value
                                            logger.debug(f"🔍 ID_DEBUG: Using string ID: {id_value}")
                                    else:
                                        # Already an object/list
                                        doc_data["id"] = id_value
                                        logger.debug(f"🔍 ID_DEBUG: Using object ID: {id_value}")
                                    docs_with_ids += 1
                                topic_examples.append(doc_data)
                            
                            representative_docs[str(topic_id)] = topic_examples
                            logger.info(f"🔍 TOPIC_DEBUG: Topic {topic_id} saved with {len(topic_examples)} examples ({docs_with_ids} with IDs)")
                        else:
                            logger.warning(f"⚠️ TOPIC_DEBUG: Topic {topic_id} has no documents")
                    
                    logger.info(f"✅ VALIDATION_PASS: Successfully extracted examples for {len(representative_docs)} topics")
                else:
                    logger.error(f"❌ VALIDATION_FAIL: No valid topic column in dataframe after alignment attempt")
                    logger.error(f"❌ VALIDATION_FAIL: This is the PRIMARY CAUSE of 'no examples available' issue")
            except Exception as e:
                logger.error(f"❌ VALIDATION_FAIL: Exception in transformed_df processing: {e}", exc_info=True)
        else:
            logger.warning("⚠️ ALIGNMENT_CHECK: No transformed_df provided. Cannot extract representative documents with IDs.")

        # Save representative documents to a JSON file
        repr_docs_path = os.path.join(output_dir, "representative_documents.json")
        logger.info(f"🔍 ALIGNMENT_CHECK: Saving {len(representative_docs)} topic groups to {repr_docs_path}")
        
        # Log summary of what we're saving
        total_examples = sum(len(examples) for examples in representative_docs.values())
        logger.info(f"🔍 ALIGNMENT_CHECK: Total examples being saved: {total_examples}")
        
        with open(repr_docs_path, 'w', encoding='utf-8') as f:
            json.dump(representative_docs, f, indent=2, ensure_ascii=False)
        
        if representative_docs:
            logger.info(f"✅ VALIDATION_PASS: Successfully saved representative documents to {repr_docs_path}")
        else:
            logger.error(f"❌ VALIDATION_FAIL: No representative documents to save - this will cause 'no examples available'")
        
    except Exception as e:
        logger.error(f"❌ VALIDATION_FAIL: Critical error in representative documents extraction: {e}", exc_info=True)
    
    logger.info(f"Analysis complete. Results saved to {output_dir}")
    
    # Return the topic model for further use
    final_topic_info = topic_model.get_topic_info()
    logger.info(f"Returning final topic info with {len(final_topic_info)} topics.")
    return topic_model, final_topic_info, topics, docs