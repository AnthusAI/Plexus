from typing import Any, Dict, Optional, Tuple, List
import logging
import asyncio
import tempfile
import os
import shutil
from pathlib import Path
import pandas as pd # Added for inspect_data if called directly
import json # For potentially writing a summary JSON

from plexus.analysis.topics.transformer import (
    transform_transcripts, 
    transform_transcripts_llm, 
    transform_transcripts_itemize,
    inspect_data # If we decide to allow inspection via block
)
from plexus.analysis.topics.analyzer import analyze_topics
from plexus.dashboard.api.models.report_block import ReportBlock # For type hinting if needed

from .base import BaseReportBlock

logger = logging.getLogger(__name__)

# Supported text-based extensions for attachment
SUPPORTED_TEXT_EXTENSIONS = ['.html', '.csv', '.json', '.txt', '.md']
# Add PNG for image attachments
SUPPORTED_IMAGE_EXTENSIONS = ['.png']

class TopicAnalysis(BaseReportBlock):
    DEFAULT_NAME = "Topic Analysis"
    """
    Performs topic analysis on transcript data and attaches resulting artifacts.

    This block orchestrates transcript transformation and BERTopic analysis,
    similar to the `plexus analyze topics` CLI command.

    Expected configuration in ReportConfiguration:
    {
        "class": "TopicAnalysis",
        "input_file_path": "/path/to/your/transcripts.parquet", // Required
        "content_column": "text", // Optional, default: "text"
        "customer_only": false, // Optional, default: false
        "sample_size": null, // Optional, default: null (process all)
        "transform_method": "chunk", // Optional, 'chunk', 'llm', 'itemize', default: "chunk"
        "prompt_template_path": null, // Optional, for 'llm'/'itemize'
        "llm_model": "gemma3:27b", // Optional, for 'llm'/'itemize'
        "llm_provider": "ollama", // Optional, 'ollama', 'openai', for 'llm'/'itemize'
        "openai_api_key_env_var": "OPENAI_API_KEY", // Optional, name of env var for OpenAI key
        "max_retries_itemize": 2, // Optional, for 'itemize'
        "fresh_transform_cache": false, // Optional, force regenerate transform cache
        // BERTopic analysis parameters (ignored if skip_analysis is true)
        "skip_analysis": false, // Optional, default: false
        "num_topics": null, // Optional, auto-determined by BERTopic if null
        "min_ngram": 1, // Optional, default: 1
        "max_ngram": 2, // Optional, default: 2
        "min_topic_size": 10, // Optional, default: 10
        "top_n_words": 10, // Optional, default: 10
        "use_representation_model": false, // Optional, OpenAI for topic representation
        "use_langchain_representation": false // Optional, LangChain for representation
    }
    """

    async def generate(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        self.log_messages: List[str] = []
        final_output_data: Dict[str, Any] = {
            "skipped_files": [],
            "errors": [],
            "summary": "Topic analysis block execution."
        }
        
        # --- 0. Get ReportBlock ID (if available) ---
        report_block_id = None
        if hasattr(self, 'report_block_id') and self.report_block_id:
            report_block_id = self.report_block_id
            self._log(f"ReportBlock ID: {report_block_id}", level="DEBUG")
        else:
            self._log("ReportBlock ID not available on self. Will not be able to attach files if this persists.", level="WARNING")


        # Create a main temporary directory for all operations of this block
        main_temp_dir = tempfile.mkdtemp(prefix="plexus_report_topic_analysis_")
        self._log(f"Created main temporary directory for block operations: {main_temp_dir}")

        try:
            # --- 1. Extract and Validate Configuration ---
            self._log("Extracting and validating configuration...")
            # Transformation params
            input_file_path = self.config.get("input_file_path")
            if not input_file_path or not Path(input_file_path).exists():
                msg = f"'input_file_path' is required and must exist. Provided: {input_file_path}"
                self._log(msg, level="ERROR")
                final_output_data["errors"].append(msg)
                final_output_data["summary"] = "Configuration error."
                # Clean up before raising or returning
                shutil.rmtree(main_temp_dir)
                self._log(f"Cleaned up main temporary directory: {main_temp_dir}")
                return final_output_data, self._get_log_string()

            content_column = self.config.get("content_column", "text")
            customer_only = self.config.get("customer_only", False)
            sample_size = self.config.get("sample_size")
            transform_method = self.config.get("transform_method", "chunk")
            prompt_template_path = self.config.get("prompt_template_path")
            prompt_template = self.config.get("prompt_template")  # Inline prompt support
            llm_model = self.config.get("llm_model", "gemma3:27b")
            llm_provider = self.config.get("llm_provider", "ollama")
            
            openai_api_key_env_var = self.config.get("openai_api_key_env_var", "OPENAI_API_KEY")
            openai_api_key = os.environ.get(openai_api_key_env_var) if llm_provider == "openai" or self.config.get("use_representation_model") else None
            if (llm_provider == "openai" or self.config.get("use_representation_model")) and not openai_api_key:
                self._log(f"OpenAI API key not found in env var '{openai_api_key_env_var}'. Certain features might fail.", level="WARNING")

            max_retries_itemize = self.config.get("max_retries_itemize", 2)
            
            # Check for fresh_transform_cache in both config and runtime params (CLI --fresh flag)
            # Runtime params take precedence over config
            fresh_transform_cache = self.config.get("fresh_transform_cache", False)
            if hasattr(self, 'params') and self.params and 'fresh_transform_cache' in self.params:
                fresh_transform_cache = self.params['fresh_transform_cache'].lower() in ('true', '1', 'yes')
                self._log(f"Fresh transform cache enabled via CLI --fresh flag")
            elif fresh_transform_cache:
                self._log(f"Fresh transform cache enabled via configuration")

            # BERTopic params
            skip_analysis = self.config.get("skip_analysis", False)
            num_topics = self.config.get("num_topics") # Default is None (auto)
            min_ngram = self.config.get("min_ngram", 1)
            max_ngram = self.config.get("max_ngram", 2)
            min_topic_size = self.config.get("min_topic_size", 10)
            top_n_words = self.config.get("top_n_words", 10)
            use_representation_model = self.config.get("use_representation_model", False)
            
            # Representation model configuration (for BERTopic topic naming)
            representation_model_provider = self.config.get("representation_model_provider", "openai")  # openai, anthropic, etc.
            representation_model_name = self.config.get("representation_model_name", "gpt-4o-mini")  # specific model name

            self._log(f"Configuration loaded: input_file_path='{input_file_path}', transform_method='{transform_method}', skip_analysis={skip_analysis}")

            # --- 2. Transform Transcripts ---
            self._log("Starting transcript transformation...")
            text_file_path_str: Optional[str] = None # Path to the text file for BERTopic
            
            # The transformer functions create their own temp subdirectories.
            # We pass `main_temp_dir` to them so their caches are contained and cleaned up.
            # However, the transformer functions from `plexus.analysis.topics.transformer`
            # currently manage their own temp directory creation internally using `tempfile.mkdtemp()`
            # and don't take an output_dir parameter for the transformed text file itself.
            # They return the path to the text file, which might be in a system-wide temp location.
            # This is acceptable, as BERTopic will read from it, and it will be cleaned up eventually by the OS or on reboot.
            # The BERTopic *output* artifacts are what we need to control into our `main_temp_dir`.

            if transform_method == 'itemize':
                self._log(f"Using itemized LLM transformation with {llm_provider} model: {llm_model}")
                _, text_file_path_str, preprocessing_info = await transform_transcripts_itemize(
                    input_file=input_file_path,
                    content_column=content_column,
                    prompt_template_file=prompt_template_path,
                    prompt_template=prompt_template,
                    model=llm_model,
                    provider=llm_provider,
                    customer_only=customer_only,
                    fresh=fresh_transform_cache,
                    max_retries=max_retries_itemize,
                    openai_api_key=openai_api_key,
                    sample_size=sample_size
                )
            elif transform_method == 'llm':
                self._log(f"Using LLM transformation with {llm_provider} model: {llm_model}")
                _, text_file_path_str, preprocessing_info = await transform_transcripts_llm(
                    input_file=input_file_path,
                    content_column=content_column,
                    prompt_template_file=prompt_template_path,
                    prompt_template=prompt_template,
                    model=llm_model,
                    provider=llm_provider,
                    customer_only=customer_only,
                    fresh=fresh_transform_cache,
                    openai_api_key=openai_api_key,
                    sample_size=sample_size
                )
            else: # 'chunk'
                self._log("Using default chunking transformation.")
                _, text_file_path_str, preprocessing_info = await asyncio.to_thread(
                    transform_transcripts,
                    input_file=input_file_path,
                    content_column=content_column,
                    customer_only=customer_only,
                    fresh=fresh_transform_cache,
                    sample_size=sample_size
                )
            
            if not text_file_path_str or not Path(text_file_path_str).exists():
                msg = "Transcript transformation failed to produce a text file."
                self._log(msg, level="ERROR")
                final_output_data["errors"].append(msg)
                final_output_data["summary"] = "Transformation error."
                shutil.rmtree(main_temp_dir)
                self._log(f"Cleaned up main temporary directory: {main_temp_dir}")
                return final_output_data, self._get_log_string()

            self._log(f"Transcript transformation completed. Text file for BERTopic: {text_file_path_str}")
            self._log(f"LLM extraction method: {preprocessing_info.get('method', 'unknown')}")
            self._log(f"LLM extraction examples count: {len(preprocessing_info.get('examples', []))}")
            final_output_data["transformed_text_file"] = text_file_path_str
            
            # Restructure output to match UI stages
            # 1. Preprocessing (programmatic steps)
            final_output_data["preprocessing"] = {
                "method": transform_method,
                "input_file": input_file_path,
                "content_column": content_column,
                "sample_size": sample_size,
                "customer_only": customer_only
            }
            
            # 2. LLM Extraction (what was previously called preprocessing)
            final_output_data["llm_extraction"] = preprocessing_info


            # --- 3. Perform BERTopic Analysis (if not skipped) ---
            if skip_analysis:
                self._log("Skipping BERTopic analysis as requested.")
                final_output_data["summary"] = "Transformation completed, analysis skipped."
            else:
                self._log("Starting BERTopic analysis...")
                # BERTopic analysis will write its outputs into a subdirectory of `main_temp_dir`
                # The `analyze_topics` function from `plexus.analysis.topics.analyzer`
                # creates its own descriptive subdirectory based on parameters.
                # So, we pass `main_temp_dir` as the base for `analyze_topics`'s output.
                
                # Set OpenMP environment variables for BERTopic if not already set by CLI layer
                # This is crucial for preventing oversubscription of threads.
                os.environ["OMP_NUM_THREADS"] = "1"
                os.environ["OPENBLAS_NUM_THREADS"] = "1"
                os.environ["MKL_NUM_THREADS"] = "1"
                os.environ["NUMEXPR_NUM_THREADS"] = "1"
                self._log(f"Set OMP_NUM_THREADS for BERTopic: {os.environ.get('OMP_NUM_THREADS')}", level="DEBUG")

                # Capture the return value from analyze_topics (it returns just one value, not a tuple)
                # 4. Fine-tuning section (representation model configuration)
                final_output_data["fine_tuning"] = {
                    "use_representation_model": use_representation_model,
                    "representation_model_provider": representation_model_provider if use_representation_model else None,
                    "representation_model_name": representation_model_name if use_representation_model else None
                }
                
                topic_model = await asyncio.to_thread(
                    analyze_topics,
                    text_file_path=text_file_path_str,
                    output_dir=main_temp_dir, # analyze_topics will create subdirs here
                    nr_topics=num_topics,
                    n_gram_range=(min_ngram, max_ngram),
                    min_topic_size=min_topic_size,
                    top_n_words=top_n_words,
                    use_representation_model=use_representation_model,
                    openai_api_key=openai_api_key, # Passed directly
                    representation_model_provider=representation_model_provider,
                    representation_model_name=representation_model_name
                )
                self._log("BERTopic analysis completed.")
                
                # 3. BERTopic Analysis section
                final_output_data["bertopic_analysis"] = {
                    "num_topics_requested": num_topics,
                    "min_topic_size": min_topic_size,
                    "top_n_words": top_n_words,
                    "min_ngram": min_ngram,
                    "max_ngram": max_ngram,
                    "skip_analysis": skip_analysis
                }
                
                # Extract topic information and add to the final output data
                if topic_model and hasattr(topic_model, 'get_topic_info'):
                    try:
                        topic_info = topic_model.get_topic_info()
                        if not topic_info.empty:
                            # Convert to dictionary format suitable for JSON
                            topics_list = []
                            for _, row in topic_info.iterrows():
                                topic_id = row.get('Topic', -1)
                                if topic_id != -1:  # Skip the -1 topic which is usually "noise"
                                    # Get the topic words and weights if available
                                    topic_words = []
                                    if hasattr(topic_model, 'get_topic'):
                                        words_weights = topic_model.get_topic(topic_id)
                                        topic_words = [{"word": word, "weight": weight} for word, weight in words_weights]
                                    
                                    topics_list.append({
                                        "id": int(topic_id),
                                        "name": row.get('Name', f'Topic {topic_id}'),
                                        "count": int(row.get('Count', 0)),
                                        "representation": row.get('Representation', ''),
                                        "words": topic_words
                                    })
                    
                            final_output_data["topics"] = topics_list
                            self._log(f"Added {len(topics_list)} topics to output data")
                            
                            # Add visualization info based on topic count
                            if len(topics_list) < 2:
                                final_output_data["visualization_notes"] = {
                                    "topics_visualization": "Skipped - requires 2+ topics for 2D visualization",
                                    "heatmap_visualization": "Skipped - requires 2+ topics",
                                    "available_files": "Topic information CSV and individual topic details available"
                                }
                    except Exception as e:
                        self._log(f"Failed to extract topic information: {e}", level="ERROR")
                        final_output_data["errors"].append(f"Error extracting topics: {str(e)}")

                # --- 4. Attach Artifacts ---
                self._log(f"Scanning for BERTopic artifacts in temporary directory: {main_temp_dir}")
                if not report_block_id:
                    self._log("No report_block_id, cannot attach files.", level="ERROR")
                    final_output_data["errors"].append("Cannot attach files: report_block_id is missing.")
                else:
                    for root, _, files in os.walk(main_temp_dir):
                        for filename in files:
                            file_path = Path(root) / filename
                            file_ext = file_path.suffix.lower()

                            if file_ext in SUPPORTED_TEXT_EXTENSIONS:
                                try:
                                    with open(file_path, 'r', encoding='utf-8') as f:
                                        content = f.read()
                                    
                                    # Use relative path for display name in attachedFiles
                                    relative_file_path = str(file_path.relative_to(main_temp_dir))
                                    
                                    # Dynamically determine content type for common text files
                                    content_type = "text/plain"
                                    if file_ext == ".html":
                                        content_type = "text/html"
                                    elif file_ext == ".csv":
                                        content_type = "text/csv"
                                    elif file_ext == ".json":
                                        content_type = "application/json"
                                    elif file_ext == ".md":
                                        content_type = "text/markdown"

                                    # Attach the file - returns path to S3 file
                                    s3_file_path = self.attach_detail_file(
                                        report_block_id=report_block_id,
                                        file_name=relative_file_path, # Use relative path for S3 name
                                        content=content.encode('utf-8'), # Encode string content to bytes
                                        content_type=content_type
                                    )
                                    # File is automatically tracked in ReportBlock.attachedFiles
                                except Exception as e:
                                    self._log(f"Failed to attach text file {file_path}: {e}", level="ERROR")
                                    final_output_data["errors"].append(f"Error attaching {file_path}: {e}")
                            elif file_ext in SUPPORTED_IMAGE_EXTENSIONS:
                                try:
                                    with open(file_path, 'rb') as f:
                                        content = f.read() # Read as bytes
                                    
                                    relative_file_path = str(file_path.relative_to(main_temp_dir))
                                    content_type = "image/png" # Assuming only PNG for now
                                        
                                    # Attach the file - returns path to S3 file
                                    s3_file_path = self.attach_detail_file(
                                        report_block_id=report_block_id,
                                        file_name=relative_file_path,
                                        content=content, # Pass bytes directly
                                        content_type=content_type
                                    )
                                    # File is automatically tracked in ReportBlock.attachedFiles
                                except Exception as e:
                                    self._log(f"Failed to attach image file {file_path}: {e}", level="ERROR")
                                    final_output_data["errors"].append(f"Error attaching {file_path}: {e}")
                            else:
                                self._log(f"Skipping unsupported file type: {file_path}", level="DEBUG")
                                final_output_data["skipped_files"].append(str(file_path))
                # Generate summary based on the number of topics found
                topic_count = len(final_output_data.get("topics", []))
                if topic_count == 0:
                    final_output_data["summary"] = "Topic analysis completed, but no distinct topics were identified in the data. Consider increasing sample size or adjusting min_topic_size parameter."
                elif topic_count == 1:
                    final_output_data["summary"] = f"Topic analysis completed with {topic_count} topic identified. Limited visualizations available due to single topic. Consider decreasing min_topic_size (currently {min_topic_size}) or increasing sample size."
                else:
                    final_output_data["summary"] = f"Topic analysis completed successfully with {topic_count} topics identified."

        except Exception as e:
            import traceback
            error_msg = f"An error occurred during TopicAnalysis block generation: {str(e)}"
            tb_str = traceback.format_exc()
            self._log(error_msg, level="ERROR")
            self._log("Traceback:", level="ERROR")
            self._log(tb_str, level="ERROR")
            final_output_data["errors"].append(error_msg)
            final_output_data["summary"] = "Topic analysis failed."
        finally:
            # --- 5. Clean up temporary directory ---
            try:
                shutil.rmtree(main_temp_dir)
                self._log(f"Successfully cleaned up main temporary directory: {main_temp_dir}")
            except Exception as e:
                self._log(f"Error cleaning up main temporary directory {main_temp_dir}: {e}", level="ERROR")
                final_output_data["errors"].append(f"Cleanup error for {main_temp_dir}: {str(e)}")
        
        # Ensure summary reflects final state if errors occurred
        if final_output_data["errors"] and not final_output_data["summary"].endswith("failed.") and not final_output_data["summary"].endswith("error."):
             final_output_data["summary"] = "Topic analysis completed with errors."

        # Add block metadata for frontend display
        final_output_data["block_title"] = self.config.get("name", self.DEFAULT_NAME)

        return final_output_data, self._get_log_string()

    def _log(self, message: str, level="INFO"):
        log_method = getattr(logger, level.lower(), logger.info)
        # Add block name if available, otherwise use class name
        block_name_prefix = f"[ReportBlock {self.config.get('name', 'TopicAnalysis')}]"
        log_method(f"{block_name_prefix} {message}")
        
        # Store log messages for the report block's log field
        # Prefix with timestamp and level for clarity in the stored log
        if level.upper() != "DEBUG": # Don't store DEBUG logs in the block's output log
            self.log_messages.append(f"{pd.Timestamp.now(tz='UTC').isoformat()} [{level.upper()}] {message}")

    def _get_log_string(self) -> str:
        return "\n".join(self.log_messages) 