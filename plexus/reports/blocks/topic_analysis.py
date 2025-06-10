from typing import Any, Dict, Optional, Tuple, List
import logging
import asyncio
import tempfile
import os
import shutil
from pathlib import Path
import pandas as pd # Added for inspect_data if called directly
import json # For potentially writing a summary JSON
import yaml # For YAML formatted output with contextual comments

from plexus.analysis.topics.transformer import (
    transform_transcripts, 
    transform_transcripts_llm, 
    transform_transcripts_itemize,
    inspect_data # If we decide to allow inspection via block
)
from plexus.analysis.topics.analyzer import analyze_topics
from plexus.dashboard.api.models.report_block import ReportBlock # For type hinting if needed
from plexus.processors.ProcessorFactory import ProcessorFactory
from plexus.reports.s3_utils import download_report_block_file

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
        "name": "My Topic Analysis", // Optional, display name
        
        // Data source configuration
        "data_source": {
            "input_file_path": "/path/to/your/transcripts.parquet", // Required
            "content_column": "text", // Optional, default: "text"
            "customer_only": false, // Optional, default: false
            "sample_size": null // Optional, default: null (process all)
        },
        
        // Stage 1: Preprocessing configuration
        "preprocessing": {
            "steps": [ // Optional, list of preprocessing steps
                {
                    "class": "RemoveSpeakerIdentifiersTranscriptFilter", // Processor class name
                    "parameters": {} // Optional parameters for the processor
                },
                {
                    "class": "ColumnDatasetFilter",
                    "parameters": {"column": "call_type", "value": "inbound"}
                }
            ]
        },
        
        // Stage 2: LLM extraction configuration
        "llm_extraction": {
            "method": "chunk", // Required: 'chunk', 'llm', 'itemize', default: "chunk"
            "provider": "ollama", // Optional: 'ollama', 'openai', 'anthropic', default: "ollama"
            "model": "gemma3:27b", // Optional, default: "gemma3:27b"
            "system_prompt": "You are an expert at analyzing conversation transcripts...", // Optional, for 'llm'/'itemize'
            "user_prompt": "Extract key themes from the following text: {text}", // Optional, for 'llm'/'itemize'
            "api_key_env_var": "OPENAI_API_KEY", // Optional, env var for API key
            "max_retries": 2, // Optional, for 'itemize', default: 2
            "fresh_cache": false // Optional, force regenerate cache, default: false
        },
        
        // Stage 3: BERTopic analysis configuration
        "bertopic_analysis": {
            "skip_analysis": false, // Optional, default: false
            "num_topics": null, // Optional, auto-determined if null
            "min_ngram": 1, // Optional, default: 1
            "max_ngram": 2, // Optional, default: 2
            "min_topic_size": 10, // Optional, default: 10
            "top_n_words": 10 // Optional, default: 10
        },
        
        // Stage 4: Fine-tuning configuration
        "fine_tuning": {
            "use_representation_model": false, // Optional, default: false
            "provider": "openai", // Optional: 'openai', 'anthropic', default: "openai"
            "model": "gpt-4o-mini", // Optional, default: "gpt-4o-mini"
            "system_prompt": "You are an expert at creating concise, descriptive topic names...", // Optional
            "user_prompt": "Create a brief, descriptive name for this topic based on these keywords: {keywords}" // Optional
        }
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
            self._log("="*60)
            self._log("🚀 STAGE 1: CONFIGURATION EXTRACTION AND VALIDATION")
            self._log("="*60)
            
            # Data source configuration
            data_source = self.config.get("data_source", {})
            input_file_path = data_source.get("input_file_path") or self.config.get("input_file_path")  # Backward compatibility
            if not input_file_path or not Path(input_file_path).exists():
                msg = f"'data_source.input_file_path' is required and must exist. Provided: {input_file_path}"
                self._log(msg, level="ERROR")
                final_output_data["errors"].append(msg)
                final_output_data["summary"] = "Configuration error."
                shutil.rmtree(main_temp_dir)
                self._log(f"Cleaned up main temporary directory: {main_temp_dir}")
                return final_output_data, self._get_log_string()

            content_column = data_source.get("content_column", self.config.get("content_column", "text"))
            customer_only = data_source.get("customer_only", self.config.get("customer_only", False))
            sample_size = data_source.get("sample_size", self.config.get("sample_size"))
            
            # LLM extraction configuration
            llm_extraction = self.config.get("llm_extraction", {})
            transform_method = llm_extraction.get("method", self.config.get("transform_method", "chunk"))
            llm_provider = llm_extraction.get("provider", self.config.get("llm_provider", "ollama"))
            llm_model = llm_extraction.get("model", self.config.get("llm_model", "gemma3:27b"))
            system_prompt = llm_extraction.get("system_prompt")
            user_prompt = llm_extraction.get("user_prompt")
            # Legacy support for old prompt fields
            prompt_template_path = llm_extraction.get("prompt_template_path", self.config.get("prompt_template_path"))
            prompt_template = llm_extraction.get("prompt_template", self.config.get("prompt_template"))
            
            api_key_env_var = llm_extraction.get("api_key_env_var", self.config.get("openai_api_key_env_var", "OPENAI_API_KEY"))
            max_retries_itemize = llm_extraction.get("max_retries", self.config.get("max_retries_itemize", 2))
            
            # Check for fresh_transform_cache in both config and runtime params (CLI --fresh flag)
            # Runtime params take precedence over config
            fresh_transform_cache = llm_extraction.get("fresh_cache", self.config.get("fresh_transform_cache", False))
            if hasattr(self, 'params') and self.params and 'fresh_transform_cache' in self.params:
                fresh_transform_cache = self.params['fresh_transform_cache'].lower() in ('true', '1', 'yes')
                self._log(f"Fresh transform cache enabled via CLI --fresh flag")
            elif fresh_transform_cache:
                self._log(f"Fresh transform cache enabled via configuration")

            # Fine-tuning configuration (define early since it's needed for API key handling)
            fine_tuning = self.config.get("fine_tuning", {})
            use_representation_model = fine_tuning.get("use_representation_model", self.config.get("use_representation_model", False))
            representation_model_provider = fine_tuning.get("provider", self.config.get("representation_model_provider", "openai"))
            representation_model_name = fine_tuning.get("model", self.config.get("representation_model_name", "gpt-4o-mini"))
            representation_system_prompt = fine_tuning.get("system_prompt")
            representation_user_prompt = fine_tuning.get("user_prompt")

            # API key handling
            openai_api_key = os.environ.get(api_key_env_var) if llm_provider == "openai" or use_representation_model else None
            if (llm_provider == "openai" or use_representation_model) and not openai_api_key:
                self._log(f"OpenAI API key not found in env var '{api_key_env_var}'. Certain features might fail.", level="WARNING")
            
            # BERTopic analysis configuration
            bertopic_analysis = self.config.get("bertopic_analysis", {})
            skip_analysis = bertopic_analysis.get("skip_analysis", self.config.get("skip_analysis", False))
            num_topics = bertopic_analysis.get("num_topics", self.config.get("num_topics"))  # Default is None (auto)
            min_ngram = bertopic_analysis.get("min_ngram", self.config.get("min_ngram", 1))
            max_ngram = bertopic_analysis.get("max_ngram", self.config.get("max_ngram", 2))
            min_topic_size = bertopic_analysis.get("min_topic_size", self.config.get("min_topic_size", 10))
            top_n_words = bertopic_analysis.get("top_n_words", self.config.get("top_n_words", 10))

            # Preprocessing configuration
            preprocessing_config = self.config.get("preprocessing", {}).get("steps", self.config.get("preprocessing", []))
            
            # Log comprehensive configuration summary
            self._log("📋 CONFIGURATION SUMMARY:")
            self._log(f"   • Input File: {input_file_path}")
            self._log(f"   • Content Column: {content_column}")
            self._log(f"   • Transform Method: {transform_method}")
            self._log(f"   • LLM Provider: {llm_provider}")
            self._log(f"   • LLM Model: {llm_model}")
            self._log(f"   • Sample Size: {sample_size or 'All data'}")
            self._log(f"   • Customer Only: {customer_only}")
            self._log(f"   • Skip Analysis: {skip_analysis}")
            self._log(f"   • Min Topic Size: {min_topic_size}")
            self._log(f"   • Use Representation Model: {use_representation_model}")
            self._log(f"   • Preprocessing Steps: {len(preprocessing_config)}")
            self._log("="*60)

            # --- 2. Apply Preprocessing (if configured) ---
            if preprocessing_config:
                self._log("🔧 STAGE 2: DATA PREPROCESSING")
                self._log("="*60)
                self._log(f"Applying {len(preprocessing_config)} preprocessing steps...")
                # Load the input data for preprocessing
                df = pd.read_parquet(input_file_path)
                self._log(f"Loaded {len(df)} rows for preprocessing")
                
                preprocessing_steps_info = []
                for i, step_config in enumerate(preprocessing_config, 1):
                    processor_class = step_config.get("class")
                    processor_params = step_config.get("parameters", {})
                    
                    if not processor_class:
                        self._log(f"Skipping preprocessing step {i}: no class specified", level="WARNING")
                        continue
                    
                    try:
                        self._log(f"Applying preprocessing step {i}: {processor_class}")
                        processor = ProcessorFactory.create_processor(processor_class, **processor_params)
                        df = processor.process(df)
                        preprocessing_steps_info.append({
                            "step": i,
                            "class": processor_class,
                            "parameters": processor_params
                        })
                        self._log(f"Preprocessing step {i} completed, {len(df)} rows remaining")
                    except Exception as e:
                        error_msg = f"Error in preprocessing step {i} ({processor_class}): {e}"
                        self._log(error_msg, level="ERROR")
                        final_output_data["errors"].append(error_msg)
                        # Continue with other preprocessing steps
                
                # Save preprocessed data to a temporary file
                temp_preprocessed_file = tempfile.NamedTemporaryFile(suffix=".parquet", delete=False)
                df.to_parquet(temp_preprocessed_file.name, index=False)
                input_file_path = temp_preprocessed_file.name  # Use preprocessed file for transformation
                self._log(f"Preprocessed data saved to temporary file: {input_file_path}")
                
                # Store preprocessing info for later use in final output
                preprocessing_steps_applied = preprocessing_steps_info
                original_input_file = self.config.get("data_source", {}).get("input_file_path") or self.config.get("input_file_path")
                preprocessed_rows_count = len(df)
            else:
                self._log("🔧 STAGE 2: DATA PREPROCESSING")
                self._log("="*60)
                self._log("No preprocessing steps configured, using original input file directly")
                self._log("="*60)

            # --- 3. Transform Transcripts ---
            self._log("⚡ STAGE 3: TRANSCRIPT TRANSFORMATION") 
            self._log("="*60)
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
                self._log(f"🤖 TRANSFORMATION METHOD: Itemized LLM")
                self._log(f"   • Provider: {llm_provider}")
                self._log(f"   • Model: {llm_model}")
                if system_prompt:
                    self._log("   • System Prompt:")
                    self._log("     " + "\n     ".join(system_prompt.split('\n')))
                if user_prompt:
                    self._log("   • User Prompt:")
                    self._log("     " + "\n     ".join(user_prompt.split('\n')))
                self._log("-" * 40)
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
                self._log(f"🤖 TRANSFORMATION METHOD: LLM")
                self._log(f"   • Provider: {llm_provider}")
                self._log(f"   • Model: {llm_model}")
                if system_prompt:
                    self._log("   • System Prompt:")
                    self._log("     " + "\n     ".join(system_prompt.split('\n')))
                if user_prompt:
                    self._log("   • User Prompt:")
                    self._log("     " + "\n     ".join(user_prompt.split('\n')))
                self._log("-" * 40)
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
                self._log(f"🤖 TRANSFORMATION METHOD: Chunking (default)")
                self._log(f"   • No LLM processing - direct text chunking")
                self._log("-" * 40)
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

            self._log("✅ TRANSFORMATION COMPLETED")
            self._log(f"   • Output file: {text_file_path_str}")
            self._log(f"   • Extraction method: {preprocessing_info.get('method', 'unknown')}")
            self._log(f"   • Examples generated: {len(preprocessing_info.get('examples', []))}")
            self._log("="*60)
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
            
            # Add preprocessing steps info if they were applied
            if 'preprocessing_steps_applied' in locals():
                final_output_data["preprocessing"]["steps"] = preprocessing_steps_applied
                final_output_data["preprocessing"]["original_input_file"] = original_input_file  
                final_output_data["preprocessing"]["preprocessed_rows"] = preprocessed_rows_count
            
            # 2. LLM Extraction (what was previously called preprocessing)
            final_output_data["llm_extraction"] = preprocessing_info

            # Add debug logging to verify hit rate stats are included
            self._log("🔍 DEBUG: LLM Extraction preprocessing_info contents:")
            self._log(f"   • Method: {preprocessing_info.get('method', 'unknown')}")
            self._log(f"   • Hit rate stats present: {'hit_rate_stats' in preprocessing_info}")
            if 'hit_rate_stats' in preprocessing_info:
                hit_stats = preprocessing_info['hit_rate_stats']
                self._log(f"   • Total processed: {hit_stats.get('total_processed', 'unknown')}")
                self._log(f"   • Successful: {hit_stats.get('successful_extractions', 'unknown')}")
                self._log(f"   • Failed: {hit_stats.get('failed_extractions', 'unknown')}")
                self._log(f"   • Hit rate: {hit_stats.get('hit_rate_percentage', 'unknown')}%")
            else:
                self._log("   • No hit_rate_stats found in preprocessing_info")
                self._log(f"   • Available keys: {list(preprocessing_info.keys())}")
            
            # 3. Add debugging information - show sample of transformed text file
            debug_info = {}
            if text_file_path_str and Path(text_file_path_str).exists():
                try:
                    with open(text_file_path_str, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        debug_info["transformed_text_lines_count"] = len(lines)
                        debug_info["transformed_text_sample"] = lines[:5] if lines else []
                        # Count unique lines to detect repetition
                        unique_lines = set(lines)
                        debug_info["unique_lines_count"] = len(unique_lines)
                        debug_info["repetition_detected"] = len(unique_lines) < len(lines) / 2
                        
                        # Show most common lines if there's repetition
                        if debug_info["repetition_detected"]:
                            from collections import Counter
                            line_counts = Counter(lines)
                            debug_info["most_common_lines"] = [
                                {"line": line.strip(), "count": count} 
                                for line, count in line_counts.most_common(3)
                            ]
                except Exception as e:
                    debug_info["error_reading_transformed_file"] = str(e)
            
            final_output_data["debug_info"] = debug_info


            # --- 4. Perform BERTopic Analysis (if not skipped) ---
            if skip_analysis:
                self._log("🔬 STAGE 4: BERTOPIC ANALYSIS")
                self._log("="*60)
                self._log("⚠️  BERTopic analysis SKIPPED as requested in configuration")
                self._log("="*60)
                final_output_data["summary"] = "Transformation completed, analysis skipped."
            else:
                self._log("🔬 STAGE 4: BERTOPIC ANALYSIS")
                self._log("="*60)
                self._log("📊 BERTOPIC PARAMETERS:")
                self._log(f"   • Min Topic Size: {min_topic_size}")
                self._log(f"   • N-gram Range: {min_ngram}-{max_ngram}")
                self._log(f"   • Top N Words: {top_n_words}")
                self._log(f"   • Requested Topics: {num_topics or 'Auto-determined'}")
                self._log("-" * 40)
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
                    use_langchain=True, # Enable LangChain path to use SQLite caching
                    representation_model_provider=representation_model_provider,
                    representation_model_name=representation_model_name
                )
                self._log("✅ BERTopic analysis completed successfully")
                self._log("="*60)
                
                # Load "before" topics data if it exists (for fine-tuning comparison)
                before_topics_data = None
                if use_representation_model:
                    try:
                        import json
                        
                        # Look for the before fine-tuning file in the temp directory
                        for root, dirs, files in os.walk(main_temp_dir):
                            if "topics_before_fine_tuning.json" in files:
                                before_topics_path = os.path.join(root, "topics_before_fine_tuning.json")
                                with open(before_topics_path, 'r', encoding='utf-8') as f:
                                    before_topics_data = json.load(f)
                                
                                self._log(f"✅ Loaded 'before' topics data from {before_topics_path}")
                                self._log(f"🔍 Found {len(before_topics_data)} topics before fine-tuning")
                                break
                        
                        if not before_topics_data:
                            self._log("⚠️  No 'before' topics data found for fine-tuning comparison")
                    except Exception as e:
                        self._log(f"❌ Failed to load 'before' topics data: {e}", level="ERROR")
                
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
                        self._log(f"🔍 BERTopic topic_info shape: {topic_info.shape}")
                        self._log(f"🔍 BERTopic topic_info columns: {list(topic_info.columns)}")
                        self._log(f"🔍 BERTopic topic IDs found: {topic_info['Topic'].tolist()}")
                        
                        # Add debugging info to the output so it shows up in universal code
                        final_output_data["bertopic_debug"] = {
                            "topic_info_shape": list(topic_info.shape),
                            "topic_info_columns": list(topic_info.columns),
                            "topic_ids_found": topic_info['Topic'].tolist(),
                            "topic_info_empty": topic_info.empty
                        }
                        
                        if not topic_info.empty:
                            # Convert to dictionary format suitable for JSON
                            topics_list = []
                            valid_topic_count = 0
                            noise_topic_count = 0
                            
                            for _, row in topic_info.iterrows():
                                topic_id = row.get('Topic', -1)
                                if topic_id != -1:  # Skip the -1 topic which is usually "noise"
                                    valid_topic_count += 1
                                    # Only store first 20 topics to reduce DynamoDB record size
                                    if len(topics_list) >= 20:
                                        continue
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
                                        "words": topic_words,
                                        "examples": []  # Will be populated later
                                    })
                                else:
                                    noise_topic_count += 1
                            
                            # Add topic processing debug info to output
                            final_output_data["bertopic_debug"]["valid_topic_count"] = valid_topic_count
                            final_output_data["bertopic_debug"]["noise_topic_count"] = noise_topic_count
                            final_output_data["bertopic_debug"]["topics_list_length"] = len(topics_list)
                            
                            self._log(f"🔍 Topic processing: {valid_topic_count} valid topics, {noise_topic_count} noise topics")
                            
                            # --- Load Representative Documents ---
                            # Try to load representative documents from the JSON file created by analyzer
                            representative_docs_loaded = False
                            try:
                                import json
                                
                                # First, look for representative_documents.json in the temp directory structure
                                # (this works for new reports currently being generated)
                                for root, dirs, files in os.walk(main_temp_dir):
                                    if "representative_documents.json" in files:
                                        repr_docs_path = os.path.join(root, "representative_documents.json")
                                        with open(repr_docs_path, 'r', encoding='utf-8') as f:
                                            repr_docs_data = json.load(f)
                                        
                                        # Add representative documents to each topic
                                        examples_added = 0
                                        for topic in topics_list:
                                            topic_id_str = str(topic["id"])
                                            if topic_id_str in repr_docs_data:
                                                topic["examples"] = repr_docs_data[topic_id_str][:20]  # Limit to 20 examples for UI
                                                examples_added += 1
                                                self._log(f"🔍 Added {len(topic['examples'])} examples to topic {topic_id_str}: {topic.get('name', 'Unnamed')}")
                                        
                                        self._log(f"✅ Added examples to {examples_added}/{len(topics_list)} topics from temp directory")
                                        
                                        representative_docs_loaded = True
                                        self._log(f"✅ Loaded representative documents from {repr_docs_path}")
                                        break
                                
                                # If not found in temp directory, try attached files (for older reports)
                                if not representative_docs_loaded and hasattr(self, '_orm') and hasattr(self._orm, 'attached_files'):
                                    attached_files = self._orm.get_attached_files()
                                    self._log(f"🔍 Checking {len(attached_files)} attached files for representative_documents.json")
                                    
                                    for file_path in attached_files:
                                        if file_path.endswith('representative_documents.json'):
                                            self._log(f"🔍 Found representative_documents.json in attached files: {file_path}")
                                            try:
                                                # Download the file from S3
                                                content, temp_path = download_report_block_file(file_path)
                                                repr_docs_data = json.loads(content)
                                                
                                                # Add representative documents to each topic
                                                examples_added = 0
                                                for topic in topics_list:
                                                    topic_id_str = str(topic["id"])
                                                    if topic_id_str in repr_docs_data:
                                                        topic["examples"] = repr_docs_data[topic_id_str][:20]  # Limit to 20 examples for UI
                                                        examples_added += 1
                                                        self._log(f"🔍 Added {len(topic['examples'])} examples to topic {topic_id_str}: {topic.get('name', 'Unnamed')}")
                                                
                                                self._log(f"✅ Added examples to {examples_added}/{len(topics_list)} topics from attached files")
                                                
                                                representative_docs_loaded = True
                                                self._log(f"✅ Loaded representative documents from attached file: {file_path}")
                                                
                                                # Clean up temp file
                                                try:
                                                    if temp_path and os.path.exists(temp_path):
                                                        os.remove(temp_path)
                                                except Exception as cleanup_error:
                                                    self._log(f"Warning: Failed to clean up temp file {temp_path}: {cleanup_error}", level="WARNING")
                                                break
                                            except Exception as download_error:
                                                self._log(f"❌ Failed to download/parse representative documents from {file_path}: {download_error}", level="ERROR")
                                                continue
                                
                                if not representative_docs_loaded:
                                    self._log("⚠️  No representative_documents.json file found in temp directory or attached files")
                                    
                            except Exception as e:
                                self._log(f"❌ Failed to load representative documents: {e}", level="ERROR")
                                # Continue without representative documents
                            
                            final_output_data["topics"] = topics_list
                            
                            # Add before topics data to fine_tuning section if available
                            if before_topics_data:
                                # Limit to first 20 topics to reduce DynamoDB record size
                                topics_before_limited = list(before_topics_data.values())[:20]
                                final_output_data["fine_tuning"]["topics_before"] = topics_before_limited
                                self._log(f"✅ Added 'before' topics data to fine_tuning section ({len(topics_before_limited)} of {len(before_topics_data)} topics)")

                            # This is critical information - ensure it goes to both console AND attached log
                            self._log("🎯 TOPIC DISCOVERY RESULTS")
                            self._log("-" * 40)
                            self._log(f"📈 FOUND {len(topics_list)} DISTINCT TOPICS")
                            
                            # Log top topic details for visibility
                            if topics_list:
                                sorted_topics = sorted(topics_list, key=lambda t: t.get('count', 0), reverse=True)
                                self._log("📊 TOP TOPICS SUMMARY:")
                                for i, topic in enumerate(sorted_topics[:5]):  # Top 5 topics
                                    top_words = [w['word'] for w in topic.get('words', [])[:8]]  # Top 8 words
                                    self._log(f"   {i+1}. Topic {topic['id']}: {topic['count']} items")
                                    self._log(f"      Name: {topic.get('name', 'Unnamed')}")
                                    self._log(f"      Keywords: {', '.join(top_words)}")
                                
                                self._log("-" * 40)
                            
                            # Add visualization info based on topic count
                            if len(topics_list) < 2:
                                final_output_data["visualization_notes"] = {
                                    "topics_visualization": "Skipped - requires 2+ topics for 2D visualization",
                                    "heatmap_visualization": "Skipped - requires 2+ topics",
                                    "available_files": "Topic information CSV and individual topic details available"
                                }
                    except Exception as e:
                        final_output_data["bertopic_debug"] = {
                            "topic_model_exists": topic_model is not None,
                            "has_get_topic_info": hasattr(topic_model, 'get_topic_info') if topic_model else False,
                            "error_reason": f"Exception during topic extraction: {str(e)}"
                        }
                        self._log(f"Failed to extract topic information: {e}", "ERROR")
                        final_output_data["errors"].append(f"Error extracting topics: {str(e)}")
                else:
                    # No topic model or couldn't get topic info
                    final_output_data["bertopic_debug"] = {
                        "topic_model_exists": topic_model is not None,
                        "has_get_topic_info": hasattr(topic_model, 'get_topic_info') if topic_model else False,
                        "error_reason": "No topic model returned or missing get_topic_info method"
                    }
                    self._log("🎯 TOPIC DISCOVERY RESULTS")
                    self._log("-" * 40)
                    self._log("⚠️  NO TOPICS DISCOVERED")
                    self._log("   This could be due to:")
                    self._log(f"   • Min topic size too high (current: {min_topic_size})")
                    self._log("   • Insufficient data diversity")
                    self._log("   • Text preprocessing issues")
                    self._log("-" * 40)

                # --- 5. Attach Artifacts ---
                self._log("📎 STAGE 5: FILE ATTACHMENT")
                self._log("="*60)
                self._log(f"Scanning artifacts in: {main_temp_dir}")
                if not report_block_id:
                    self._log("❌ No report_block_id available - cannot attach files", level="ERROR")
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
                    summary_msg = "Topic analysis completed, but no distinct topics were identified in the data. Consider increasing sample size or adjusting min_topic_size parameter."
                    final_output_data["summary"] = summary_msg
                    self._log(f"⚠️ Analysis Summary: {summary_msg}", "WARNING")
                elif topic_count == 1:
                    summary_msg = f"Topic analysis completed with {topic_count} topic identified. Limited visualizations available due to single topic. Consider decreasing min_topic_size (currently {min_topic_size}) or increasing sample size."
                    final_output_data["summary"] = summary_msg
                    self._log(f"📋 Analysis Summary: {summary_msg}", "INFO") 
                else:
                    summary_msg = f"Topic analysis completed successfully with {topic_count} topics identified."
                    final_output_data["summary"] = summary_msg
                    self._log(f"✅ Analysis Summary: {summary_msg}", "INFO")

        except Exception as e:
            import traceback
            error_msg = f"An error occurred during TopicAnalysis block generation: {str(e)}"
            tb_str = traceback.format_exc()
            self._log(error_msg, "ERROR")
            self._log("Traceback:", "ERROR")
            self._log(tb_str, "ERROR")
            final_output_data["errors"].append(error_msg)
            final_output_data["summary"] = "Topic analysis failed."
        finally:
            # --- 6. Clean up temporary directory ---
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

        # Debug logging to verify hit rate stats are in final output
        self._log("🔍 DEBUG: Final output data structure verification:")
        if "llm_extraction" in final_output_data:
            llm_data = final_output_data["llm_extraction"]
            self._log(f"   • LLM extraction present: True")
            self._log(f"   • Hit rate stats in final output: {'hit_rate_stats' in llm_data}")
            if 'hit_rate_stats' in llm_data:
                hit_stats = llm_data['hit_rate_stats']
                self._log(f"   • Final hit rate: {hit_stats.get('hit_rate_percentage', 'unknown')}%")
                self._log(f"   • Final total processed: {hit_stats.get('total_processed', 'unknown')}")
            else:
                self._log(f"   • LLM extraction keys: {list(llm_data.keys())}")
        else:
            self._log("   • LLM extraction missing from final output")

        # Return YAML formatted output with contextual comments
        try:
            contextual_comment = """# Topic Analysis Report Output
# 
# This is the structured output from a multi-stage topic analysis pipeline that:
# 1. Preprocesses data through programmatic filtering and preparation
# 2. Extracts content using LLM-powered transformation with custom prompts  
# 3. Discovers topics using BERTopic clustering and analysis
# 4. Fine-tunes topic representations using LLM-based naming models
#
# The output contains configuration parameters, extracted examples, discovered topics,
# visualization metadata, and file attachments from the complete analysis workflow.

"""
            yaml_output = yaml.dump(final_output_data, indent=2, allow_unicode=True, sort_keys=False)
            formatted_output = contextual_comment + yaml_output
        except Exception as e:
            self._log(f"Failed to create YAML formatted output: {e}", level="ERROR")
            # Fallback to basic YAML without comments
            formatted_output = yaml.dump(final_output_data, indent=2, allow_unicode=True, sort_keys=False)

        # Return the formatted YAML output (the frontend expects a YAML string)
        return formatted_output, self._get_log_string()

    # Remove custom _log method - now inherited from BaseReportBlock with unified logging 